from OAT.config.check_update import UpdateChecker
from OAT.tools.config_manager import ConfigReader

class UpdateManager:
    """更新管理器，负责对更新相关操作(忽略更新，立即更新)"""

    checker: UpdateChecker = UpdateChecker() # 更新检查器

    def __init__(self):
        self.config_reader = ConfigReader("config/update.json")
        self.config_data = self.config_reader.read_config()

    def get_update(self) -> str | None:
        """检查是否有新的版本"""
        # 获取最新版本
        latest_version = self.checker.latest_version()
        if latest_version:
            print(f"最新版本为{latest_version}")
            return latest_version
        else:
            print("获取最新版本失败")
            return None

    def ignore_update(self, version: str) -> bool:
        """忽略指定版本的更新"""
        try:
            # 确保ignore_versions是列表
            if "ignore_versions" not in self.config_data:
                self.config_data["ignore_versions"] = []

            # 只添加不重复的版本号
            if version not in self.config_data["ignore_versions"]:
                # 尝试将最新获取的版本写入到json
                self.config_data["ignore_versions"].append(version)
                self.config_reader.write_config(self.config_data)
                print(f"已忽略更新版本 {version}")
                return True
            else:
                print(f"版本 {version} 已经在忽略列表中")
                return True
        except Exception as e:
            print(f"忽略更新版本 {version} 时出现异常: {e}")
            return False


if __name__ == '__main__':
    update_manager = UpdateManager()
    latest_version = update_manager.get_update()
    if latest_version:
        # 将版本号转换为列表
        ignore_version: str = UpdateChecker.split_version(latest_version)
        # 忽略最新版本的更新
        update_manager.ignore_update(ignore_version)

