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


class UpdateDownloadThread(QThread):
    """更新下载线程"""
    download_progress = pyqtSignal(int, int, float, float)  # 当前下载量, 总大小, 速度(字节/秒), 剩余时间(秒)
    download_complete = pyqtSignal(str)  # 下载完成，返回文件路径
    download_error = pyqtSignal(str)  # 下载错误

    def __init__(self, download_url: str):
        super().__init__()
        self.download_url = download_url

    def progress_callback(self, downloaded, total_size, speed, remaining):
        """
        下载进度回调
        :param downloaded: 已下载字节数
        :param total_size: 总字节数
        :param speed: 下载速度 (字节/秒)
        :param remaining: 剩余时间 (秒)
        :return: None
        """
        self.download_progress.emit(downloaded, total_size, speed, remaining)

    def run(self):
        try:
            update_manager = UpdateManager()
            zip_path = update_manager.download_new_version(
                self.download_url,
                progress_callback=self.progress_callback
            )
            
            if zip_path:
                self.download_complete.emit(zip_path)
            else:
                self.download_error.emit("下载失败")
        except Exception as e:
            self.download_error.emit(str(e))