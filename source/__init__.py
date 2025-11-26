import os
from functools import lru_cache
from typing import Optional

# 定义模式和对应文件夹名的映射字典（保持原有结构）
MODE_MAPPING = {
    '魂土': {
        'default': 'huntu',
        '队长': 'huntu',
        '队员': 'huntu_double'
    },
    '魂王': {
        'default': 'hunwang_double',
        '队长': 'hunwang_double',
        '队员': 'hunwang_double'
    },
    '业原火': 'yeyuanhuo',
    '觉醒': 'juexing',
    '爬塔': {
        'default': 'pata',
        '门票': 'pata',
        '体力': 'pata_tili',
    },
    '灵染试炼': 'lingran',
    '御灵': 'yuling',
    '契灵探查': 'qilingtancha'
}

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
        raise FileNotFoundError(f"脚本目录不存在: {script_dir}")

    return script_dir

# 优化后的模式选择函数
def mode_choice(mode, sub_mode, times, config, window_title, hidden_window=False):
    try:
        # 调用缓存函数获取路径
        script_dir = get_script_dir(mode, sub_mode)
    except ValueError as e:
        print(f"模式配置错误: {e}")
        print('暂不支持此模式，敬请期待！')
        return
    except FileNotFoundError as e:
        print(f"路径错误: {e}")
        return

    # 执行通用挑战函数（保持原有逻辑）
    from .common_challenge import common_challenge
    common_challenge(times, config, script_dir, window_title, hidden_window)