import requests
from urllib3.exceptions import InsecureRequestWarning

from OAT.tools.settings import APP_VERSION
from OAT.utils.logging import logger


class UpdateChecker:
    """
    GitHub版本更新检查器
    用于检查当前软件版本是否需要更新
    """

    # 禁用不安全请求警告
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    # 版本相关常量
    CURRENT_VERSION = f"{APP_VERSION}"  # 当前版本，不允许修改，用于检查是否更新
    GITHUB_OWNER = "RMA-MUN"  # 仓库所有人
    GITHUB_REPO = "OnmyojiAuto"  # 仓库名

    def __init__(self, owner: str = None, repo: str = None, current_version: str = CURRENT_VERSION):
        """
        初始化更新检查器

        :param owner: GitHub仓库的所有者
        :param repo: GitHub仓库的名称
        :param current_version: 当前版本
        """
        self.owner = owner if owner else self.GITHUB_OWNER
        self.repo = repo if repo else self.GITHUB_REPO
        self.current_version = current_version if current_version else self.CURRENT_VERSION

    def get_latest_release_info(self) -> dict | None:
        """
        获取指定GitHub仓库的最新release信息。

        :return: 最新release信息的字典，如果获取失败则返回None
        """
        api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest"
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        try:
            response = requests.get(api_url, headers=headers, verify=False, timeout=10)
            # print(f"响应状态码: {response.status_code}")
            # print(f"响应头: {response.headers}")
            # print(f"响应内容前200字符: {response.text[:200]}...")

            response.raise_for_status()  # 检查请求是否成功

            # 尝试解析JSON
            info = response.json()
            return info

        except requests.exceptions.RequestException as e:
            logger.error(f"检查更新请求失败: {e}")
            return None
        except KeyError:
            logger.error("未找到tag_name字段，请检查仓库是否有release")
            return None

    @staticmethod
    def get_tag(info: dict) -> str | None:
        """
        从release info中提取tag name。

        :param info: release info字典
        :return: tag name字符串，如果未找到则返回None
        """
        return info.get("tag_name")

    @staticmethod
    def get_update_info(info: dict) -> str | None:
        """
        从release info中提取更新描述。

        :param info: release info字典
        :return: 更新描述字符串，如果未找到则返回None
        """
        return info.get("body")

    @staticmethod
    def split_version(version: str):
        """
        分割版本字符串，返回版本号的数字列表。

        :param version: 版本字符串，例如 "OAT-v1.5.4"
        :return: 版本号数字列表，例如 [1, 5, 4]
        """
        # 处理带前缀的版本字符串
        if "-v" in version:
            version = version.split("-v")[-1]
        # 按点分割版本号，转换为整数列表
        return [int(part) for part in version.split(".")]

    def latest_version(self) -> str | None:
        """
        无参获取最新版本号。

        :return: 最新版本号字符串，如果获取失败则返回None， 如"OAT-v1.5.4"
        """
        info = self.get_latest_release_info()
        if info:
            return self.get_tag(info)
        return None

    def check_update(self) -> bool:
        """
        检查当前版本是否需要更新。

        :return: 如果需要更新则返回True，否则返回False
        """
        info = self.get_latest_release_info()
        if info:
            latest_tag = self.get_tag(info)
            if latest_tag:
                latest_version = self.split_version(latest_tag)  # ["1", "5", "4"]
                current_version = self.split_version(self.current_version)  # ["1", "5", "3"]
                # print(f"【调试】最新版本: {latest_version}, 当前版本: {current_version}")
                if latest_version > current_version:
                    return True
        return False


if __name__ == "__main__":
    # 创建更新检查器实例
    checker: UpdateChecker = UpdateChecker()

    # 获取最新版本信息
    latest_info = checker.get_latest_release_info()

    # # 输出最新版本信息和更新描述
    # if latest_info:
    #     tag = checker.get_tag(latest_info)
    #     update_info = checker.get_update_info(latest_info)
    #     print(f"最新版本: {tag}")
    #     print(f"更新描述: {update_info}")
    #     if checker.check_update():
    #         print("当前版本需要更新")
    #     else:
    #         print("当前版本已更新")

    # 检查是否需要更新
    if checker.check_update():
        print(f"当前版本{checker.current_version}需要更新, 最新版本为{checker.latest_version()}")
    else:
        print(f"当前版本{checker.current_version}无更新")

    # 输出更新描述
    update_info = checker.get_update_info(latest_info)
    print(f"更新描述: {update_info}")
