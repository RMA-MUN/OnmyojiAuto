APP_VERSION = "2.0.1"

import json
import os

# 加载设置配置
current_dir = os.path.dirname(os.path.abspath(__file__))
settings_file_path = os.path.join(current_dir, 'settings.json')

# 读取配置文件
try:
    with open(settings_file_path, 'r', encoding='utf-8') as f:
        settings_data = json.load(f)
except Exception as e:
    print(f"加载配置文件失败: {str(e)}")
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
        'windows_per_row': 3  # 平铺排列时一行的窗口数量
    }

# 导出配置变量
FIND_MODE = settings_data.get('find_mode', 'opencv')
FIND_THRESHOLD = settings_data.get('find_value', 85)
FIND_THRESHOLD_VALUE = FIND_THRESHOLD / 100.0  # 转换为0-1之间的值

# 其他配置变量
THEME = settings_data.get('theme', 'light')
TRANSPARENCY = settings_data.get('transparency', 50)
CLOSE_PROGRAM_AFTER_CHALLENGE = settings_data.get('close_program_after_challenge', False)
CLOSE_GAME_AFTER_CHALLENGE = settings_data.get('close_game_after_challenge', False)
SYNC_MODE = settings_data.get('sync_mode', 'exactly_sync')
CUSTOM_RES_WIDTH = settings_data.get('custom_res_width', 1404)
CUSTOM_RES_HEIGHT = settings_data.get('custom_res_height', 834)
# 窗口排列相关设置
WINDOW_ARRANGE_MODE = settings_data.get('window_arrange_mode', 'diagonal')  # 窗口排列方式
WINDOWS_PER_ROW = settings_data.get('windows_per_row', 3)  # 平铺排列时一行的窗口数量

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
        elif key == 'theme':
            global THEME
            THEME = value
        elif key == 'transparency':
            global TRANSPARENCY
            TRANSPARENCY = value
        elif key == 'close_program_after_challenge':
            global CLOSE_PROGRAM_AFTER_CHALLENGE
            CLOSE_PROGRAM_AFTER_CHALLENGE = value
        elif key == 'close_game_after_challenge':
            global CLOSE_GAME_AFTER_CHALLENGE
            CLOSE_GAME_AFTER_CHALLENGE = value
        elif key == 'sync_mode':
            global SYNC_MODE
            SYNC_MODE = value
        elif key == 'custom_res_width':
            global CUSTOM_RES_WIDTH
            CUSTOM_RES_WIDTH = value
        elif key == 'custom_res_height':
            global CUSTOM_RES_HEIGHT
            CUSTOM_RES_HEIGHT = value
        elif key == 'window_arrange_mode':
            global WINDOW_ARRANGE_MODE
            WINDOW_ARRANGE_MODE = value
        elif key == 'windows_per_row':
            global WINDOWS_PER_ROW
            WINDOWS_PER_ROW = value
        return True
    except Exception as e:
        print(f"保存配置文件失败: {str(e)}")
        return False

