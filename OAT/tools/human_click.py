"""前台鼠标点击共享原语（从 OnmyojiAutomation 提取，行为逐字一致）

OAT/tools/OnmyojiAuto.py 的前台点击链（_complex_move 人性化移动 +
_win32_double_click）与 OAT/pipeline/recognition_opencv.py 的前台分支
共享同一实现，避免两处各自维护一套鼠标移动/点击逻辑。
"""
import time

import pyautogui
import win32api
import win32con


def human_like_move(target_x: int, target_y: int) -> None:
    """
    核心方法：实现模拟人为的鼠标移动
    :param target_x: 目标X坐标（屏幕绝对坐标）
    :param target_y: 目标Y坐标（屏幕绝对坐标）
    """
    try:
        # 获取当前鼠标位置
        start_x, start_y = pyautogui.position()

        # 如果已经在目标位置，直接返回
        if abs(start_x - target_x) < 5 and abs(start_y - target_y) < 5:
            return

        pyautogui.moveTo(target_x, target_y, duration=0.3)

        # 最后确保精确到达目标位置
        win32api.SetCursorPos((target_x, target_y))
    except Exception:
        pass


def complex_move(target_x: int, target_y: int, lock=None) -> None:
    """
    :param target_x: 目标X坐标
    :param target_y: 目标Y坐标
    :param lock: 可选的线程锁；提供时回退路径在其保护下执行
    """
    try:
        human_like_move(target_x, target_y)
    except Exception:
        if lock is not None:
            with lock:
                try:
                    win32api.SetCursorPos((target_x, target_y))
                except Exception:
                    pyautogui.moveTo(target_x, target_y, duration=0.2)
        else:
            try:
                win32api.SetCursorPos((target_x, target_y))
            except Exception:
                pyautogui.moveTo(target_x, target_y, duration=0.2)


def win32_double_click() -> None:
    """优化的双击操作，减少延迟"""
    # 组合鼠标事件，减少系统调用
    flags = win32con.MOUSEEVENTF_LEFTDOWN | win32con.MOUSEEVENTF_LEFTUP
    win32api.mouse_event(flags, 0, 0, 0, 0)
    # 更短的双击间隔
    time.sleep(0.03)
    win32api.mouse_event(flags, 0, 0, 0, 0)


def foreground_click(target_x: int, target_y: int, lock=None) -> None:
    """前台点击：人性化移动 + win32 双击（屏幕绝对坐标）"""
    complex_move(target_x, target_y, lock)
    win32_double_click()


def human_drag(x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> None:
    """前台拖拽：移动到起点 → 按下 → 拖到终点 → 抬起（屏幕绝对坐标）"""
    try:
        try:
            hold = max(0.0, float(duration))
        except (ValueError, TypeError):
            hold = 0.5
        complex_move(int(x1), int(y1))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        pyautogui.moveTo(int(x2), int(y2), duration=hold)
        win32api.SetCursorPos((int(x2), int(y2)))
        time.sleep(0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    except Exception:
        pass
