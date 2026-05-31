from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TaskAction:
    """任务匹配后执行的动作"""

    type: str = "click"  # click, swipe, wait
    target: str = "matched"  # matched, fixed_coord
    x_range: Optional[tuple] = None  # (min_x, max_x)
    y_range: Optional[tuple] = None  # (min_y, max_y)


@dataclass
class Task:
    """单个管道任务，类比 MAA TaskModel"""

    name: str
    template: str  # 模板图片路径（相对 mode 目录）
    recognition: str = "template"  # template, ocr, template+ocr

    # 识别参数
    threshold: Optional[float] = None
    ocr_text: Optional[str] = None
    ocr_confidence: float = 0.8

    # 管道控制
    next: Optional[str] = None  # 匹配后跳转的任务名
    is_start: bool = False  # 匹配此任务时，挑战计数 +1
    is_global: bool = False  # 全局任务（始终检测，不受 next 限制）

    # 动作
    action: TaskAction = field(default_factory=TaskAction)

    # 超时和重试
    timeout: int = 15
    max_retries: int = 5


def parse_pipeline(pipeline_data: dict) -> List[Task]:
    """从 dict（来自 config.json 的 pipeline key）解析为 Task 列表"""
    tasks = []
    for item in pipeline_data.get("tasks", []):
        action_data = item.get("action", {})
        action = TaskAction(
            type=action_data.get("type", "click"),
            target=action_data.get("target", "matched"),
            x_range=tuple(action_data["x_range"]) if "x_range" in action_data else None,
            y_range=tuple(action_data["y_range"]) if "y_range" in action_data else None,
        )
        task = Task(
            name=item["name"],
            template=item["template"],
            recognition=item.get("recognition", "template"),
            threshold=item.get("threshold"),
            ocr_text=item.get("ocr_text"),
            ocr_confidence=item.get("ocr_confidence", 0.8),
            next=item.get("next"),
            is_start=item.get("is_start", False),
            is_global=item.get("is_global", False),
            action=action,
            timeout=item.get("timeout", 15),
            max_retries=item.get("max_retries", 5),
        )
        tasks.append(task)
    return tasks
