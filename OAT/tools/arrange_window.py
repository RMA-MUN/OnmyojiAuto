import win32gui
import win32con
import pygetwindow as gw

def is_window_visible(hwnd):
    """检查窗口是否可见"""
    return win32gui.IsWindowVisible(hwnd) and hwnd != win32gui.GetDesktopWindow()

def get_window_rect(hwnd):
    """获取窗口的位置和大小"""
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bottom - top
    return left, top, width, height

def get_all_visible_windows():
    """获取所有可见窗口的句柄和标题"""
    windows = []

    def callback(hwnd, extra):
        if is_window_visible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and ("MuMu" in title or "阴阳师" in title or "模拟器"):
                _, _, width, height = get_window_rect(hwnd)
                if width > 100 and height > 100: # 过滤掉过小的窗口，防止将工具窗口也包含进来
                    if (hwnd, title, width, height) not in windows: # 过滤重复窗口
                        windows.append((hwnd, title, width, height))

    win32gui.EnumWindows(callback, None)
    return windows

def arrange_windows_diagonally_fixed_size():
    """按对角线排列所有可见窗口，保持窗口原有大小"""
    # 获取屏幕分辨率
    screen_width = gw.getScreenDimensions()[0]
    screen_height = gw.getScreenDimensions()[1]

    # 获取所有可见窗口
    windows = get_all_visible_windows()
    if not windows:
        print("没有找到可见窗口")
        return

    num_windows = len(windows)
    if num_windows == 1:
        # 只有一个窗口时最大化
        hwnd, title, _, _ = windows[0]
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        print(f"已最大化窗口: {title}")
        return

    # 计算对角线步长（基于屏幕大小和窗口数量）
    step_x = (screen_width - 500) / (num_windows - 1) if num_windows > 1 else 0
    step_y = (screen_height - 400) / (num_windows - 1) if num_windows > 1 else 0

    # 排列窗口
    for i, (hwnd, title, width, height) in enumerate(windows):
        # 计算窗口位置（确保窗口不会超出屏幕）
        x = int(i * step_x)
        y = int(i * step_y)

        # 确保窗口不会超出屏幕右侧
        if x + width > screen_width:
            x = screen_width - width

        # 确保窗口不会超出屏幕底部
        if y + height > screen_height:
            y = screen_height - height

        # 只调整窗口位置，不改变大小
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOP,
            x, y,
            0, 0,  # 宽度和高度设为0表示保持原有大小
            win32con.SWP_NOSIZE | win32con.SWP_NOZORDER | win32con.SWP_SHOWWINDOW
        )
        print(f"已排列窗口: {title} 位置: ({x}, {y}) 大小: ({width}, {height})")


