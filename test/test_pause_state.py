"""Task D verification: OAT/utils/pause_state.py (no Qt, no GUI)."""
import threading
import time

import pytest

from OAT.utils import pause_state  # noqa: F401  (ensures module import path)
from OAT.utils.pause_state import (
    begin_run,
    is_paused,
    is_stale,
    is_stopped,
    my_gen,
    pause,
    pause_aware_sleep,
    request_stop,
    reset,
    resume,
    stop_all,
    wait_if_paused,
)


@pytest.fixture(autouse=True)
def _clean_state():
    reset()
    yield
    reset()


def _run_in_thread(func, *args):
    box = {}
    t = threading.Thread(
        target=lambda: box.setdefault("ret", func(*args)), daemon=True
    )
    t.start()
    return t, box


def test_pause_blocks_wait():
    """暂停时 wait 一直阻塞（超过请求时长仍不返回），resume 后释放并返回约请求时长。"""
    pause()
    assert is_paused() is True
    t, box = _run_in_thread(wait_if_paused, 0.3)
    time.sleep(0.45)  # 已超过请求的 0.3s：仍阻塞说明暂停时长未被消耗
    assert t.is_alive()
    resume()
    t.join(timeout=2.0)
    assert not t.is_alive()
    assert box["ret"] == pytest.approx(0.3, abs=0.2)


def test_resume_releases_without_pause():
    """未暂停时 wait 按请求时长返回。"""
    t0 = time.monotonic()
    ret = wait_if_paused(0.2)
    wall = time.monotonic() - t0
    assert ret == pytest.approx(0.2, abs=0.15)
    assert wall == pytest.approx(0.2, abs=0.15)


def test_stop_wakes_waiter_with_minus_one():
    """request_stop 唤醒暂停中的等待者并返回 -1.0。"""
    pause()
    t, box = _run_in_thread(wait_if_paused, 5.0)
    time.sleep(0.15)
    assert t.is_alive()
    request_stop()
    t.join(timeout=2.0)
    assert not t.is_alive()
    assert box["ret"] == -1.0
    assert is_stopped() is True


def test_slept_excludes_paused_time():
    """等待中途暂停 0.3s：返回值约等于请求时长，而非请求时长+0.3。"""
    start = time.monotonic()
    t, box = _run_in_thread(wait_if_paused, 0.4)
    time.sleep(0.1)
    pause()
    time.sleep(0.3)
    assert t.is_alive()
    resume()
    t.join(timeout=2.0)
    wall = time.monotonic() - start
    assert not t.is_alive()
    assert box["ret"] == pytest.approx(0.4, abs=0.2)
    assert box["ret"] < 0.4 + 0.3 - 0.05
    assert wall >= 0.6  # 暂停确实阻塞了等待（0.1+0.3+0.3）


def test_pause_aware_sleep_completes():
    """分片休眠正常完成返回 True，耗时约等于总量。"""
    t0 = time.monotonic()
    assert pause_aware_sleep(0.3, 0.1) is True
    assert time.monotonic() - t0 == pytest.approx(0.3, abs=0.15)


def test_pause_aware_sleep_aborts_on_stop():
    """分片休眠中途收到停止请求返回 False。"""
    t, box = _run_in_thread(pause_aware_sleep, 5.0, 0.1)
    time.sleep(0.15)
    request_stop()
    t.join(timeout=2.0)
    assert not t.is_alive()
    assert box["ret"] is False


def test_never_raise_on_odd_inputs():
    """异常输入永不抛异常：None/负数按单次检查（0.0），非法类型按 0 处理。"""
    assert wait_if_paused(None) == 0.0
    assert wait_if_paused(0) == 0.0
    assert wait_if_paused(-2.5) == 0.0
    assert wait_if_paused("bad-timeout") == 0.0
    assert wait_if_paused(float("nan")) == 0.0
    assert wait_if_paused(object()) == 0.0
    pause()
    resume()
    assert is_paused() is False
    request_stop()
    assert is_stopped() is True
    assert wait_if_paused(None) == -1.0
    assert wait_if_paused(0) == -1.0
    assert pause_aware_sleep(0.1) is False


class _FakeThread:
    """start_challenge 回收逻辑的替身：只实现 is_alive/join，不建真线程。"""

    def __init__(self, alive=True):
        self._alive = alive
        self.joins = []

    def is_alive(self):
        return self._alive

    def join(self, timeout=None):
        self.joins.append(timeout)
        self._alive = False


class _ExplodingThread:
    def is_alive(self):
        raise RuntimeError("boom")

    def join(self, timeout=None):
        raise RuntimeError("boom")


def test_stop_all_requests_stop_and_joins_alive():
    """stop_all 置停止位并回收存活线程（平分总预算），死线程不 join。"""
    live1, live2, dead = _FakeThread(True), _FakeThread(True), _FakeThread(False)
    stop_all([live1, live2, dead], timeout=1.0)
    assert is_stopped() is True
    assert live1.joins == [pytest.approx(0.5)]
    assert live2.joins == [pytest.approx(0.5)]
    assert dead.joins == []


def test_stop_all_accepts_real_threads():
    """真线程（已结束）可直接传入：不存活则不 join，不抛异常。"""
    t = threading.Thread(target=lambda: None, daemon=True)
    t.start()
    t.join(timeout=2.0)
    stop_all([t], timeout=0.5)
    assert is_stopped() is True


def test_stop_all_never_raises():
    """坏线程/None/坏输入永不抛异常，且仍置停止位。"""
    stop_all([_ExplodingThread(), None, "not-a-thread"], timeout=0.2)
    assert is_stopped() is True
    stop_all(None)
    stop_all([], timeout=0.1)
    stop_all([_FakeThread(True)], timeout="bad-timeout")
    stop_all([_FakeThread(True)], timeout=-1)
    assert is_stopped() is True


def _begin_in_thread(box, key="gen"):
    box[key] = begin_run()


def test_begin_run_clears_stopped_and_paused():
    """begin_run 清停止位+暂停位，固定当前 gen，my_gen/is_stale 一致。"""
    request_stop()
    pause()
    assert is_stopped() is True
    assert is_paused() is True
    gen = begin_run()
    assert isinstance(gen, int)
    assert is_stopped() is False
    assert is_paused() is False
    assert my_gen() == gen
    assert is_stale() is False
    assert is_stale(gen) is False


def test_gen_pinned_per_thread_across_stop_all():
    """两次 begin_run 被 stop_all 隔开则 gen 不同（per-thread pin）。"""
    box1, box2 = {}, {}
    t1 = threading.Thread(target=_begin_in_thread, args=(box1,), daemon=True)
    t1.start()
    t1.join(timeout=2.0)
    assert not t1.is_alive()
    stop_all([], timeout=0.1)
    t2 = threading.Thread(target=_begin_in_thread, args=(box2,), daemon=True)
    t2.start()
    t2.join(timeout=2.0)
    assert not t2.is_alive()
    assert isinstance(box1["gen"], int)
    assert isinstance(box2["gen"], int)
    assert box1["gen"] != box2["gen"]


def test_stale_detection_old_stale_new_fresh():
    """stop_all 后旧 gen 为 stale，新 begin_run 的 gen 为 fresh。"""
    old = begin_run()
    assert is_stale(old) is False
    stop_all([], timeout=0.1)
    assert is_stopped() is True
    assert is_stale(old) is True
    new = begin_run()
    assert is_stopped() is False
    assert is_stale(new) is False
    assert is_stale() is False
    assert is_stale(old) is True


def test_is_stale_fresh_thread_without_begin_is_false():
    """从未 begin_run 的线程视为 fresh（None → False），保持旧测试绿色。"""
    box = {}
    def _probe():
        box["gen"] = my_gen()
        box["stale"] = is_stale()
    t = threading.Thread(target=_probe, daemon=True)
    t.start()
    t.join(timeout=2.0)
    assert not t.is_alive()
    assert box["gen"] is None
    assert box["stale"] is False


def test_double_start_old_thread_stays_stale_after_new_begin():
    """核心回归：A begin(g) → stop_all(g+1, event) → B begin(清event) 后 A 仍 stale。"""
    box_a, box_b = {}, {}
    ready = threading.Event()
    go = threading.Event()
    done = threading.Event()

    def _thread_a():
        box_a["gen"] = begin_run()
        ready.set()
        assert go.wait(timeout=2.0)
        box_a["stale_after"] = is_stale()
        done.set()

    t_a = threading.Thread(target=_thread_a, daemon=True)
    t_a.start()
    assert ready.wait(timeout=2.0)
    gen_a = box_a["gen"]
    stop_all([], timeout=0.1)
    assert is_stopped() is True
    assert is_stale(gen_a) is True
    t_b = threading.Thread(
        target=lambda: box_b.setdefault("gen", begin_run()), daemon=True
    )
    t_b.start()
    t_b.join(timeout=2.0)
    assert not t_b.is_alive()
    # B 的 begin_run 已清停止位，但 A 的旧 gen 仍必须 stale
    assert is_stopped() is False
    assert is_stale(gen_a) is True
    assert is_stale(box_b["gen"]) is False
    go.set()
    assert done.wait(timeout=2.0)
    t_a.join(timeout=2.0)
    assert box_b["gen"] != gen_a
    assert box_a["stale_after"] is True
