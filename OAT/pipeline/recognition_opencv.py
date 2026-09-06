import random
import time
from typing import Optional, Tuple

import cv2
import numpy as np
import pyautogui
import win32gui
import win32con

from OAT.tools.GetDC import WindowCapture, effective_client_dy
from OAT.tools import settings
from OAT.tools.human_click import foreground_click, human_drag
from OAT.utils.OCRService import ocr_service
from OAT.utils.logging import logger
from .recognition import RecognitionEngine, RecognitionResult


def _normalize_threshold(threshold) -> float:
    """统一阈值到 0-1：兼容 0-100 百分比写法（与 GetDC.find_image_precise 一致）"""
    try:
        v = float(threshold)
    except (ValueError, TypeError):
        return settings.FIND_THRESHOLD / 100.0
    if v > 1.0:
        v = v / 100.0
    return min(1.0, max(0.0, v))


class OpenCVRecognitionEngine(RecognitionEngine):
    """基于 OpenCV 模板匹配 + RapidOCR 的识别引擎"""

    _template_cache: dict = {}

    def __init__(
        self,
        hwnd: int,
        threshold: float = None,
        find_mode: str = None,
        synchronizer=None,
        hidden_window: bool = True,
    ):
        self.hwnd = hwnd
        self.hidden_window = hidden_window
        self.threshold = _normalize_threshold(
            threshold if threshold is not None else settings.FIND_THRESHOLD
        )
        self.find_mode = find_mode if find_mode else settings.FIND_MODE
        self.synchronizer = synchronizer

        # 窗口捕获器（隐藏窗口模式下使用）
        self.window_capture = None
        if hwnd:
            try:
                self.window_capture = WindowCapture(hwnd=hwnd)
            except Exception:
                pass

    def get_window_rect(self) -> Tuple[int, int, int, int]:
        rect = win32gui.GetClientRect(self.hwnd)
        return (rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1])

    def _get_title_bar_height(self) -> int:
        """计算标题栏高度（窗口高度 - 客户区高度）"""
        try:
            window_rect = win32gui.GetWindowRect(self.hwnd)
            client_rect = win32gui.GetClientRect(self.hwnd)
            window_h = window_rect[3] - window_rect[1]
            client_h = client_rect[3] - client_rect[1]
            return max(0, window_h - client_h)
        except Exception:
            return 0

    def _load_template(self, template_path: str) -> Optional[np.ndarray]:
        if template_path in self._template_cache:
            return self._template_cache[template_path]
        target = cv2.imread(template_path)
        if target is not None:
            self._template_cache[template_path] = target
        return target

    def capture_screenshot(self) -> Optional[np.ndarray]:
        if self.hidden_window:
            if self.window_capture:
                return self.window_capture.capture_window()
            return None
        # 前台模式：截取窗口矩形区域
        try:
            if not self.hwnd or not win32gui.IsWindow(self.hwnd):
                return None
            left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
            w, h = right - left, bottom - top
            if w <= 0 or h <= 0:
                return None
            img = pyautogui.screenshot(region=(left, top, w, h))
            arr = np.array(img)
            return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        except Exception:
            return None

    def find_template(self, template_path: str, threshold: float = None, region: Tuple = None) -> RecognitionResult:
        if threshold is None:
            threshold = self.threshold
        else:
            threshold = _normalize_threshold(threshold)

        return self._find_template_hidden(template_path, threshold, region)

    def _find_template_hidden(self, template_path: str, threshold: float, region: Tuple = None) -> RecognitionResult:
        screenshot = self.capture_screenshot()
        if screenshot is None:
            return RecognitionResult(found=False)

        try:
            target = self._load_template(template_path)
            if target is None:
                return RecognitionResult(found=False)

            h, w = target.shape[:2]
            sh, sw = screenshot.shape[:2]
            _, _, cw, ch = self.get_window_rect()
            title_bar = effective_client_dy(sh, ch, self._get_title_bar_height())

            # region 为客户区坐标；截图含标题栏时顶部需要先偏移（纯客户区截图偏移为0）
            search = screenshot
            offset_x, offset_y = 0, 0
            if region:
                rx, ry, rw, rh = region
                sh, sw = screenshot.shape[:2]
                x1, y1 = int(rx), int(ry) + title_bar
                x2, y2 = min(int(rx + rw), sw), min(int(ry + rh) + title_bar, sh)
                if x2 <= x1 or y2 <= y1:
                    return RecognitionResult(found=False)
                search = screenshot[y1:y2, x1:x2]
                offset_x, offset_y = x1, y1

            result = cv2.matchTemplate(search, target, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if max_val >= threshold:
                x1, y1 = max_loc[0] + offset_x, max_loc[1] + offset_y
                y1 = max(0, y1 - title_bar)
                return RecognitionResult(
                    found=True,
                    region=(x1, y1, w, h),
                    confidence=float(max_val),
                )
        except Exception as e:
            logger.error(f"模板匹配出错: {e}")

        return RecognitionResult(found=False)

    def find_text(self, target_text: str, confidence: float = 0.8) -> RecognitionResult:
        screenshot = self.capture_screenshot()
        if screenshot is None:
            return RecognitionResult(found=False)

        found, text_area, real_text = ocr_service.find_text(screenshot, target_text)
        if found and text_area:
            sh = screenshot.shape[0]
            _, _, _, ch = self.get_window_rect()
            title_bar = effective_client_dy(sh, ch, self._get_title_bar_height())
            xs = [p[0] for p in text_area]
            ys = [p[1] - title_bar for p in text_area]
            # OCR 返回的是 float 坐标，统一转 int，避免下游 randint/位运算报错
            # ('float' object cannot be interpreted as an integer)
            x, y = int(min(xs)), int(max(0, min(ys)))
            w, h = int(max(xs) - min(xs)), int(max(ys) - min(ys))
            w, h = max(0, w), max(0, h)
            return RecognitionResult(
                found=True,
                region=(x, y, w, h),
                text=real_text,
            )
        return RecognitionResult(found=False)

    def click(self, x: int, y: int, sync_mode: bool = False) -> None:
        """在客户区坐标 (x, y) 处执行点击"""
        # 防御：上游可能传入 float（OCR 坐标），位运算要求 int
        x, y = int(x), int(y)
        if self.hidden_window:
            if sync_mode and self.synchronizer and self.synchronizer.sync_enabled:
                # 同步模式：向主窗口和所有副窗口发送点击消息
                main_hwnd = self.synchronizer.main_window[0] if self.synchronizer.main_window else self.hwnd
                self.synchronizer.send_click_message(hwnd=main_hwnd, relative_x=x, relative_y=y)
                for sub_hwnd, _ in self.synchronizer.get_sub_windows():
                    self.synchronizer.send_click_message(hwnd=sub_hwnd, relative_x=x, relative_y=y)
            else:
                # 非同步模式：向当前窗口发送 PostMessage
                l_param = x | (y << 16)
                win32gui.PostMessage(self.hwnd, win32con.WM_MOUSEMOVE, 0, l_param)
                time.sleep(0.05)
                win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, l_param)
                time.sleep(0.2)
                win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONUP, 0, l_param)
        else:
            # 前台模式：客户区坐标 → 屏幕坐标后移动鼠标真实点击
            if sync_mode:
                logger.warn("前台模式不支持多窗口同步点击，仅执行本窗口点击（同步需后台模式）")
            try:
                if not self.hwnd or not win32gui.IsWindow(self.hwnd):
                    return
                win_left, win_top, _, _ = win32gui.GetWindowRect(self.hwnd)
                title_bar = self._get_title_bar_height()
                screen_x = win_left + x
                screen_y = win_top + title_bar + y
                foreground_click(screen_x, screen_y)
            except Exception:
                return

        time.sleep(random.uniform(1.5, 3.0))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5, sync_mode: bool = False) -> None:
        """在客户区坐标 (x1, y1) → (x2, y2) 处执行滑动"""
        try:
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        except (ValueError, TypeError):
            return
        try:
            duration = float(duration)
        except (ValueError, TypeError):
            duration = 0.5
        duration = max(0.0, duration)
        if self.hidden_window:
            if sync_mode and self.synchronizer and self.synchronizer.sync_enabled:
                # 同步模式：向主窗口和所有副窗口发送滑动消息
                main_hwnd = self.synchronizer.main_window[0] if self.synchronizer.main_window else self.hwnd
                targets = [main_hwnd] + [h for h, _ in self.synchronizer.get_sub_windows()]
                for hwnd in targets:
                    try:
                        if not hwnd or not win32gui.IsWindow(hwnd):
                            continue
                        self.synchronizer.send_mouse_move(hwnd, x1, y1)
                        self.synchronizer.send_mouse_down(hwnd, x1, y1)
                        time.sleep(0.05)
                        self.synchronizer.send_mouse_move(hwnd, x2, y2)
                        time.sleep(min(duration, 5.0))
                        self.synchronizer.send_mouse_up(hwnd, x2, y2)
                    except Exception:
                        continue
            else:
                # 非同步模式：向当前窗口发送 PostMessage
                try:
                    if not self.hwnd or not win32gui.IsWindow(self.hwnd):
                        return
                    l_param1 = x1 | (y1 << 16)
                    l_param2 = x2 | (y2 << 16)
                    win32gui.PostMessage(self.hwnd, win32con.WM_MOUSEMOVE, 0, l_param1)
                    win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, l_param1)
                    time.sleep(0.05)
                    win32gui.PostMessage(self.hwnd, win32con.WM_MOUSEMOVE, 0, l_param2)
                    time.sleep(min(duration, 5.0))
                    win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONUP, 0, l_param2)
                except Exception:
                    return
        else:
            # 前台模式：客户区坐标 → 屏幕坐标后真实拖拽
            if sync_mode:
                logger.warn("前台模式不支持多窗口同步滑动，仅执行本窗口滑动（同步需后台模式）")
            try:
                if not self.hwnd or not win32gui.IsWindow(self.hwnd):
                    return
                win_left, win_top, _, _ = win32gui.GetWindowRect(self.hwnd)
                title_bar = self._get_title_bar_height()
                human_drag(win_left + x1, win_top + title_bar + y1,
                           win_left + x2, win_top + title_bar + y2,
                           duration=duration)
            except Exception:
                return

        time.sleep(random.uniform(1.5, 3.0))
