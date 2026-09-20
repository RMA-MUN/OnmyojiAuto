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


def test_convert_xy():
    ipc = ni.NemuIpc.__new__(ni.NemuIpc)
    ipc.height = 720
    assert ipc.convert_xy(100, 200) == (520, 100)


def test_bad_dll_raises():
    try:
        ni.NemuIpc("definitely-not-exist.dll", 0)
    except ni.NemuIpcIncompatible:
        return
    raise AssertionError("expected NemuIpcIncompatible")
