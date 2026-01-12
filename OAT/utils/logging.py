<<<<<<< HEAD
import sys
import traceback
import os
from PyQt6.QtCore import QObject, pyqtSignal

class LogEmitter(QObject):
    log_signal = pyqtSignal(str)

    def write(self, message):
        if message.strip():
            # 获取调用栈，找到实际的print触发位置
            stack = traceback.extract_stack()
            # 查找调用栈中第一个不在logging.py文件中的调用
            caller_frame = None
            for frame in reversed(stack):
                if os.path.basename(frame.filename) != 'logging.py':
                    caller_frame = frame
                    break
            
            if caller_frame:
                # 格式化调用位置信息
                module_name = os.path.basename(caller_frame.filename)
                # 去掉.py扩展名
                if module_name.endswith('.py'):
                    module_name = module_name[:-3]
                
                # 构建新的日志消息，包含调用位置
                location_info = f"[{module_name}:{caller_frame.lineno}] "
                self.log_signal.emit(location_info + message)
            else:
                self.log_signal.emit(message)

    def flush(self):
        pass

def setup_logging(window):
    log_emitter = LogEmitter()
    log_emitter.log_signal.connect(window.log_redirect.print)
    sys.stdout = log_emitter
=======
import sys
import traceback
import os
from PyQt6.QtCore import QObject, pyqtSignal

class LogEmitter(QObject):
    log_signal = pyqtSignal(str)

    def write(self, message: str):
        if message.strip():
            # 获取调用栈，找到实际的print触发位置
            stack = traceback.extract_stack()
            # 查找调用栈中第一个不在logging.py文件中的调用
            caller_frame = None
            for frame in reversed(stack):
                if os.path.basename(frame.filename) != 'logging.py':
                    caller_frame = frame
                    break
            
            if caller_frame:
                # 格式化调用位置信息
                module_name = os.path.basename(caller_frame.filename)
                # 去掉.py扩展名
                if module_name.endswith('.py'):
                    module_name = module_name[:-3]
                
                # 构建新的日志消息，包含调用位置
                location_info = f"[{module_name}:{caller_frame.lineno}] "
                self.log_signal.emit(location_info + message)
            else:
                self.log_signal.emit(message)

    def flush(self):
        pass

def setup_logging(window):
    log_emitter = LogEmitter()
    log_emitter.log_signal.connect(window.log_redirect.print)
    sys.stdout = log_emitter
>>>>>>> develop
    sys.stderr = log_emitter