# 初始化应用程序
import time

from PyQt6 import QtWidgets

from OAT.utils.error_handler import handle_global_exception
from OAT.tools.mainGui import MainWindow

def launch_app():
    app = QtWidgets.QApplication([])
    window = None
    try:
        window = MainWindow()
        window.show()
        print("程序启动成功")
        time.sleep(1)
        return app.exec()
    except Exception as e:
        handle_global_exception(e, window)
        return 1