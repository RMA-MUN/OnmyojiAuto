"""Task E3: zuihou 连续匹配预算（默认 5，配置可调大到 20）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from OAT.pipeline.runner import PipelineRunner
from OAT.pipeline.task_definition import Task, parse_pipeline


def _runner_with(task):
    return PipelineRunner(tasks=[task], engine=object(), script_dir=".")


def test_default_budget_aborts_at_five():
    r = _runner_with(Task(name="zuihou", template="zuihou.png"))
    assert r._task_map["zuihou"].max_consecutive == 5
    for _ in range(4):
        r._update_consecutive("zuihou")
        assert r._should_abort("zuihou") is False
    r._update_consecutive("zuihou")
    assert r._should_abort("zuihou") is True


def test_budget_20_survives_five_consecutive():
    r = _runner_with(Task(name="zuihou", template="zuihou.png", max_consecutive=20))
    for _ in range(5):
        r._update_consecutive("zuihou")
        assert r._should_abort("zuihou") is False


def test_budget_20_boundary():
    r = _runner_with(Task(name="zuihou", template="zuihou.png", max_consecutive=20))
    r.retry_count = 0
    r.consecutive_count["zuihou"] = 19
    assert r._should_abort("zuihou") is False
    r.retry_count = 0
    r.consecutive_count["zuihou"] = 20
    assert r._should_abort("zuihou") is True


def test_budget_20_survives_ten_consecutive_and_aborts_at_21():
    r = _runner_with(Task(name="zuihou", template="zuihou.png", max_consecutive=20))
    for _ in range(10):
        r._update_consecutive("zuihou")
        assert r._should_abort("zuihou") is False
    for _ in range(10):
        r._update_consecutive("zuihou")
    r._update_consecutive("zuihou")
    assert r._should_abort("zuihou") is True


def test_parse_max_consecutive_defaults_and_invalid():
    tasks = parse_pipeline({"tasks": [
        {"name": "a", "template": "a.png"},
        {"name": "b", "template": "b.png", "max_consecutive": 20},
        {"name": "c", "template": "c.png", "max_consecutive": 0},
        {"name": "d", "template": "d.png", "max_consecutive": -3},
        {"name": "e", "template": "e.png", "max_consecutive": "x"},
    ]})
    assert [t.max_consecutive for t in tasks] == [5, 20, 5, 5, 5]


def test_converters_preserve_max_consecutive():
    from OAT.tools.edit_mode_and_img import (
        _image_paths_to_pipeline_task,
        _pipeline_task_to_image_paths,
    )
    t = {"name": "zuihou", "template": "zuihou.png", "max_consecutive": 20}
    back = _image_paths_to_pipeline_task("zuihou", _pipeline_task_to_image_paths(t))
    assert back["max_consecutive"] == 20
    # 缺键 → 省略 → parse 回退 5（往返稳定，不污染旧 JSON）
    d2 = _pipeline_task_to_image_paths({"name": "a", "template": "a.png"})
    back2 = _image_paths_to_pipeline_task("a", d2)
    assert "max_consecutive" not in back2
    assert parse_pipeline({"tasks": [back2]})[0].max_consecutive == 5
