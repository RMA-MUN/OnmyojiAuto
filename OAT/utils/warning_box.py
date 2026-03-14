import sys
from PyQt6.QtWidgets import QMessageBox, QApplication


def warning_box(message: str):
    """
    显示警告弹窗
    
    Args:
        message: 警告信息内容
    
    Returns:
        None
    """
    try:
        # 检查是否已有QApplication实例
        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)
        QMessageBox.warning(None, "警告", message)
        app.exec()
    except Exception:
        pass
