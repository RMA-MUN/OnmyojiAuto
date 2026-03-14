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
        # 用于去重的属性
        self.last_log_message = None
        self.last_log_time = 0
        self.log_threshold = 10  # 日志去重时间阈值（秒）
        # 日志文件清理设置
        self.max_log_size = 50 * 1024 * 1024  # 最大日志文件大小（50MB）

    # 将print函数输出的内容定向写入到textBrowser中
    def _safe_append(self, text):
        if self.text_browser:
            self.text_browser.append(text)
            scroll_bar = self.text_browser.verticalScrollBar()
            scroll_bar.setValue(scroll_bar.maximum())

    @staticmethod
    def get_caller_info():
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

    @staticmethod
    def get_timestamp():
        # ISO 8601标准时间格式
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def log(self, message, level='INFO'):
        current_time = datetime.datetime.now().timestamp()
        
        # 检查是否是重复消息
        if message == self.last_log_message and (current_time - self.last_log_time) < self.log_threshold:
            return  # 跳过重复日志

        # 更新最后一条日志信息
        self.last_log_message = message
        self.last_log_time = current_time
        
        timestamp = self.get_timestamp()
        caller_info = self.get_caller_info()
        
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
            # 检查日志文件大小
            if os.path.exists(LOG_FILE):
                file_size = os.path.getsize(LOG_FILE)
                if file_size > self.max_log_size:
                    # 清理日志文件，只保留最后1000行
                    self._cleanup_log_file()
            
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False)
                f.write('\n')
        except Exception:
            pass

    def _cleanup_log_file(self):
        """
        清理日志文件，只保留最后50行
        """
        try:
            # 读取日志文件
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 只保留最后1000行
            if len(lines) > 50:
                lines = lines[-50:]
            
            # 写回日志文件
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            # 记录清理信息
            cleanup_message = f"检测到日志文件过大，已自动清理。"
            cleanup_log_data = {
                'timestamp': self.get_timestamp(),
                'level': 'INFO',
                'module': 'OAT.utils.logging',
                'message': cleanup_message
            }
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                json.dump(cleanup_log_data, f, ensure_ascii=False)
                f.write('\n')
        except Exception:
            pass
