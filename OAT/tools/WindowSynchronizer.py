import win32gui
import win32con
import threading

from pynput import mouse
from typing import List, Tuple

from OAT.tools.WindowChecker import WindowChecker

class WindowSynchronizer:
    def __init__(self):
        self.windows = []
        self.main_window = None
        self.sub_windows = []
        self.lock = threading.Lock()
        self.shutdown_flag = False
        self.mouse_listener = None
        self.main_window_hwnd = None
        self.sub_window_hwnd = []
        self.sync_enabled = False

    def get_all_windows(self, window_titles: List[str]) -> List[Tuple[int, str]]:
        """
        获取所有相关窗口的句柄和标题
        """
        def enum_windows_callback(hwnd, window_list):
            window_text = win32gui.GetWindowText(hwnd)
            # 使用集合快速检查窗口是否已存在
            if hwnd in existing_windows:
                return True
            
            # 检查窗口是否匹配任何标题
            for title in window_titles:
                if title in window_text:
                    window_list.append((hwnd, window_text))
                    existing_windows.add(hwnd)
                    break
            return True

        self.windows = []
        existing_windows = set()  # 用于存储已添加的窗口句柄
        win32gui.EnumWindows(enum_windows_callback, self.windows)
        return self.windows

    def set_main_and_sub_windows(self, main_title: str, sub_titles: List[str], main_hwnd: int = None, sub_hwnds: List[int] = None) -> None:
        """
        设置主窗口和副窗口
        :param main_title: 主窗口标题
        :param sub_titles: 副窗口标题列表
        :param main_hwnd: 主窗口句柄，用于直接设置
        :param sub_hwnds: 副窗口句柄列表，用于直接设置
        """
        with self.lock:
            # 重置窗口列表
            self.main_window = None
            self.sub_windows = []

            if main_hwnd and sub_hwnds:
                # 如果提供了明确的窗口句柄，直接使用
                self.main_window = (main_hwnd, main_title)
                # print(f"【调试】：直接设置主窗口 hwnd={main_hwnd}, title={main_title}")
                
                for hwnd, title in zip(sub_hwnds, sub_titles):
                    if hwnd != main_hwnd:
                        self.sub_windows.append((hwnd, title))
                        # print(f"【调试】：直接添加副窗口 hwnd={hwnd}, title={title}")
                    else:
                        #  print(f"【调试】：跳过主窗口 hwnd={hwnd}, title={title}")
                        pass
            else:
                # 否则使用标题识别的方式
                # 获取所有相关窗口
                all_windows = self.get_all_windows([main_title] + sub_titles)

                # 识别主窗口
                for hwnd, title in all_windows:
                    print(f"【调试】：检查窗口 hwnd={hwnd}, title={title}")
                    if main_title in title:
                        self.main_window = (hwnd, title)
                        break

                # 识别副窗口
                for hwnd, title in all_windows:
                    print(f"【调试】：检查窗口 hwnd={hwnd}, title={title}")
                    # 确保不是主窗口，并且标题匹配副窗口标题
                    if self.main_window and hwnd != self.main_window[0]:
                        for sub_title in sub_titles:
                            if sub_title in title:
                                self.sub_windows.append((hwnd, title))
                                print(f"【调试】：添加副窗口 hwnd={hwnd}, title={title}")
                                break
                    elif self.main_window and hwnd == self.main_window[0]:
                        print(f"【调试】：跳过主窗口 hwnd={hwnd}, title={title}")
                    else:
                        print(f"【调试】：跳过窗口 hwnd={hwnd}, title={title}")

    def calc_the_position(self, main_window_title: str, sub_window_titles: List[str], screen_x: int, screen_y: int) -> List[Tuple[int, int]]:
        """
        计算出在主窗口内的相对位置，然后映射到副窗口中
        :param main_window_title: 主窗口标题
        :param sub_window_titles: 副窗口标题列表
        :param screen_x, screen_y: 屏幕上的点击坐标
        :return: 副窗口中的相对坐标列表
        """
        # 获取主窗口信息
        main_checker = WindowChecker()
        main_checker.set_window_title(main_window_title)
        main_window_info = main_checker.get_window_info()

        if not main_window_info:
            print(f"未找到标题为 {main_window_title} 的主窗口")
            return []

        main_left, main_top, main_right, main_bottom = main_window_info[0][0], main_window_info[0][1], main_window_info[1][0], main_window_info[1][1]
        main_width = main_right - main_left
        main_height = main_bottom - main_top

        # 计算主窗口内的相对位置
        main_relative_x = screen_x - main_left
        main_relative_y = screen_y - main_top

        # 检查相对位置是否在主窗口内
        if 0 <= main_relative_x <= main_width and 0 <= main_relative_y <= main_height:
            sub_relative_positions = []
            with self.lock:
                # 使用已识别的副窗口列表
                for hwnd, title in self.sub_windows:
                    sub_checker = WindowChecker()
                    sub_checker.set_window_handle(hwnd)  # 保持不变
                    sub_window_info = sub_checker.get_window_info()

                    if sub_window_info:
                        # 计算副窗口中的相对位置
                        sub_relative_positions.append((main_relative_x, main_relative_y))
                    else:
                        print(f"未找到句柄为 {hwnd} 的副窗口")
            return sub_relative_positions
        else:
            # print("点击位置不在主窗口内")
            return []

    def send_click_message(self, hwnd: int, relative_x: int, relative_y: int) -> None:
        """
        发送点击消息给指定窗口
        :param hwnd: 窗口句柄
        :param relative_x, relative_y: 相对坐标
        """
        # 将相对坐标转换为LPARAM格式
        l_param = relative_x | (relative_y << 16)
        # 发送鼠标移动过去的信息
        win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, l_param)
        # 发送鼠标左键按下消息
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, l_param)
        # 发送鼠标左键释放消息
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, l_param)
        # 输出点击信息
        # print(f"已发送点击消息给句柄 {hwnd}，相对坐标 ({relative_x}, {relative_y})")

    def send_click_message_to_all(self, relative_x: int, relative_y: int) -> None:
        """
        发送点击消息给所有副窗口
        :param relative_x, relative_y: 相对坐标
        """
        for hwnd, _ in self.sub_windows:
            self.send_click_message(hwnd, relative_x, relative_y)
            # 输出点击信息
            # print(f"已发送点击消息给句柄 {hwnd}，相对坐标 ({relative_x}, {relative_y})")

    def start_listening(self):
        """
        启动鼠标监听器
        """
        if not self.mouse_listener or not self.mouse_listener.is_alive():
            self.mouse_listener = mouse.Listener(on_click=self.where_click)
            self.mouse_listener.start()
            self.sync_enabled = True
            print("鼠标监听器已启动")

    def stop_listening(self):
        """
        停止鼠标监听器并释放资源
        """
        self.mouse_listener.stop()
        self.mouse_listener.join()
        self.mouse_listener = None
        # 停止所有和副窗口的通信
        self.sub_windows = []
        self.shutdown_flag = True
        self.sync_enabled = False
        print("鼠标监听器已停止")

    def set_true_enable(self):
        """设置同步启用"""
        self.sync_enabled = True

    def set_false_enable(self):
        """设置同步禁用"""
        self.sync_enabled = False


    def where_click(self, x, y, button, pressed):
        if pressed and button == mouse.Button.left:
            if self.main_window and self.sub_windows:
                # 从类属性中获取主窗口和副窗口标题
                main_window_title = self.main_window[1]
                sub_window_titles = [title for hwnd, title in self.sub_windows]

                # 计算相对位置
                relative_positions = self.calc_the_position(main_window_title, sub_window_titles, x, y)

                # 发送点击消息给所有副窗口
                if relative_positions:
                    for rel_x, rel_y in relative_positions:
                        self.send_click_message_to_all(rel_x, rel_y)
            # print(f"鼠标左键在坐标 ({x}, {y}) 处被按下")
        elif pressed and button == mouse.Button.right:
            pass
            # print(f"鼠标右键在坐标 ({x}, {y}) 处被按下")

    def arrange_windows(self, main_window_hwnd: int, sub_window_hwnd: List[int]):
        """
        通过句柄将窗口依次排列，然后再将主窗口激活至前台
        :param main_window_hwnd: 主窗口句柄
        :param sub_window_hwnd: 副窗口句柄列表
        后续可以考虑把窗口的排列位置和间隔根据窗口数目的多少进行自适应
        """
        print("窗口排序开始: ")
        # 获取窗口的数目
        sub_window_count = len(sub_window_hwnd)
        window_count = sub_window_count + 1

        x_position = 10
        y_position = 10
        # 根据窗口数量动态设置间隔（分区间定义不同间隔）
        # 窗口数量越少，间隔越大；数量越多，间隔越小（但不小于最小值）
        if window_count <= 3:
            wide_add = 100
            high_add = 80
        elif window_count <= 6:
            wide_add = 80
            high_add = 60
        elif window_count <= 10:
            wide_add = 60
            high_add = 40
        else:
            wide_add = 40
            high_add = 20

        for hwnd in sub_window_hwnd:
            if not win32gui.IsWindow(hwnd):
                continue
            result = win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, x_position, y_position, 0, 0, win32con.SWP_NOSIZE)
            win32gui.SetForegroundWindow(hwnd)
            print(f"设置副窗口位置成功: HWND={hwnd}, x={x_position}, y={y_position}")
            if not result:
                print(f"设置窗口位置失败: HWND={hwnd}")
            x_position += wide_add
            y_position += high_add

        if win32gui.IsWindow(main_window_hwnd):
            win32gui.SetWindowPos(main_window_hwnd, win32con.HWND_TOP, x_position, y_position, 0, 0, win32con.SWP_NOSIZE)
            win32gui.SetForegroundWindow(main_window_hwnd)
            print(f"设置主窗口位置成功: HWND={main_window_hwnd}, x={x_position}, y={y_position}")
        else:
            print(f"主窗口句柄无效: HWND={main_window_hwnd}")

        print("窗口排序结束")

    def get_sub_windows(self) -> List[Tuple[int, str]]:
        """
        返回所有副窗口列表
        """
        return self.sub_windows