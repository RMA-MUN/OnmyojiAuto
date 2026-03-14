import yaml
import json
import os

class ConfigReader:
    def __init__(self, file_path: str):
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
                # 根据文件扩展名选择合适的解析方式
                if self.file_path.endswith('.yaml') or self.file_path.endswith('.yml'):
                    return yaml.safe_load(f)
                elif self.file_path.endswith('.json'):
                    return json.load(f)
                else:
                    # 默认使用yaml解析
                    return yaml.safe_load(f)
        except Exception:
            return None

    def write_config(self, config_data):
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                # 根据文件扩展名选择合适的写入方式
                if self.file_path.endswith('.yaml') or self.file_path.endswith('.yml'):
                    yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
                elif self.file_path.endswith('.json'):
                    json.dump(config_data, f, ensure_ascii=False, indent=2)
                else:
                    # 默认使用yaml写入
                    yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
            return True
        except Exception:
            return False
