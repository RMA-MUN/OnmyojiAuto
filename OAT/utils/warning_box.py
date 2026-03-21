import sys
from PyQt6.QtWidgets import QMessageBox, QApplication
from PyQt6.QtCore import Qt, QObject, pyqtSignal

class PopupWorker(QObject):
    """弹窗工作类，用于在主线程中显示弹窗"""
    show_warning_signal = pyqtSignal(str)
    show_error_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        # 连接信号到槽函数
        self.show_warning_signal.connect(self._show_warning)
        self.show_error_signal.connect(self._show_error)
        # 保存弹窗实例，防止被垃圾回收
        self.active_popups = []
    
    def _show_warning(self, message: str):
        """显示警告弹窗"""
        msg_box = QMessageBox()
        msg_box.setWindowTitle("警告")
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        # 连接按钮点击信号，点击后从列表中移除
        msg_box.finished.connect(lambda: self._remove_popup(msg_box))
        msg_box.show()
        # 添加到活跃弹窗列表
        self.active_popups.append(msg_box)
    
    def _show_error(self, message: str):
        """显示错误弹窗"""
        msg_box = QMessageBox()
        msg_box.setWindowTitle("错误")
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        # 连接按钮点击信号，点击后从列表中移除
        msg_box.finished.connect(lambda: self._remove_popup(msg_box))
        msg_box.show()
        # 添加到活跃弹窗列表
        self.active_popups.append(msg_box)
    
    def _remove_popup(self, popup):
        """从活跃弹窗列表中移除弹窗"""
        if popup in self.active_popups:
            self.active_popups.remove(popup)

# 创建全局的弹窗工作实例
popup_worker = PopupWorker()

def warning_box(message: str):
    """显示警告弹窗"""
    try:
        # 通过信号在主线程中显示弹窗
        popup_worker.show_warning_signal.emit(message)
    except Exception as e:
        print(f"显示警告弹窗失败: {e}")
