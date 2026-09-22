import os
import sys
import traceback
from .error_box import error_box
from .logging import logger

# 创建 logs 文件夹
LOGS_DIR = 'logs'
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

# 日志文件路径见 OAT.utils.logging（file sink 按天轮转）；main_window 从本模块导入 LOG_FILE，保持再导出
from .logging import LOG_FILE  # noqa: F401  (re-export for OAT.app.main_window)

__all__ = ["LOG_FILE", "handle_global_exception", "log_exception", "log_error", "setup_global_exception_handler"]


def handle_global_exception(e: Exception, window=None):
    """
    处理全局异常
    :param e: 异常对象
    :param window: 窗口对象（可选）
    """
    error_msg = f"主程序运行时出现异常: {e}"
    error_box(str(e))
    log_error(error_msg)


def log_exception(exc_type, exc_value, exc_traceback):
    """
    捕获全局异常并写入日志文件，方便后续调试。
    """
    tb = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logger.error(f"Uncaught exception:\n{tb}")


def log_error(error_msg: str):
    """
    记录错误信息到日志文件
    :param error_msg: 错误信息
    """
    logger.error(error_msg)


def setup_global_exception_handler():
    """
    设置全局异常处理器
    """
    sys.excepthook = log_exception
