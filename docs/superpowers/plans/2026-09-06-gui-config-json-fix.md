# GUI 图像配置 JSON 格式修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让“编辑图像配置”窗口保存的 config.json 与管道运行时要的格式完全一致，往返不丢字段。

**Architecture:** 不换架构，保持 image_paths + pipeline.tasks 双写兼容老 common_challenge；只修两个转换函数对称性 + 对话框校验 + 改名引用完整性。运行时仍以 pipeline 为准（OAT/source/__init__.py:80）。

**Tech Stack:** Python, PySide6 QDialog, JSON, parse_pipeline（OAT/pipeline/task_definition.py）

**Spec:** 本 plan 即 spec（用户已用弹窗审批：接受冗余字段 / ocr_action 实现语义并拦截 / 落盘并开干 Task1）。

## Global Constraints

- 运行时以 pipeline.tasks 为准，image_paths 仅兼容老链路。
- image_paths 允许冗余存 recognition/threshold/timeout/max_retries（已审批）。
- ocr_action 选“点击自定义区域”但无 click_area 时必须拦截（已审批）。
- ocr_confidence 归一化到 0-1（用户填 80 视为 80%）。
- 不主动 commit（无明确要求不提交）。

---

## 文件结构

- Modify: `OAT/tools/edit_mode_and_img.py:95-127` 正向转换 `_image_paths_to_pipeline_task`
- Modify: `OAT/tools/edit_mode_and_img.py:130-163` 逆向转换 `_pipeline_task_to_image_paths`
- Modify: `OAT/tools/edit_mode_and_img.py:388-530` `ImageConfigDialog.save`
- Modify: `OAT/tools/edit_mode_and_img.py:1208-1231` 打开加载优先级
- Modify: `OAT/tools/edit_mode_and_img.py:499-507` 改名引用更新
- Test: `test/test_pipeline_config_roundtrip.py`（新建）
- Verify: `OAT/source/huntu/config.json`

---

### Task 1: 补对称转换（丢字段的根因）

**Files:**
- Modify: `OAT/tools/edit_mode_and_img.py:95-163`
- Test: `test/test_pipeline_config_roundtrip.py`

**Interfaces:**
- Consumes: pipeline task dict（name/template/recognition/threshold/ocr_text/ocr_confidence/next/is_start/is_global/action/timeout/max_retries）
- Produces: `def _image_paths_to_pipeline_task(name: str, data: dict) -> dict`、`def _pipeline_task_to_image_paths(task: dict) -> dict` 往返无损（除 message 只存 image_paths）

- [ ] **Step 1: 写失败测试**

```python
def test_roundtrip_preserves_advanced_fields():
    from OAT.tools.edit_mode_and_img import _image_paths_to_pipeline_task, _pipeline_task_to_image_paths
    task = {"name": "tiaozhan", "template": "tiaozhan.png", "recognition": "ocr",
            "ocr_text": "挑战", "ocr_confidence": 0.8, "threshold": 0.85,
            "timeout": 20, "max_retries": 3, "is_start": True}
    data = _pipeline_task_to_image_paths(task)
    back = _image_paths_to_pipeline_task("tiaozhan", data)
    assert back["recognition"] == "ocr"
    assert back["threshold"] == 0.85
    assert back["timeout"] == 20 and back["max_retries"] == 3

def test_template_ocr_click_area_roundtrip():
    from OAT.tools.edit_mode_and_img import _image_paths_to_pipeline_task, _pipeline_task_to_image_paths
    task = {"name": "zishepi", "template": "zishepi.png",
            "action": {"type": "click", "target": "fixed_coord", "x_range": [100, 200], "y_range": [200, 400]}}
    back = _image_paths_to_pipeline_task("zishepi", _pipeline_task_to_image_paths(task))
    assert back["action"] == task["action"]
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest test/test_pipeline_config_roundtrip.py -v`
Expected: FAIL（threshold/timeout 丢失，ocr 变 template）

- [ ] **Step 3: 最小实现**

见本文件“附录 A：Task1 实现代码”。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest test/test_pipeline_config_roundtrip.py -v`
Expected: PASS

### Task 2: ocr_action 语义 + 输入校验

**Files:**
- Modify: `OAT/tools/edit_mode_and_img.py:283,310,318-327,419-445`
- Test: `test/test_pipeline_config_roundtrip.py` 追加

**Interfaces:**
- Consumes: Task1 的转换函数
- Produces: `def _normalize_confidence(raw, default=0.8) -> float`、`def _parse_click_area(raw) -> list | None`；非法输入拦截不落盘

- [ ] **Step 1: 写失败测试**

```python
def test_confidence_clamp_and_click_area_validation():
    from OAT.tools.edit_mode_and_img import _normalize_confidence, _parse_click_area
    assert _normalize_confidence("80") == 0.8
    assert _normalize_confidence("1.5") == 1.0
    assert _normalize_confidence("abc") == 0.8
    assert _parse_click_area("[100,200,200,400]") == [100, 200, 200, 400]
    assert _parse_click_area("xxx") is None
    assert _parse_click_area("[3,1,4,2]") is None
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest test/test_pipeline_config_roundtrip.py::test_confidence_clamp_and_click_area_validation -v`
Expected: FAIL（函数不存在）

- [ ] **Step 3: 最小实现**

见“附录 B”。save() 改动：ocr_threshold 走 _normalize_confidence；click_area 走 _parse_click_area，非法弹 QMessageBox.warning 并 return；ocr_action=="点击点击区域设置的区域"但无 click_area 时弹警告 return。

- [ ] **Step 4: 运行通过**

Run: `python -m pytest test/test_pipeline_config_roundtrip.py -v`
Expected: PASS

### Task 3: 加载优先级 + 改名引用完整性

**Files:**
- Modify: `OAT/tools/edit_mode_and_img.py:1208-1221,499-507`

- [ ] **Step 1: 测试**：构造 config 同时有 image_paths.tiaozhan（旧）和 pipeline tiaozhan（新，含 threshold），断言对话框加载到的是 pipeline 值；构造 A.next=B，改名 B->C，断言 A.next 自动更新为 C。
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**：打开时若 pipeline 有同名 task 则以 pipeline 为准（二者合并，pipeline 优先）；save 改名时遍历 config["image_paths"] 的 next_image 和 pipeline.tasks 的 next 做同名替换。
- [ ] **Step 4: 验证 + 回归 huntu（7 个 task 数量不变）**

### Task 4: 真实配置回归

- [ ] 用 OAT/source/huntu/config.json 做往返脚本：load → _pipeline_task_to_image_paths → _image_paths_to_pipeline_task → parse_pipeline，断言 7 个 task 数量不变、tiaozhan 的 ocr_text=挑战、zishepi 的 x_range/y_range 不变。
- [ ] 跑 `python -m pytest test/test_pipeline_config_roundtrip.py -v` 全绿。

## 附录 A：Task1 实现代码

```python
def _image_paths_to_pipeline_task(name: str, data: dict) -> dict:
    task = {"name": name, "template": data.get("path", name + ".png")}
    if data.get("is_challenge_start"):
        task["is_start"] = True
    if data.get("is_global"):
        task["is_global"] = True
    if data.get("next_image"):
        task["next"] = data["next_image"]
    if data.get("threshold") is not None:
        try:
            task["threshold"] = float(data["threshold"])
        except (ValueError, TypeError):
            pass
    ocr_enabled = data.get("ocr_enabled", False)
    ocr_text = (data.get("ocr_target_text") or "").strip()
    ocr_mode = data.get("recognition", "")
    if ocr_mode == "ocr" or (ocr_enabled and ocr_text and data.get("recognition") == "ocr"):
        task["recognition"] = "ocr"
        task["ocr_text"] = ocr_text
        task["ocr_confidence"] = float(data.get("ocr_confidence_threshold", 0.8))
    elif ocr_enabled and ocr_text:
        task["recognition"] = "template+ocr"
        task["ocr_text"] = ocr_text
        task["ocr_confidence"] = float(data.get("ocr_confidence_threshold", 0.8))
    click_area = data.get("click_area")
    if click_area and len(click_area) == 4:
        task["action"] = {"type": "click", "target": "fixed_coord",
                          "x_range": [int(click_area[0]), int(click_area[1])],
                          "y_range": [int(click_area[2]), int(click_area[3])]}
    if data.get("timeout") is not None:
        task["timeout"] = int(data["timeout"])
    if data.get("max_retries") is not None:
        task["max_retries"] = int(data["max_retries"])
    return task
```

逆向保留 recognition/threshold/timeout/max_retries，删掉重复 is_global 键，click_area 转 int（详见执行时文件）。

## 附录 B：Task2 实现代码

```python
def _normalize_confidence(raw, default=0.8) -> float:
    try:
        v = float(raw)
    except (ValueError, TypeError):
        return default
    if v > 1.0:
        v = v / 100.0
    return min(1.0, max(0.0, v))

def _parse_click_area(raw):
    import ast
    try:
        area = ast.literal_eval(raw)
    except (ValueError, SyntaxError, TypeError):
        return None
    if not isinstance(area, list) or len(area) != 4:
        return None
    try:
        area = [int(x) for x in area]
    except (ValueError, TypeError):
        return None
    if area[0] > area[1] or area[2] > area[3]:
        return None
    return area
```
