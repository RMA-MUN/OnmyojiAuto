import win32gui
import win32con
import win32api
import ctypes
import threading
import inspect
import time
from pynput import mouse, keyboard
from typing import List, Tuple, Optional
from OAT.tools.WindowChecker import WindowChecker
from OAT.tools.settings import CUSTOM_RES_WIDTH, CUSTOM_RES_HEIGHT, WINDOW_ARRANGE_MODE, WINDOWS_PER_ROW
from OAT.utils.logging import logger


class WindowSynchronizer:
    def __init__(self, sync_mode: str = "exactly_sync"):
        self.windows = []
        self.main_window = None
        self.sub_windows = []
        self.lock = threading.Lock()
        self.shutdown_flag = False
        self.mouse_listener = None
        self.main_window_hwnd = None
        self.sub_window_hwnd = []
        self.sync_enabled = False
        # 同步模式：exactly_sync（完全同步）、program_sync（程序同步）、input_sync（键鼠同步）
        self.sync_mode = sync_mode
        # 管道任务同步：记录 PipelineRunner 当前正在执行的任务名
        self.pipeline_task_name: Optional[str] = None

        # 键盘监听器相关属性
        self.keyboard_listener = None  # 键盘监听器实例
        self.keyboard_listener_thread = None  # 键盘监听器线程
        
        # 窗口信息缓存，减少重复计算
        self.window_info_cache = {}  # 格式: {hwnd: (timestamp, window_info)}
        self.cache_timeout = 1.0  # 缓存超时时间（秒）
        
        # 鼠标状态跟踪
        self.mouse_pressed = False  # 跟踪鼠标左键是否按下
        self.last_mouse_pos = (0, 0)  # 上次鼠标位置，用于移动事件

    def get_all_windows(self, window_titles: List[str]) -> List[Tuple[int, int]]:
        """
        获取所有相关窗口的句柄和标题
        """
        def enum_windows_callback(hwnd: int, window_list: List[Tuple[int, str]]):
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
        
    def get_window_client_info(self, hwnd: int) -> Optional[Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int]]]:
        """
        获取窗口客户区域信息，使用缓存减少重复计算
        :param hwnd: 窗口句柄
        :return: 窗口客户区域信息，如果获取失败返回None
        """
        current_time = time.time()
        
        # 检查缓存是否有效
        if hwnd in self.window_info_cache:
            timestamp, cached_info = self.window_info_cache[hwnd]
            if current_time - timestamp < self.cache_timeout:
                return cached_info
        
        # 缓存无效，重新获取窗口信息
        checker = WindowChecker()
        checker.set_window_handle(hwnd)
        client_info = checker.get_client_info()
        
        # 更新缓存
        if client_info:
            self.window_info_cache[hwnd] = (current_time, client_info)
        
        return client_info
        
    def clear_window_info_cache(self):
        """
        清除窗口信息缓存
        """
        self.window_info_cache.clear()

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
                # 如果提供了窗口句柄，直接使用
                self.main_window = (main_hwnd, main_title)

                for hwnd, title in zip(sub_hwnds, sub_titles):
                    if hwnd != main_hwnd:
                        self.sub_windows.append((hwnd, title))
            else:
                # 否则使用标题识别的方式
                # 获取所有相关窗口
                all_windows = self.get_all_windows([main_title] + sub_titles)

                # 识别主窗口
                for hwnd, title in all_windows:
                    if main_title in title:
                        self.main_window = (hwnd, title)
                        break

                # 识别副窗口
                for hwnd, title in all_windows:
                    # 确保不是主窗口，并且标题匹配副窗口标题
                    if self.main_window and hwnd != self.main_window[0]:
                        for sub_title in sub_titles:
                            if sub_title in title:
                                self.sub_windows.append((hwnd, title))
                                break
                    else:
                        pass
    def calc_the_position(self, main_window_title: str, sub_window_titles: List[str], screen_x: int, screen_y: int) -> List[Tuple[int, int]]:
        """
        计算出在主窗口内的相对位置，然后映射到副窗口中
        :param main_window_title: 主窗口标题
        :param sub_window_titles: 副窗口标题列表
        :param screen_x, screen_y: 屏幕上的点击坐标
        :return: 副窗口中的相对坐标列表
        """
        try:
            # 验证输入参数
            if not main_window_title:
                logger.error("主窗口标题不能为空")
                return []

            if screen_x < 0 or screen_y < 0:
                logger.error("屏幕坐标不能为负数")
                return []
            
            # 获取主窗口信息
            main_checker = WindowChecker()
            main_checker.set_window_title(main_window_title)
            # 使用客户区域信息而非窗口边界，减少边框影响
            main_window_info = main_checker.get_client_info()

            if not main_window_info:
                logger.error(f"未找到标题为 {main_window_title} 的主窗口")
                return []

            main_left, main_top, main_right, main_bottom = main_window_info[0][0], main_window_info[0][1], main_window_info[1][0], main_window_info[1][1]
            main_width = main_right - main_left
            main_height = main_bottom - main_top
            
            # 检查主窗口尺寸是否有效
            if main_width <= 0 or main_height <= 0:
                logger.error(f"主窗口尺寸无效: 宽={main_width}, 高={main_height}")
                return []

            # 计算主窗口内的相对位置
            main_relative_x = screen_x - main_left
            main_relative_y = screen_y - main_top

            # 初始化结果列表
            sub_relative_positions = []

            # 检查相对位置是否在主窗口内
            if 0 <= main_relative_x <= main_width and 0 <= main_relative_y <= main_height:
                sub_relative_positions = []
                with self.lock:
                    # 检查副窗口列表是否为空
                    if not self.sub_windows:
                        logger.error("副窗口列表为空")
                        return []
                        
                    # 使用已识别的副窗口列表
                    for hwnd, title in self.sub_windows:
                        # 检查窗口句柄是否有效
                        if not win32gui.IsWindow(hwnd):
                            logger.error(f"窗口句柄无效: {hwnd}")
                            # 从缓存中移除无效窗口
                            if hwnd in self.window_info_cache:
                                del self.window_info_cache[hwnd]
                            continue
                            
                        try:
                            # 使用带缓存的方法获取副窗口客户区域信息
                            sub_window_info = self.get_window_client_info(hwnd)

                            if sub_window_info:
                                # 导入设置模块，获取用户自定义的宽高

                                # 获取副窗口实际客户区域尺寸
                                sub_client_left, sub_client_top, sub_client_right, sub_client_bottom = sub_window_info[0][0], sub_window_info[0][1], sub_window_info[1][0], sub_window_info[1][1]
                                sub_client_width = sub_client_right - sub_client_left
                                sub_client_height = sub_client_bottom - sub_client_top
                                
                                # 检查副窗口尺寸是否有效
                                if sub_client_width <= 0 or sub_client_height <= 0:
                                    logger.error(f"副窗口尺寸无效: 宽={sub_client_width}, 高={sub_client_height}")
                                    continue
                                
                                # 计算相对比例
                                relative_x_ratio = main_relative_x / main_width
                                relative_y_ratio = main_relative_y / main_height
                                
                                # 确保比例在有效范围内
                                relative_x_ratio = max(0.0, min(1.0, relative_x_ratio))
                                relative_y_ratio = max(0.0, min(1.0, relative_y_ratio))
                                
                                # 使用副窗口实际客户区域尺寸计算目标坐标，提高准确性
                                # 先按自定义分辨率计算理想坐标
                                ideal_x = relative_x_ratio * CUSTOM_RES_WIDTH
                                ideal_y = relative_y_ratio * CUSTOM_RES_HEIGHT
                                
                                # 然后根据副窗口实际尺寸进行缩放，确保映射到正确位置
                                sub_absolute_x = int(round((ideal_x / CUSTOM_RES_WIDTH) * sub_client_width))
                                sub_absolute_y = int(round((ideal_y / CUSTOM_RES_HEIGHT) * sub_client_height))
                                
                                # 确保坐标在有效范围内
                                sub_absolute_x = max(0, min(sub_absolute_x, sub_client_width))
                                sub_absolute_y = max(0, min(sub_absolute_y, sub_client_height))
                                
                                # 添加到结果列表
                                sub_relative_positions.append((sub_absolute_x, sub_absolute_y))
                            else:
                                logger.error(f"未找到句柄为 {hwnd} 的副窗口")
                        except Exception as e:
                            logger.error(f"处理副窗口 {hwnd} 时出错: {e}")
                            continue
            
            return sub_relative_positions
        except Exception as e:
            logger.error(f"计算坐标时出错: {e}")
            return []

    def send_mouse_move(self, hwnd: int, relative_x: int, relative_y: int) -> None:
        """
        发送鼠标移动消息给指定窗口
        :param hwnd: 窗口句柄
        :param relative_x, relative_y: 相对坐标
        """
        # 检查窗口是否有效
        if not win32gui.IsWindow(hwnd):
            return
            
        # 将相对坐标转换为LPARAM格式
        l_param = relative_x | (relative_y << 16)
        # 发送鼠标移动消息
        win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, l_param)
        
    def send_mouse_down(self, hwnd: int, relative_x: int, relative_y: int) -> None:
        """
        发送鼠标按下消息给指定窗口
        :param hwnd: 窗口句柄
        :param relative_x, relative_y: 相对坐标
        """
        # 检查窗口是否有效
        if not win32gui.IsWindow(hwnd):
            return
            
        # 将相对坐标转换为LPARAM格式
        l_param = relative_x | (relative_y << 16)
        # 发送鼠标按下消息
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, l_param)
        
    def send_mouse_up(self, hwnd: int, relative_x: int, relative_y: int) -> None:
        """
        发送鼠标抬起消息给指定窗口
        :param hwnd: 窗口句柄
        :param relative_x, relative_y: 相对坐标
        """
        # 检查窗口是否有效
        if not win32gui.IsWindow(hwnd):
            return
            
        # 将相对坐标转换为LPARAM格式
        l_param = relative_x | (relative_y << 16)
        # 发送鼠标抬起消息
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, l_param)
        
    def send_click_message(self, hwnd: int, relative_x: int, relative_y: int) -> None:
        """
        发送点击消息给指定窗口（组合移动、按下、抬起）
        :param hwnd: 窗口句柄
        :param relative_x, relative_y: 相对坐标
        """
        # 检查窗口是否有效
        if not win32gui.IsWindow(hwnd):
            return
            
        # 组合发送鼠标消息
        self.send_mouse_move(hwnd, relative_x, relative_y)
        
        # 添加短暂延时确保鼠标移动到位
        import time
        time.sleep(0.05)
        
        self.send_mouse_down(hwnd, relative_x, relative_y)
        
        # 增加鼠标按下时长，确保点击被正确识别
        time.sleep(0.1)
        
        self.send_mouse_up(hwnd, relative_x, relative_y)

    def send_mouse_move_to_all(self, relative_x: int, relative_y: int) -> None:
        """
        发送鼠标移动消息给所有副窗口
        :param relative_x, relative_y: 相对坐标
        """
        with self.lock:
            for hwnd, title in self.sub_windows:
                self.send_mouse_move(hwnd, relative_x, relative_y)
        
    def send_mouse_down_to_all(self, relative_x: int, relative_y: int) -> None:
        """
        发送鼠标按下消息给所有副窗口
        :param relative_x, relative_y: 相对坐标
        """
        with self.lock:
            for hwnd, title in self.sub_windows:
                self.send_mouse_down(hwnd, relative_x, relative_y)
        
    def send_mouse_up_to_all(self, relative_x: int, relative_y: int) -> None:
        """
        发送鼠标抬起消息给所有副窗口
        :param relative_x, relative_y: 相对坐标
        """
        with self.lock:
            for hwnd, title in self.sub_windows:
                self.send_mouse_up(hwnd, relative_x, relative_y)
        
    def send_click_message_to_all(self, relative_x: int, relative_y: int) -> None:
        """
        发送点击消息给所有副窗口
        :param relative_x, relative_y: 相对坐标
        """
        with self.lock:
            for hwnd, title in self.sub_windows:
                self.send_click_message(hwnd, relative_x, relative_y)

    def send_key_message(self, hwnd: int, key_code: int, is_pressed: bool = True) -> None:
        """
        发送键盘按键消息到指定窗口（兼容普通字符/特殊键）
        :param hwnd: 目标窗口句柄
        :param key_code: 按键虚拟键码（VK_CODE）
        :param is_pressed: True=按下，False=松开
        """
        if not win32gui.IsWindow(hwnd):
            return

        # 构造键盘消息参数（扫描码+扩展键标志）
        scan_code = win32api.MapVirtualKey(key_code, 0)
        l_param = (scan_code << 16) | (0 if is_pressed else 0xC000)  # 松开时加0xC000标志

        # 发送按键消息
        if is_pressed:
            win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, key_code, l_param)
        else:
            win32gui.PostMessage(hwnd, win32con.WM_KEYUP, key_code, l_param)

    def send_key_message_to_all(self, key_code: int, is_pressed: bool = True) -> None:
        """
        发送键盘消息到所有副窗口
        :param key_code: 按键虚拟键码
        :param is_pressed: True=按下，False=松开
        """
        with self.lock:
            for hwnd, title in self.sub_windows:
                self.send_key_message(hwnd, key_code, is_pressed)

    def sync_controller(self):
        """
        整体控制同步：作为总控入口，统一启动/管理鼠标+键盘同步
        """
        with self.lock:
            # 重置关闭标志
            self.shutdown_flag = False
            
            # 确保同步开关开启
            self.sync_enabled = True

            # 根据同步模式启动相应的同步
            mouse_started = False
            keyboard_started = False
            
            if self.sync_mode == "exactly_sync" or self.sync_mode == "input_sync":
                # 完全同步或键鼠同步时，启动鼠标和键盘监听器
                mouse_started = self.mouse_sync()
                keyboard_started = self.keyboard_sync()
            elif self.sync_mode == "program_sync":
                # 程序同步时，不启动监听器（由程序操作触发同步）
                pass

            if mouse_started and keyboard_started:
                return True
            elif mouse_started:
                return True
            elif keyboard_started:
                return True
            elif self.sync_mode == "program_sync":
                # 程序同步模式下，虽然没有启动监听器，但同步功能是启用的
                return True
            else:
                return False
    
    def set_sync_mode(self, sync_mode: str):
        """
        设置同步模式
        :param sync_mode: 同步模式，可选值：exactly_sync、program_sync、input_sync
        """
        with self.lock:
            self.sync_mode = sync_mode
    
    def get_sync_mode(self) -> str:
        """
        获取当前同步模式
        :return: 当前同步模式
        """
        with self.lock:
            return self.sync_mode

    def keyboard_sync(self):
        """
        启动键盘监听器（线程安全）
        """
        
        # 检查是否已经在锁的保护下（通过检查调用栈）
        caller_frame = inspect.currentframe().f_back
        caller_method = caller_frame.f_code.co_name if caller_frame else ""
        
        if caller_method != "sync_controller":
            # 如果不是从 sync_controller 调用的，需要加锁保护
            with self.lock:
                return self._keyboard_sync_impl()
        else:
            # 如果是从 sync_controller 调用的，已经在锁保护下，直接执行
            return self._keyboard_sync_impl()
    
    def _keyboard_sync_impl(self):
        """
        键盘同步的实际实现
        """
        if self.shutdown_flag:
            return False

        if self.keyboard_listener and self.keyboard_listener.is_alive():
            return False

        # 启动键盘监听器（设置为守护线程，避免阻塞主线程）
        self.keyboard_listener = keyboard.Listener(
            on_press=self.on_key_press,
            on_release=self.on_key_release,
            daemon=True
        )
        self.keyboard_listener.start()
        self.keyboard_listener_thread = None  # 不再需要单独的join线程

        self.sync_enabled = True
        return True

    def keyboard_listener(self):
        """
        兼容原有命名的键盘监听器入口（实际逻辑在on_key_press/on_key_release）
        """
        return self.keyboard_sync()

    def on_key_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        """
        键盘按下事件处理：仅同步主窗口的按键到副窗口
        """
        # 调试信息
        key_str = f"'{key.char}'" if hasattr(key, 'char') and key.char else str(key)
        # print(f"[调试] 检测到键盘按下事件: 按键={key_str}")
        
        if not self.sync_enabled or not self.main_window or not self.sub_windows:
            return

        # 检查当前激活窗口是否为主窗口（确保只同步主窗口的按键）
        foreground_hwnd = win32gui.GetForegroundWindow()

        if foreground_hwnd != self.main_window[0]:
            return

        try:
            # 转换按键为虚拟键码
            key_code = self._get_vk_code(key)
            if key_code is not None:
                # 发送按键按下消息到所有副窗口
                self.send_key_message_to_all(key_code, is_pressed=True)
        except Exception as e:
            logger.error(f"处理键盘按下事件时出错: {e}")

    def on_key_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        """
        键盘松开事件处理：同步按键松开到副窗口
        """
        # 详细调试信息
        key_str = f"'{key.char}'" if hasattr(key, 'char') and key.char else str(key)
        
        if not self.sync_enabled or not self.main_window or not self.sub_windows:
            return

        # 检查当前激活窗口是否为主窗口
        foreground_hwnd = win32gui.GetForegroundWindow()

        if foreground_hwnd != self.main_window[0]:
            return

        try:
            # 转换按键为虚拟键码
            key_code = self._get_vk_code(key)

            if key_code is not None:
                # 发送按键松开消息到所有副窗口
                self.send_key_message_to_all(key_code, is_pressed=False)
        except Exception as e:
            logger.error(f"处理键盘松开事件时出错: {e}")

    def _get_vk_code(self, key: keyboard.Key | keyboard.KeyCode) -> Optional[int]:
        """
        转换pynput按键对象为Windows虚拟键码（VK_CODE）
        :return: 虚拟键码，无法转换返回None
        """
        try:
            # 处理普通字符键
            if isinstance(key, keyboard.KeyCode) and key.char is not None:
                return win32api.VkKeyScan(key.char) & 0xFF
            # 处理特殊键
            elif isinstance(key, keyboard.Key):
                return key.value.vk if hasattr(key, 'value') else None
        except Exception as e:
            logger.error(f"转换按键 {key} 为虚拟键码失败：{e}")
            return None
        return None

    def stop_keyboard_sync(self):
        """
        停止键盘监听器并释放资源
        """
        with self.lock:
            if self.keyboard_listener and self.keyboard_listener.is_alive():
                self.keyboard_listener.stop()
                self.keyboard_listener = None
                self.keyboard_listener_thread = None
                logger.info("键盘监听器已停止")
            else:
                logger.info("键盘监听器未启动")

    def stop_all_sync(self):
        """
        停止所有同步（鼠标+键盘）
        """
        self.shutdown_flag = True
        self.sync_enabled = False
        self.stop_mouse_sync()
        self.stop_keyboard_sync()
        logger.info("所有同步已停止")

    def mouse_sync(self):
        """
        启动鼠标监听器
        """
        # 检查是否已经在锁的保护下（通过检查调用栈）

        caller_frame = inspect.currentframe().f_back
        caller_method = caller_frame.f_code.co_name if caller_frame else ""
        if caller_method != "sync_controller":
            # 如果不是从 sync_controller 调用的，需要加锁保护
            with self.lock:
                return self._mouse_sync_impl()
        else:
            # 如果是从 sync_controller 调用的，已经在锁保护下，直接执行
            return self._mouse_sync_impl()
    
    def _mouse_sync_impl(self):
        """
        鼠标同步的实际实现
        """
        if self.shutdown_flag:
            return False
            
        if self.mouse_listener and self.mouse_listener.is_alive():
            return False

        # 启动鼠标监听器（设置为守护线程，避免阻塞主线程）
        # 添加对移动、按下和释放事件的处理
        self.mouse_listener = mouse.Listener(
            on_move=self.on_mouse_move,
            on_click=self.where_click,
            daemon=True
        )
        self.mouse_listener.start()
        self.sync_enabled = True

        return True

    def stop_mouse_sync(self):
        """
        停止鼠标监听器并释放资源
        """
        if self.mouse_listener and self.mouse_listener.is_alive():
            self.mouse_listener.stop()
            self.mouse_listener = None
            # 仅设置同步禁用标志，不设置全局关闭标志
            self.sync_enabled = False
            logger.info("鼠标监听器已停止")
        else:
            logger.info("鼠标监听器未启动")

    def set_true_enable(self):
        """设置同步启用"""
        self.sync_enabled = True

    def set_false_enable(self):
        """设置同步禁用"""
        self.sync_enabled = False

    def on_mouse_move(self, x: int, y: int) -> None:
        """
        处理鼠标移动事件，实现拖拽同步
        :param x, y: 鼠标移动坐标
        """
        # 检查是否需要处理移动事件
        if not self.sync_enabled or not self.mouse_pressed or not self.main_window or not self.sub_windows:
            return

        # 检测主窗口是否在最前端
        moved_window_hwnd = win32gui.WindowFromPoint((x, y))

        # 检查移动的窗口是否为主窗口
        if moved_window_hwnd != self.main_window[0]:
            return

        try:
            # 从类属性中获取主窗口信息
            main_window_title = self.main_window[1]
            # 计算相对位置
            relative_positions = self.calc_the_position(main_window_title, [], x, y)  # 副窗口标题列表不再需要

            # 发送鼠标移动消息给所有副窗口
            if relative_positions:
                for rel_x, rel_y in relative_positions:
                    self.send_mouse_move_to_all(rel_x, rel_y)
            
            # 更新上次鼠标位置
            self.last_mouse_pos = (x, y)
        except Exception as e:
            logger.error(f"处理鼠标移动事件时出错: {e}")
    
    def where_click(self, x: int, y: int, button, pressed) -> None:
        """
        处理鼠标点击事件
        :param x, y: 鼠标点击坐标
        :param button: 点击的按钮
        :param pressed: 是否按下
        """
        # 详细调试信息
        # print(f"[调试] 检测到鼠标点击事件: 坐标=({x}, {y}), 按钮={button}, 状态={'按下' if pressed else '释放'}")

        if not self.sync_enabled or button != mouse.Button.left or not self.main_window or not self.sub_windows:
            return

        # 检测主窗口是否在最前端
        clicked_window_hwnd = win32gui.WindowFromPoint((x, y))

        # 检查点击的窗口是否为主窗口
        if clicked_window_hwnd != self.main_window[0]:
            return

        try:
            # 从类属性中获取主窗口信息
            main_window_title = self.main_window[1]
            # 计算相对位置
            relative_positions = self.calc_the_position(main_window_title, [], x, y)  # 副窗口标题列表不再需要

            if relative_positions:
                for rel_x, rel_y in relative_positions:
                    if pressed:
                        # 鼠标按下时发送按下消息
                        self.send_mouse_down_to_all(rel_x, rel_y)
                        # 更新鼠标按下状态
                        self.mouse_pressed = True
                    else:
                        # 鼠标释放时发送释放消息
                        self.send_mouse_up_to_all(rel_x, rel_y)
                        # 更新鼠标按下状态
                        self.mouse_pressed = False
        except Exception as e:
            logger.error(f"处理鼠标点击事件时出错: {e}")
            # 出错时重置鼠标状态
            if not pressed:
                self.mouse_pressed = False

    def arrange_windows_diagonal(self, main_window_hwnd: int, sub_window_hwnd: List[int]):
        """
        对角线排列窗口：窗口依次向右下方排列
        :param main_window_hwnd: 主窗口句柄
        :param sub_window_hwnd: 副窗口句柄列表
        """
        logger.info("对角线排列窗口开始: ")
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
            logger.info(f"设置副窗口位置成功: HWND={hwnd}, x={x_position}, y={y_position}")
            if not result:
                logger.error(f"设置窗口位置失败: HWND={hwnd}")
            x_position += wide_add
            y_position += high_add

        if win32gui.IsWindow(main_window_hwnd):
            win32gui.SetWindowPos(main_window_hwnd, win32con.HWND_TOP, x_position, y_position, 0, 0, win32con.SWP_NOSIZE)
            win32gui.SetForegroundWindow(main_window_hwnd)
            logger.info(f"设置主窗口位置成功: HWND={main_window_hwnd}, x={x_position}, y={y_position}")
        else:
            logger.error(f"主窗口句柄无效: HWND={main_window_hwnd}")

        logger.info("对角线排列窗口结束")
    
    def arrange_windows_tile(self, main_window_hwnd: int, sub_window_hwnd: List[int], windows_per_row: int = 3):
        """
        平铺排列窗口：窗口横向排列，一行铺满后开始下一行，尽量保持不互相遮挡
        :param main_window_hwnd: 主窗口句柄
        :param sub_window_hwnd: 副窗口句柄列表
        :param windows_per_row: 一行排列的窗口数量，默认3个
        """
        logger.info("平铺排列窗口开始: ")
        # 获取窗口的数目
        sub_window_count = len(sub_window_hwnd)
        total_window_count = sub_window_count + 1  # 包括主窗口
        
        # 获取屏幕宽度，用于计算窗口布局
        user32 = ctypes.windll.user32
        screen_width = user32.GetSystemMetrics(0)  # 获取屏幕宽度
        screen_height = user32.GetSystemMetrics(1)  # 获取屏幕高度
        
        logger.info(f"屏幕分辨率: {screen_width}x{screen_height}")
        
        # 计算窗口位置
        x_position = 10
        y_position = 10
        
        # 估算窗口平均宽度和高度
        estimated_window_width = screen_width // 4
        estimated_window_height = estimated_window_width * 3 // 4  # 4:3 宽高比
        
        # 计算窗口间距
        # 根据屏幕宽度和每行窗口数量动态计算间距
        if windows_per_row > 1:
            available_width = screen_width - (x_position * 2)
            total_required_width = estimated_window_width * windows_per_row
            if total_required_width < available_width:
                # 有足够空间，计算合适的间距
                window_spacing = (available_width - total_required_width) // (windows_per_row - 1)
                if window_spacing < 10:
                    window_spacing = 10  # 最小间距
            else:
                # 空间不足，使用最小间距，可能会有轻微遮挡
                window_spacing = 5
                logger.warning("警告：屏幕宽度不足，窗口可能会有轻微遮挡")
        else:
            window_spacing = 20  # 只有一个窗口时的默认间距
        
        logger.info(f"窗口间距: {window_spacing}")
        
        # 计算当前行和列
        current_row = 0
        current_col = 0
        
        # 排列副窗口
        for i, hwnd in enumerate(sub_window_hwnd):
            if not win32gui.IsWindow(hwnd):
                continue
            
            # 计算当前窗口位置
            x = x_position + (current_col * (window_spacing + estimated_window_width))
            y = y_position + (current_row * (window_spacing + estimated_window_height))
            
            # 检查窗口位置是否超出屏幕范围
            if x + estimated_window_width > screen_width:
                # 超出屏幕宽度，换行
                current_col = 0
                current_row += 1
                x = x_position
                y = y_position + (current_row * (window_spacing + estimated_window_height))
            
            result = win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, x, y, 0, 0, win32con.SWP_NOSIZE)
            win32gui.SetForegroundWindow(hwnd)
            logger.info(f"设置副窗口位置成功: HWND={hwnd}, x={x}, y={y}")
            if not result:
                logger.error(f"设置窗口位置失败: HWND={hwnd}")
            
            # 更新行列计数
            current_col += 1
            if current_col >= windows_per_row:
                current_col = 0
                current_row += 1
        
        # 排列主窗口
        if win32gui.IsWindow(main_window_hwnd):
            # 计算主窗口位置
            x = x_position + (current_col * (window_spacing + estimated_window_width))
            y = y_position + (current_row * (window_spacing + estimated_window_height))
            
            # 检查主窗口位置是否超出屏幕范围
            if x + estimated_window_width > screen_width:
                # 超出屏幕宽度，换行
                current_col = 0
                current_row += 1
                x = x_position
                y = y_position + (current_row * (window_spacing + estimated_window_height))
            
            win32gui.SetWindowPos(main_window_hwnd, win32con.HWND_TOP, x, y, 0, 0, win32con.SWP_NOSIZE)
            win32gui.SetForegroundWindow(main_window_hwnd)
            logger.info(f"设置主窗口位置成功: HWND={main_window_hwnd}, x={x}, y={y}")
        else:
            logger.error(f"主窗口句柄无效: HWND={main_window_hwnd}")

        logger.info("平铺排列窗口结束")
    
    def arrange_windows(self, main_window_hwnd: int, sub_window_hwnd: List[int]):
        """
        窗口排列控制器：根据设置选择排列方式
        :param main_window_hwnd: 主窗口句柄
        :param sub_window_hwnd: 副窗口句柄列表
        """
        # 导入设置模块，获取排列方式和每行窗口数
        from OAT.tools.settings import WINDOW_ARRANGE_MODE, WINDOWS_PER_ROW
        
        if WINDOW_ARRANGE_MODE == "diagonal":
            # 对角线排列
            self.arrange_windows_diagonal(main_window_hwnd, sub_window_hwnd)
        elif WINDOW_ARRANGE_MODE == "tile":
            # 平铺排列
            self.arrange_windows_tile(main_window_hwnd, sub_window_hwnd, WINDOWS_PER_ROW)
        else:
            # 默认使用对角线排列
            self.arrange_windows_diagonal(main_window_hwnd, sub_window_hwnd)

    def get_sub_windows(self) -> List[Tuple[int, str]]:
        """
        返回所有副窗口列表
        """
        return self.sub_windows

    def on_pipeline_task(self, task_name: str) -> None:
        """由 PipelineRunner 调用，通知同步器当前执行的管道任务"""
        self.pipeline_task_name = task_name