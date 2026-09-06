"""Task A verification: loguru backend for OAT/utils/logging.py."""
import json
import re
import time
import uuid
from pathlib import Path

import pytest

from OAT.utils import logging as logmod
from OAT.utils.logging import LOG_LEVELS, LogRedirect, logger

TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}$")


@pytest.fixture(autouse=True)
def _isolate_log_file(tmp_path, monkeypatch):
    """Task E2: 文件 sink 重定向到 tmp，生产 logs/ 零污染；测后恢复。"""
    tmp_file = tmp_path / "test-log.log"
    assert logmod.set_log_file(str(tmp_file))
    monkeypatch.setattr(logmod, "LOG_FILE", str(tmp_file))
    yield
    try:
        logmod.set_log_file(logmod.LOG_FILE_PATTERN)
    except Exception:
        pass


def _tag(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _file_lines():
    try:
        return Path(logmod.LOG_FILE).read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        return []


def _records_for(tag, before):
    out = []
    for line in _file_lines()[len(before):]:
        if tag not in line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


class _Collector:
    def __init__(self):
        self.items = []
        self._fn = lambda s: self.items.append(s)

    def __enter__(self):
        logger.append_log.connect(self._fn)
        return self

    def __exit__(self, *exc):
        try:
            logger.append_log.disconnect(self._fn)
        except Exception:
            pass
        return False

    def tagged(self, tag):
        return [s for s in self.items if tag in s]


def _settle():
    time.sleep(0.4)


def test_api_surface_compat():
    assert hasattr(logger, "info")
    assert hasattr(logger, "warn")
    assert hasattr(logger, "error")
    assert hasattr(logger, "debug")
    assert hasattr(logger, "print")
    assert hasattr(logger, "set_text_browser")
    assert hasattr(logger, "bind")
    assert hasattr(logger, "bind_window")
    assert isinstance(logger, LogRedirect)
    assert LOG_LEVELS.get("WARN") == 30
    assert LOG_LEVELS.get("WARNING") == 30
    assert not hasattr(logger, "_cleanup_log_file")
    # log_level settable property
    old = logger.log_level
    try:
        logger.log_level = "WARNING"
        assert logger.log_level == "WARNING"
    finally:
        logger.log_level = old


def test_json_keys_and_timestamp_and_run_id():
    old = logger.log_level
    logger.log_level = "INFO"
    logmod._reset_display_dedup()
    try:
        tag = _tag("keys")
        before = _file_lines()
        with _Collector() as c:
            logger.info(f"{tag}-hello")
            _settle()
        recs = _records_for(tag, before)
        assert len(recs) == 1
        r = recs[0]
        for k in ("timestamp", "level", "module", "message", "window", "run_id"):
            assert k in r, f"missing key {k}: {r}"
        assert r["level"] == "INFO"
        assert r["message"] == f"{tag}-hello"
        assert r["window"] == ""
        assert isinstance(r["run_id"], str) and r["run_id"]
        assert TS_RE.match(r["timestamp"]), r["timestamp"]
        assert re.match(r".+:\d+$", r["module"]), r["module"]
        # run_id stable within process
        tag2 = _tag("keys2")
        before2 = _file_lines()
        logger.info(f"{tag2}-hello2")
        _settle()
        r2 = _records_for(tag2, before2)[0]
        assert r2["run_id"] == r["run_id"]
        # display stays human text with full info
        disp = c.tagged(tag)
        assert len(disp) >= 1
        assert "\u25cf" in disp[0] and f"{tag}-hello" in disp[0]
        assert "[INFO]" not in disp[0]
        assert re.search(r"\d{2}:\d{2}:\d{2}", disp[0]), disp[0]
    finally:
        logger.log_level = old
        logmod._reset_display_dedup()


def test_level_filter_hides_display_but_file_writes_all():
    old = logger.log_level
    logger.log_level = "WARNING"
    logmod._reset_display_dedup()
    try:
        tag = _tag("lvl")
        before = _file_lines()
        with _Collector() as c:
            logger.info(f"{tag}-hidden-info")
            _settle()
            assert c.tagged(tag) == []
        recs = _records_for(tag, before)
        assert len(recs) == 1
        assert recs[0]["level"] == "INFO"
    finally:
        logger.log_level = old
        logmod._reset_display_dedup()


def test_debug_default_hidden_but_file_writes():
    old = logger.log_level
    logger.log_level = "INFO"
    logmod._reset_display_dedup()
    try:
        tag = _tag("dbg")
        before = _file_lines()
        with _Collector() as c:
            logger.debug(f"{tag}-d")
            _settle()
            assert c.tagged(tag) == []
        recs = _records_for(tag, before)
        assert len(recs) == 1
        assert recs[0]["level"] == "DEBUG"
    finally:
        logger.log_level = old
        logmod._reset_display_dedup()


def test_dedup_display_collapses_file_keeps_all():
    old = logger.log_level
    logger.log_level = "INFO"
    logmod._reset_display_dedup()
    try:
        tag = _tag("dedup")
        before = _file_lines()
        with _Collector() as c:
            for _ in range(3):
                logger.info(f"{tag}-same")
            _settle()
            recs = _records_for(tag, before)
            assert len(recs) == 3, f"file must keep every record, got {len(recs)}"
            assert len(c.tagged(tag)) == 1, f"display must collapse, got {len(c.tagged(tag))}"
            # next distinct message flushes summary …（xN）
            logger.info(f"{tag}-other")
            _settle()
            assert any("x3" in s for s in c.items), c.items
    finally:
        logger.log_level = old
        logmod._reset_display_dedup()


def test_warn_maps_to_warning():
    old = logger.log_level
    logger.log_level = "INFO"
    logmod._reset_display_dedup()
    try:
        tag = _tag("warn")
        before = _file_lines()
        with _Collector() as c:
            logger.warn(f"{tag}-w")
            _settle()
        recs = _records_for(tag, before)
        assert len(recs) == 1
        assert recs[0]["level"] == "WARNING"
        disp = c.tagged(tag)
        assert len(disp) == 1
        assert "\u25cf" in disp[0] and f"{tag}-w" in disp[0]
        assert "[WARNING]" not in disp[0] and "[WARN]" not in disp[0]
    finally:
        logger.log_level = old
        logmod._reset_display_dedup()


def test_print_joins_args():
    old = logger.log_level
    logger.log_level = "INFO"
    logmod._reset_display_dedup()
    try:
        tag = _tag("prt")
        before = _file_lines()
        with _Collector() as c:
            logger.print(f"{tag}-a", 1, None)
            _settle()
        recs = _records_for(tag, before)
        assert len(recs) == 1
        assert recs[0]["message"] == f"{tag}-a 1 None"
        assert recs[0]["level"] == "INFO"
        assert any(f"{tag}-a 1 None" in s for s in c.tagged(tag))
    finally:
        logger.log_level = old
        logmod._reset_display_dedup()


def test_bind_extras_in_file_not_display():
    old = logger.log_level
    logger.log_level = "INFO"
    logmod._reset_display_dedup()
    try:
        tag = _tag("bind")
        before = _file_lines()
        with _Collector() as c:
            logger.bind(conf=0.97, pos=(1211, 511)).info(f"{tag}-k28hit")
            _settle()
        recs = _records_for(tag, before)
        assert len(recs) == 1
        r = recs[0]
        assert r["conf"] == 0.97
        assert list(r["pos"]) == [1211, 511]
        disp = c.tagged(tag)
        assert len(disp) == 1
        assert f"{tag}-k28hit" in disp[0]
        assert "0.97" not in disp[0]
    finally:
        logger.log_level = old
        logmod._reset_display_dedup()


def test_bind_window_carries_window():
    old = logger.log_level
    logger.log_level = "INFO"
    logmod._reset_display_dedup()
    try:
        tag = _tag("win")
        before = _file_lines()
        with _Collector():
            logger.bind_window(9876).info(f"{tag}-wmsg")
            _settle()
        recs = _records_for(tag, before)
        assert len(recs) == 1
        assert recs[0]["window"] == "9876"
    finally:
        logger.log_level = old
        logmod._reset_display_dedup()


def test_progress_emits_without_file_or_display():
    old = logger.log_level
    logger.log_level = "INFO"
    logmod._reset_display_dedup()
    try:
        with _Collector() as c:
            before_n = len(_file_lines())
            before_disp = len(c.items)
            received = []
            fn = lambda d, t: received.append((d, t))
            logger.progress_updated.connect(fn)
            try:
                logger.progress(2, 5)
                _settle()
            finally:
                try:
                    logger.progress_updated.disconnect(fn)
                except Exception:
                    pass
            assert received == [(2, 5)]
            assert len(_file_lines()) == before_n
            assert len(c.items) == before_disp
    finally:
        logger.log_level = old
        logmod._reset_display_dedup()


def test_bound_logger_progress_passthrough():
    old = logger.log_level
    logger.log_level = "INFO"
    logmod._reset_display_dedup()
    try:
        with _Collector() as c:
            before_n = len(_file_lines())
            before_disp = len(c.items)
            received = []
            fn = lambda d, t: received.append((d, t))
            logger.progress_updated.connect(fn)
            try:
                logger.bind(conf=0.5).progress(1, 3)
                logger.bind_window(1234).progress(3, 3)
                _settle()
            finally:
                try:
                    logger.progress_updated.disconnect(fn)
                except Exception:
                    pass
            assert (1, 3) in received
            assert (3, 3) in received
            assert len(_file_lines()) == before_n
            assert len(c.items) == before_disp
    finally:
        logger.log_level = old
        logmod._reset_display_dedup()


class _StubSig:
    def __init__(self, calls):
        self._calls = calls

    def emit(self, html):
        self._calls.append(html)


class _StubInst:
    def __init__(self, tb, calls):
        self.text_browser = tb
        self.append_log = _StubSig(calls)


def test_emit_to_browsers_dedupes_shared_browser():
    calls = []
    shared, solo = object(), object()
    stubs = [_StubInst(shared, calls), _StubInst(shared, calls), _StubInst(solo, calls)]
    with logmod._instances_lock:
        for s in stubs:
            logmod._instances.add(s)
    try:
        logmod._emit_to_browsers("<b>dup</b>")
    finally:
        with logmod._instances_lock:
            for s in stubs:
                logmod._instances.discard(s)
    assert calls == ["<b>dup</b>", "<b>dup</b>"]


class _FakeBrowser:
    def __init__(self):
        self.htmls = []

    def property(self, name):
        return None

    def verticalScrollBar(self):
        raise RuntimeError("headless")

    def insertHtml(self, html):
        self.htmls.append(html)

    def append(self, text):
        self.htmls.append(text)


def test_two_instances_one_browser_single_display_line():
    old = logger.log_level
    logger.log_level = "INFO"
    logmod._reset_display_dedup()
    tag = _tag("dupinst")
    fb = _FakeBrowser()
    r1, r2 = LogRedirect(fb), LogRedirect(fb)
    try:
        logger.info(tag)
        _settle()
        hits = [h for h in fb.htmls if tag in h]
        assert len(hits) == 1
    finally:
        with logmod._instances_lock:
            logmod._instances.discard(r1)
            logmod._instances.discard(r2)
        logger.log_level = old
        logmod._reset_display_dedup()


def test_daily_file_pattern_and_rotation_config():
    assert "{time:YYYY-MM-DD}" in logmod.LOG_FILE_PATTERN
    assert logmod.LOG_ROTATION == "00:00"
    assert logmod.LOG_RETENTION == "30 days"
    assert re.match(r"log_\d{4}-\d{2}-\d{2}\.log$",
                    Path(logmod._daily_log_file()).name)  # 生产默认（fixture 已重定向 LOG_FILE）


def test_set_log_file_redirect_and_restore(tmp_path):
    alt = tmp_path / "alt.log"
    assert logmod.set_log_file(str(alt)) is True
    try:
        tag = _tag("redir")
        logger.info(f"{tag}-hello")
        _settle()
        lines = alt.read_text(encoding="utf-8", errors="replace").splitlines()
        recs = [json.loads(l) for l in lines if tag in l]
        assert len(recs) == 1
        assert recs[0]["message"] == f"{tag}-hello"
    finally:
        # 回到本测例的隔离文件（autouse fixture 负责最终恢复生产 sink）
        assert logmod.set_log_file(str(Path(logmod.LOG_FILE))) is True


def test_production_logs_gain_zero_lines():
    prod = Path("logs")
    before_sizes = {}
    if prod.is_dir():
        for p in list(prod.glob("log_*.log")) + (
                [prod / "log.log"] if (prod / "log.log").exists() else []):
            try:
                before_sizes[p.name] = p.stat().st_size
            except OSError:
                pass
    tag = _tag("nopollute")
    before = _file_lines()
    logger.info(f"{tag}-hello")
    _settle()
    assert len(_records_for(tag, before)) == 1  # 自己的 slice 在隔离文件里可读
    if prod.is_dir():
        after = {p.name for p in prod.glob("log_*.log")}
        if (prod / "log.log").exists():
            after.add("log.log")
        assert after == set(before_sizes), (after, set(before_sizes))
        for name, size in before_sizes.items():
            assert (prod / name).stat().st_size == size, name
