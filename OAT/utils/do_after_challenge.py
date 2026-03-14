"""
挑战完成后执行的操作模块
包含关闭程序和关闭游戏的功能
"""

import json
import os
import signal
import sys
import threading
import time
import win32api
import win32con
import win32gui
from OAT.utils.warning_box import warning_box
from OAT.utils.error_handler import log_error

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
        error_msg = f"警告：加载设置文件失败：{str(e)}"
        # 使用warning_box显示错误信息
        warning_box(error_msg)
        # 写入日志文件
        log_error(error_msg)
        return {}


def close_game(window_hwnd: int) -> bool:
    """
    关闭指定句柄的游戏窗口
    处理关闭时可能出现的确认弹窗
    """
    try:
        if window_hwnd:
            # 获取窗口标题用于日志输出
            window_title = win32gui.GetWindowText(window_hwnd)
            # 发送关闭消息
            win32gui.PostMessage(window_hwnd, win32con.WM_CLOSE, 0, 0)
            print(f"已发送关闭命令到窗口：{window_title} (句柄: {window_hwnd})")

            # 等待一下，让窗口有时间处理关闭消息
            time.sleep(5)

            # 检查是否有确认弹窗
            confirm_title = "退出游戏"
            confirm_hwnd = win32gui.FindWindow(None, confirm_title)  # 尝试查找顶层确认窗口
            
            # 如果顶层查找失败，再尝试作为子窗口查找
            if not confirm_hwnd:
                confirm_hwnd = win32gui.FindWindowEx(window_hwnd, 0, None, confirm_title)
            
            if confirm_hwnd:
                confirm_window_title = win32gui.GetWindowText(confirm_hwnd)
                print(f"检测到确认弹窗：{confirm_window_title} (句柄: {confirm_hwnd})")
                print(f"发送确认关闭命令到窗口：{confirm_title}")
                
                # 1. 确保确认弹窗获得焦点
                try:
                    # 先将模拟器窗口置前
                    win32gui.SetForegroundWindow(window_hwnd)
                    time.sleep(0.5)
                    # 再将确认弹窗置前
                    win32gui.SetForegroundWindow(confirm_hwnd)
                    time.sleep(0.5)
                    print("已激活确认弹窗")
                except Exception as e:
                    print(f"激活确认弹窗时发生错误：{str(e)}")
                
                # 2. 尝试多种方式确认，增加成功率
                success = False
                retry_count = 3
                
                for attempt in range(retry_count):
                    print(f"第{attempt+1}/{retry_count}次尝试确认关闭")
                    
                    try:
                        # 方式1：发送完整的回车键消息（包含必要的参数）
                        # WM_KEYDOWN参数：(vk, scanCode, flags, time)
                        # WM_KEYUP参数：(vk, scanCode, flags, time)
                        scan_code = win32api.MapVirtualKey(win32con.VK_RETURN, 0)
                        lParam_down = (scan_code << 16) | 1  # 0x00000001表示按键按下
                        lParam_up = (scan_code << 16) | 0xC0000001  # 释放按键标记
                        
                        win32gui.SendMessage(confirm_hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, lParam_down)
                        time.sleep(0.1)
                        win32gui.SendMessage(confirm_hwnd, win32con.WM_KEYUP, win32con.VK_RETURN, lParam_up)

                        time.sleep(1)
                        
                        # 检查窗口是否还存在
                        if not win32gui.IsWindow(confirm_hwnd):
                            print("确认弹窗已关闭，操作成功")
                            success = True
                            break
                            
                    except Exception as e:
                        print(f"方式1（完整回车键）失败：{str(e)}")

                    
                    # 方式2：尝试查找确认按钮并点击
                    try:
                        print("尝试查找并点击确认按钮")
                        # 查找确认按钮（可能需要根据实际情况调整类名或标题）
                        # 先尝试作为子窗口查找按钮
                        confirm_btn_hwnd = win32gui.FindWindowEx(confirm_hwnd, 0, "Button", "确定")
                        if not confirm_btn_hwnd:
                            confirm_btn_hwnd = win32gui.FindWindowEx(confirm_hwnd, 0, "Button", "确认")
                        
                        if confirm_btn_hwnd:
                            print(f"找到确认按钮，句柄：{confirm_btn_hwnd}")
                            # 发送点击消息
                            win32gui.SendMessage(confirm_btn_hwnd, win32con.BM_CLICK, 0, 0)
                            time.sleep(1)
                            
                            if not win32gui.IsWindow(confirm_hwnd):
                                print("确认弹窗已关闭，操作成功")
                                success = True
                                break
                                
                    except Exception as e:
                        print(f"方式2（点击确认按钮）失败：{str(e)}")
                    
                    # 如果所有方式都失败，等待后重试
                    if attempt < retry_count - 1:
                        time.sleep(2)
                
                if not success:
                    print("警告：所有确认关闭尝试都失败了！")
                else:
                    print("确认关闭操作成功")

            return True
        else:
            print("无效的窗口句柄")
            return False
    except Exception as e:
        print(f"关闭游戏窗口时发生错误：{str(e)}")
        import traceback
        traceback.print_exc()
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
    实现与mainGui中emergency_stop相同的功能
    """
    try:
        print("程序将在5秒后关闭...")
        import time
        time.sleep(5)  # 延迟5秒，让用户看到消息
        
        print("正在终止所有进程...")

        try:
            # 获取当前进程的所有线程
            threads = threading.enumerate()
            print(f"当前活动线程数: {len(threads)}")
            
            # 终止PyQt应用程序
            try:
                from PyQt6 import QtWidgets
                app = QtWidgets.QApplication.instance()
                if app:
                    # 立即退出PyQt应用程序，不等待线程
                    app.exit(0)
                    return
            except (ImportError, NameError):
                pass

            print("直接终止进程")
            os.kill(os.getpid(), signal.SIGTERM)
            
        except Exception as thread_e:
            print(f"终止线程时发生错误：{str(thread_e)}")
            # 如果还是不行，就直接退出
            sys.exit(0)
    except Exception as e:
        print(f"关闭程序时发生错误：{str(e)}")
        # 确保在内部try-except块中处理所有QtWidgets相关操作
        try:
            from PyQt6 import QtWidgets
            # 只在导入成功后使用QtWidgets
            app = QtWidgets.QApplication.instance()
            if app:
                app.exit(1)
                return
        except (ImportError, NameError):
            # 捕获ImportError和可能的NameError
            pass
        sys.exit(1)


def do_after_challenge(window_hwnds: list[int] | int, synchronizer=None, is_sync: bool = False) -> None:
    """
    挑战完成后执行的操作
    根据设置决定是否关闭游戏或程序

    Args:
        window_hwnds: 游戏窗口句柄或句柄列表
        synchronizer: 同步器实例
        is_sync: 是否启用同步模式
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
        if synchronizer and is_sync and synchronizer.sync_enabled:
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