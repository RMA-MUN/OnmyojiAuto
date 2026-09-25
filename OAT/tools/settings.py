APP_VERSION = "2.3.2"

import json
import os
from typing import Optional

# 加载设置配置
current_dir = os.path.dirname(os.path.abspath(__file__))
settings_file_path = os.path.join(current_dir, 'settings.json')
from ..utils.logging import logger

# 读取配置文件
try:
    with open(settings_file_path, 'r', encoding='utf-8') as f:
        settings_data = json.load(f)
except Exception as e:
    logger.error(f"加载配置文件失败: {str(e)}")
    # 使用默认配置
    settings_data = {
        'theme': 'light',
        'transparency': 50,
        'close_program_after_challenge': False,
        'close_game_after_challenge': False,
        'sync_mode': 'exactly_sync',
        'find_value': 85,
        'find_mode': 'opencv',
        'custom_res_width': 1404,
        'custom_res_height': 834,
        'window_arrange_mode': 'diagonal',  # 窗口排列方式：diagonal（对角线）或 tile（平铺）
        'windows_per_row': 3,  # 平铺排列时一行的窗口数量
        'capture_window_mode': 'PrintWindow'  # 窗口捕获模式(PrintWindow/BitBlt)
    }

# 导出配置变量
FIND_MODE = settings_data.get('find_mode', 'opencv')
FIND_THRESHOLD = settings_data.get('find_value', 85)
FIND_THRESHOLD_VALUE = FIND_THRESHOLD / 100.0  # 转换为0-1之间的值

# 其他配置变量
# 窗口排列相关设置
WINDOW_ARRANGE_MODE = settings_data.get('window_arrange_mode', 'diagonal')  # 窗口排列方式
WINDOWS_PER_ROW = settings_data.get('windows_per_row', 3)  # 平铺排列时一行的窗口数量
# 后台获取图像模式
BACKEND_GET_IMG_MODE = settings_data.get('capture_window_mode', 'PrintWindow')  # 后台获取图像模式(PrintWindow/BitBlt)
# 模拟器后台模式（MuMu 免 ADB）
EMULATOR_TYPE = settings_data.get('emulator_type', 'pc')
HANDLE_SPEC = settings_data.get('handle_spec', 'auto')
SCREENSHOT_METHOD = settings_data.get('screenshot_method', 'nemu_ipc')
CONTROL_METHOD = settings_data.get('control_method', 'window_message')
DEFAULT_MUMU_FOLDER = 'E:\\MuMuPlayer'
MUMU_FOLDER = settings_data.get('mumu_folder', DEFAULT_MUMU_FOLDER)

# 提供更新配置的函数
def update_settings(key, value):
    """
    更新配置并保存到文件
    
    Args:
        key: 配置键名
        value: 配置值
    """
    settings_data[key] = value
    try:
        with open(settings_file_path, 'w', encoding='utf-8') as f:
            json.dump(settings_data, f, ensure_ascii=False, indent=2)
        # 更新导出的变量
        if key == 'find_mode':
            global FIND_MODE
            FIND_MODE = value
        elif key == 'find_value':
            global FIND_THRESHOLD, FIND_THRESHOLD_VALUE
            FIND_THRESHOLD = value
            FIND_THRESHOLD_VALUE = value / 100.0
        elif key == 'window_arrange_mode':
            global WINDOW_ARRANGE_MODE
            WINDOW_ARRANGE_MODE = value
        elif key == 'windows_per_row':
            global WINDOWS_PER_ROW
            WINDOWS_PER_ROW = value
        elif key == 'capture_window_mode':
            global BACKEND_GET_IMG_MODE
            BACKEND_GET_IMG_MODE = value
        elif key == 'emulator_type':
            global EMULATOR_TYPE
            EMULATOR_TYPE = value
        elif key == 'handle_spec':
            global HANDLE_SPEC
            HANDLE_SPEC = value
        elif key == 'screenshot_method':
            global SCREENSHOT_METHOD
            SCREENSHOT_METHOD = value
        elif key == 'control_method':
            global CONTROL_METHOD
            CONTROL_METHOD = value
        elif key == 'mumu_folder':
            global MUMU_FOLDER
            MUMU_FOLDER = value
        return True
    except Exception as e:
        logger.error(f"保存配置文件失败: {str(e)}")
        return False


def _is_valid_mumu_folder(folder) -> bool:
    """配置目录是否为有效 MuMu 根（惰性导入避免启动加载 win32/psutil）。"""
    try:
        from OAT.tools.emulator.mumu_handle import is_mumu_root
        return is_mumu_root(folder)
    except Exception:
        return False


def _detect_mumu_folder_safe() -> Optional[str]:
    """进程反推 MuMu 安装目录；任何异常按未找到处理。"""
    try:
        from OAT.tools.emulator.mumu_handle import detect_mumu_folder
        return detect_mumu_folder()
    except Exception:
        return None


def resolve_mumu_folder() -> str:
    """生效的 MuMu 安装目录：配置有效→配置；否则进程反推并回写；再失败→默认。"""
    if _is_valid_mumu_folder(MUMU_FOLDER):
        return MUMU_FOLDER
    try:
        detected = _detect_mumu_folder_safe()
    except Exception:
        detected = None
    if detected:
        update_settings('mumu_folder', detected)
        return detected
    return MUMU_FOLDER or DEFAULT_MUMU_FOLDER

