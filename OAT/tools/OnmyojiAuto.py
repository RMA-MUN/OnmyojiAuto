import os
import random
import threading
import time
import traceback
from functools import lru_cache

import cv2
import numpy as np
import pyautogui
import win32api
import win32con
import win32gui
from PIL import Image

from .WindowSynchronizer import WindowSynchronizer
from .GetDC import WindowCapture
# 导入整个settings模块，而不是单个变量
from . import settings
from OAT.utils.warning_box import warning_box
from OAT.utils.error_handler import log_error
from OAT.utils.OCRService import ocr_service
from ..utils.logging import logger


class OnmyojiAutomation:
    def __init__(self, window_title: str, synchronizer=None, sync_mode: str = "exactly_sync", find_mode=None, find_threshold=None):
        self.window_title = window_title
        # 窗口信息获取与初始化
        self.hwnd = win32gui.FindWindow(None, window_title)
        if not self.hwnd:
            logger.error(f"无法找到窗口 {window_title}")
            # 设置默认窗口信息
            self.area = (0, 0, 1920, 1080)  # 默认屏幕尺寸
            self.x1, self.y1, self.width, self.height = self.area
            self.x2, self.y2 = self.x1 + self.width, self.y1 + self.height
            # 设置同步器为None
            if synchronizer is None:
                self.synchronizer = None
            else:
                self.synchronizer = synchronizer
            # 跳过后续窗口初始化
            self._init_common_params(find_mode, find_threshold)
            return

        # 窗口同步器 - 如果没有提供则创建新实例
        if synchronizer is None:
            self.synchronizer = WindowSynchronizer(sync_mode=sync_mode)
        else:
            self.synchronizer = synchronizer
            # 如果提供了同步器，设置其同步模式
            if hasattr(self.synchronizer, 'set_sync_mode'):
                self.synchronizer.set_sync_mode(sync_mode)

        self.area = self.get_window_rect()
        self.x1, self.y1, self.width, self.height = self.area
        self.x2, self.y2 = self.x1 + self.width, self.y1 + self.height

        # 初始化公共参数
        self._init_common_params(find_mode, find_threshold)
    
    def _init_common_params(self, find_mode=None, find_threshold=None):
        """初始化公共参数"""
        # 线程与控制变量
        self.lock = threading.Lock()
        self.shutdown_flag = False

        # 图像识别缓存和参数
        self.recognition_cache = {}
        self.cache_timeout = 1.0
        # 设置识别模式和阈值
        # 优先使用传入的参数，其次使用settings.py中的配置
        self.find_mode = find_mode if find_mode else settings.FIND_MODE
        # 获取阈值并转换为0-1之间的值
        threshold_value = find_threshold if find_threshold is not None else settings.FIND_THRESHOLD
        self.default_confidence = threshold_value / 100.0  # 转换为0-1之间的值
        self.image_templates = {}

        # 模拟鼠标移动的参数
        self.move_duration_range = (0.3, 0.8)  # 移动时长范围（秒）
        self.jitter_amplitude = 0.5  # 鼠标抖动幅度
        self.curve_intensity = 5  # 曲线弯曲程度
        
        # 创建WindowCapture实例，用于隐藏窗口模式
        self.window_capture = None
        if hasattr(self, 'hwnd') and self.hwnd:
            try:
                self.window_capture = WindowCapture(hwnd=self.hwnd)
            except Exception:
                pass

        # 窗口矩形缓存
        self._window_rect_cache = None
        self._window_rect_cache_ts = 0.0

    def _get_cached_window_rect(self):
        """获取窗口矩形（带1秒TTL缓存）"""
        now = time.time()
        if self._window_rect_cache is not None and now - self._window_rect_cache_ts < 1.0:
            return self._window_rect_cache
        rect = win32gui.GetWindowRect(self.hwnd)
        client = win32gui.GetClientRect(self.hwnd)
        self._window_rect_cache = (rect, client)
        self._window_rect_cache_ts = now
        return self._window_rect_cache

    def is_window_present(self) -> bool:
        """检查窗口是否存在且有效"""
        if self.hwnd == 0:
            return False
        
        # 尝试获取窗口矩形，进一步验证窗口是否有效
        try:
            rect = win32gui.GetWindowRect(self.hwnd)
            # 检查窗口是否有有效的尺寸
            x1, y1, x2, y2 = rect
            if x1 == 0 and y1 == 0 and x2 == 0 and y2 == 0:
                return False
            if x2 <= x1 or y2 <= y1:
                return False
            return True
        except Exception:
            # 如果获取窗口矩形失败，说明窗口无效
            return False

    def print_window_info(self) -> None:
        """输出窗口信息"""
        logger.info('已获取到游戏窗口信息\n'
              f'窗口左上角的位置是({self.x1},{self.y1})\n'
              f'窗口右下角的位置是({self.x2},{self.y2})\n')

    def get_window_rect(self) -> tuple:
        """获取窗口矩形区域"""
        rect = win32gui.GetWindowRect(self.hwnd)
        x1, y1, x2, y2 = rect
        return x1, y1, x2 - x1, y2 - y1

    def preload_image(self, logo_path: str) -> bool:
        """预加载并缓存图像模板"""
        if logo_path not in self.image_templates:
            if not os.path.exists(logo_path):
                logger.warn(f"图像文件不存在，跳过预加载: {logo_path}")
                return False
            try:
                # 读取图像并进行预处理
                image = Image.open(logo_path)
                # 转换为RGB模式（如果不是）
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                self.image_templates[logo_path] = image
            except Exception as e:
                logger.warn(f"警告：预加载图像 {logo_path} 失败：{str(e)}")
                return False
        return True

    @lru_cache(maxsize=32)
    def _get_scaled_logo(self, logo: str, scale: float=1.0):
        """缓存并返回缩放后的图像模板"""
        # 确保先预加载图像
        self.preload_image(logo)
        return logo

    def find_img(self, logo: str, use_cache=True) -> bool:
        """图像识别 + 缓存机制"""
        current_time = time.time()

        # 检查缓存
        if use_cache and logo in self.recognition_cache:
            cached_result, cache_time = self.recognition_cache[logo]
            if current_time - cache_time < self.cache_timeout:
                if cached_result:
                    x, y, width, height = cached_result
                    self.target_x = random.randint(x, x + width)
                    self.target_y = random.randint(y, y + height)
                return cached_result is not None

        # 预加载图像
        self.preload_image(logo)

        # 执行图像识别
        target = None
        try:
            # 使用预加载的图像模板而不是文件路径
            if logo in self.image_templates:
                target = pyautogui.locateOnScreen(
                    self.image_templates[logo],
                    confidence=self.default_confidence,
                    region=self.area
                )
            else:
                # 降级到文件路径方式
                target = pyautogui.locateOnScreen(
                    logo,
                    confidence=self.default_confidence,
                    region=self.area
                )
        except pyautogui.ImageNotFoundException:
            # 未找到图像时设置target为None
            target = None
        except OSError:
            # 处理文件读取错误
            pass
        except Exception:
            # 处理其他未预期的错误
            traceback.print_exc()

        # 更新缓存
        self.recognition_cache[logo] = (target, current_time)

        if target:
            x, y, width, height = target
            self.target_x = random.randint(x, x + width)
            self.target_y = random.randint(y, y + height)
            return True
        
        return False
    
    def find_text_ocr(self, target_text: str) -> tuple:
        """
        使用OCR识别文字（异步执行）
        
        参数:
            target_text: 要识别的目标文字
            
        返回:
            tuple: (是否找到, 文字区域坐标, 文字内容)
        """
        import queue
        
        # 创建队列用于接收OCR结果
        result_queue = queue.Queue()
        
        def ocr_task():
            """OCR识别任务，在单独线程中执行"""
            start_time = time.time()
            
            try:
                # 获取窗口截图
                screenshot = None
                if self.window_capture:
                    # 使用隐藏窗口捕获
                    screenshot = self.window_capture.capture_window()
                else:
                    # 使用pyautogui截图
                    screenshot = pyautogui.screenshot(region=self.area)
                    # 转换为OpenCV格式
                    screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
                
                if screenshot is None:
                    result_queue.put((False, None, None))
                    return
                
                # 使用OCR服务识别文字
                found, text_area, real_text = ocr_service.find_text(screenshot, target_text)
                
                # 记录识别时间（仅在找到文字时打印）
                elapsed_time = time.time() - start_time
                if found:
                    logger.info(f"OCR识别成功: '{target_text}'，耗时: {elapsed_time:.3f}秒")
                    
                    # 如果有窗口句柄，将OCR坐标转换为客户区坐标
                    if self.hwnd and text_area:
                        try:
                            # 获取窗口信息（使用缓存）
                            window_rect, client_rect = self._get_cached_window_rect()

                            # 计算标题栏高度（窗口高度 - 客户区高度）
                            window_height = window_rect[3] - window_rect[1]
                            client_height = client_rect[3] - client_rect[1]
                            title_bar_height = window_height - client_height
                            
                            # 将OCR坐标（包含标题栏）转换为客户区坐标
                            converted_text_area = []
                            for point in text_area:
                                x, y = point
                                # 减去标题栏高度
                                converted_text_area.append([x, y - title_bar_height])
                            
                            text_area = converted_text_area
                        except Exception:
                            # 如果转换失败，使用原始坐标
                            pass
                
                result_queue.put((found, text_area, real_text))
            except pyautogui.FailSafeException:
                logger.error("OCR识别失败: 触发了PyAutoGUI安全模式")
                result_queue.put((False, None, None))
            except Exception as e:
                logger.error(f"OCR识别发生错误: {str(e)}")
                result_queue.put((False, None, None))
        
        # 创建并启动线程
        ocr_thread = threading.Thread(target=ocr_task, daemon=True)
        ocr_thread.start()
        
        # 等待结果，设置超时时间避免无限等待
        try:
            return result_queue.get(timeout=15.0)  # 15秒超时，适应OCR识别耗时
        except queue.Empty:
            logger.error("OCR识别超时")
            return False, None, None

    def _move_mouse(self, x: int, y: int) -> None:
        """鼠标移动（基础方法）"""
        # 使用绝对坐标移动，更高效
        win32api.SetCursorPos((x, y))

    def _win32_double_click(self) -> None:
        """优化的双击操作，减少延迟"""
        # 组合鼠标事件，减少系统调用
        flags = win32con.MOUSEEVENTF_LEFTDOWN | win32con.MOUSEEVENTF_LEFTUP
        win32api.mouse_event(flags, 0, 0, 0, 0)
        # 更短的双击间隔
        time.sleep(0.03)
        win32api.mouse_event(flags, 0, 0, 0, 0)

    def _calc_relative_position(self, absolute_x: int, absolute_y: int) -> tuple:
        """
        计算绝对坐标在窗口内的相对位置
        :param absolute_x: 屏幕绝对X坐标
        :param absolute_y: 屏幕绝对Y坐标
        :return: 窗口内的相对坐标(x, y)
        """
        rect, _ = self._get_cached_window_rect()
        window_left, window_top, _, _ = rect
        relative_x = absolute_x - window_left
        relative_y = absolute_y - window_top
        return relative_x, relative_y

    def send_click_message(self, relative_x: int, relative_y: int) -> None:
        """
        向指定窗口发送点击消息
        :param relative_x: 窗口内相对X坐标
        :param relative_y: 窗口内相对Y坐标
        """
        # 将相对坐标转换为LPARAM格式
        l_param = relative_x | (relative_y << 16)
        
        # 发送鼠标移动过去的信息
        win32gui.PostMessage(self.hwnd, win32con.WM_MOUSEMOVE, 0, l_param)
        
        # 添加短暂延时确保鼠标移动到位
        time.sleep(0.05)
        
        # 发送鼠标左键按下消息
        win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, l_param)
        
        # 增加鼠标按下时长，确保点击被正确识别
        time.sleep(0.2)
        
        # 发送鼠标左键释放消息
        win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONUP, 0, l_param)


    def perform_action(self,
                       logo: str,
                       hidden_window: bool = False,
                       threshold: float = None,
                       sync_mode: bool = False,
                       click_type: str = "image",
                       click_area: list = None,
                       ocr_enabled: bool = False,
                       ocr_target_text: str = "",
                       # sync_type: str = "完全同步"
                       ) -> bool:
        """
        执行操作：根据是否隐藏窗口选择不同的执行模式
        :param logo: 要识别的图像路径
        :param hidden_window: 是否使用隐藏窗口模式
        :param threshold: 识别阈值，默认使用设置中的值
        :param sync_mode: 是否同步执行
        :param click_type: 点击方式：image（图片区域）、coordinate（指定坐标）
        :param click_area: 当click_type为coordinate时的点击区域 [x1, x2, y1, y2]
        :param ocr_enabled: 是否启用OCR识别
        :param ocr_target_text: OCR目标文字
        :param sync_type: 同步类型，可选值："完全同步"、"点击同步"
        :return: 是否成功执行操作
        """
        try:
            # 使用设置中的阈值作为默认值
            if threshold is None:
                threshold = self.default_confidence
                
            # 如果启用了OCR，先尝试OCR识别
            if ocr_enabled and ocr_target_text:
                found, text_area, real_text = self.find_text_ocr(ocr_target_text)
                if found and text_area:
                    # 在文字区域内随机点击
                    x, y = ocr_service.get_random_point_in_area(text_area)
                    if hidden_window:
                        # 隐藏窗口模式下使用相对坐标
                        self._send_click_messages(int(x), int(y), sync_mode)
                    else:
                        # 普通模式下转换为绝对坐标
                        absolute_x = self.x1 + int(x)
                        absolute_y = self.y1 + int(y)
                        with self.lock:
                            self._complex_move(target_x=absolute_x, target_y=absolute_y)
                            self._win32_double_click()
                            if sync_mode and self.synchronizer.sync_enabled:
                                self.synchronizer.sync_controller()
                            time.sleep(random.uniform(1.5, 3.0))
                    return True
                # 如果OCR未识别到文字，不输出错误信息，直接尝试图像识别
            
            # 如果OCR未启用或识别失败，使用常规图像识别
            if hidden_window:
                return self._perform_action_hidden_window(logo, threshold, sync_mode, click_type, click_area)
            else:
                return self._perform_action_normal(logo, threshold, sync_mode, click_type, click_area)
        except pyautogui.FailSafeException:
            error_msg = "警告：触发了PyAutoGUI的安全模式，操作已停止"
            # 使用warning_box显示错误信息
            warning_box(error_msg)
            # 写入日志文件
            log_error(error_msg)
            return False
        except Exception as e:
            error_msg = f"警告：执行操作时发生错误：{str(e)}"
            # 使用warning_box显示错误信息
            warning_box(error_msg)
            # 写入日志文件
            log_error(error_msg)
            return False

    def _perform_action_hidden_window(self, logo: str, threshold: float, sync_mode: bool, click_type: str = "image", click_area: list = None) -> bool:
        """使用隐藏窗口捕获模式执行操作"""
        try:
            # 使用初始化时创建的WindowCapture实例
            if not self.window_capture:
                self.window_capture = WindowCapture(hwnd=self.hwnd)
            
            wc = self.window_capture
            
            # 准备目标图像：优先使用预加载的图像
            target_image = logo
            if logo in self.image_templates:
                # 将PIL图像转换为OpenCV格式（NumPy数组）
                pil_image = self.image_templates[logo]
                # 转换为RGB模式
                if pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')
                # 转换为NumPy数组并调整通道顺序（PIL是RGB，OpenCV是BGR）
                target_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            
            # 使用设置的识别模式和阈值
            position = wc.find_image_precise(target_image, threshold=threshold, method=self.find_mode)
            if position:
                # 确定点击坐标
                if click_type == "coordinate" and click_area:
                    # 使用指定区域生成随机坐标
                    x1, x2, y1, y2 = click_area
                    relative_x = random.randint(x1, x2)
                    relative_y = random.randint(y1, y2)
                else:
                    # 从区域范围中计算中心点坐标
                    (x1, x2), (y1, y2) = position
                    
                    # 计算区域中心
                    center_x = (x1 + x2) // 2
                    center_y = (y1 + y2) // 2
                    
                    # 计算标题栏高度并转换坐标（后台模式下，图像识别返回的坐标包含标题栏）
                    try:
                        # 获取窗口信息（使用缓存）
                        window_rect, client_rect = self._get_cached_window_rect()

                        # 计算标题栏高度（窗口高度 - 客户区高度）
                        window_height = window_rect[3] - window_rect[1]
                        client_height = client_rect[3] - client_rect[1]
                        title_bar_height = window_height - client_height
                        
                        # 将包含标题栏的坐标转换为客户区坐标
                        center_y = center_y - title_bar_height
                        y1 = y1 - title_bar_height
                        y2 = y2 - title_bar_height
                        
                        # 确保坐标在客户区内
                        center_y = max(0, center_y)
                        y1 = max(0, y1)
                        y2 = max(0, y2)
                    except Exception:
                        # 如果转换失败，使用原始坐标
                        pass
                    
                    # 计算区域的1/3大小作为随机范围，使点击更靠近中心
                    range_x = (x2 - x1) // 3
                    range_y = (y2 - y1) // 3
                    # 在中心附近生成随机坐标
                    relative_x = random.randint(max(x1, center_x - range_x), min(x2, center_x + range_x))
                    relative_y = random.randint(max(y1, center_y - range_y), min(y2, center_y + range_y))

                self._send_click_messages(relative_x, relative_y, sync_mode)
                return True
            else:
                return False
        except Exception as e:
            logger.error(f"隐藏窗口捕获发生错误: {str(e)}")
            # 降级到常规模式
            return self._perform_action_normal(logo, threshold, sync_mode, click_type, click_area)

    def _perform_action_normal(self, logo: str, threshold: float, sync_mode: bool, click_type: str = "image", click_area: list = None) -> bool:
        """使用常规模式执行操作"""
        found = self.find_img(logo)
        if not found:
            return False

        with self.lock:  # 只在执行关键操作时持有锁
            # 确定点击坐标
            if click_type == "coordinate" and click_area:
                # 使用指定区域生成随机坐标
                x1, x2, y1, y2 = click_area
                # 转换为屏幕绝对坐标
                target_x = self.x1 + random.randint(x1, x2)
                target_y = self.y1 + random.randint(y1, y2)
            else:
                # 重新计算更靠近中心的随机坐标
                # 从find_img方法中，target_x和target_y是在区域内随机生成的
                if logo in self.recognition_cache:
                    cached_result, _ = self.recognition_cache[logo]
                    if cached_result:
                        x, y, width, height = cached_result
                        # 计算区域中心
                        center_x = x + width // 2
                        center_y = y + height // 2
                        # 计算区域的1/3大小作为随机范围，使点击更靠近中心
                        range_x = width // 3
                        range_y = height // 3
                        # 在中心附近生成随机坐标
                        target_x = random.randint(max(x, center_x - range_x), min(x + width, center_x + range_x))
                        target_y = random.randint(max(y, center_y - range_y), min(y + height, center_y + range_y))
                    else:
                        # 如果缓存中没有结果，使用原来的坐标
                        target_x, target_y = self.target_x, self.target_y
                else:
                    # 如果缓存中没有结果，使用原来的坐标
                    target_x, target_y = self.target_x, self.target_y

            self._complex_move(target_x=target_x, target_y=target_y)
            self._win32_double_click()
            
            # 如果启用同步模式，根据同步类型执行相应操作
            if sync_mode and self.synchronizer.sync_enabled:
                self.synchronizer.sync_controller()
            
            time.sleep(random.uniform(1.5, 3.0))
            return True

    def _send_click_messages(self, relative_x: int, relative_y: int, sync_mode: bool) -> None:
        """发送点击消息，根据同步模式决定是否同步到多个窗口
        :param relative_x, relative_y: 相对坐标
        :param sync_mode: 是否启用同步
        :param sync_type: 同步类型，可选值："完全同步"、"点击同步"
        """
        if sync_mode and self.synchronizer.sync_enabled:
            # 确保使用主窗口句柄
            if self.synchronizer.main_window and self.hwnd != self.synchronizer.main_window[0]:
                self.hwnd = self.synchronizer.main_window[0]

            # 给主窗口发送点击消息
            self.synchronizer.send_click_message(hwnd=self.hwnd, relative_x=relative_x, relative_y=relative_y)

            # 给所有副窗口发送点击消息
            for sub_hwnd, _ in self.synchronizer.get_sub_windows():
                self.synchronizer.send_click_message(hwnd=sub_hwnd, relative_x=relative_x, relative_y=relative_y)

        elif sync_mode and not self.synchronizer.sync_enabled:
            # 同步模式已被禁用，只给当前窗口发送点击消息
            self.synchronizer.send_click_message(hwnd=self.hwnd, relative_x=relative_x, relative_y=relative_y)
        else:
            # 非同步模式，使用普通点击方法
            self.send_click_message(relative_x, relative_y)

        # 等待点击操作完成
        time.sleep(random.uniform(1.5, 3.0))

    def _ease_in_out_cubic(self, t: float) -> float:
        """
        缓动函数：模拟移动鼠标的加速/减速过程
        :param t: 0~1之间的数值，表示移动进度
        :return: 0~1之间的数值，表示当前进度对应的速度权重
        """
        return t * t * (3 - 2 * t) if t <= 1 else 1

    def _generate_bezier_path(self, start: tuple, end: tuple, num_points: int = 50) -> list:
        """
        生成简单的曲线路径点（模拟移动鼠标的弯曲轨迹）
        :param start: 起点坐标 (x, y)
        :param end: 终点坐标 (x, y)
        :param num_points: 路径点数量
        :return: 按顺序排列的路径点列表 [(x,y), (x,y), ...]
        """
        path_points = []
        sx, sy = start
        ex, ey = end
        dx, dy = ex - sx, ey - sy
        
        # 使用简单的抛物线轨迹
        for i in range(num_points):
            t = i / (num_points - 1)
            # 应用缓动函数
            eased_t = self._ease_in_out_cubic(t)
            
            # 计算当前点坐标
            x = sx + dx * eased_t
            y = sy + dy * eased_t
            
            # 添加随机偏移，模拟人手抖动
            x += random.uniform(-self.jitter_amplitude, self.jitter_amplitude)
            y += random.uniform(-self.jitter_amplitude, self.jitter_amplitude)
            
            path_points.append((round(x), round(y)))
        
        return path_points

    def _human_like_move(self, target_x: int, target_y: int) -> None:
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

    def _complex_move(self, target_x: int, target_y: int) -> None:
        """
        :param target_x: 目标X坐标
        :param target_y: 目标Y坐标
        """
        try:
            self._human_like_move(target_x, target_y)
        except Exception:
            with self.lock:
                try:
                    win32api.SetCursorPos((target_x, target_y))
                except:
                    pyautogui.moveTo(target_x, target_y, duration=0.2)

    def clear_cache(self):
        """清除识别缓存"""
        self.recognition_cache.clear()
        self._get_scaled_logo.cache_clear()