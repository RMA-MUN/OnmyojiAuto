"""同步器坐标映射：给句柄时不再依赖窗口标题（向后兼容标题链路）。"""
import OAT.tools.WindowSynchronizer as ws


def _patch_win32(monkeypatch, find_calls):
    monkeypatch.setattr(ws.win32gui, "IsWindow", lambda h: True)
    monkeypatch.setattr(ws.win32gui, "FindWindow",
                        lambda cls, title: (find_calls.append(title), 0)[1])
    monkeypatch.setattr(ws.win32gui, "GetClientRect", lambda h: (0, 0, 100, 100))
    monkeypatch.setattr(ws.win32gui, "ClientToScreen", lambda h, pt: pt)


def test_calc_the_position_uses_hwnd_without_title_lookup(monkeypatch):
    """句柄优先：即使标题不存在，映射照样算出来，且不调用 FindWindow。"""
    sync = ws.WindowSynchronizer()
    sync.sub_windows = [(2222, "副窗口")]
    find_calls = []
    _patch_win32(monkeypatch, find_calls)

    out = sync.calc_the_position("这个标题不存在", 10, 10, main_hwnd=1111)

    assert find_calls == []
    assert out == [(10, 10)]


def test_calc_the_position_falls_back_to_title(monkeypatch):
    """没给句柄时沿用旧的标题查找链路。"""
    sync = ws.WindowSynchronizer()
    sync.sub_windows = [(2222, "副窗口")]
    find_calls = []
    _patch_win32(monkeypatch, find_calls)

    sync.calc_the_position("阴阳师", 10, 10)

    assert find_calls == ["阴阳师"]
