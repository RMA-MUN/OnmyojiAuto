"""绘卷刷分仅探索打法：explore_only=True 跳过突破环节，False 保持原流程（纯逻辑，无需游戏窗口）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import OAT.source.huijuanshuafen.huijuan as hj_mod


class _FakeExplore:
    def __init__(self):
        self.explore_round = 0
        self.started = 0

    def start_explore_loop(self):
        self.started += 1
        self.explore_round = 3
        return True


def _fake_bot(explore_only, rounds=1, tickets=3):
    from OAT.source.huijuanshuafen.huijuan import HuiJuan

    b = HuiJuan.__new__(HuiJuan)
    b.engine = None
    b.sync_mode = False
    b.templates = {}
    b.images_dir = ""
    b._missing_warned = set()
    b.rounds = rounds
    b.explore_count = 3
    b.explore_only = explore_only
    b.config = {}
    b.window_title = "test"
    b.explore = _FakeExplore()
    b.calls = []

    b.check_global_popup = lambda: False
    b._enter_explore_28 = lambda: b.calls.append("enter") or True
    b._ensure_explore_list = lambda: b.calls.append("ensure_list") or True
    b._find_jiejietupo_entry = lambda timeout=15.0: b.calls.append("find_entry") or (100, 100)
    b._get_ticket_count = lambda: b.calls.append("tickets") or tickets
    b._wait_jiejietupo_scene = lambda timeout=8.0: b.calls.append("wait_scene") or True
    b._run_common_breakthrough = lambda t: b.calls.append("breakthrough") or True
    b.click = lambda x, y: b.calls.append("click_entry")
    return b


@pytest.fixture(autouse=True)
def _fast_pause(monkeypatch):
    """屏蔽模块级暂停/休眠：单测不真等 2~3 秒，也不受全局暂停态影响。"""
    monkeypatch.setattr(hj_mod, "pause_aware_sleep", lambda *a, **k: True)
    monkeypatch.setattr(hj_mod, "wait_if_paused", lambda *a, **k: 0)
    monkeypatch.setattr(hj_mod, "is_stale", lambda: False)


BREAKTHROUGH_STEPS = ("ensure_list", "find_entry", "tickets", "click_entry",
                      "wait_scene", "breakthrough")


def test_explore_only_skips_breakthrough():
    b = _fake_bot(explore_only=True, rounds=2)
    assert b.run() is True
    assert b.explore.started == 2
    assert b.calls.count("enter") == 2
    for step in BREAKTHROUGH_STEPS:
        assert step not in b.calls


def test_default_mode_keeps_explore_breakthrough_loop():
    b = _fake_bot(explore_only=False, rounds=1)
    assert b.run() is True
    assert b.calls == ["enter", "ensure_list", "find_entry", "tickets",
                       "click_entry", "wait_scene", "breakthrough"]


def test_zero_tickets_still_skips_breakthrough_in_combined_mode():
    # 原有行为回归：探索+突破模式下突破券为 0 时跳过本轮突破
    b = _fake_bot(explore_only=False, rounds=1, tickets=0)
    assert b.run() is True
    assert "breakthrough" not in b.calls
    assert "click_entry" not in b.calls


def _capture_run(monkeypatch):
    captured = {}

    def fake_run(**kw):
        captured.update(kw)
        return True

    monkeypatch.setattr(hj_mod, "run_huijuanshuafen", fake_run)
    return captured


def test_mode_choice_plumbs_explore_only(monkeypatch):
    captured = _capture_run(monkeypatch)
    from OAT.source import mode_choice

    mode_choice(
        "绘卷刷分", None, 2,
        config={"script": "huijuanshuafen", "explore_per_round": 5},
        window_title="测试窗口",
        explore_per_round=7,
        explore_only=True,
    )
    assert captured["explore_only"] is True
    assert captured["rounds"] == 2
    assert captured["explore_per_round"] == 7


def test_mode_choice_config_can_force_explore_only(monkeypatch):
    captured = _capture_run(monkeypatch)
    from OAT.source import mode_choice

    mode_choice(
        "绘卷刷分", None, 1,
        config={"script": "huijuanshuafen", "explore_only": True},
        window_title="测试窗口",
    )
    assert captured["explore_only"] is True


def test_mode_choice_default_is_combined(monkeypatch):
    captured = _capture_run(monkeypatch)
    from OAT.source import mode_choice

    mode_choice(
        "绘卷刷分", None, 1,
        config={"script": "huijuanshuafen"},
        window_title="测试窗口",
    )
    assert captured["explore_only"] is False


def test_config_json_declares_explore_only_default():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "OAT", "source", "huijuanshuafen", "config.json"),
              "r", encoding="utf-8") as f:
        import json
        cfg = json.load(f)
    assert cfg["explore_only"] is False
