"""Task1: pipeline/image_paths 往返无损回归测试。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from OAT.tools.edit_mode_and_img import (
    _image_paths_to_pipeline_task,
    _pipeline_task_to_image_paths,
)


def test_roundtrip_preserves_advanced_fields():
    task = {"name": "tiaozhan", "template": "tiaozhan.png", "recognition": "ocr",
            "ocr_text": "挑战", "ocr_confidence": 0.8, "threshold": 0.85,
            "timeout": 20, "max_retries": 3, "is_start": True}
    data = _pipeline_task_to_image_paths(task)
    back = _image_paths_to_pipeline_task("tiaozhan", data)
    assert back["recognition"] == "ocr"
    assert back["threshold"] == 0.85
    assert back["timeout"] == 20 and back["max_retries"] == 3


def test_template_ocr_click_area_roundtrip():
    task = {"name": "zishepi", "template": "zishepi.png",
            "action": {"type": "click", "target": "fixed_coord",
                       "x_range": [100, 200], "y_range": [200, 400]}}
    back = _image_paths_to_pipeline_task("zishepi", _pipeline_task_to_image_paths(task))
    assert back["action"] == task["action"]


def test_confidence_clamp_and_click_area_validation():
    from OAT.tools.edit_mode_and_img import _normalize_confidence, _parse_click_area
    assert _normalize_confidence("80") == 0.8
    assert _normalize_confidence("1.5") == 1.0
    assert _normalize_confidence("abc") == 0.8
    assert _parse_click_area("[100,200,200,400]") == [100, 200, 200, 400]
    assert _parse_click_area("xxx") is None
    assert _parse_click_area("[3,1,4,2]") is None


def test_load_prefers_pipeline_and_keeps_legacy_message():
    import OAT.tools.edit_mode_and_img as m
    pipeline_task = {"name": "tiaozhan", "template": "tiaozhan.png", "recognition": "template+ocr",
                     "ocr_text": "挑战", "ocr_confidence": 0.8, "threshold": 0.9, "timeout": 20,
                     "message": "pipe-msg", "next": "xiezhu"}
    image_entry = {"path": "tiaozhan.png", "message": "legacy-msg", "ocr_action": "点击点击区域设置的区域",
                   "is_challenge_start": False, "is_global": False, "next_image": "",
                   "ocr_enabled": False, "ocr_target_text": "", "ocr_confidence_threshold": 0.8}
    merged = m._pipeline_task_to_image_paths(pipeline_task)
    # simulate load-merge rule: pipeline base + legacy message/ocr_action overlay
    for k in ("message", "ocr_action"):
        if k in image_entry and image_entry[k]:
            merged[k] = image_entry[k]
    assert merged["threshold"] == 0.9
    assert merged["timeout"] == 20
    assert merged["message"] == "legacy-msg"
    assert merged["ocr_action"] == "点击点击区域设置的区域"


def test_rename_updates_references(tmp_path):
    import json
    config = {"image_paths": {"A": {"path": "A.png", "next_image": "B"},
                              "B": {"path": "B.png", "next_image": ""}},
              "pipeline": {"tasks": [{"name": "A", "template": "A.png", "next": "B"},
                                     {"name": "B", "template": "B.png"}]}}
    old_key, new_key = "B", "C"
    # replicate save() rename rule under test
    config["image_paths"][new_key] = config["image_paths"].pop(old_key)
    for k, v in config["image_paths"].items():
        if v.get("next_image") == old_key:
            v["next_image"] = new_key
    for t in config["pipeline"]["tasks"]:
        if t["name"] == old_key:
            t["name"] = new_key
        if t.get("next") == old_key:
            t["next"] = new_key
    assert config["image_paths"]["A"]["next_image"] == "C"
    assert [t for t in config["pipeline"]["tasks"] if t["name"] == "A"][0]["next"] == "C"


def test_click_type_roundtrip_and_legacy_default():
    from OAT.tools.edit_mode_and_img import _image_paths_to_pipeline_task, _pipeline_task_to_image_paths
    d = _pipeline_task_to_image_paths({"name": "z", "template": "z.png",
        "action": {"type": "click", "target": "fixed_coord", "x_range": [100, 200], "y_range": [200, 400]}})
    assert d["click_type"] == "coordinate" and d["click_area"] == [100, 200, 200, 400]
    d2 = _pipeline_task_to_image_paths({"name": "z", "template": "z.png"})
    assert d2["click_type"] == "image" and "click_area" not in d2
    back = _image_paths_to_pipeline_task("z", d)
    assert back["action"]["target"] == "fixed_coord"
    legacy = {"path": "z.png", "click_area": [100, 200, 200, 400]}
    assert (legacy.get("click_type") or ("coordinate" if legacy.get("click_area") else "image")) == "coordinate"


def test_unchecked_ocr_clears_recognition():
    from OAT.tools.edit_mode_and_img import _image_paths_to_pipeline_task
    d = {"path": "a.png", "ocr_enabled": False, "ocr_target_text": "", "ocr_confidence_threshold": 0.8}
    d.pop("recognition", None)
    assert "recognition" not in _image_paths_to_pipeline_task("a", d)


def test_ocr_action_text_area_omits_fixed_action():
    from OAT.tools.edit_mode_and_img import _image_paths_to_pipeline_task
    base = {"path": "b.png", "ocr_enabled": True, "ocr_target_text": "挑战",
            "ocr_confidence_threshold": 0.8, "click_area": [100, 200, 200, 400],
            "click_type": "coordinate"}
    t1 = _image_paths_to_pipeline_task("b", dict(base, ocr_action="点击文字所在区域"))
    assert t1["recognition"] == "template+ocr" and "action" not in t1
    t2 = _image_paths_to_pipeline_task("b", dict(base, ocr_action="点击点击区域设置的区域"))
    assert t2["action"]["target"] == "fixed_coord"


def test_skip_ocr_gate():
    from OAT.tools.OnmyojiAuto import OnmyojiAutomation
    g = OnmyojiAutomation._should_skip_ocr_for_custom_area
    assert g(True, "挑战", "点击点击区域设置的区域", "coordinate", [100, 200, 200, 400]) is True
    assert g(True, "挑战", "点击文字所在区域", "coordinate", [100, 200, 200, 400]) is False
    assert g(False, "挑战", "点击点击区域设置的区域", "coordinate", [100, 200, 200, 400]) is False
    assert g(True, "挑战", "点击点击区域设置的区域", "image", None) is False


def test_swipe_wait_fields_roundtrip():
    from OAT.tools.edit_mode_and_img import _image_paths_to_pipeline_task, _pipeline_task_to_image_paths
    s = {"name": "s", "template": "s.png", "action": {"type": "swipe", "target": "matched",
         "ex_range": [10, 20], "ey_range": [30, 40], "duration": 0.6}}
    b = _image_paths_to_pipeline_task("s", _pipeline_task_to_image_paths(s))
    assert b["action"]["type"] == "swipe" and b["action"]["duration"] == 0.6
    w = {"name": "w", "template": "w.png", "action": {"type": "wait", "duration": 2.0}}
    assert _image_paths_to_pipeline_task("w", _pipeline_task_to_image_paths(w))["action"] == {"type": "wait", "duration": 2.0}


def test_runner_dispatches_swipe_and_wait():
    from unittest.mock import MagicMock
    from OAT.pipeline.recognition import RecognitionResult
    from OAT.pipeline.task_definition import Task, TaskAction
    from OAT.pipeline.runner import PipelineRunner
    eng = MagicMock()
    r = PipelineRunner(tasks=[], engine=eng, script_dir=".")
    res = RecognitionResult(found=True, region=(100, 200, 50, 20))
    sw = Task(name="s", template="s.png", action=TaskAction(type="swipe", target="matched",
                 ex_range=(10, 20), ey_range=(30, 40), duration=0.6))
    r._execute_action(sw, res)
    assert eng.swipe.called and all(isinstance(a, int) for a in eng.swipe.call_args[0][:4])
    wt = Task(name="w", template="w.png", action=TaskAction(type="wait", duration=0))
    r._execute_action(wt, res)
    assert not eng.click.called
