import yaml
import json
import os
from OAT.utils.error_box import error_box
from OAT.utils.error_handler import log_error
from OAT.utils.logging import logger


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
                logger.info(f"已成功读取配置文件: {self.file_path}")
                # 根据文件扩展名选择合适的解析方式
                if self.file_path.endswith('.yaml') or self.file_path.endswith('.yml'):
                    return yaml.safe_load(f)
                elif self.file_path.endswith('.json'):
                    return json.load(f)
                else:
                    # 默认使用yaml解析
                    return yaml.safe_load(f)
        except Exception as e:
            error_msg = f"读取配置文件 {self.file_path} 时出现异常: {e}"
            # 使用错误级别记录日志
            from OAT.utils.logging import LogRedirect
            log_redirect = LogRedirect(None)
            log_redirect.error(error_msg)
            # 使用error_box显示错误弹窗
            error_box(error_msg)
            # 写入日志文件
            log_error(error_msg)
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
            logger.info(f"已成功写入配置文件: {self.file_path}")
            return True
        except Exception as e:
            error_msg = f"写入配置文件 {self.file_path} 时出现异常: {e}"
            # 使用错误级别记录日志
            from OAT.utils.logging import LogRedirect
            log_redirect = LogRedirect(None)
            log_redirect.error(error_msg)
            # 使用error_box显示错误弹窗
            error_box(error_msg)
            # 写入日志文件
            log_error(error_msg)
            return False
