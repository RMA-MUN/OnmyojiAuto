"""Task 5: lparam 打包 + 物理换算 + 消息序列（全 mock win32/IPC）。"""
import OAT.tools.emulator.mumu_input as mi


def _handle(scale=2.0):
    return type("H", (), {
        "control_hwnds": [100, 110], "scale_rate": scale})()


def test_pack_lparam():
    assert mi.pack_lparam(0x1234, 0x00AB) == (0x00AB << 16 | 0x1234)


def test_phys_divides_scale():
    assert mi.phys(_handle(2.0), 100, 50) == (50, 25)


def test_phys_zero_scale_guards():
    assert mi.phys(_handle(0), 100, 50) == (100, 50)


def test_click_uses_ipc_when_present():
    calls = []

    class _Ipc:
        def down(self, x, y):
            calls.append(("down", x, y))

        def up(self):
            calls.append(("up",))

    inp = mi.MumuInput(_handle(), ipc=_Ipc())
    inp.click(1280, 720)
    assert calls[0][0] == "down" and calls[-1] == ("up",)


def test_ipc_coords_scaled_to_native():
    """客户区坐标 → IPC 原生坐标：窗口缩放（1386x780 vs 1280x720）时按比例换算。"""
    calls = []

    class _Ipc:
        width = 1280
        height = 720

        def get_resolution(self):
            pass

        def down(self, x, y):
            calls.append(("down", x, y))

        def up(self):
            calls.append(("up",))

    class _H:
        control_hwnds = [1, 2]
        scale_rate = 1.0
        client_w = 1386
        client_h = 780

    inp = mi.MumuInput(_H(), ipc=_Ipc())
    inp.click(1386, 780)
    assert calls[0] == ("down", 1280, 720)


def test_click_posts_send_sequence_without_ipc(monkeypatch):
    seq = []
    monkeypatch.setattr(mi, "_send", lambda h, m, w, l: seq.append((h, m)))
    monkeypatch.setattr(mi, "_sleep", lambda s: None)
    import win32con
    inp = mi.MumuInput(_handle(1.0), ipc=None)
    inp.click(10, 20)
    msgs = [m for _, m in seq]
    assert msgs[0] == win32con.WM_ACTIVATE
    assert win32con.WM_LBUTTONDOWN in msgs and win32con.WM_LBUTTONUP in msgs
