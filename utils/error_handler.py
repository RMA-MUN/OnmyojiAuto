def handle_global_exception(e, window=None):
    error_msg = f"主程序运行时出现异常: {e}"
    if window and hasattr(window, 'log_redirect'):
        window.log_redirect.print(error_msg)
    from PyQt6.QtWidgets import QMessageBox
    QMessageBox.critical(None, "致命错误", str(e))