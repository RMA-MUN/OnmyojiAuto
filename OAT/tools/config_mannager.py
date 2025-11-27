import yaml
import os

class ConfigReader:
    def __init__(self, file_path):
        # 如果是相对路径，相对于Onmyoji目录解析
        if not os.path.isabs(file_path):
            # 获取Onmyoji目录的绝对路径
            onmyoji_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.file_path = os.path.join(onmyoji_dir, file_path)
        else:
            self.file_path = file_path

    def read_config(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                print(f"已成功读取配置文件: {self.file_path}")
                return yaml.safe_load(f)
        except Exception as e:
            error_msg = f"读取配置文件 {self.file_path} 时出现异常: {e}"
            print(error_msg)
            return None