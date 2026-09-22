"""Task 3: DLL 定位顺序 + IPC 坐标翻转（不加载真 DLL）。"""
import OAT.tools.emulator.nemu_ipc as ni


def test_candidate_order():
    assert ni.DLL_CANDIDATES[0] == "nx_main/sdk/external_renderer_ipc.dll"
    assert len(ni.DLL_CANDIDATES) == 4


def test_find_prefers_first(tmp_path):
    root = tmp_path / "MuMuPlayer"
    second = root / ni.DLL_CANDIDATES[1]
    second.parent.mkdir(parents=True)
    second.write_bytes(b"x")
    assert ni.find_ipc_dll(str(root)).replace("\\", "/").endswith(ni.DLL_CANDIDATES[1])


def test_find_first_wins(tmp_path):
    root = tmp_path / "MuMuPlayer"
    for c in (ni.DLL_CANDIDATES[0], ni.DLL_CANDIDATES[1]):
        p = root / c
        p.parent.mkdir(parents=True)
        p.write_bytes(b"x")
    assert ni.find_ipc_dll(str(root)).replace("\\", "/").endswith(ni.DLL_CANDIDATES[0])


def test_find_none(tmp_path):
    assert ni.find_ipc_dll(str(tmp_path / "empty")) is None


def test_override(tmp_path):
    dll = tmp_path / "custom.dll"
    dll.write_bytes(b"x")
    assert ni.find_ipc_dll("whatever", override=str(dll)) == str(dll)


def test_down_forwards_contact_plus_one():
    """down() 必须按 MAA 同款语义转发 contact+1（弥补 convert_xy 删除后的坐标链路覆盖）。"""
    ipc = ni.NemuIpc.__new__(ni.NemuIpc)
    calls = {}

    class FakeLib:
        def nemu_input_event_finger_touch_down(self, cid, did, contact1, x, y):
            calls.update(cid=cid, did=did, contact1=contact1, x=x, y=y)
            return 0

    ipc.lib = FakeLib()
    ipc.connect_id = 7
    ipc.display_id = 3
    ipc.width = 1280
    ipc.height = 720
    ipc.down(100, 200, contact=0)
    assert (calls["cid"], calls["did"], calls["contact1"], calls["x"], calls["y"]) == (7, 3, 1, 100, 200)

    ipc.down(10, 20, contact=2)
    assert calls["contact1"] == 3


def test_down_raises_on_failure():
    ipc = ni.NemuIpc.__new__(ni.NemuIpc)

    class FailLib:
        def nemu_input_event_finger_touch_down(self, *a):
            return 1

    ipc.lib = FailLib()
    ipc.connect_id = 7
    ipc.display_id = 0
    ipc.width = 1280
    ipc.height = 720
    try:
        ipc.down(0, 0)
    except ni.NemuIpcError:
        return
    raise AssertionError("expected NemuIpcError")


def test_refresh_display_id_fallback_keeps_old():
    """nemu_get_display_id 抛异常时必须保持原 display_id（后台识别兜底）。"""
    ipc = ni.NemuIpc.__new__(ni.NemuIpc)

    class BoomLib:
        def nemu_get_display_id(self, *a):
            raise RuntimeError("boom")

    ipc.lib = BoomLib()
    ipc.connect_id = 9
    ipc.display_id = 5
    assert ipc.refresh_display_id("com.example") == 5
    assert ipc.display_id == 5


def test_bad_dll_raises():
    try:
        ni.NemuIpc("definitely-not-exist.dll", 0)
    except ni.NemuIpcIncompatible:
        return
    raise AssertionError("expected NemuIpcIncompatible")
