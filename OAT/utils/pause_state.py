"""全局挑战暂停/停止协同状态（标准库 only）。

挑战线程（legacy / pipeline / 绘卷）通过本模块协同：
- 暂停：`pause()` 后所有 `wait_if_paused()` 调用阻塞，直到 `resume()`；
  阻塞期间不计入任何休眠时长（暂停多久都不消耗超时/休眠预算）。
- 停止：`request_stop()` 唤醒全部等待者；等待中的 `wait_if_paused()`
  返回 -1.0，调用方据此干净退出（返回 False + 打一条"挑战已停止"日志）。

所有函数永不抛异常。检查点只放在循环顶部与休眠处，
绝不打断飞行中的点击/拖拽动作。
"""

import math
import threading
import time

# 暂停轮询粒度（秒）：resume/stop 的最大感知延迟
_PAUSE_POLL = 0.05
# 定时等待的切片（秒）：stop 的最大感知延迟
_SLEEP_SLICE = 0.05

_paused = threading.Event()  # set = 已暂停
_stopped = threading.Event()  # set = 已请求停止

# 全局代际计数：每次 stop_all 递增，用于识别双起旧线程（旧 gen 即 stale）。
_gen = 0
_gen_lock = threading.Lock()
_local = threading.local()


def pause() -> None:
    """请求全局暂停（幂等，永不抛异常）。"""
    try:
        _paused.set()
    except Exception:
        pass


def resume() -> None:
    """恢复全局暂停（幂等，永不抛异常）。"""
    try:
        _paused.clear()
    except Exception:
        pass


def is_paused() -> bool:
    """当前是否处于暂停状态（永不抛异常）。"""
    try:
        return bool(_paused.is_set())
    except Exception:
        return False


def request_stop() -> None:
    """请求全局停止并唤醒全部等待者（幂等，永不抛异常）。"""
    try:
        _stopped.set()
    except Exception:
        pass
    try:
        # 直接清除暂停位，让卡在暂停等待中的调用立刻醒来并看到停止位
        _paused.clear()
    except Exception:
        pass


def _is_alive(thread) -> bool:
    """线程是否存活（鸭子类型；任何异常 → False）。永不抛异常。"""
    try:
        return bool(thread.is_alive())
    except Exception:
        return False


def stop_all(threads, timeout: float = 3.0) -> None:
    """请求全局停止并尽力回收给定的挑战线程（新开局前置，永不抛异常）。

    先 `request_stop()` 唤醒卡在暂停/休眠中的线程，再对存活线程逐个 join
    （平分 `timeout` 总预算）。线程不配合也无妨：它们会在下个检查点自行退出。
    每次调用递增全局代际 `_gen`，旧线程的 pinned gen 即变为 stale。
    """
    try:
        request_stop()
    except Exception:
        pass
    try:
        global _gen
        with _gen_lock:
            _gen += 1
    except Exception:
        pass
    try:
        try:
            pending = [t for t in list(threads or []) if _is_alive(t)]
        except Exception:
            pending = []
        if not pending:
            return
        try:
            budget = float(timeout)
        except Exception:
            budget = 3.0
        if not budget > 0:
            return
        per_thread = budget / max(1, len(pending))
        for t in pending:
            try:
                t.join(timeout=per_thread)
            except Exception:
                continue
    except Exception:
        pass


def is_stopped() -> bool:
    """是否已请求停止（永不抛异常）。"""
    try:
        return bool(_stopped.is_set())
    except Exception:
        return False


def begin_run() -> int:
    """开始新一轮：清停止位+暂停位，固定当前全局代际到本线程并返回（永不抛异常）。"""
    try:
        try:
            _stopped.clear()
        except Exception:
            pass
        try:
            _paused.clear()
        except Exception:
            pass
        try:
            with _gen_lock:
                cur = int(_gen)
        except Exception:
            try:
                cur = int(_gen)
            except Exception:
                cur = 0
        try:
            _local.gen = cur
        except Exception:
            pass
        return cur
    except Exception:
        return 0


def my_gen() -> int | None:
    """本线程 pinned 代际（未 begin_run 则为 None，永不抛异常）。"""
    try:
        return getattr(_local, "gen", None)
    except Exception:
        return None


def is_stale(gen=None) -> bool:
    """给定代际是否已过期（永不抛异常）。

    gen 为 None 时取本线程 pinned 值；仍为 None 则视为 fresh 返回 False；
    否则当且仅当 gen != 当前全局 `_gen` 时为 True。
    """
    try:
        try:
            g = gen if gen is not None else getattr(_local, "gen", None)
        except Exception:
            return False
        if g is None:
            return False
        try:
            with _gen_lock:
                cur = _gen
        except Exception:
            try:
                cur = _gen
            except Exception:
                return False
        try:
            return bool(g != cur)
        except Exception:
            return False
    except Exception:
        return False


def reset() -> None:
    """清除暂停与停止位（测试/新一轮开始前的隔离辅助，永不抛异常）。"""
    try:
        _paused.clear()
    except Exception:
        pass
    try:
        _stopped.clear()
    except Exception:
        pass


def _drain_pause() -> float:
    """阻塞直到暂停解除；停止则返回 -1.0，否则返回 0.0。永不抛异常。"""
    try:
        while True:
            try:
                if _stopped.is_set():
                    return -1.0
                if not _paused.is_set():
                    return 0.0
                # 在停止位上等待：request_stop 立刻唤醒；resume 靠轮询感知
                if _stopped.wait(_PAUSE_POLL):
                    return -1.0
            except Exception:
                return 0.0
    except Exception:
        return 0.0


def wait_if_paused(timeout: float | None = None) -> float:
    """如已暂停则阻塞等待，直到恢复或停止。

    Args:
        timeout: 需要休眠的秒数（不含暂停时长）。None 表示只做暂停等待、
            不休眠；<=0 表示单次检查、不休眠；非法输入按 0 处理。

    Returns:
        实际休眠秒数（不含暂停时长，>=0.0）；收到停止请求时返回 -1.0。
        调用方约定：`if wait_if_paused(x) < 0: <干净退出>`。永不抛异常。
    """
    try:
        if timeout is None:
            target = None
        else:
            try:
                target = float(timeout)
            except Exception:
                return 0.0
            try:
                if math.isnan(target) or not math.isfinite(target):
                    # NaN/+inf：不休眠，只报告停止状态（避免无限等待）
                    return -1.0 if is_stopped() else 0.0
            except Exception:
                return 0.0
            if target <= 0:
                return -1.0 if is_stopped() else 0.0

        # 先排空暂停（不计入休眠时长）
        if _drain_pause() < 0:
            return -1.0
        if target is None:
            return 0.0

        # 定时休眠：暂停中途按下则排空暂停且该段不计数
        slept = 0.0
        try:
            while slept < target:
                try:
                    if _stopped.is_set():
                        return -1.0
                    if _paused.is_set():
                        if _drain_pause() < 0:
                            return -1.0
                        continue
                    step = target - slept
                    if step > _SLEEP_SLICE:
                        step = _SLEEP_SLICE
                    t0 = time.monotonic()
                    if _stopped.wait(step):
                        return -1.0
                    if _paused.is_set():
                        continue
                    try:
                        dt = time.monotonic() - t0
                    except Exception:
                        dt = step
                    if dt < 0:
                        dt = 0.0
                    slept += dt
                except Exception:
                    # 单片异常不中断调用方：返回已休眠部分
                    break
        except Exception:
            pass
        try:
            return float(slept)
        except Exception:
            return 0.0
    except Exception:
        return 0.0


def pause_aware_sleep(total_seconds: float, slice_seconds: float = 0.1) -> bool:
    """暂停感知的分片休眠（`wait_if_paused` 切片累加到总量）。

    Args:
        total_seconds: 目标休眠秒数（暂停时长不计入）。
        slice_seconds: 单切片上限（暂停/停止感知粒度）。

    Returns:
        True=休眠完成，False=中途收到停止请求。永不抛异常。
    """
    try:
        try:
            total = float(total_seconds)
        except Exception:
            return True
        try:
            sl = float(slice_seconds)
        except Exception:
            sl = 0.1
        try:
            if math.isnan(sl) or not math.isfinite(sl) or sl <= 0:
                sl = 0.1
        except Exception:
            sl = 0.1
        try:
            if math.isnan(total) or not math.isfinite(total):
                return not is_stopped()
        except Exception:
            return True
        if total <= 0:
            return not is_stopped()
        slept = 0.0
        while slept < total:
            chunk = total - slept
            if chunk > sl:
                chunk = sl
            try:
                s = float(wait_if_paused(chunk))
            except Exception:
                return True
            if s < 0:
                return False
            slept += s
            if s <= 0 and slept < total:
                # 零进展兜底：一次有界休眠保证必推进（正常路径走不到这里）
                try:
                    _fb = total - slept
                    if _fb > sl:
                        _fb = sl
                    time.sleep(_fb)
                    slept += _fb
                except Exception:
                    return True
        return True
    except Exception:
        return True
