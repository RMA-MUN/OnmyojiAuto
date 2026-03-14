import datetime
import os
import traceback
import sys
from OAT.utils.warning_box import warning_box

# 创建 logs 文件夹
LOGS_DIR = 'logs'
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

# 日志文件路径
LOG_FILE = os.path.join(LOGS_DIR, 'log.log')


def handle_global_exception(e: Exception, window=None):
    """
    处理全局异常
    
    Args:
        e: 异常对象
        window: 窗口对象（可选）
    
    Returns:
        None
    """
    error_msg = f"主程序运行时出现异常: {e}"
    # 记录错误到日志文件
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{timestamp} - Global exception: {error_msg}\n")
        traceback.print_exc(file=f)
    # 显示警告弹窗
    warning_box(error_msg)


def log_exception(exc_type, exc_value, exc_traceback):
    """
    捕获全局异常并写入日志文件，方便后续调试。
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{timestamp} - Uncaught exception:\n")
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)


def setup_global_exception_handler():
    """
    设置全局异常处理器
    """
    sys.excepthook = log_exception