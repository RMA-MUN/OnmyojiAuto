"""ClientDiscovery 测试（全 mock psutil/win32/cli，无需真进程）。"""
import OAT.tools.ClientDiscovery as cd
import OAT.tools.emulator.mumu_handle as mh


def _patch(monkeypatch):
    infos = [
        {"pid": 8188, "name": "MuMuNxDevice.exe",
         "exe": "E:\\MuMuPlayer\\nx_device\\15.0\\shell\\MuMuNxDevice.exe"},
        {"pid": 9000, "name": "Launch.exe", "exe": "E:\\Onmyoji\\Onmyoji\\Launch.exe"},
        {"pid": 9001, "name": "Launch.exe", "exe": "C:\\Other\\Launch.exe"},
        {"pid": 1234, "name": "notepad.exe", "exe": "C:\\Windows\\notepad.exe"},
    ]
    monkeypatch.setattr(cd, "_iter_procs", lambda: iter(infos))
    # cli 权威行：HWND 直给（标题改名也无关）
    monkeypatch.setattr(mh, "query_cli_windows",
                        lambda f: [(2231448, 1, "MuMu安卓设备-1")])
    monkeypatch.setattr(mh, "is_window", lambda h: True)
    monkeypatch.setattr(cd, "_pid_of_window", lambda h: {2231448: 8188}.get(h, 0))
    # 设备进程的渲染容器窗口句柄树校验失败 → 不得另起一行
    def _boom(hwnd, *a, **k):
        raise ValueError("not a game root")
    monkeypatch.setattr(mh, "build_handle", _boom)
    # pid → 窗口：8188 另有容器窗口 27920964；9000 有窗口 555；9001 无窗口
    monkeypatch.setattr(cd, "windows_of_pid",
                        lambda pid, visible_only=True: {8188: [27920964], 9000: [555]}.get(pid, []))
    monkeypatch.setattr("win32gui.GetWindowText",
                        lambda h: {2231448: "RenamedGame", 555: "Onmyoji"}.get(h, ""))


def test_discover_emulator_title_independent(monkeypatch):
    """窗口改名后（无 MuMu 关键字）仍能按 cli HWND 识别，index 权威。"""
    _patch(monkeypatch)
    out = cd.discover_clients("E:\\MuMuPlayer")
    emu = [c for c in out if c.kind == "emulator"]
    assert len(emu) == 1
    assert (emu[0].pid, emu[0].hwnd, emu[0].index) == (8188, 2231448, 1)


def test_discover_pc_requires_onmyoji_path(monkeypatch):
    _patch(monkeypatch)
    out = cd.discover_clients("")
    pcs = [c for c in out if c.kind == "pc"]
    assert [(c.pid, c.hwnd) for c in pcs] == [(9000, 555)]


def test_discover_device_fallback_without_cli(monkeypatch):
    """cli 缺失时设备进程窗口经句柄树校验入选，后缀解析 id。"""
    infos = [{"pid": 8188, "name": "MuMuNxDevice.exe", "exe": "E:\\x\\MuMuNxDevice.exe"}]
    monkeypatch.setattr(cd, "_iter_procs", lambda: iter(infos))
    monkeypatch.setattr(mh, "query_cli_windows", lambda f: [])

    class _H:
        root_hwnd = 300
        root_title = "Renamed-2"
        shot_hwnd = 310

    monkeypatch.setattr(mh, "build_handle", lambda h, *a, **k: _H())
    monkeypatch.setattr(cd, "windows_of_pid", lambda pid, visible_only=True: [300])
    out = cd.discover_clients("")
    emu = [c for c in out if c.kind == "emulator"]
    assert [(c.pid, c.hwnd, c.index) for c in emu] == [(8188, 300, 2)]


def test_discover_empty(monkeypatch):
    monkeypatch.setattr(cd, "_iter_procs", lambda: iter([]))
    monkeypatch.setattr(mh, "query_cli_windows", lambda f: [])
    assert cd.discover_clients("") == []


def test_windows_of_pid_real_signature():
    import inspect
    assert "visible_only" in inspect.signature(cd.windows_of_pid).parameters


def test_client_label_emulator_and_pc():
    emu = cd.ClientInfo(kind="emulator", pid=8188, hwnd=2231448,
                        title="任意名字", index=1, detail="MuMu安卓设备-1")
    pc = cd.ClientInfo(kind="pc", pid=9000, hwnd=555, title="阴阳师", index=None, detail="阴阳师")
    assert cd.client_label(emu) == "模拟器 · MuMu安卓设备-1 (实例1)"
    assert cd.client_label(pc) == "PC桌面版 · 阴阳师"
    emu_no_index = cd.ClientInfo(kind="emulator", pid=1, hwnd=2, title="X", index=None, detail="")
    assert cd.client_label(emu_no_index) == "模拟器 · X"


def test_build_client_items_dedup_and_fallback():
    emu = cd.ClientInfo(kind="emulator", pid=8188, hwnd=2231448,
                        title="T", index=1, detail="MuMu安卓设备-1")
    items = cd.build_client_items([emu, emu], ["阴阳师-MuMu模拟器专版", "", "阴阳师-网易游戏"])
    labels = [label for label, _ in items]
    assert labels == ["模拟器 · MuMu安卓设备-1 (实例1)", "阴阳师-MuMu模拟器专版", "阴阳师-网易游戏"]
    assert items[0][1] is emu and items[1][1] is None


def test_build_client_items_empty_falls_back():
    items = cd.build_client_items([], ["A"])
    assert items == [("A", None)]
    assert cd.build_client_items([], []) == []
