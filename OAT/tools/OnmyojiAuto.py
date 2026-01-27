import threading
import time
import win32gui
import win32api
import win32con
import pyautogui
import random
from PIL import Image
from functools import lru_cache
from .get_DC import WindowCapture
from .WindowSynchronizer import WindowSynchronizer


class OnmyjiAutomation:
    def __init__(self, window_title: str, synchronizer=None):
        self.window_title = window_title
        # 窗口信息获取与初始化
        self.hwnd = win32gui.FindWindow(None, window_title)
        if not self.hwnd:
            print(f"无法找到窗口 {window_title}")
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
            self._init_common_params()
            return

        # 窗口同步器 - 如果没有提供则创建新实例
        if synchronizer is None:
            self.synchronizer = WindowSynchronizer()
        else:
            self.synchronizer = synchronizer

        self.area = self.get_window_rect()
        self.x1, self.y1, self.width, self.height = self.area
        self.x2, self.y2 = self.x1 + self.width, self.y1 + self.height

        # 初始化公共参数
        self._init_common_params()
    
    def _init_common_params(self):
        """初始化公共参数"""
        # 线程与控制变量
        self.lock = threading.Lock()
        self.shutdown_flag = False

        # 图像识别缓存和参数
        self.recognition_cache = {}
        self.cache_timeout = 1.0
        self.default_confidence = 0.85  # 默认置信度
        self.image_templates = {}

        # 模拟鼠标移动的参数
        self.move_duration_range = (0.3, 0.8)  # 移动时长范围（秒）
        self.jitter_amplitude = 0.5  # 鼠标抖动幅度
        self.curve_intensity = 5  # 曲线弯曲程度

    def print_window_info(self) -> None:
        """输出窗口信息"""
        print('已获取到游戏窗口信息\n'
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
            try:
                # 读取图像并进行预处理
                image = Image.open(logo_path)
                # 转换为RGB模式（如果不是）
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                self.image_templates[logo_path] = image
            except Exception as e:
                print(f"警告：预加载图像 {logo_path} 失败：{str(e)}")
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
            import traceback
            traceback.print_exc()

        # 更新缓存
        self.recognition_cache[logo] = (target, current_time)

        if target:
            x, y, width, height = target
            self.target_x = random.randint(x, x + width)
            self.target_y = random.randint(y, y + height)
            return True
        
        return False

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
        rect = win32gui.GetWindowRect(self.hwnd)
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
        # 发送鼠标左键按下消息
        win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, l_param)
        # 发送鼠标左键释放消息
        win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONUP, 0, l_param)


    def perform_action(self,
                       logo: str,
                       hidden_window: bool = False,
                       threshold: float = 0.85,
                       sync_mode: bool = False,
                       # sync_type: str = "完全同步"
                       ) -> bool:
        """
        执行操作：根据是否隐藏窗口选择不同的执行模式
        :param logo: 要识别的图像路径
        :param hidden_window: 是否使用隐藏窗口模式
        :param threshold: 识别阈值
        :param sync_mode: 是否同步执行
        :param sync_type: 同步类型，可选值："完全同步"、"点击同步"
        :return: 是否成功执行操作
        """
        try:
            if hidden_window:
                return self._perform_action_hidden_window(logo, threshold, sync_mode)
            else:
                return self._perform_action_normal(logo, threshold, sync_mode)
        except pyautogui.FailSafeException:
            print("警告：触发了PyAutoGUI的安全模式，操作已停止")
            return False
        except Exception as e:
            print(f"警告：执行操作时发生错误：{str(e)}")
            return False

    def _perform_action_hidden_window(self, logo: str, threshold: float, sync_mode: bool) -> bool:
        """使用隐藏窗口捕获模式执行操作"""
        try:
            wc = WindowCapture(hwnd=self.hwnd)
            position = wc.find_image_precise(logo, threshold=threshold)
            if position:
                # 从区域范围中计算中心点坐标
                (x1, x2), (y1, y2) = position
                # 使用随机偏移点击
                relative_x = random.randint(x1, x2)
                relative_y = random.randint(y1, y2)

                self._send_click_messages(relative_x, relative_y, sync_mode)
                return True
            else:
                return False
        except Exception as e:
            print(f"隐藏窗口捕获发生错误: {str(e)}")
            # 降级到常规模式
            return self._perform_action_normal(logo, threshold, sync_mode)



    def _perform_action_normal(self, logo: str, threshold: float, sync_mode: bool) -> bool:
        """使用常规模式执行操作"""
        found = self.find_img(logo)
        if not found:
            return False

        with self.lock:  # 只在执行关键操作时持有锁
            self._complex_move(target_x=self.target_x, target_y=self.target_y)
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