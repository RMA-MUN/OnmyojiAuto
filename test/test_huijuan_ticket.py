"""绘卷刷分突破券识别：模拟器适配 + 部分读取回归测试（纯逻辑，无需游戏窗口）。

回归背景（真机实测 2026-09-19）:
- 模拟器(backend)截图下，原 config ticket_region [800,10,115,50] 裁剪过紧，
  RapidOCR 检测框只读到 '/30'，丢了前导 '1'；
- _ocr_ticket_text 接受 '/30'（含 "/30"）返回，导致全宽兜底永远不执行，
  _parse_ticket_number('/30') 返回 -1 → 识别失败。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np


def _fake_engine(shot, has_backend=True):
    class _Engine:
        def __init__(self):
            self.backend = object() if has_backend else None
            self.hwnd = 12345

        def capture_screenshot(self):
            return self._shot

        def get_window_rect(self):
            h, w = self._shot.shape[:2]
            return (0, 0, w, h)

        def _get_title_bar_height(self):
            return 0

    e = _Engine()
    e._shot = shot
    return e


def _fake_bot(shot, has_backend=True, config=None):
    from OAT.source.huijuanshuafen.huijuan import HuiJuan
    b = HuiJuan.__new__(HuiJuan)
    b.engine = _fake_engine(shot, has_backend)
    b.config = config or {}
    b.sync_mode = False
    b.templates = {}
    b.images_dir = ""
    b._missing_warned = set()
    return b


class _OcrResult:
    def __init__(self, txts):
        self.txts = list(txts)
        self.boxes = [[[0, 0], [10, 0], [10, 10], [0, 10]] for _ in txts]


def _patch_ocr(monkeypatch, reader):
    import OAT.utils.OCRService as svc_mod
    mgr = svc_mod.ocr_service.ocr_manager
    monkeypatch.setattr(mgr, "_init_reader", lambda: None)
    monkeypatch.setattr(mgr, "reader", reader)


def test_ticket_region_fraction_for_emulator_backend():
    from OAT.source.huijuanshuafen.huijuan import HuiJuan, TICKET_REGION_FRAC
    assert tuple(TICKET_REGION_FRAC) == (0.55, 0.0, 0.15, 0.11)
    shot = np.zeros((500, 1000, 3), dtype=np.uint8)
    b = _fake_bot(shot, has_backend=True)
    assert b._ticket_region(shot) == (550, 0, 150, 55)


def test_ticket_region_uses_config_for_pc():
    shot = np.zeros((500, 1000, 3), dtype=np.uint8)
    b = _fake_bot(shot, has_backend=False, config={"ticket_region": [800, 10, 115, 50]})
    assert b._ticket_region(shot) == (800, 10, 115, 50)


def test_ocr_ticket_text_rejects_partial_slash30(monkeypatch):
    shot = np.zeros((200, 400, 3), dtype=np.uint8)
    b = _fake_bot(shot)
    _patch_ocr(monkeypatch, lambda crop: _OcrResult(["/30"]))
    assert b._ocr_ticket_text(shot, (220, 0, 60, 22)) == ""


def test_ocr_ticket_text_accepts_full_number(monkeypatch):
    shot = np.zeros((200, 400, 3), dtype=np.uint8)
    b = _fake_bot(shot)
    _patch_ocr(monkeypatch, lambda crop: _OcrResult(["/30", "1/30"]))
    assert b._ocr_ticket_text(shot, (220, 0, 60, 22)) == "1/30"


def test_get_ticket_count_uses_full_strip_when_region_partial(monkeypatch):
    shot = np.zeros((200, 400, 3), dtype=np.uint8)

    def fake_reader(crop):
        # 区域裁剪（窄）模拟真机 RapidOCR 丢前导数字；全宽条带正常
        if crop.shape[1] < 100:
            return _OcrResult(["/30"])
        return _OcrResult(["/30", "1/30"])

    b = _fake_bot(shot)
    _patch_ocr(monkeypatch, fake_reader)
    assert b._get_ticket_count() == 1
