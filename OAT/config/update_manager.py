from OAT.config.check_update import UpdateChecker
from OAT.tools.config_manager import ConfigReader
import os
import zipfile
import requests
import time
from urllib3.exceptions import InsecureRequestWarning
from tqdm import tqdm

# 禁用不安全请求警告
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

class UpdateManager:
    """更新管理器，负责对更新相关操作(忽略更新，立即更新)"""

    def __init__(self):
        self.checker: UpdateChecker = UpdateChecker() # 更新检查器
        # 明确指定配置文件的绝对路径
        config_dir = os.path.dirname(os.path.abspath(__file__))
        update_json_path = os.path.join(config_dir, "update.json")

        # 调试信息：打印配置文件路径
        print(f"尝试读取配置文件: {update_json_path}")

        # 确保文件存在
        if not os.path.exists(update_json_path):
            print(f"警告：配置文件不存在: {update_json_path}")
            # 创建默认配置
            default_config = {
                "current_version": "1.5.3",
                "ignore_versions": []
            }
            # 保存默认配置
            with open(update_json_path, 'w', encoding='utf-8') as f:
                import json
                json.dump(default_config, f, ensure_ascii=False, indent=2)
            print(f"已创建默认配置文件: {update_json_path}")

        self.config_reader = ConfigReader(update_json_path)
        self.config_data = self.config_reader.read_config()

        # 确保配置数据有效
        if self.config_data is None:
            print("警告：配置文件读取失败，使用默认配置")
            self.config_data = {
                "current_version": "1.5.3",
                "ignore_versions": []
            }

        # 确保ignore_versions字段存在
        if "ignore_versions" not in self.config_data:
            self.config_data["ignore_versions"] = []

    def get_update(self) -> str | None:
        """
        检查是否有新的版本
        :return: 最新版本号字符串或None，如"1.5.4"
        """
        # 获取最新版本
        latest_version_tag = self.checker.latest_version() # 如OAT-v1.5.4

        # 确保latest_version_tag不为None
        if not latest_version_tag:
            print("无法获取最新版本信息")
            return None

        latest_version_split = UpdateChecker.split_version(latest_version_tag) # 如"1.5.4"

        # 确保ignore_versions是列表
        if "ignore_versions" not in self.config_data:
            self.config_data["ignore_versions"] = []

        # 如果新版本不在忽略列表里， 则返回最新版本
        if latest_version_split not in self.config_data["ignore_versions"]:
            print(f"最新版本为{latest_version_tag}, {latest_version_split}")
            return latest_version_split
        else:
            print("当前无新的版本")
            return None

    def ignore_update(self, version: str) -> bool:
        """
        忽略指定版本的更新
        :param version: 版本号字符串，如"1.5.4"
        :return: 是否成功忽略更新
        """
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

    @staticmethod
    def download_new_version(url: str, max_retries: int = 3):
        """
        下载最新版本，支持重试机制
        :param url: 最新版本的下载链接
        :param max_retries: 最大重试次数
        :return: 下载成功返回文件路径，失败返回False
        """
        # 创建临时目录用于存储下载的文件
        temp_dir = os.path.join(os.getcwd(), "temp")
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        
        # 从URL中提取文件名
        file_name = url.split("/")[-1]
        save_path = os.path.join(temp_dir, file_name)
        
        retry_count = 0
        while retry_count <= max_retries:
            try:
                print(f"开始下载最新版本，保存路径: {save_path} (尝试 {retry_count + 1}/{max_retries + 1})")
                
                # 发送HTTP请求，获取文件大小
                response = requests.get(url, stream=True, timeout=30, verify=False)
                response.raise_for_status()
                
                # 获取文件大小
                total_size = int(response.headers.get("content-length", 0))
                
                # 下载文件并显示进度
                with open(save_path, "wb") as f, tqdm(
                    desc=file_name,
                    total=total_size,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                ) as bar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            bar.update(len(chunk))
                
                print(f"下载完成: {save_path}")
                return save_path
            except requests.exceptions.HTTPError as e:
                # 特殊处理5xx服务器错误
                if e.response.status_code >= 500 and e.response.status_code < 600:
                    retry_count += 1
                    if retry_count <= max_retries:
                        wait_time = 2 ** retry_count  # 指数退避
                        print(f"服务器错误 ({e.response.status_code})，将在 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                        continue
                print(f"下载最新版本时出现HTTP错误: {e}")
                return False
            except requests.exceptions.RequestException as e:
                # 网络请求错误，尝试重试
                retry_count += 1
                if retry_count <= max_retries:
                    wait_time = 2 ** retry_count  # 指数退避
                    print(f"网络请求失败: {e}，将在 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    continue
                print(f"下载最新版本时出现网络错误: {e}")
                return False
            except Exception as e:
                print(f"下载最新版本时出现异常: {e}")
                return False
        return False

    @staticmethod
    def unzip(zip_path: str, extract_path: str):
        """
        解压最新版本文件
        :param zip_path: 压缩包路径
        :param extract_path: 解压路径
        :return: bool 是否成功解压
        """
        try:
            # 确保解压目录存在
            if not os.path.exists(extract_path):
                os.makedirs(extract_path)
            
            print(f"开始解压文件: {zip_path} 到 {extract_path}")
            
            # 解压文件
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 获取所有文件列表
                file_list = zip_ref.namelist()
                total_files = len(file_list)
                
                # 检查是否有共同的顶层目录
                top_level_dirs = set()
                for file_name in file_list:
                    # 只考虑包含目录的文件路径
                    if '/' in file_name or '\\' in file_name:
                        # 获取第一个目录
                        top_dir = file_name.split('/')[0] if '/' in file_name else file_name.split('\\')[0]
                        top_level_dirs.add(top_dir)
                
                # 如果只有一个顶层目录，且所有文件都在这个目录下
                if len(top_level_dirs) == 1:
                    top_dir = top_level_dirs.pop()
                    print(f"检测到zip文件包含单一顶层目录: {top_dir}，将直接解压内容到目标目录")
                    
                    # 解压并显示进度，去掉顶层目录
                    with tqdm(total=total_files, desc="解压进度") as bar:
                        for file in file_list:
                            # 构建目标文件路径，去掉顶层目录
                            if file.startswith(top_dir + '/'):
                                target_file = file[len(top_dir) + 1:]
                            elif file.startswith(top_dir + '\\'):
                                target_file = file[len(top_dir) + 1:]
                            else:
                                target_file = file  # 处理顶层目录本身
                            
                            if target_file:
                                # 获取完整的目标路径
                                target_path = os.path.join(extract_path, target_file)
                                
                                # 检查是否是目录条目（以/或\结尾）
                                if target_file.endswith('/') or target_file.endswith('\\'):
                                    # 如果是目录，只需要确保目录存在
                                    os.makedirs(target_path, exist_ok=True)
                                else:
                                    # 确保目标目录存在
                                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                                    # 解压文件到目标路径
                                    with open(target_path, 'wb') as f:
                                        f.write(zip_ref.read(file))
                            
                            bar.update(1)
                else:
                    # 正常解压
                    with tqdm(total=total_files, desc="解压进度") as bar:
                        for file in file_list:
                            zip_ref.extract(file, extract_path)
                            bar.update(1)
            
            print(f"解压完成: {extract_path}")
            return True
        except Exception as e:
            print(f"解压文件时出现异常: {e}")
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def install_new_version(extract_path: str, ignore_folder: list, ignore_files: list = None):
        """
        安装最新版本
        :param extract_path: 安装路径
        :param ignore_folder: 忽略的文件夹列表，保护更新时不覆盖的文件夹
        :param ignore_files: 忽略的文件列表，应该忽略用户的配置文件(json,yaml)结尾的配置文件和png,jpg,ico结尾的图片文件
        :return: None
        """
        try:
            # 确保忽略文件列表存在
            if ignore_files is None:
                ignore_files = []
            
            # 获取当前工作目录作为安装目标路径
            target_path = os.getcwd()
            print(f"开始安装最新版本，从 {extract_path} 到 {target_path}")
            
            # 遍历解压目录中的所有文件
            total_files = 0
            for root, dirs, files in os.walk(extract_path):
                # 过滤掉需要忽略的文件夹
                dirs[:] = [d for d in dirs if d not in ignore_folder]
                total_files += len(files)
            
            # 再次遍历并复制文件，显示进度
            copied_files = 0
            with tqdm(total=total_files, desc="安装进度") as bar:
                for root, dirs, files in os.walk(extract_path):
                    # 过滤掉需要忽略的文件夹
                    dirs[:] = [d for d in dirs if d not in ignore_folder]
                    
                    # 计算相对路径
                    rel_path = os.path.relpath(root, extract_path)
                    if rel_path == ".":
                        rel_path = ""
                    
                    # 确保目标目录存在
                    target_dir = os.path.join(target_path, rel_path)
                    if not os.path.exists(target_dir):
                        os.makedirs(target_dir)
                    
                    # 复制文件
                    for file in files:
                        # 检查是否需要忽略该文件
                        if file in ignore_files:
                            bar.update(1)
                            continue
                        
                        # 检查文件扩展名是否需要忽略
                        ext = os.path.splitext(file)[1].lower()
                        if ext in [".json", ".yaml", ".png", ".jpg", ".ico"]:
                            bar.update(1)
                            continue
                        
                        # 复制文件
                        src_file = os.path.join(root, file)
                        dst_file = os.path.join(target_dir, file)
                        
                        # 确保目标文件所在目录存在
                        os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                        
                        # 复制文件
                        with open(src_file, 'rb') as fsrc, open(dst_file, 'wb') as fdst:
                            fdst.write(fsrc.read())
                        
                        copied_files += 1
                        bar.update(1)
            
            print(f"安装完成，共复制 {copied_files} 个文件")
            print(f"请重新启动应用程序以应用更新")
        except Exception as e:
            print(f"安装最新版本时出现异常: {e}")



if __name__ == '__main__':
    update_manager = UpdateManager()
    # latest_version = update_manager.get_update()
    # if latest_version:
    #     # 将版本号转换为列表
    #     ignore_version: str = UpdateChecker.split_version(latest_version)
    #     # 忽略最新版本的更新
    #     update_manager.ignore_update(ignore_version)

    # 检查是否有更新
    # update_info = update_manager.get_update()
    # if update_info:
    #     print(f"发现新的版本: {update_info}")
    #     # 开始下载最新版本
    #     download_url = "https://github.com/RMA-MUN/OnmyojiAuto/releases/download/OAT-v1.5.5/OAT-v1.5.5.zip"
    #     if update_manager.download_new_version(download_url):
    #         # 解压最新版本文件
    #         zip_path = os.path.join(os.path.dirname(__file__), '../update/program/OAT-v1.5.5.zip')
    #         extract_path = os.path.join(os.path.dirname(__file__), '../update/program/OAT-v1.5.5')
    #         if update_manager.unzip(zip_path, extract_path):
    #             # 安装最新版本
    #             update_manager.install_new_version(extract_path, ignore_folder=['update'],
    #                                    ignore_files=['config.json', 'update.json'])

    # 从检查更新到下载最新压缩包都是可以使用的，现在修改为将解压文件放到temp/OAT_old目录
    zip_path = os.path.join(os.path.dirname(__file__), 'temp/OAT-v1.5.5.zip')
    extract_path = os.path.join(os.path.dirname(__file__), 'temp/OAT_old')
    if update_manager.unzip(zip_path, extract_path):
        # 安装最新版本，将解压后的文件从temp/OAT_old安装到当前工作目录
        update_manager.install_new_version(extract_path, ignore_folder=['update'],
                                       ignore_files=['config.json', 'update.json'])