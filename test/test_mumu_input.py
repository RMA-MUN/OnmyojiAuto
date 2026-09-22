"""Task 5: lparam 打包 + 物理换算 + 消息序列（全 mock win32/IPC）。"""
import OAT.tools.emulator.mumu_input as mi


def _handle(scale=2.0):
    return type("H", (), {
        "control_hwnds": [100, 110], "scale_rate": scale})()


class _IpcRecorder:
    """记录 down/up 调用的最小 IPC 假件。"""

    def __init__(self):
        self.calls = []

    def down(self, x, y):
        self.calls.append(("down", x, y))

    def up(self):
        self.calls.append(("up",))


def test_pack_lparam():
    assert mi.pack_lparam(0x1234, 0x00AB) == (0x00AB << 16 | 0x1234)


def test_phys_divides_scale():
    assert mi.phys(_handle(2.0), 100, 50) == (50, 25)


def test_phys_zero_scale_guards():
    assert mi.phys(_handle(0), 100, 50) == (100, 50)


def test_click_uses_ipc_when_present():
    ipc = _IpcRecorder()
    inp = mi.MumuInput(_handle(), ipc=ipc)
    inp.click(1280, 720)
    assert ipc.calls[0][0] == "down" and ipc.calls[-1] == ("up",)


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


def test_down_move_up_with_ipc_continue_drag():
    """有 IPC：down/拖动中的 move 都走 ipc.down 续点，up 走 ipc.up；悬停无能力则不发。"""
    ipc = _IpcRecorder()
    inp = mi.MumuInput(_handle(1.0), ipc=ipc)
    inp.down(10, 20)
    inp.move(30, 40, pressed=True)
    inp.move(50, 60, pressed=False)
    inp.up(70, 80)
    assert ipc.calls == [("down", 10, 20), ("down", 30, 40), ("up",)]


def test_down_move_up_without_ipc_hits_control_child(monkeypatch):
    """无 IPC：按下/拖动/抬起都打 control 子句柄（深层），坐标按 scale 换算。"""
    sent, posted = [], []
    monkeypatch.setattr(mi, "_send", lambda h, m, w, l: sent.append((h, m, w, l)))
    monkeypatch.setattr(mi, "_post", lambda h, m, w, l: posted.append((h, m, w, l)))
    import win32con
    inp = mi.MumuInput(_handle(2.0), ipc=None)
    inp.down(100, 50)
    inp.move(200, 100, pressed=True)
    inp.up(300, 150)

    assert [h for h, *_ in sent] == [110, 110, 110]  # 子句柄，不是根窗口 100
    assert [m for _h, m, *_ in sent] == [win32con.WM_ACTIVATE,
                                         win32con.WM_LBUTTONDOWN,
                                         win32con.WM_LBUTTONUP]
    assert posted[0][1] == win32con.WM_MOUSEMOVE
    assert posted[0][2] == win32con.MK_LBUTTON
    assert posted[0][3] == mi.pack_lparam(100, 50)  # 200/2, 100/2
