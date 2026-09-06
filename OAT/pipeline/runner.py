import os
import random
import time
from typing import Dict, List, Optional

from OAT.utils.do_after_challenge import do_after_challenge
from OAT.utils.logging import logger
from OAT.utils.pause_state import is_stale, pause_aware_sleep, wait_if_paused
from .recognition import RecognitionEngine
from .task_definition import Task, TaskAction, parse_pipeline


class PipelineRunner:
    """MAA 风格管道运行器，替换 CommonChallenge"""

    def __init__(
        self,
        tasks: List[Task],
        engine: RecognitionEngine,
        script_dir: str,
        synchronizer=None,
        hidden_window: bool = False,
        sync_mode: bool = False,
    ):
        self.tasks = tasks
        self.engine = engine
        self.script_dir = script_dir
        self.synchronizer = synchronizer
        self.hidden_window = hidden_window
        self.sync_mode = sync_mode

        self._task_map: Dict[str, Task] = {t.name: t for t in tasks}
        self._global_tasks = [t for t in tasks if t.is_global]
        self._non_global_tasks = [t for t in tasks if not t.is_global]

        # 运行时状态
        self.current_next: Optional[str] = None
        self.consecutive_count: Dict[str, int] = {}
        self.retry_count: int = 0
        self.next_start_time: Optional[float] = None
        self.current_task: Optional[Task] = None
        self._last_matched_task: Optional[Task] = None
        self._last_matched_task_name: Optional[str] = None

    def run(self, times: int) -> bool:
        """执行挑战主循环"""
        try:
            i = 0
            while i < times:
                # 全局协同暂停：暂停时阻塞等待；收到停止请求则干净退出
                try:
                    if wait_if_paused() < 0:
                        try:
                            logger.info("挑战已停止")
                        except Exception:
                            pass
                        return False
                except Exception:
                    pass
                # 代际过期：双起旧线程即使错过 join 也必须退出（不替代上方停止检查）
                try:
                    try:
                        _stale = is_stale()
                    except Exception:
                        _stale = False
                    if _stale:
                        try:
                            logger.info("挑战已停止")
                        except Exception:
                            pass
                        return False
                except Exception:
                    pass
                self._check_global_tasks()

                if self.current_next and self.current_next in self._task_map:
                    if self._process_next_task():
                        task = self._task_map[self.current_next]
                        if task.is_start:
                            i += 1
                            logger.info(f"还剩{times - i}次挑战")
                            try:
                                logger.progress(i, times)
                            except Exception:
                                pass
                            self.consecutive_count.clear()
                            self.retry_count = 0
                else:
                    if self._process_non_global_tasks():
                        active = self._get_last_matched()
                        if active and active.is_start:
                            i += 1
                            logger.info(f"还剩{times - i}次挑战")
                            try:
                                logger.progress(i, times)
                            except Exception:
                                pass
                            self.consecutive_count.clear()
                            self.retry_count = 0
                # 两次识别之间的随机休眠（暂停不计入休眠，停止则干净退出）
                try:
                    _sleep_target = random.uniform(1.0, 2.0)
                except Exception:
                    _sleep_target = 1.0
                try:
                    _sleep_done = pause_aware_sleep(_sleep_target, 0.1)
                except Exception:
                    _sleep_done = True
                if not _sleep_done:
                    try:
                        logger.info("挑战已停止")
                    except Exception:
                        pass
                    return False

            logger.info(f"挑战完成！共执行{times}次挑战")
            do_after_challenge(
                getattr(self.engine, "hwnd", None),
                self.synchronizer,
                self.sync_mode,
            )
            return True
        except Exception as e:
            logger.error(f"挑战过程出现致命错误：{e}")
            return False

    def _check_global_tasks(self) -> None:
        """优先检测所有全局任务"""
        for task in self._global_tasks:
            if self._match_and_execute(task):
                self.consecutive_count.clear()
                self.retry_count = 0
                self.next_start_time = None

    def _process_next_task(self) -> bool:
        """处理 current_next 指定的任务，返回是否匹配成功"""
        task = self._task_map[self.current_next]
        if self.next_start_time is None:
            self.next_start_time = time.time()

        if time.time() - self.next_start_time > task.timeout:
            logger.warn(f"识别超时：{task.name}，回到默认识别模式")
            self.current_next = None
            self.next_start_time = None
            self.consecutive_count.clear()
            self.retry_count = 0
            return False

        if self._match_and_execute(task):
            if task.name != self._last_matched_task_name:
                self.retry_count = 0
            self._update_consecutive(task.name)
            if self._should_abort(task.name):
                return False
            self._last_matched_task_name = task.name
            self.next_start_time = None
            return True
        return False

    def _process_non_global_tasks(self) -> bool:
        """遍历所有非全局任务，返回是否匹配到任一任务"""
        for task in self._non_global_tasks:
            if self._match_and_execute(task):
                if task.name != self._last_matched_task_name:
                    self.retry_count = 0
                self._update_consecutive(task.name)
                if self._should_abort(task.name):
                    return False
                self._last_matched_task_name = task.name
                return True
        return False

    def _get_last_matched(self) -> Optional[Task]:
        return getattr(self, "_last_matched_task", None)

    def _match_and_execute(self, task: Task) -> bool:
        """对单个任务执行识别 → 点击 → 状态更新"""
        self.current_task = task
        result = self._recognize(task)
        if not result.found:
            return False

        if result.text:
            logger.info(f"OCR识别: {result.text}")
        logger.info(f"匹配到: {task.name} (置信度: {result.confidence:.2f})")

        self._execute_action(task, result)
        self._last_matched_task = task

        # 同步器通知
        if self.synchronizer and hasattr(self.synchronizer, "on_pipeline_task"):
            self.synchronizer.on_pipeline_task(task.name)

        # 更新 next 状态
        if task.next:
            self.current_next = task.next
        else:
            self.current_next = None

        self.next_start_time = None
        return True

    def _recognize(self, task: Task):
        """根据任务配置选择识别方式"""
        full_path = os.path.join(self.script_dir, task.template)

        if task.recognition == "ocr":
            return self.engine.find_text(task.ocr_text or "", task.ocr_confidence)
        elif task.recognition == "template+ocr":
            result = self.engine.find_template(full_path, task.threshold)
            if not result.found and task.ocr_text:
                result = self.engine.find_text(task.ocr_text, task.ocr_confidence)
            return result
        else:
            return self.engine.find_template(full_path, task.threshold)

    def _execute_action(self, task: Task, result) -> None:
        """执行任务匹配后的动作（click / swipe / wait，pipeline 专属）"""
        action_type = (task.action.type or "click")
        if action_type == "swipe":
            x1, y1 = self._resolve_click_coords(task, result)
            x2, y2 = x1, y1
            if task.action.ex_range and task.action.ey_range:
                try:
                    x2 = random.randint(int(task.action.ex_range[0]), int(task.action.ex_range[1]))
                except (ValueError, TypeError):
                    x2 = x1
                try:
                    y2 = random.randint(int(task.action.ey_range[0]), int(task.action.ey_range[1]))
                except (ValueError, TypeError):
                    y2 = y1
            self.engine.swipe(int(x1), int(y1), int(x2), int(y2),
                              duration=(task.action.duration if task.action.duration is not None else 0.5),
                              sync_mode=self.sync_mode)
        elif action_type == "wait":
            raw = task.action.duration if task.action.duration is not None else 1.0
            try:
                seconds = float(raw)
            except (ValueError, TypeError):
                seconds = 1.0
            time.sleep(max(0.0, seconds))
        else:
            x, y = self._resolve_click_coords(task, result)
            self.engine.click(x, y, sync_mode=self.sync_mode)

    def _resolve_click_coords(self, task: Task, result) -> tuple:
        """确定点击坐标"""
        if task.action.target == "fixed_coord" and task.action.x_range and task.action.y_range:
            return (
                random.randint(int(task.action.x_range[0]), int(task.action.x_range[1])),
                random.randint(int(task.action.y_range[0]), int(task.action.y_range[1])),
            )
        # matched / ocr_area
        if result.region:
            # OCR 返回的 region 可能是 float，randint/位运算要求 int，这里统一转换
            rx, ry, rw, rh = (int(v) for v in result.region)
            rw, rh = max(0, rw), max(0, rh)
            cx = rx + rw // 2
            cy = ry + rh // 2
            range_x = rw // 3
            range_y = rh // 3
            lo_x, hi_x = max(rx, cx - range_x), min(rx + rw, cx + range_x)
            lo_y, hi_y = max(ry, cy - range_y), min(ry + rh, cy + range_y)
            # 防御：int 截断后理论上 lo<=hi，若异常则回退到中心点
            if lo_x > hi_x:
                lo_x, hi_x = cx, cx
            if lo_y > hi_y:
                lo_y, hi_y = cy, cy
            return (
                random.randint(lo_x, hi_x),
                random.randint(lo_y, hi_y),
            )
        return (0, 0)

    def _update_consecutive(self, task_name: str) -> None:
        self.consecutive_count[task_name] = self.consecutive_count.get(task_name, 0) + 1

    def _should_abort(self, task_name: str) -> bool:
        count = self.consecutive_count.get(task_name, 0)
        try:
            budget = int(getattr(self._task_map.get(task_name), "max_consecutive", 5))
        except (ValueError, TypeError, AttributeError):
            budget = 5
        if budget <= 0:
            budget = 5
        if count >= budget:
            logger.error(f"图片 {task_name} 已连续出现{budget}次，强制停止")
            return True
        if count >= 2:
            self.retry_count += 1
            if self.retry_count >= budget:
                logger.error(f"重试{budget}次后图片 {task_name} 仍然存在，结束挑战")
                return True
        return False


def create_and_run_pipeline(
    config: dict,
    script_dir: str,
    window_title: str,
    hidden_window: bool = False,
    sync_mode: bool = False,
    synchronizer=None,
    sync_mode_value: str = "exactly_sync",
    threshold: int = None,
    find_mode: str = None,
    times: int = 1,
) -> bool:
    """便捷函数：解析配置 → 创建引擎 → 创建运行器 → 执行

    供 source/__init__.py 中的 mode_choice() 调用。
    """
    from OAT.tools import settings
    from OAT.tools.GetDC import WindowCapture

    if threshold is None:
        threshold = settings.FIND_THRESHOLD
    if find_mode is None:
        find_mode = settings.FIND_MODE

    # 获取窗口句柄
    hwnd = None
    try:
        import win32gui

        hwnd = win32gui.FindWindow(None, window_title)
    except Exception:
        pass

    engine = OpenCVRecognitionEngine(
        hwnd=hwnd,
        threshold=threshold,
        find_mode=find_mode,
        synchronizer=synchronizer,
        hidden_window=hidden_window,
    )
    logger.info(f"管道识别模式: {'后台' if hidden_window else '前台'}")

    pipeline_data = config.get("pipeline", config)
    tasks = parse_pipeline(pipeline_data)

    runner = PipelineRunner(
        tasks=tasks,
        engine=engine,
        script_dir=script_dir,
        synchronizer=synchronizer,
        hidden_window=hidden_window,
        sync_mode=sync_mode,
    )
    return runner.run(times)


# 延迟导入避免循环引用
from .recognition_opencv import OpenCVRecognitionEngine  # noqa: E402
