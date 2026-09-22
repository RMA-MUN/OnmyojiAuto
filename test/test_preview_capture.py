"""预览取图路由与最小化提示节流回归。

背景：MuMu 句柄走后台通道（PrintWindow→IPC→BitBlt，最小化可预览），
PC 客户端最小化时由截图链路统一弹窗提示（30s 全局节流）。
"""
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _fake_window():
    from OAT.app.main_window import MainWindow
    return MainWindow.__new__(MainWindow)


class _FakeBackend:
    def __init__(self, img):
        self.img = img
        self.closed = False

    def screenshot(self):
        return self.img

    def close(self):
        self.closed = True


class _FakeWindowCapture:
    last_hwnd = None

    def __init__(self, hwnd=None):
        _FakeWindowCapture.last_hwnd = hwnd

    def capture_window(self, *args, **kwargs):
        return "fallback_img"


def test_mumu_hwnd_routes_to_backend(monkeypatch):
    import OAT.app.main_window as mw
    img = np.full((4, 4, 3), 9, dtype=np.uint8)
    backend = _FakeBackend(img)
    specs = []

    def fake_create_backend(emulator_type, **kwargs):
        assert emulator_type == "mumu12"
        specs.append(kwargs)
        return backend

    monkeypatch.setattr(
        "OAT.tools.emulator.mumu_handle.build_handle",
        lambda h, wait_tries=10: object(), raising=False)
    monkeypatch.setattr(
        "OAT.tools.emulator.backend.create_backend",
        fake_create_backend, raising=False)
    got = mw.MainWindow._capture_preview_frame(_fake_window(), 12345)
    assert got is img
    assert backend.closed is True
    assert specs and specs[0]["handle_spec"] == 12345


def test_non_mumu_hwnd_falls_back_to_window_capture(monkeypatch):
    import OAT.app.main_window as mw

    def boom(h, wait_tries=10):
        raise RuntimeError("not mumu")

    monkeypatch.setattr(
        "OAT.tools.emulator.mumu_handle.build_handle", boom, raising=False)
    monkeypatch.setattr(mw, "WindowCapture", _FakeWindowCapture)
    got = mw.MainWindow._capture_preview_frame(_fake_window(), 888)
    assert got == "fallback_img"
    assert _FakeWindowCapture.last_hwnd == 888


def test_backend_none_falls_back_to_window_capture(monkeypatch):
    import OAT.app.main_window as mw
    backend = _FakeBackend(None)

    monkeypatch.setattr(
        "OAT.tools.emulator.mumu_handle.build_handle",
        lambda h, wait_tries=10: object(), raising=False)
    monkeypatch.setattr(
        "OAT.tools.emulator.backend.create_backend",
        lambda t, **k: backend, raising=False)
    monkeypatch.setattr(mw, "WindowCapture", _FakeWindowCapture)
    got = mw.MainWindow._capture_preview_frame(_fake_window(), 777)
    assert got == "fallback_img"
    assert backend.closed is True


def test_minimized_warning_throttled(monkeypatch):
    import OAT.tools.GetDC as G

    pops = []
    monkeypatch.setattr(G, "warning_box", lambda msg: pops.append(msg), raising=False)
    monkeypatch.setattr(G, "_minimize_warn_ts", 0.0)
    G.warn_minimized_capture()
    G.warn_minimized_capture()  # 节流窗口内不再弹
    assert len(pops) == 1
    assert "最小化" in pops[0]
    monkeypatch.setattr(G, "_minimize_warn_ts", time.time() - 31.0)
    G.warn_minimized_capture()
    assert len(pops) == 2
