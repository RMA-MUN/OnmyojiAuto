<<<<<<< HEAD
from PyQt6 import QtWidgets

from OAT.tools.mainGui import MainWindow

class WindowFactory:
    @staticmethod
    def create_main_window() -> QtWidgets.QMainWindow:
        """创建并返回主窗口实例"""
=======
from PyQt6 import QtWidgets

from OAT.tools.mainGui import MainWindow

class WindowFactory:
    @staticmethod
    def create_main_window() -> MainWindow:
        """创建并返回主窗口实例"""
>>>>>>> develop
        return MainWindow()