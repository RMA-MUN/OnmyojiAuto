"""绘卷刷分全局识别：任何场景下冒出的关闭钮都要无条件点掉（纯逻辑，无需游戏窗口）。"""
import json
import os


def _fake_bot(find_result=None):
    from OAT.source.huijuanshuafen.base import BaseBot

    class _Engine:
        hwnd = 12345

    b = BaseBot.__new__(BaseBot)
    b.engine = _Engine()
    b.sync_mode = False
    b.templates = {}
    b.images_dir = ""
    b._missing_warned = set()
    b.clicked = []
    b.click_center = lambda rect, **kw: b.clicked.append(tuple(rect)) or (rect[0] + rect[2] // 2, rect[1] + rect[3] // 2)
    b.find_img = lambda name, **kw: find_result if name == "global_xiezhu" else None
    return b


def test_global_template_registered():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tpl_path = os.path.join(root, "OAT", "source", "huijuanshuafen", "images", "templates.json")
    with open(tpl_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["templates"]["global_xiezhu"] == "xiezhu_global.png"
    img = os.path.join(root, "OAT", "source", "huijuanshuafen", "images", "xiezhu_global.png")
    assert os.path.exists(img)


def test_check_global_popup_clicks_center():
    from OAT.pipeline.recognition import RecognitionResult

    r = RecognitionResult(found=True, region=(10, 20, 30, 40), confidence=0.9)
    b = _fake_bot(find_result=r)
    assert b.check_global_popup() is True
    assert b.clicked == [(10, 20, 30, 40)]


def test_check_global_popup_miss_returns_false():
    b = _fake_bot(find_result=None)
    assert b.check_global_popup() is False
    assert b.clicked == []


def test_check_global_popup_never_raises_without_template():
    from OAT.source.huijuanshuafen.base import BaseBot

    b = BaseBot.__new__(BaseBot)
    b.engine = object()
    b.sync_mode = False
    b.templates = {}
    b.images_dir = ""
    b._missing_warned = set()
    b.find_img = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    assert b.check_global_popup() is False
