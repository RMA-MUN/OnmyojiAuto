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

class OnmyjiAutomation:
    def __init__(self, window_title):
        self.window_title = window_title
        # 窗口信息获取与初始化
        self.hwnd = win32gui.FindWindow(None, window_title)
        if not self.hwnd:
            print(f"无法找到窗口 {window_title}")
            raise Exception('无法获取游戏窗口尺寸')

        self.area = self.get_window_rect()
        self.x1, self.y1, self.width, self.height = self.area
        self.x2, self.y2 = self.x1 + self.width, self.y1 + self.height


        # 线程与控制变量
        self.lock = threading.Lock()
        self.shutdown_flag = False

        # 图像识别缓存和参数
        self.recognition_cache = {}
        self.cache_timeout = 1.0
        self.default_confidence = 0.85  # 默认置信度
        self.image_templates = {}

    def print_window_info(self):
        """输出窗口信息"""
        print('已获取到游戏窗口信息\n'
              f'窗口左上角的位置是({self.x1},{self.y1})\n'
              f'窗口右下角的位置是({self.x2},{self.y2})\n')

    def get_window_rect(self):
        """获取窗口矩形区域"""
        rect = win32gui.GetWindowRect(self.hwnd)
        x1, y1, x2, y2 = rect
        return x1, y1, x2 - x1, y2 - y1

    def preload_image(self, logo_path):
        """预加载并缓存图像模板"""
        if logo_path not in self.image_templates:
            try:
                # 读取图像并进行预处理
                image = Image.open(logo_path)
                # 转换为RGB模式（如果不是）
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                # 可以在这里添加缩放、增强对比度等预处理
                self.image_templates[logo_path] = image
            except Exception as e:
                print(f"警告：预加载图像 {logo_path} 失败：{str(e)}")
                return False
        return True

    @lru_cache(maxsize=32)
    def _get_scaled_logo(self, logo, scale=1.0):
        """缓存并返回缩放后的图像模板"""
        # 确保先预加载图像
        self.preload_image(logo)
        # 这里可以添加图像预处理逻辑，如缩放、灰度化
        return logo

    def onmyji(self, logo, use_cache=True):
        """图像识别 + 缓存机制"""
        current_time = time.time()

        # 检查缓存
        if use_cache and logo in self.recognition_cache:
            cached_result, cache_time = self.recognition_cache[logo]
            if current_time - cache_time < self.cache_timeout:
                if cached_result:
                    x, y, width, height = cached_result
                    self.x1 = random.randint(x, x + width)
                    self.y1 = random.randint(y, y + height)
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
            print(f"查找图片{logo}的可信度低于预期")
        except OSError as e:
            # 处理文件读取错误
           pass
        except Exception as e:
            # 处理其他未预期的错误
            pass

        # 更新缓存
        self.recognition_cache[logo] = (target, current_time)

        if target:
            x, y, width, height = target
            self.x1 = random.randint(x, x + width)
            self.y1 = random.randint(y, y + height)
            return True
        return False

    def move_mouse(self, x, y):
        """鼠标移动"""
        # 使用绝对坐标移动，更高效
        win32api.SetCursorPos((x, y))

    def win32_double_click(self):
        """优化的双击操作，减少延迟"""
        # 组合鼠标事件，减少系统调用
        flags = win32con.MOUSEEVENTF_LEFTDOWN | win32con.MOUSEEVENTF_LEFTUP
        win32api.mouse_event(flags, 0, 0, 0, 0)
        # 更短的双击间隔
        time.sleep(0.03)
        win32api.mouse_event(flags, 0, 0, 0, 0)
        
    def calc_relative_position(self, absolute_x, absolute_y):
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
        
    def send_click_message(self, relative_x, relative_y):
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


    def perform_action(self, logo, hidden_window=False, threshold=0.85):
        # 先进行识别，减少锁持有时间
        try:
            # 如果启用隐藏窗口捕获
            if hidden_window:
                # print("使用隐藏窗口捕获模式进行图像识别")
                try:
                    # 创建WindowCapture实例
                    wc = WindowCapture(hwnd=self.hwnd)
                    # 使用WindowCapture查找图像，只传递必要的参数
                    position = wc.find_image_precise(logo, threshold=threshold)
                    if position:
                        # 从区域范围中计算中心点坐标
                        (x1, x2), (y1, y2) = position
                        # 使用随机偏移点击
                        relative_x = random.randint(x1, x2)
                        relative_y = random.randint(y1, y2)
                        # 直接发送点击消息
                        self.send_click_message(relative_x, relative_y)
                        time.sleep(random.uniform(1.5, 3.0))
                        return True
                    else:
                        return False
                except Exception as e:
                    print(f"隐藏窗口捕获发生错误: {str(e)}")
                    return self.perform_action(logo, hidden_window=False, threshold=threshold)
                 
            # 常规方法
            found = self.onmyji(logo)
            if not found:
                return False

            with self.lock:  # 只在执行关键操作时持有锁
                # 计算相对坐标
                relative_x, relative_y = self.calc_relative_position(self.x1, self.y1)
                if "MuMu" in self.window_title or "模拟器" in self.window_title:
                    pyautogui.moveTo(self.x1, self.y1)
                    pyautogui.doubleClick(self.x1, self.y1)
                    time.sleep(random.uniform(1.5, 3.0))
                    return True
                # 发送点击消息
                else:
                    self.send_click_message(relative_x, relative_y)
                    time.sleep(random.uniform(1.5, 3.0))
                    return True
        except pyautogui.FailSafeException:
            print("警告：触发了PyAutoGUI的安全模式，操作已停止")
            return False
        except Exception as e:
            print(f"警告：执行操作时发生错误：{str(e)}")
            return False

    def clear_cache(self):
        """清除识别缓存"""
        self.recognition_cache.clear()
        self._get_scaled_logo.cache_clear()
