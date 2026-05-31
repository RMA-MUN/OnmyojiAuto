import sys
import time

from PyQt6 import QtWidgets

from OAT.utils.error_handler import handle_global_exception
from OAT.app.main_window import MainWindow
from OAT.utils.logging import logger

if not hasattr(sys, 'setcheckinterval'):
    def setcheckinterval(interval):
        sys.setswitchinterval(interval / 1000.0)
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
