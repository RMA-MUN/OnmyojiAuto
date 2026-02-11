"""
挑战完成后执行的操作模块
包含关闭程序和关闭游戏的功能
"""

import json
import sys
import os
import win32gui
import win32con
import time

def load_settings():
    """
    加载设置文件
    
    Returns:
        dict: 设置数据字典
    """
    # 获取settings.json文件的路径
    settings_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tools')
    settings_file_path = os.path.join(settings_dir, 'settings.json')
    
    try:
        with open(settings_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"警告：加载设置文件失败：{str(e)}")
        return {}


def close_game(window_hwnd: int) -> bool:
    """
    关闭指定句柄的游戏窗口
    
    Args:
        window_hwnd: 游戏窗口句柄
    
    Returns:
        bool: 是否成功关闭窗口
    """
    try:
        if window_hwnd:
            # 获取窗口标题用于日志输出
            window_title = win32gui.GetWindowText(window_hwnd)
            # 发送关闭消息
            win32gui.PostMessage(window_hwnd, win32con.WM_CLOSE, 0, 0)
            print(f"已发送关闭命令到窗口：{window_title} (句柄: {window_hwnd})")
            return True
        else:
            print("无效的窗口句柄")
            return False
    except Exception as e:
        print(f"关闭游戏窗口时发生错误：{str(e)}")
        return False


def close_multiple_games(window_hwnds: list[int]) -> bool:
    """
    关闭多个指定句柄的游戏窗口
    
    Args:
        window_hwnds: 游戏窗口句柄列表
    
    Returns:
        bool: 是否全部成功关闭
    """
    if not window_hwnds:
        print("没有提供窗口句柄列表")
        return False
    
    all_success = True
    for hwnd in window_hwnds:
        if not close_game(hwnd):
            all_success = False
    
    return all_success


def close_program() -> None:
    """
    关闭当前程序
    """
    try:
        print("程序将在5秒后关闭...")
        import time
        time.sleep(5)  # 延迟5秒，让用户看到消息
        sys.exit(0)
    except Exception as e:
        print(f"关闭程序时发生错误：{str(e)}")
        sys.exit(1)


def do_after_challenge(window_hwnds: list[int] | int, synchronizer=None, sync_mode: bool=False) -> None:
    """
    挑战完成后执行的操作
    根据设置决定是否关闭游戏或程序
    
    Args:
        window_hwnds: 游戏窗口句柄或句柄列表
        synchronizer: 同步器实例
        sync_mode: 是否启用同步模式
    """
    settings = load_settings()
    
    # 检查是否需要关闭游戏
    close_game_flag = settings.get('close_game_after_challenge', False)
    # 检查是否需要关闭程序
    close_program_flag = settings.get('close_program_after_challenge', False)
    
    if close_game_flag:
        # 收集所有需要关闭的窗口句柄
        windows_to_close = []
        
        # 处理同步模式
        if synchronizer and sync_mode and synchronizer.sync_enabled:
            # 关闭所有同步窗口
            print("正在关闭所有同步窗口...")
            
            # 添加主窗口
            if synchronizer.main_window:
                windows_to_close.append(synchronizer.main_window[0])
            
            # 添加所有副窗口
            for sub_hwnd, _ in synchronizer.get_sub_windows():
                windows_to_close.append(sub_hwnd)
        else:
            # 处理单个窗口或窗口列表
            if isinstance(window_hwnds, list):
                windows_to_close.extend(window_hwnds)
            else:
                windows_to_close.append(window_hwnds)
        
        # 去重，避免重复关闭同一个窗口
        unique_windows = list(set(windows_to_close))
        
        # 关闭所有窗口
        if unique_windows:
            close_multiple_games(unique_windows)
        
        # 如果同时需要关闭程序，等待游戏窗口关闭
        if close_program_flag:
            import time
            time.sleep(2)  # 等待2秒，让游戏窗口有时间处理关闭消息
    
    # 最后关闭程序（如果需要）
    if close_program_flag:
        close_program()