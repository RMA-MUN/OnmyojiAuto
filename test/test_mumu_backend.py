"""Task 7: MumuBackend 组装（假 handle/假 capture/假 input/假 IPC，全 mock）。"""
import numpy as np

from OAT.tools.emulator import backend as B
from OAT.tools.emulator.mumu_backend import MumuBackend, is_admin


class _H:
    root_hwnd = 100
    root_title = "MuMu模拟器12"
    shot_hwnd = 110
    control_hwnds = [100, 110]
    scale_rate = 1.0
    client_w, client_h = 1280, 720


class _Cap:
    def __init__(self, h, ipc=None):
        self.calls = 0

    def capture(self):
        self.calls += 1
        return np.zeros((720, 1280, 3), dtype=np.uint8)


class _Inp:
    def __init__(self, h, ipc=None):
        self.clicked = []

    def click(self, x, y, fast=False):
        self.clicked.append((x, y))

    def long_click(self, x, y, d):
        self.clicked.append(("long", x, y, d))

    def swipe(self, x1, y1, x2, y2, duration=0.5):
        self.clicked.append(("swipe", x1, y1, x2, y2))

    def down(self, x, y):
        self.clicked.append(("down", x, y))

    def move(self, x, y, pressed=False):
        self.clicked.append(("move", x, y, pressed))

    def up(self, x, y):
        self.clicked.append(("up", x, y))


def _make(monkeypatch):
    monkeypatch.setattr("OAT.tools.emulator.mumu_handle.enum_mumu_windows",
                        lambda: [(100, "MuMu模拟器12")])
    # resolve_auto 三级解析全部封死，保证不碰真实窗口/cli/进程表
    monkeypatch.setattr("OAT.tools.emulator.mumu_handle.query_cli_windows", lambda f: [])
    monkeypatch.setattr("OAT.tools.emulator.mumu_handle.enum_mumu_by_process", lambda: [])
    monkeypatch.setattr("OAT.tools.emulator.mumu_backend.build_handle", lambda s: _H())
    monkeypatch.setattr("OAT.tools.emulator.mumu_backend.MumuCapture", _Cap)
    monkeypatch.setattr("OAT.tools.emulator.mumu_backend.MumuInput", _Inp)
    monkeypatch.setattr("OAT.tools.emulator.mumu_backend.find_ipc_dll", lambda *a, **k: None)
    return MumuBackend(handle_spec="auto", instance_index=0, mumu_folder="X")


def test_screenshot_shape(monkeypatch):
    b = _make(monkeypatch)
    img = b.screenshot()
    assert img.shape == (720, 1280, 3)
    assert b.instance_hwnds() == [100]


def test_click_delegates(monkeypatch):
    b = _make(monkeypatch)
    b.click(100, 200)
    assert (100, 200) in b._input.clicked


def test_down_move_up_delegate(monkeypatch):
    """同步器拖拽需要的三个原语转发到 MumuInput。"""
    b = _make(monkeypatch)
    b.down(10, 20)
    b.move(30, 40, pressed=True)
    b.up(50, 60)
    assert b._input.clicked == [("down", 10, 20), ("move", 30, 40, True), ("up", 50, 60)]


def test_factory_returns_mumu(monkeypatch):
    _make(monkeypatch)
    b = B.create_backend("mumu12", handle_spec="auto")
    assert isinstance(b, MumuBackend)


def test_is_admin_bool():
    assert isinstance(is_admin(), bool)


def test_is_elevated_attr(monkeypatch):
    b = _make(monkeypatch)
    assert b.is_elevated == is_admin()


def test_ipc_gets_resolved_instance_id(monkeypatch):
    seen = {}

    class _FakeIpc:
        def __init__(self, dll_path, instance_id, mumu_root=""):
            seen["dll_path"] = dll_path
            seen["instance_id"] = instance_id
            seen["mumu_root"] = mumu_root

        def connect(self):
            pass

        def disconnect(self):
            pass

    class _H2:
        root_hwnd = 200
        root_title = "MuMu安卓设备"
        shot_hwnd = 210
        control_hwnds = [200, 210]
        scale_rate = 1.0
        client_w, client_h = 1280, 720

    monkeypatch.setattr("OAT.tools.emulator.mumu_handle.enum_mumu_windows",
                        lambda: [(100, "MuMu模拟器12"), (200, "MuMu安卓设备")])
    monkeypatch.setattr("OAT.tools.emulator.mumu_handle.query_cli_windows", lambda f: [])
    monkeypatch.setattr("OAT.tools.emulator.mumu_handle.enum_mumu_by_process", lambda: [])
    monkeypatch.setattr("OAT.tools.emulator.mumu_backend.build_handle", lambda s: _H2())
    monkeypatch.setattr("OAT.tools.emulator.mumu_backend.MumuCapture", _Cap)
    monkeypatch.setattr("OAT.tools.emulator.mumu_backend.MumuInput", _Inp)
    monkeypatch.setattr("OAT.tools.emulator.mumu_backend.find_ipc_dll",
                        lambda *a, **k: "C:\\fake\\external_renderer_ipc.dll")
    monkeypatch.setattr("OAT.tools.emulator.mumu_backend.NemuIpc", _FakeIpc)
    b = MumuBackend(handle_spec="auto", instance_index=1, mumu_folder="X")
    assert seen["instance_id"] == 1
    assert seen["dll_path"] == "C:\\fake\\external_renderer_ipc.dll"
    assert b.instance_hwnds() == [200]
