import os
from functools import lru_cache
from typing import Optional

from OAT.source.mode_config import mode_config

# 获取当前文件所在目录
current_dir = os.path.dirname(__file__)
# 构建mode.json的绝对路径
mode_json_path = os.path.join(current_dir, 'mode.json')

# 从模式配置文件里加载到MODE_MAPPING
MODE_MAPPING = mode_config(mode_json_path)

__all__ = ['mode_choice']

# 带缓存的路径获取函数
@lru_cache(maxsize=20)
def get_script_dir(mode: str, sub_mode: Optional[str] = None) -> str:
    """根据模式和子模式获取脚本目录（带缓存）"""
    folder_info = MODE_MAPPING.get(mode)
    if not folder_info:
        raise ValueError(f"不支持的模式: {mode}")

    if isinstance(folder_info, dict):
        folder_name = folder_info.get(sub_mode, folder_info['default'])
        if not folder_name:
            raise ValueError(f"模式 {mode} 下无有效子模式配置: {sub_mode}")
    else:
        folder_name = folder_info

    script_dir = os.path.join(os.path.dirname(__file__), folder_name)
    if not os.path.exists(script_dir):
        raise FileNotFoundError(f"目录不存在: {script_dir}")

    return script_dir

# 模式选择函数
def mode_choice(mode, sub_mode, times, config, window_title, hidden_window=False):
    try:
        # 调用缓存函数获取路径
        script_dir = get_script_dir(mode, sub_mode)
    except ValueError as e:
        print(f"模式配置错误: {e}")
        print('请检查是否正确选择了模式或配置文件！')
        return
    except FileNotFoundError as e:
        print(f"路径错误: {e}")
        return

    # 执行通用挑战函数
    from .common_challenge import common_challenge
    common_challenge(times, config, script_dir, window_title, hidden_window)