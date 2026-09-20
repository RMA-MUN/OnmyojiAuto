"""Task 2: 句柄树与家族判定（monkeypatch 假 win32，无需真 MuMu）。"""
import OAT.tools.emulator.mumu_handle as mh


class _FakeWin:
    # 桌面：两个 MuMu 顶层窗口；100 下挂 MuMuPlayer 子树
    tops = {100: "MuMu模拟器12", 200: "MuMu安卓设备"}
    children = {100: [110], 110: [], 200: [210], 210: []}
    names = {110: "MuMuPlayer", 210: "MuMuPlayer"}

    def EnumWindows(self, cb, param):
        for h in self.tops:
            cb(h, param)

    def GetWindowText(self, h):
        return self.tops.get(h, self.names.get(h, ""))

    def EnumChildWindows(self, h, cb, param):
        for c in self.children.get(h, []):
            cb(c, param)

    def GetParent(self, h):
        for p, cs in self.children.items():
            if h in cs:
                return p
        return 0

    def IsWindow(self, h):
        return h in self.tops or h in self.names

    def GetWindowRect(self, h):
        return (0, 0, 1280, 800)

    def GetClientRect(self, h):
        return (0, 0, 1280, 720)


def _patch(monkeypatch):
    fake = _FakeWin()
    monkeypatch.setattr(mh, "_gui", fake)
    return fake


def test_enum_sorted(monkeypatch):
    _patch(monkeypatch)
    wins = mh.enum_mumu_windows()
    assert wins == sorted(wins)
    assert [h for h, _ in wins] == [100, 200]


def test_build_handle_auto_picks_first(monkeypatch):
    _patch(monkeypatch)
    h = mh.build_handle("auto")
    assert isinstance(h, mh.MumuHandle)
    assert (h.root_hwnd, h.shot_hwnd) == (100, 110)
    assert h.control_hwnds == [100, 110]


def test_build_handle_numeric(monkeypatch):
    _patch(monkeypatch)
    h = mh.build_handle(200)
    assert (h.root_hwnd, h.shot_hwnd) == (200, 210)


def test_scale_rate(monkeypatch):
    _patch(monkeypatch)
    monkeypatch.setattr(mh, "_sysmetrics", lambda i: 1280 if i == 0 else 720)
    monkeypatch.setattr(mh, "_deskhres", lambda: 1280)
    assert mh.window_scale_rate() == 1.0


def test_enum_ignores_updater_message_windows(monkeypatch):
    """updater 残留窗口含 MuMuPlayer 子串但必须排除（真机实测：NxUpdaterMessageWndMuMuPlayer）。"""
    fake = _patch(monkeypatch)
    fake.tops[300] = "NxUpdaterMessageWndMuMuPlayer"
    fake.tops[400] = "UpdaterMessageWndMuMuPlayer"
    wins = mh.enum_mumu_windows()
    assert [h for h, _ in wins] == [100, 200]


def test_query_cli_instances_parses_names(monkeypatch):
    import json

    payload = {"0": {"name": "MuMu安卓设备"}, "1": {"name": "MuMu安卓设备-1"}}

    class _Proc:
        stdout = json.dumps(payload).encode("utf-8")

    monkeypatch.setattr("subprocess.run", lambda *a, **k: _Proc())
    monkeypatch.setattr("os.path.isfile", lambda p: True)
    assert mh.query_cli_instances("E:\\MuMuPlayer") == {"MuMu安卓设备": 0, "MuMu安卓设备-1": 1}


def test_query_cli_instances_failure_returns_empty(monkeypatch):
    def _boom(*a, **k):
        raise OSError("no cli")

    monkeypatch.setattr("subprocess.run", _boom)
    assert mh.query_cli_instances("E:\\MuMuPlayer") == {}
    assert mh.query_cli_instances("") == {}


def test_order_windows_prefers_cli_index():
    wins = [(200, "MuMu安卓设备-1"), (100, "MuMu模拟器12")]
    ordered = mh.order_windows(wins, {"MuMu安卓设备-1": 1, "MuMu模拟器12": 0})
    assert [h for h, _ in ordered] == [100, 200]


def test_order_windows_falls_back_without_map():
    wins = [(200, "MuMu安卓设备-1"), (100, "MuMu模拟器12")]
    assert [h for h, _ in mh.order_windows(wins, {})] == [100, 200]


def test_suffix_id():
    assert mh._suffix_id("MuMu安卓设备-1", 0) == 1
    assert mh._suffix_id("MuMu模拟器12", 0) == 0
    assert mh._suffix_id("", 3) == 3


def test_query_cli_windows_parses_main_wnd(monkeypatch):
    import json

    payload = {"0": {"name": "MuMu安卓设备"},
               "1": {"main_wnd": "00220C98", "name": "MuMu安卓设备-1"}}

    class _Proc:
        stdout = json.dumps(payload).encode("utf-8")

    monkeypatch.setattr("subprocess.run", lambda *a, **k: _Proc())
    monkeypatch.setattr("os.path.isfile", lambda p: True)
    monkeypatch.setattr(mh, "is_window", lambda h: True)
    assert mh.query_cli_windows("E:\\MuMuPlayer") == [(0x220C98, 1, "MuMu安卓设备-1")]


def test_query_cli_windows_skips_stopped(monkeypatch):
    import json

    class _Proc:
        stdout = json.dumps({"0": {"name": "MuMu安卓设备"}}).encode("utf-8")

    monkeypatch.setattr("subprocess.run", lambda *a, **k: _Proc())
    monkeypatch.setattr("os.path.isfile", lambda p: True)
    assert mh.query_cli_windows("E:\\MuMuPlayer") == []


def test_enum_mumu_by_process(monkeypatch):
    _patch(monkeypatch)
    monkeypatch.setattr(mh, "_pid_of", lambda h: {100: 1111, 200: 2222}[h])
    monkeypatch.setattr(mh, "_exe_of",
                        lambda pid: "MuMuNxDevice.exe" if pid == 1111 else "notepad.exe")
    assert mh.enum_mumu_by_process() == [100]


def test_resolve_auto_cli_first(monkeypatch):
    monkeypatch.setattr(mh, "query_cli_windows", lambda f: [(999, 5, "RenamedGame")])
    assert mh.resolve_auto(0, "X") == (999, 5)


def test_resolve_auto_process_fallback(monkeypatch):
    _patch(monkeypatch)
    monkeypatch.setattr(mh, "query_cli_windows", lambda f: [])
    monkeypatch.setattr(mh, "enum_mumu_by_process", lambda: [200])
    assert mh.resolve_auto(0, "X") == (200, 0)


def test_resolve_auto_legacy_title(monkeypatch):
    _patch(monkeypatch)
    monkeypatch.setattr(mh, "query_cli_windows", lambda f: [])
    monkeypatch.setattr(mh, "enum_mumu_by_process", lambda: [])
    monkeypatch.setattr(mh, "query_cli_instances", lambda f: {})
    # 优先级顺序 [(100, 模拟器12), (200, 安卓设备)]，取 index 1，无后缀沿用顺序号
    assert mh.resolve_auto(1, "X") == (200, 1)
