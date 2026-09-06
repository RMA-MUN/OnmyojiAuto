import datetime
import html
import json
import os
import sys
import threading
import time
import uuid
import weakref
from PyQt6 import QtCore

from loguru import logger as _lq

# 创建 logs 文件夹
LOGS_DIR = 'logs'
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

# 日志文件：按天轮转（loguru 路径模板，{time} 在 sink 创建/轮转时解析）
LOG_FILE_PATTERN = os.path.join(LOGS_DIR, 'log_{time:YYYY-MM-DD}.log')
LOG_ROTATION = "00:00"
LOG_RETENTION = "30 days"


def _daily_log_file() -> str:
    """当日日志文件路径（兼容用；file sink 按天轮转后当日文件即此路径）。永不抛异常。"""
    try:
        return os.path.join(LOGS_DIR, 'log_%s.log' % datetime.date.today().isoformat())
    except Exception:
        try:
            return os.path.join(LOGS_DIR, 'log_%s.log' % time.strftime('%Y-%m-%d'))
        except Exception:
            return os.path.join(LOGS_DIR, 'log.log')


# 日志文件路径（当日文件；测试可用 set_log_file 重定向）
LOG_FILE = _daily_log_file()

# 进程唯一 id，import 时生成一次
_RUN_ID = uuid.uuid4().hex[:8]

# 日志级别常量（兼容：同时保留 WARN / WARNING）
LOG_LEVELS = {
    'DEBUG': 10,
    'INFO': 20,
    'WARN': 30,
    'WARNING': 30,
    'ERROR': 40,
}

_DEDUP_WINDOW = 10.0  # 秒


def _normalize_level(level):
    try:
        name = str(level).upper()
    except Exception:
        return 'INFO'
    if name == 'WARN':
        return 'WARNING'
    if name in ('DEBUG', 'INFO', 'WARNING', 'ERROR'):
        return 'WARNING' if name == 'WARN' else name
    # 兼容：未知级别回退 INFO
    return 'INFO'


def _level_value(level):
    try:
        return LOG_LEVELS.get(str(level).upper(), 20)
    except Exception:
        return 20


def _get_timestamp():
    try:
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    except Exception:
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---- display 去重状态（全局，display-side only；file 永远全写） ----
_dedup_lock = threading.Lock()
_dedup_last_key = None  # (level, message)
_dedup_count = 0
_dedup_last_time = 0.0
_dedup_timer = None

_instances_lock = threading.Lock()
_instances = weakref.WeakSet()


def _reset_display_dedup():
    """测试/调试用：清空 display 去重状态并取消 pending 定时 flush。"""
    global _dedup_last_key, _dedup_count, _dedup_last_time, _dedup_timer
    try:
        with _dedup_lock:
            _dedup_last_key = None
            _dedup_count = 0
            _dedup_last_time = 0.0
            t = _dedup_timer
            _dedup_timer = None
        if t is not None:
            try:
                t.cancel()
            except Exception:
                pass
    except Exception:
        pass


def _display_threshold():
    try:
        g = globals().get('logger', None)
        lvl = getattr(g, 'log_level', 'INFO') if g is not None else 'INFO'
        return _level_value(_normalize_level(lvl))
    except Exception:
        return 20


def _color_for(level, dark):
    if dark:
        color_map = {
            'DEBUG': '#999999',
            'INFO': '#22C55E',
            'WARN': '#FFC107',
            'WARNING': '#FFC107',
            'ERROR': '#F44336',
        }
    else:
        color_map = {
            'DEBUG': '#999999',
            'INFO': '#22C55E',
            'WARN': '#FFC107',
            'WARNING': '#FFC107',
            'ERROR': '#F44336',
        }
    try:
        return color_map.get(str(level).upper(), '#999999')
    except Exception:
        return '#999999'


def _short_time(ts):
    """显示用短时间：从全时间戳取 HH:MM:SS。永不抛异常。"""
    try:
        s = str(ts or '')
        if ' ' in s:
            s = s.rsplit(' ', 1)[-1]
        elif 'T' in s and ':' in s:
            s = s.rsplit('T', 1)[-1]
        if '.' in s:
            s = s.split('.', 1)[0]
        s = s.strip()
        if len(s) > 8 and ':' in s:
            s = s[-8:]
        return s or str(ts)
    except Exception:
        try:
            return str(ts)
        except Exception:
            return ''


def _build_display_html(timestamp, level, message, caller='', window=''):
    """显示行格式（display only）：`● HH:MM:SS message`，圆点按级别着色，模块进 tooltip。"""
    try:
        from qfluentwidgets.common.config import isDarkTheme
        _dark = isDarkTheme()
    except Exception:
        _dark = False
    try:
        color = _color_for(level, _dark)
    except Exception:
        color = '#999999'
    try:
        ts_short = _short_time(timestamp)
    except Exception:
        ts_short = str(timestamp)
    try:
        msg_esc = html.escape(str(message), quote=False)
    except Exception:
        msg_esc = str(message)
    try:
        tip_parts = []
        try:
            tip_parts.append(str(level))
        except Exception:
            pass
        try:
            tip_parts.append(str(timestamp))
        except Exception:
            pass
        try:
            if caller:
                tip_parts.append(str(caller))
        except Exception:
            pass
        try:
            if window:
                tip_parts.append(f"window={window}")
        except Exception:
            pass
        tip = html.escape(' | '.join([p for p in tip_parts if p]), quote=True)
    except Exception:
        tip = ''
    try:
        if tip:
            return f"<span title=\"{tip}\"><font color='{color}'>\u25cf</font> {ts_short} {msg_esc}</span>"
        return f"<font color='{color}'>\u25cf</font> {ts_short} {msg_esc}"
    except Exception:
        return f"\u25cf {ts_short} {message}"


def _emit_to_browsers(html):
    # 同一 textBrowser 只投递一次：main_window 会建两个 LogRedirect 实例
    # （self.log_redirect + 全局 logger）绑同一个浏览器，广播会导致每行显示两次。
    # 无浏览器的实例保留各自 emit（外部可能另接了槽），反正 _safe_append 是 no-op。
    try:
        with _instances_lock:
            targets = list(_instances)
    except Exception:
        targets = []
    seen_browsers = set()
    for inst in targets:
        try:
            try:
                tb = getattr(inst, 'text_browser', None)
            except Exception:
                tb = None
            if tb is not None:
                key = id(tb)
                if key in seen_browsers:
                    continue
                seen_browsers.add(key)
            inst.append_log.emit(html)
        except Exception:
            continue


def _timed_flush():
    global _dedup_last_key, _dedup_count, _dedup_last_time, _dedup_timer
    try:
        with _dedup_lock:
            if _dedup_last_key is None or _dedup_count <= 1:
                _dedup_timer = None
                return
            pending_level = _dedup_last_key[0]
            pending_count = _dedup_count
            _dedup_last_key = None
            _dedup_count = 0
            _dedup_last_time = 0.0
            _dedup_timer = None
        try:
            ts = _get_timestamp()
            html = _build_display_html(ts, pending_level, f"...（x{pending_count}）")
            _emit_to_browsers(html)
        except Exception:
            pass
    except Exception:
        pass


def _ensure_flush_timer():
    global _dedup_timer
    try:
        with _dedup_lock:
            t = _dedup_timer
            if t is not None and t.is_alive():
                return
            try:
                nt = threading.Timer(_DEDUP_WINDOW, _timed_flush)
                nt.daemon = True
                _dedup_timer = nt
            except Exception:
                return
        try:
            nt.start()
        except Exception:
            pass
    except Exception:
        pass


def _display_sink(message):
    """loguru display handler：经 append_log Qt 信号到 QTextBrowser。永不抛异常。"""
    try:
        record = message.record
    except Exception:
        return
    try:
        # file-only 记录（如 legacy log_to_file(str)）不走 display
        try:
            extra0 = record.get('extra', {}) or {}
        except Exception:
            extra0 = {}
        if extra0.get('_file_only'):
            return
        try:
            _caller0 = str(extra0.get('_caller', '') or '')
        except Exception:
            _caller0 = ''
        try:
            _window0 = str(extra0.get('window', '') or '')
        except Exception:
            _window0 = ''
        try:
            level = record['level'].name
        except Exception:
            level = 'INFO'
        level = _normalize_level(level)
        try:
            raw_msg = str(record.get('message', ''))
        except Exception:
            raw_msg = ''
        # 级别过滤：display 按 singleton log_level；file 全写
        try:
            if _level_value(level) < _display_threshold():
                return
        except Exception:
            pass
        try:
            ts = record['time'].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        except Exception:
            ts = _get_timestamp()
        now = time.time()
        key = (level, raw_msg)
        flush_html = None
        emit_html = None
        need_timer = False
        global _dedup_last_key, _dedup_count, _dedup_last_time
        try:
            with _dedup_lock:
                if _dedup_last_key is not None and key == _dedup_last_key and (now - _dedup_last_time) < _DEDUP_WINDOW:
                    _dedup_count += 1
                    _dedup_last_time = now
                    need_timer = True
                else:
                    if _dedup_last_key is not None and _dedup_count > 1:
                        try:
                            p_level = _dedup_last_key[0]
                            p_count = _dedup_count
                            flush_html = _build_display_html(ts, p_level, f"...（x{p_count}）")
                        except Exception:
                            flush_html = None
                    _dedup_last_key = key
                    _dedup_count = 1
                    _dedup_last_time = now
                    try:
                        emit_html = _build_display_html(ts, level, raw_msg, _caller0, _window0)
                    except Exception:
                        emit_html = f"\u25cf {_short_time(ts)} {raw_msg}"
        except Exception:
            try:
                emit_html = _build_display_html(ts, level, raw_msg, _caller0, _window0)
            except Exception:
                return
        if need_timer:
            _ensure_flush_timer()
            return
        try:
            if flush_html is not None:
                _emit_to_browsers(flush_html)
            if emit_html is not None:
                _emit_to_browsers(emit_html)
        except Exception:
            pass
    except Exception:
        pass


def _file_format(record):
    """loguru file handler format：每行一个扁平 JSON（serialize 兼容补丁）。"""
    try:
        try:
            extra = dict(record.get('extra', {}) or {})
        except Exception:
            extra = {}
        try:
            window = str(extra.pop('window', '') or '')
        except Exception:
            window = ''
        try:
            run_id = str(extra.pop('run_id', _RUN_ID) or _RUN_ID)
        except Exception:
            run_id = _RUN_ID
        try:
            caller = str(extra.pop('_caller', '') or '')
        except Exception:
            caller = ''
        try:
            extra.pop('_file_only', None)
        except Exception:
            pass
        if not caller:
            try:
                caller = f"{record.get('module', 'unknown')}:{record.get('line', 0)}"
            except Exception:
                caller = 'unknown:0'
        try:
            ts = record['time'].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        except Exception:
            ts = _get_timestamp()
        try:
            level = record['level'].name
        except Exception:
            level = 'INFO'
        try:
            level = _normalize_level(level)
        except Exception:
            level = 'INFO'
        try:
            msg = str(record.get('message', ''))
        except Exception:
            msg = ''
        data = {
            'timestamp': ts,
            'level': level,
            'module': caller,
            'message': msg,
            'window': window,
            'run_id': run_id,
        }
        try:
            for k, v in extra.items():
                if k not in data:
                    data[k] = v
        except Exception:
            pass
        try:
            s = json.dumps(data, ensure_ascii=False, default=str)
        except Exception:
            s = json.dumps(
                {'timestamp': ts, 'level': level, 'module': caller,
                 'message': msg, 'window': window, 'run_id': run_id},
                ensure_ascii=False, default=str,
            )
        return s.replace('{', '{{').replace('}', '}}') + '\n'
    except Exception:
        try:
            s = json.dumps(
                {'timestamp': _get_timestamp(), 'level': 'INFO', 'module': 'unknown:0',
                 'message': '', 'window': '', 'run_id': _RUN_ID},
                ensure_ascii=False,
            )
            return s.replace('{', '{{').replace('}', '}}') + '\n'
        except Exception:
            return '{message}\n'


try:
    _lq.remove()
except Exception:
    pass
try:
    _lq.add(_display_sink, level=0, format='{message}', catch=True)
except Exception:
    pass

_file_handler_id = None


def _add_file_sink(path):
    """按文件 sink 标准配置添加 handler，返回 handler id（失败返回 None）。永不抛异常。"""
    global _file_handler_id
    try:
        _file_handler_id = _lq.add(
            path,
            level=0,
            format=_file_format,
            rotation=LOG_ROTATION,
            retention=LOG_RETENTION,
            encoding="utf-8",
            errors="replace",
            catch=True,
        )
        return _file_handler_id
    except Exception:
        return None


def set_log_file(path: str) -> bool:
    """将文件 sink 重定向到 path（移除当前文件 handler，按相同配置重加）。

    测试隔离用；成功返回 True，失败返回 False；永不抛异常。
    """
    global _file_handler_id
    try:
        try:
            if _file_handler_id is not None:
                _lq.remove(_file_handler_id)
        except Exception:
            pass
        _file_handler_id = None
        return _add_file_sink(path) is not None
    except Exception:
        return False


try:
    _add_file_sink(LOG_FILE_PATTERN)
except Exception:
    pass


class _BoundLogger:
    """logger.bind(...)/bind_window(...) 返回的绑定 logger：display 保持人类文本，file 追加字段。"""

    def __init__(self, owner, extras):
        try:
            self._owner = owner
        except Exception:
            self._owner = None
        try:
            self._extras = dict(extras or {})
        except Exception:
            self._extras = {}

    def bind(self, **kwargs):
        try:
            merged = dict(self._extras)
            merged.update(kwargs or {})
        except Exception:
            merged = dict(self._extras)
        return _BoundLogger(None, merged)

    def bind_window(self, hwnd=None):
        try:
            merged = dict(self._extras)
            merged['window'] = '' if hwnd is None else str(hwnd)
        except Exception:
            merged = {'window': ''}
        return _BoundLogger(None, merged)

    def _emit(self, level, message):
        try:
            canon = _normalize_level(level)
            try:
                caller = LogRedirect.get_caller_info()
            except Exception:
                caller = 'unknown:0'
            try:
                eff = dict(self._extras)
            except Exception:
                eff = {}
            try:
                if 'window' not in eff:
                    eff['window'] = ''
                else:
                    eff['window'] = str(eff['window'] or '')
            except Exception:
                eff['window'] = ''
            try:
                if 'run_id' not in eff:
                    eff['run_id'] = _RUN_ID
            except Exception:
                eff['run_id'] = _RUN_ID
            try:
                eff['_caller'] = caller
            except Exception:
                pass
            try:
                _lq.bind(**eff).log(canon, str(message))
            except Exception:
                pass
        except Exception:
            pass

    def log(self, message, level='INFO'):
        self._emit(level, message)

    def debug(self, message):
        self._emit('DEBUG', message)

    def info(self, message):
        self._emit('INFO', message)

    def warn(self, message):
        self._emit('WARNING', message)

    def warning(self, message):
        self._emit('WARNING', message)

    def error(self, message):
        self._emit('ERROR', message)

    def print(self, *args, **kwargs):
        try:
            self._emit('INFO', ' '.join(map(str, args)))
        except Exception:
            pass

    def progress(self, done, total):
        """进度透传：经拥有者或全局单例发出 progress_updated。永不抛异常。"""
        try:
            try:
                owner = getattr(self, '_owner', None)
            except Exception:
                owner = None
            if owner is not None:
                try:
                    owner.progress(done, total)
                    return
                except Exception:
                    pass
            try:
                g = globals().get('logger', None)
            except Exception:
                g = None
            if g is not None:
                try:
                    g.progress(done, total)
                except Exception:
                    pass
        except Exception:
            pass


class LogRedirect(QtCore.QObject):
    append_log = QtCore.pyqtSignal(str)
    progress_updated = QtCore.pyqtSignal(int, int)

    def __init__(self, text_browser=None):
        super().__init__()
        self.text_browser = text_browser
        self.append_log.connect(self._safe_append)
        # 兼容保留：去重时间阈值（实际去重走全局 display-side 逻辑）
        self.last_log_message = None
        self.last_log_time = 0
        self.log_threshold = 10  # 日志去重时间阈值（秒）
        self._log_level = 'INFO'
        try:
            with _instances_lock:
                _instances.add(self)
        except Exception:
            pass

    @property
    def log_level(self):
        try:
            return self._log_level
        except Exception:
            return 'INFO'

    @log_level.setter
    def log_level(self, value):
        try:
            self._log_level = str(value).upper() if isinstance(value, str) else 'INFO'
        except Exception:
            self._log_level = 'INFO'

    def set_text_browser(self, text_browser):
        """
        设置文本浏览器用于显示日志
        :param text_browser: QTextBrowser 实例
        """
        self.text_browser = text_browser

    # 将print函数输出的内容定向写入到textBrowser中
    def _safe_append(self, text):
        try:
            browser = self.text_browser
        except Exception:
            return
        if browser is None:
            return
        try:
            # 暂停：冻结显示追加（文件照写，display 丢弃）
            try:
                paused = browser.property('logPaused')
            except Exception:
                paused = False
            if paused:
                return
            try:
                auto = browser.property('logAutoScroll')
                auto_scroll = True if auto is None else bool(auto)
            except Exception:
                auto_scroll = True
            try:
                bar = browser.verticalScrollBar()
                at_bottom = bar.value() >= bar.maximum() - 20
            except Exception:
                bar = None
                at_bottom = True
            # 检查text是否包含HTML标记
            if '<font' in text or '<span' in text:
                # 如果是HTML，使用insertHtml
                browser.insertHtml(text + '<br>')
            else:
                # 如果是普通文本，使用append
                browser.append(text)
            # 智能自动滚动：仅当追加前已在底部且允许自动滚动时才置底；读历史不打断
            if auto_scroll and at_bottom and bar is not None:
                try:
                    bar.setValue(bar.maximum())
                except Exception:
                    pass
        except Exception:
            pass

    @staticmethod
    def get_caller_info():
        try:
            frame = sys._getframe(1)
        except Exception:
            return 'unknown:0'
        try:
            while frame is not None:
                try:
                    mod = frame.f_globals.get('__name__', '')
                except Exception:
                    mod = ''
                try:
                    if not (str(mod).startswith('OAT.utils.logging') or str(mod).startswith('loguru')):
                        try:
                            lineno = frame.f_lineno
                        except Exception:
                            lineno = 0
                        return f"{mod or 'unknown'}:{lineno}"
                except Exception:
                    pass
                try:
                    frame = frame.f_back
                except Exception:
                    break
            return 'unknown:0'
        except Exception:
            return 'unknown:0'

    @staticmethod
    def get_timestamp():
        return _get_timestamp()

    def _log(self, level, message, extras=None):
        try:
            canon = _normalize_level(level)
            try:
                msg_str = str(message)
            except Exception:
                msg_str = ''
            try:
                caller = self.get_caller_info()
            except Exception:
                caller = 'unknown:0'
            try:
                eff = dict(extras or {})
            except Exception:
                eff = {}
            try:
                if 'window' not in eff:
                    eff['window'] = ''
                else:
                    eff['window'] = str(eff['window'] or '')
            except Exception:
                eff['window'] = ''
            try:
                if 'run_id' not in eff:
                    eff['run_id'] = _RUN_ID
            except Exception:
                eff['run_id'] = _RUN_ID
            try:
                eff['_caller'] = caller
            except Exception:
                pass
            try:
                self.last_log_message = msg_str
                self.last_log_time = time.time()
            except Exception:
                pass
            try:
                _lq.bind(**eff).log(canon, msg_str)
            except Exception:
                pass
        except Exception:
            pass

    def log(self, message, level='INFO'):
        self._log(level, message)

    def debug(self, message):
        self._log('DEBUG', message)

    def info(self, message):
        self._log('INFO', message)

    def warn(self, message):
        self._log('WARNING', message)

    def warning(self, message):
        self._log('WARNING', message)

    def error(self, message):
        self._log('ERROR', message)

    def print(self, *args, **kwargs):
        # 保持原print功能，默认INFO级别
        try:
            self._log('INFO', ' '.join(map(str, args)))
        except Exception:
            pass

    def progress(self, done, total):
        """挑战进度信号（signal ONLY：无日志行、无文件记录）。永不抛异常。"""
        try:
            try:
                d = int(done)
            except Exception:
                d = 0
            try:
                t = int(total)
            except Exception:
                t = 0
            try:
                self.progress_updated.emit(d, t)
            except Exception:
                pass
            # 广播到其他存活实例（如 main_window 自建 LogRedirect），保证连单例的槽也能收到
            try:
                with _instances_lock:
                    targets = list(_instances)
            except Exception:
                targets = []
            for inst in targets:
                if inst is self:
                    continue
                try:
                    inst.progress_updated.emit(d, t)
                except Exception:
                    continue
        except Exception:
            pass

    def bind(self, **kwargs):
        try:
            return _BoundLogger(self, dict(kwargs or {}))
        except Exception:
            return _BoundLogger(self, {})

    def bind_window(self, hwnd=None):
        try:
            return _BoundLogger(self, {'window': '' if hwnd is None else str(hwnd)})
        except Exception:
            return _BoundLogger(self, {'window': ''})

    def log_to_file(self, log_data):
        """
        兼容保留：只写文件，不走 display（静默）。
        :param log_data: 日志数据字典或纯文本消息
        """
        try:
            if isinstance(log_data, dict):
                try:
                    lvl = _normalize_level(log_data.get('level', 'INFO'))
                except Exception:
                    lvl = 'INFO'
                try:
                    msg = str(log_data.get('message', ''))
                except Exception:
                    msg = ''
                try:
                    caller = str(log_data.get('module', '') or self.get_caller_info())
                except Exception:
                    caller = 'unknown:0'
                extras = {'window': '', 'run_id': _RUN_ID, '_caller': caller, '_file_only': True}
                try:
                    for k, v in log_data.items():
                        if k not in ('timestamp', 'level', 'module', 'message') and k not in extras:
                            extras[k] = v
                except Exception:
                    pass
                try:
                    _lq.bind(**extras).log(lvl, msg)
                except Exception:
                    pass
            else:
                try:
                    caller = self.get_caller_info()
                except Exception:
                    caller = 'unknown:0'
                try:
                    _lq.bind(window='', run_id=_RUN_ID, _caller=caller, _file_only=True).log('INFO', str(log_data))
                except Exception:
                    pass
        except Exception:
            pass


logger = LogRedirect()
