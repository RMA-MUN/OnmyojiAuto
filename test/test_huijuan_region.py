"""Task9: 第28章右侧面板门控回归测试（纯逻辑，无需游戏窗口）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _fake_bot(size=(1404, 834)):
    from OAT.source.huijuanshuafen.base import BaseBot
    b = BaseBot.__new__(BaseBot)
    b._fake_size = size
    b.client_size = lambda: b._fake_size
    b.templates = {}
    b.images_dir = ""
    b._missing_warned = set()
    return b


def test_chapter28_region_is_right_panel():
    from OAT.source.huijuanshuafen.base import BaseBot, CHAPTER28_PANEL_FRAC
    b = BaseBot.__new__(BaseBot)
    b._fake_size = (1404, 834)
    b.client_size = lambda: b._fake_size
    x, y, w, h = BaseBot.chapter28_region(b)
    assert x >= 0.5 * 1404 and x + w <= 1404 and y >= 0 and y + h <= 834


def test_chapter28_panel_frac_constant():
    from OAT.source.huijuanshuafen.base import CHAPTER28_PANEL_FRAC
    assert tuple(CHAPTER28_PANEL_FRAC) == (0.55, 0.10, 0.45, 0.80)


def test_chapter28_region_within_bounds_small_client():
    from OAT.source.huijuanshuafen.base import BaseBot
    b = _fake_bot((800, 600))
    x, y, w, h = BaseBot.chapter28_region(b)
    assert x >= 0 and y >= 0 and w >= 0 and h >= 0
    assert x + w <= 800 and y + h <= 600
    assert x >= 0.5 * 800


def test_k28_score_on_missing_never_raises():
    b = _fake_bot()
    score, loc = b.k28_score_on(None, b.chapter28_region())
    assert score == 0.0 and loc is None
    import numpy as np
    shot = np.zeros((100, 100, 3), dtype=np.uint8)
    score, loc = b.k28_score_on(shot, b.chapter28_region())
    assert score == 0.0 and loc is None


def test_save_debug_shot_never_raises_without_capture():
    b = _fake_bot()
    b.engine = None  # _raw_capture 捕获异常返回 None
    assert b.save_debug_shot("unittest") is None


def test_chapter28_search_uses_panel_gate():
    import inspect
    from OAT.source.huijuanshuafen import explore as ex_mod
    from OAT.source.huijuanshuafen import huijuan as hj_mod
    assert "chapter28_region" in inspect.getsource(ex_mod.ExploreManager._find_chapter28_ocr)
    assert "chapter28_region" in inspect.getsource(ex_mod.ExploreManager._enter_chapter28_from_list)
    assert "chapter28_region" in inspect.getsource(hj_mod.HuiJuan._find_chapter28_on)
    assert "chapter28_region" in inspect.getsource(hj_mod.HuiJuan._find_chapter28_scroll)
