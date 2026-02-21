from PyQt6 import QtWidgets

from OAT.tools.MainGui import MainWindow

class WindowFactory:
    @staticmethod
    def create_main_window() -> MainWindow:
        """创建并返回主窗口实例"""
        return MainWindow()