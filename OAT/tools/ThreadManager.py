from PyQt6.QtCore import pyqtSignal, QThread

from OAT.config.check_update import UpdateChecker
from OAT.config.update_manager import UpdateManager


class UpdateCheckThread(QThread):
    # 信号定义
    update_available = pyqtSignal(str, dict)
    update_not_available = pyqtSignal()
    update_error = pyqtSignal(str)

    def __init__(self):
        super().__init__()

    def run(self):
        try:
            # 创建实例
            update_manager = UpdateManager()

            # 检查更新
            latest_version = update_manager.get_update()  # 获取带前缀的最新版本号

            if latest_version:
                update_checker = UpdateChecker()  # 创建更新检查器实例
                latest_info = update_checker.get_latest_release_info()  # 获取最新版本信息
                if latest_info:
                    self.update_available.emit(latest_version, latest_info)
                else:
                    self.update_not_available.emit()
            else:
                self.update_not_available.emit()
        except Exception as e:
            self.update_error.emit(str(e))