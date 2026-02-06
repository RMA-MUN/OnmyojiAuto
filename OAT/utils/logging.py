import datetime
import inspect
import json
import os
from PyQt6 import QtCore

# 创建 logs 文件夹
LOGS_DIR = 'logs'
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

# 日志文件路径
LOG_FILE = os.path.join(LOGS_DIR, 'log.log')


class LogRedirect(QtCore.QObject):
    append_log = QtCore.pyqtSignal(str)

    def __init__(self, text_browser):
        super().__init__()
        self.text_browser = text_browser
        self.append_log.connect(self._safe_append)

    # 将print函数输出的内容定向写入到textBrowser中
    def _safe_append(self, text):
        if self.text_browser:
            self.text_browser.append(text)
            scroll_bar = self.text_browser.verticalScrollBar()
            scroll_bar.setValue(scroll_bar.maximum())

    def get_caller_info(self):
        stack = inspect.stack()
        # 遍历调用栈，找到实际的print触发位置
        # 跳过当前方法(get_caller_info)、log方法、info/warn/error方法和print方法
        # 寻找第一个不在logging.py和mainGui.py中的调用点
        for i in range(3, len(stack)):
            frame = stack[i]
            module = inspect.getmodule(frame[0])
            # 检查是否为目标调用点
            if module and not module.__name__.startswith('OAT.utils.logging') and not module.__name__.startswith('OAT.tools.mainGui'):
                return f"{module.__name__}:{frame.lineno}"

        # 如果没有找到合适的调用点，回退到原逻辑
        frame = stack[3] if len(stack) > 3 else stack[-1]
        module = inspect.getmodule(frame[0])
        module_name = module.__name__ if module else 'unknown'
        return f"{module_name}:{frame.lineno}"

    def get_timestamp(self):
        # ISO 8601标准时间格式
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def log(self, message, level='INFO'):
        timestamp = self.get_timestamp()
        caller_info = self.get_caller_info()
        # 文本浏览器显示格式（保持可读性）
        display_text = f"{timestamp} - {message}"
        self.append_log.emit(display_text)

        # 日志文件JSON格式（便于后续分析）
        log_data = {
            'timestamp': timestamp,
            'level': level,
            'module': caller_info,
            'message': message
        }
        self.log_to_file(log_data)

    def info(self, message):
        self.log(message, 'INFO')

    def warn(self, message):
        self.log(message, 'WARN')

    def error(self, message):
        self.log(message, 'ERROR')

    def print(self, *args, **kwargs):
        # 保持原print功能，默认INFO级别
        self.info(' '.join(map(str, args)))

    def log_to_file(self, log_data):
        """
        将日志数据写入文件
        :param log_data: 日志数据字典
        """
        try:
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False)
                f.write('\n')
        except Exception as e:
            print(f"写入日志文件失败: {e}")
