"""同步器 → 模拟器：鼠标输入按实例路由到 EmulatorBackend（参考挑战链路）。

模拟器实例的句柄树：root（表格里那个）→ shot 子窗口；输入必须走 backend
（IPC 或 control 子句柄），PostMessage 给 root 是打不进去的。
"""
import win32con

import OAT.tools.WindowSynchronizer as ws


class _FakeBackend:
    def __init__(self, hwnds=()):
        self._hwnds = [int(h) for h in hwnds]
        self.calls = []

    def instance_hwnds(self):
        return list(self._hwnds)

    def click(self, x, y):
        self.calls.append(("click", x, y))

    def move(self, x, y, pressed=False):
        self.calls.append(("move", x, y, pressed))

    def down(self, x, y):
        self.calls.append(("down", x, y))

    def up(self, x, y):
        self.calls.append(("up", x, y))


def _spy_post(monkeypatch):
    posted = []
    monkeypatch.setattr(ws.win32gui, "PostMessage", lambda h, m, w, l: posted.append((h, m, w, l)))
    monkeypatch.setattr(ws.win32gui, "IsWindow", lambda h: True)
    return posted


def _patch_build_handle(monkeypatch, mumu_hwnd=None):
    """MuMu 句柄树校验：mumu_hwnd=None 表示所有句柄都当模拟器，否则只有它一个。"""
    import OAT.tools.emulator.mumu_handle as mh

    def _build(hwnd, wait_tries=1):
        if mumu_hwnd is None or int(hwnd) == int(mumu_hwnd):
            return object()
        raise ValueError(f"not a MuMu window tree: {hwnd}")

    monkeypatch.setattr(mh, "build_handle", _build)


def test_emulator_drag_routes_to_backend_and_skips_post_message(monkeypatch):
    """注入挑战用的 backend 后：拖拽的 down/move/up 走 backend，不再 PostMessage。"""
    sync = ws.WindowSynchronizer()
    backend = _FakeBackend([1111])
    sync.backend = backend
    sync.sub_windows = [(1111, "模拟器 · MuMu安卓设备-1 (实例1)")]
    posted = _spy_post(monkeypatch)

    sync.send_mouse_down(1111, 10, 20)
    sync.send_mouse_move_to_all(30, 40, pressed=True)
    sync.send_mouse_up(1111, 50, 60)

    assert backend.calls == [("down", 10, 20), ("move", 30, 40, True), ("up", 50, 60)]
    assert posted == []


def test_emulator_click_routes_to_backend(monkeypatch):
    """点击链路沿用同一套路由（挑战流程注入的 backend 也在这里生效）。"""
    sync = ws.WindowSynchronizer()
    backend = _FakeBackend([1111])
    sync.backend = backend
    posted = _spy_post(monkeypatch)

    sync.send_click_message(1111, 10, 20)

    assert backend.calls == [("click", 10, 20)]
    assert posted == []


def test_backend_resolved_lazily_for_mumu_window(monkeypatch):
    """没有注入 backend 时，MuMu 句柄树自动解析出实例 backend（同步器单独可用）。"""
    import OAT.tools.emulator.backend as eb
    sync = ws.WindowSynchronizer()
    backend = _FakeBackend([3333])
    monkeypatch.setattr(eb, "create_backend", lambda kind, **kw: backend)
    _patch_build_handle(monkeypatch)
    posted = _spy_post(monkeypatch)

    sync.send_mouse_down(3333, 1, 2)
    sync.send_mouse_up(3333, 1, 2)

    assert backend.calls == [("down", 1, 2), ("up", 1, 2)]
    assert posted == []


def test_pc_window_falls_back_to_window_messages(monkeypatch):
    """PC 窗口过不了句柄树校验 → 回落旧的消息发送链路。"""
    sync = ws.WindowSynchronizer()
    _patch_build_handle(monkeypatch, mumu_hwnd=1111)
    posted = _spy_post(monkeypatch)

    sync.send_mouse_down(2222, 10, 20)

    assert [m for _h, m, _w, _l in posted] == [win32con.WM_LBUTTONDOWN]
    assert posted[0][0] == 2222


def test_failed_resolution_attempted_once(monkeypatch):
    """PC 窗口每次鼠标移动都重试句柄树校验会拖慢同步，失败结果必须缓存。"""
    import OAT.tools.emulator.mumu_handle as mh
    sync = ws.WindowSynchronizer()
    attempted = []

    def _boom(hwnd, wait_tries=1):
        attempted.append(int(hwnd))
        raise ValueError("not a MuMu window tree")

    monkeypatch.setattr(mh, "build_handle", _boom)
    _spy_post(monkeypatch)

    sync.send_mouse_down(2222, 1, 2)
    sync.send_mouse_move_to_all(3, 4, pressed=True)
    sync.send_mouse_up(2222, 5, 6)

    assert attempted == [2222]
