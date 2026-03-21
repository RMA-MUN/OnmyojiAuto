from OAT.utils.warning_box import popup_worker

def error_box(message: str):
    """显示错误弹窗"""
    try:
        # 通过信号在主线程中显示弹窗
        popup_worker.show_error_signal.emit(message)
    except Exception as e:
        print(f"显示错误弹窗失败: {e}")