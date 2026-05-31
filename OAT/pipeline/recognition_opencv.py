import random
import time
from typing import Optional, Tuple

import cv2
import numpy as np
import win32gui
import win32con

from OAT.tools.GetDC import WindowCapture
from OAT.tools import settings
from OAT.utils.OCRService import ocr_service
from OAT.utils.logging import logger
from .recognition import RecognitionEngine, RecognitionResult


class OpenCVRecognitionEngine(RecognitionEngine):
    """基于 OpenCV 模板匹配 + RapidOCR 的识别引擎"""

    def __init__(
        self,
        hwnd: int,
        threshold: float = None,
        find_mode: str = None,
        synchronizer=None,
    ):
        self.hwnd = hwnd
        self.threshold = threshold if threshold is not None else settings.FIND_THRESHOLD / 100.0
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

    def capture_screenshot(self) -> Optional[np.ndarray]:
        if self.window_capture:
            return self.window_capture.capture_window()
        return None

    def find_template(self, template_path: str, threshold: float = None) -> RecognitionResult:
        if threshold is None:
            threshold = self.threshold

        if self.window_capture:
            return self._find_template_hidden(template_path, threshold)
        return RecognitionResult(found=False)

    def _find_template_hidden(self, template_path: str, threshold: float) -> RecognitionResult:
        screenshot = self.window_capture.capture_window()
        if screenshot is None:
            return RecognitionResult(found=False)

        try:
            target = cv2.imread(template_path)
            if target is None:
                return RecognitionResult(found=False)

            h, w = target.shape[:2]
            result = cv2.matchTemplate(screenshot, target, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if max_val >= threshold:
                x1, y1 = max_loc[0], max_loc[1]
                title_bar = self._get_title_bar_height()
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
        if not self.window_capture:
            return RecognitionResult(found=False)

        screenshot = self.window_capture.capture_window()
        if screenshot is None:
            return RecognitionResult(found=False)

        found, text_area, real_text = ocr_service.find_text(screenshot, target_text)
        if found and text_area:
            title_bar = self._get_title_bar_height()
            xs = [p[0] for p in text_area]
            ys = [p[1] - title_bar for p in text_area]
            x, y = min(xs), max(0, min(ys))
            w, h = max(xs) - x, max(ys) - y
            return RecognitionResult(
                found=True,
                region=(x, y, w, h),
                text=real_text,
            )
        return RecognitionResult(found=False)

    def click(self, x: int, y: int, sync_mode: bool = False) -> None:
        """在客户区坐标 (x, y) 处执行点击"""
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

        time.sleep(random.uniform(1.5, 3.0))
