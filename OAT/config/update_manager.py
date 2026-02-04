from OAT.config.check_update import UpdateChecker
from OAT.tools.config_manager import ConfigReader
import os
import zipfile
import requests
from tqdm import tqdm

class UpdateManager:
    """更新管理器，负责对更新相关操作(忽略更新，立即更新)"""

    checker: UpdateChecker = UpdateChecker() # 更新检查器

    def __init__(self):
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

    def download_new_version(self, url: str):
        """
        下载最新版本
        :param url: 最新版本的下载链接
        :return: bool 是否成功下载
        """
        try:
            # 创建临时目录用于存储下载的文件
            temp_dir = os.path.join(os.getcwd(), "temp")
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            
            # 从URL中提取文件名
            file_name = url.split("/")[-1]
            save_path = os.path.join(temp_dir, file_name)
            
            print(f"开始下载最新版本，保存路径: {save_path}")
            
            # 发送HTTP请求，获取文件大小
            response = requests.get(url, stream=True, timeout=30)
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
        except Exception as e:
            print(f"下载最新版本时出现异常: {e}")
            return False

    def unzip(self, zip_path: str, extract_path: str):
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
                
                # 解压并显示进度
                with tqdm(total=total_files, desc="解压进度") as bar:
                    for file in file_list:
                        zip_ref.extract(file, extract_path)
                        bar.update(1)
            
            print(f"解压完成: {extract_path}")
            return True
        except Exception as e:
            print(f"解压文件时出现异常: {e}")
            return False

    def install_new_version(self, extract_path: str, ignore_folder: list, ignore_files: list = None):
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

    # 安装最新版本
    update_manager.install_new_version(extract_path=os.path.join(os.path.dirname(__file__), '../update/program/OAT-v1.5.5'),
                                       ignore_folder=['update'],
                                       ignore_files=['config.json', 'update.json'])
