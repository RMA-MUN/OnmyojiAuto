from typing import Optional
import json

def mode_config(path) -> Optional[dict]:
    """读取当前目录下的json文件，获取其中的模式配置并返回"""

    try:
        with open(path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            print(f"已成功读取到模式配置文件: {path}")
            return config
    except FileNotFoundError:
        print(f"文件未找到: {path}")
        return None
    except json.JSONDecodeError:
        print(f"JSON解析错误: {path}")
        return None

def mode_choice(path) -> Optional[list]:
    """读取json文件，然后返回每个模式的名称"""
    config = mode_config(path)
    if config:
        return list(config.keys())
    return None

if __name__ == '__main__':
    config = mode_config('mode.json')
