"""Task E1: ch28 k28 阈值 0.85 回归测试（0.897 取证分必须命中）。

纯逻辑 + stub engine，不碰真窗口/真 OCR。cv2 真跑（构造全黑图），
只把 minMaxLoc 打桩为取证分，验证阈值门限与调用点 wiring。
"""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from OAT.source.huijuanshuafen.base import CHAPTER28_K28_THRESHOLD
from OAT.source.huijuanshuafen.explore import ExploreManager
from OAT.source.huijuanshuafen.huijuan import HuiJuan


class _StubEngine:
    """find_template 按给定 score 与传入 threshold 比较，记录每次传入的阈值。"""

    def __init__(self, score=0.897):
        self.score = score
        self.thresholds = []
        self.clicked = []

    def get_window_rect(self):
        return (0, 0, 1920, 1080)

    def click(self, x, y, sync_mode=False):
        self.clicked.append((x, y))

    def find_template(self, path, threshold=None, region=None):
        self.thresholds.append(threshold)
        eff = 0.9 if threshold is None else threshold
        if self.score >= eff:
            return SimpleNamespace(found=True, region=(1100, 200, 60, 24),
                                   confidence=self.score)
        return SimpleNamespace(found=False, region=None, confidence=self.score)


def test_k28_threshold_constant_is_085():
    assert CHAPTER28_K28_THRESHOLD == 0.85


def test_explore_k28_fallback_hits_at_0897(tmp_path):
    (tmp_path / "k28.png").write_bytes(b"\x89PNG\r\n\x1a\n")  # 仅需存在；匹配由 stub 完成
    eng = _StubEngine(score=0.897)
    mgr = ExploreManager(engine=eng, templates={"k28": "k28.png"},
                         images_dir=str(tmp_path))
    mgr._find_chapter28_ocr = lambda: None  # 直达 k28 模板兜底
    ok = mgr._enter_chapter28_from_list(timeout=2)
    assert ok is False  # title_28 无素材 → 验证失败，但 k28 必须已被点击
    assert len(eng.clicked) == 1
    assert CHAPTER28_K28_THRESHOLD in eng.thresholds


def test_explore_k28_fallback_misses_below_threshold(tmp_path):
    (tmp_path / "k28.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    eng = _StubEngine(score=0.84)
    mgr = ExploreManager(engine=eng, templates={"k28": "k28.png"},
                         images_dir=str(tmp_path))
    mgr._find_chapter28_ocr = lambda: None
    assert mgr._enter_chapter28_from_list(timeout=2) is False
    assert eng.clicked == []


def _make_huijuan(tmp_path):
    import cv2
    import numpy as np
    cv2.imwrite(str(tmp_path / "k28.png"), np.zeros((20, 20, 3), dtype=np.uint8))
    shot = np.zeros((1080, 1920, 3), dtype=np.uint8)
    eng = _StubEngine()
    bot = HuiJuan(engine=eng, templates={"k28": "k28.png"},
                  images_dir=str(tmp_path))
    bot._ocr_on = lambda *a, **k: (None, None)  # 直达 k28 图像兜底
    return bot, shot


def test_huijuan_k28_fallback_hits_at_0897(tmp_path, monkeypatch):
    import cv2
    bot, shot = _make_huijuan(tmp_path)
    monkeypatch.setattr(cv2, "minMaxLoc", lambda r: (0.0, 0.897, (0, 0), (5, 5)))
    center, via = bot._find_chapter28_on(shot)
    assert via == "k28"
    assert center is not None


def test_huijuan_k28_fallback_misses_below_threshold(tmp_path, monkeypatch):
    import cv2
    bot, shot = _make_huijuan(tmp_path)
    monkeypatch.setattr(cv2, "minMaxLoc", lambda r: (0.0, 0.84, (0, 0), (5, 5)))
    center, via = bot._find_chapter28_on(shot)
    assert (center, via) == (None, None)
