import sys
import time

from PyQt6 import QtWidgets

from OAT.utils.admin import ELEVATION_FLAG, alert_no_admin, is_admin, relaunch_as_admin
from OAT.utils.error_handler import handle_global_exception
from OAT.app.main_window import MainWindow
from OAT.utils.logging import logger

if not hasattr(sys, 'setcheckinterval'):
    def setcheckinterval(interval):
        sys.setswitchinterval(interval / 1000.0)
    sys.setcheckinterval = setcheckinterval


def _ensure_admin() -> bool:
    """启动最前端的权限守门，必须在创建 QApplication 之前调用。

    非管理员直接触发 UAC 重启自身并退出本实例；拉起失败或提权后仍无权限
    （带 ELEVATION_FLAG 的实例）时，用原生弹窗提示后退出，不进入任何 UI 初始化。
    """
    if is_admin():
        return True
    logger.warn("当前未以管理员身份运行，正在请求提权")
    # 提权重启过来的实例若仍无管理员权限，不再二次拉起（否则会循环弹窗拉起）
    if ELEVATION_FLAG not in sys.argv and relaunch_as_admin():
        return False
    logger.warn("未能获取管理员权限，程序退出")
    alert_no_admin()
    return False


def launch_app():
    if not _ensure_admin():
        return 0
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
