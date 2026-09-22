"""WindowChecker.connect_all 最小化自动恢复回归。

背景：窗口检测必须真实 resize（对齐模板尺度），iconic 窗口上 resize 可能
不生效，因此最小化时先 SW_RESTORE 再继续；恢复失败才弹窗中止。
"""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 包命名空间里 WindowChecker 被同名类遮蔽，必须用 importlib 取模块本身
WM = importlib.import_module("OAT.tools.WindowChecker")


def _make_checker(monkeypatch, state):
    import win32con

    monkeypatch.setattr(WM.win32gui, "IsIconic", lambda h: not state["restored"])

    def fake_show(h, cmd):
        assert cmd == win32con.SW_RESTORE
        state["restored"] = True

    monkeypatch.setattr(WM.win32gui, "ShowWindow", fake_show)
    monkeypatch.setattr(
        WM.win32gui, "GetWindowRect",
        lambda h: (0, 0, 1404, 834) if state["resized"] else (0, 0, 1000, 600))
    monkeypatch.setattr(
        WM.win32gui, "SetWindowPos",
        lambda h, after, x, y, w, ht, flags: state.__setitem__("resized", True))
    monkeypatch.setattr(WM, "warning_box", lambda msg: state["warns"].append(msg))
    monkeypatch.setattr(WM.time, "sleep", lambda s: None)

    checker = WM.WindowChecker()
    checker.set_window_title("game")
    checker.set_window_handle(4321)
    return checker


def test_minimized_restored_then_resized(monkeypatch):
    state = {"restored": False, "resized": False, "warns": []}
    checker = _make_checker(monkeypatch, state)
    checker.connect_all()
    assert state["restored"] is True
    assert state["resized"] is True
    assert state["warns"] == []


def test_restore_failure_aborts_with_warning(monkeypatch):
    state = {"restored": False, "resized": False, "warns": []}
    checker = _make_checker(monkeypatch, state)
    # ShowWindow 无效（恢复失败），IsIconic 恒为 True
    monkeypatch.setattr(WM.win32gui, "ShowWindow", lambda h, cmd: None)
    checker.connect_all()
    assert any("恢复失败" in w for w in state["warns"])
    assert state["resized"] is False


def test_restored_window_skips_resize_when_size_matches(monkeypatch):
    state = {"restored": True, "resized": False, "warns": []}
    checker = _make_checker(monkeypatch, state)
    # 窗口已是目标尺寸，不得触发 resize
    monkeypatch.setattr(WM.win32gui, "GetWindowRect", lambda h: (0, 0, 1404, 834))
    checker.connect_all()
    assert state["resized"] is False
    assert state["warns"] == []
