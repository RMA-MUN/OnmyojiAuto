"""GetDC 冷却锁存回归：一次失败后，成功截图或超时必须自动恢复。"""
import time

import numpy as np

from OAT.tools.GetDC import WindowCapture


def _fake_capture():
    cap = WindowCapture.__new__(WindowCapture)
    cap.hwnd = 12345
    cap.last_capture_mode = None
    cap.last_shot_shape = None
    cap._capture_cooldown = False
    cap._cooldown_duration = 30.0
    cap._last_capture_failure = 0.0
    return cap


def test_success_clears_cooldown(monkeypatch):
    # 非冷却态成功截图后必须保持非冷却（成功路径不得误置锁存）
    cap = _fake_capture()
    cap._capture_cooldown = False
    cap.is_window_minimized = lambda: False
    monkeypatch.setattr("OAT.tools.GetDC.settings.BACKEND_GET_IMG_MODE", "PrintWindow", raising=False)
    cap.capture_window_printwindow = lambda region=None: np.full((4, 4, 3), 100, dtype=np.uint8)
    img = cap.capture_window(capture_mode="PrintWindow")
    assert img is not None
    assert cap._capture_cooldown is False


def test_cooldown_expires_after_duration(monkeypatch):
    cap = _fake_capture()
    cap._capture_cooldown = True
    cap._last_capture_failure = time.time() - 31.0
    cap.is_window_minimized = lambda: False
    monkeypatch.setattr("OAT.tools.GetDC.settings.BACKEND_GET_IMG_MODE", "PrintWindow", raising=False)
    cap.capture_window_printwindow = lambda region=None: np.full((4, 4, 3), 100, dtype=np.uint8)
    img = cap.capture_window(capture_mode="PrintWindow")
    assert img is not None
    assert cap._capture_cooldown is False


def test_cooldown_blocks_within_duration():
    cap = _fake_capture()
    cap._capture_cooldown = True
    cap._last_capture_failure = time.time()
    assert cap.capture_window(capture_mode="PrintWindow") is None
