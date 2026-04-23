# 初始化应用程序
import sys
import time

from PyQt6 import QtWidgets

from OAT.utils.error_handler import handle_global_exception
from OAT.tools.MainGui import MainWindow
from OAT.utils.logging import logger

# 兼容性处理：为Python 3.2+版本添加setcheckinterval函数
if not hasattr(sys, 'setcheckinterval'):
    def setcheckinterval(interval):
        """兼容Python 3.2+版本的setcheckinterval函数
        将interval转换为switchinterval的值（从毫秒转换为秒）
        """
        sys.setswitchinterval(interval / 1000.0)  # 转换为秒
    sys.setcheckinterval = setcheckinterval

def launch_app():
    app = QtWidgets.QApplication([])
    window = None
    try:
        window = MainWindow()
        window.show()
        logger.info("程序启动成功")
        time.sleep(1)
        return app.exec()
    except Exception as e:
        handle_global_exception(e, window)
        return 1