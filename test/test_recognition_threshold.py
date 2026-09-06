"""管道模板阈值归一化回归测试（settings 用 0-100 百分比，matchTemplate 用 0-1）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from OAT.pipeline.recognition_opencv import OpenCVRecognitionEngine


def test_engine_threshold_percent_normalized():
    engine = OpenCVRecognitionEngine(hwnd=None, threshold=90)
    assert engine.threshold == 0.9


def test_engine_threshold_ratio_kept():
    engine = OpenCVRecognitionEngine(hwnd=None, threshold=0.85)
    assert engine.threshold == 0.85


def test_engine_default_threshold_from_settings():
    from OAT.tools import settings
    engine = OpenCVRecognitionEngine(hwnd=None)
    assert engine.threshold == settings.FIND_THRESHOLD / 100.0
    assert 0.0 < engine.threshold <= 1.0


def test_engine_hidden_flag_and_foreground_safe_without_hwnd():
    from OAT.pipeline.recognition_opencv import OpenCVRecognitionEngine
    bg = OpenCVRecognitionEngine(hwnd=None, threshold=90)
    assert bg.hidden_window is True and bg.threshold == 0.9
    fg = OpenCVRecognitionEngine(hwnd=None, threshold=90, hidden_window=False)
    assert fg.hidden_window is False
    assert fg.capture_screenshot() is None
    assert fg.find_template("nonexistent.png").found is False
    fg.click(100, 200)  # must not raise with hwnd=None


def test_foreground_uses_shared_primitives():
    import inspect
    import OAT.tools.human_click as hc
    import OAT.tools.OnmyojiAuto as oa
    assert callable(hc.foreground_click) and callable(hc.win32_double_click)
    src = inspect.getsource(oa.OnmyojiAutomation._win32_double_click)
    assert "human_click" in src or "win32_double_click" in src
