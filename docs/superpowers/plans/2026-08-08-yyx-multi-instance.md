# yyx 多开迁移实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 移除 2box 多开，改为 OAT 按用户输入的数量与间隔在后台批量启动 `yyx\yyx-launcher.exe`，游戏路径自动写入 `yyx\yyx-launcher.ini`。

**Architecture:** 重写 `MultiInstanceManager`（保留类名与接口语义）：`launch_instances(exe_path, count, interval)` 先写 ini 再循环 Popen launcher，间隔 sleep 在后台线程；UI 通过 `instance_added` 信号（4 参数）跨线程通知 GUI 更新表格；实例表格显示 PID/状态/启动时间，关闭用 psutil 进程树杀。删除 `2box/` 与 `build_2box.py`。

**Tech Stack:** Python 3.12（.venv）、PyQt6 + qfluentwidgets、psutil、pywin32、unittest（stdlib，项目无 pytest）。

## Global Constraints

- 一律使用 `.venv\Scripts\python.exe` 运行（系统 Python 混装 PyQt5/6+PySide6，会崩）
- 测试用 unittest + unittest.mock（stdlib），禁止新增依赖；运行命令：`.venv\Scripts\python.exe -m unittest discover -s test -p "test_multi_instance_*.py" -v`
- 不写代码注释（项目风格）
- 所有 Qt 控件操作只在 GUI 线程；worker 线程只能 emit 信号（已确立的模式）
- `yyx-launcher.ini` 格式必须与原始文件逐字节兼容：`[YYXLaucher]\r\nYYSLaunchPath=<path>\r\n`（段名含原始拼写 YYXLaucher，CRLF 结尾），ANSI 编码 `locale.getpreferredencoding(False)`（原文件为 ASCII/ANSI）
- 目标平台：Windows only（win32gui/psutil/launcher）

---

### Task 1: 重写 MultiInstanceManager 为 yyx 版

**Files:**
- Modify: `OAT/tools/MultiInstanceManager.py`（整体重写）
- Create: `test/test_multi_instance_manager.py`

**Interfaces:**
- Consumes: 无（独立模块）
- Produces（Task 2/3 依赖）:
  - `MultiInstanceManager(yyx_dir: Optional[Path] = None)` — yyx_dir 缺省为 `项目根/yyx`
  - `GameInstance` dataclass: `instance_id: int`, `pid: Optional[int] = None`, `status: str = "启动中"`, `launched_at: str = ""`
  - `build_init_file(exe_path: str) -> None`
  - `launch_instances(exe_path: str, count: int = 1, interval: float = 5.0) -> list[GameInstance]` — launcher 缺失抛 `FileNotFoundError`；ini 写入失败原样抛异常；单次 Popen 失败该实例 status=`"失败: <e>"` 并继续
  - `close_instance(instance_id: int) -> bool`
  - `close_all() -> int`
  - `get_instance_status(instance_id: int) -> str`
  - `refresh_all_status() -> None`
  - `get_all_instances() -> dict[int, GameInstance]`

- [ ] **Step 1: 写失败的测试**

创建 `test/test_multi_instance_manager.py`：

```python
import locale
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from OAT.tools.MultiInstanceManager import MultiInstanceManager

ENCODING = locale.getpreferredencoding(False)


class FakeProc:
    pid = 1234


class TestBuildInitFile(unittest.TestCase):
    def test_writes_expected_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = MultiInstanceManager(yyx_dir=Path(tmp))
            manager.build_init_file(r"D:\Games\Launch.exe")
            expected = "[YYXLaucher]\r\nYYSLaunchPath=D:\\Games\\Launch.exe\r\n"
            self.assertEqual(
                manager.launcher_ini.read_bytes(),
                expected.encode(ENCODING),
            )

    def test_overwrites_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            ini = Path(tmp) / "yyx-launcher.ini"
            ini.write_text("old", encoding=ENCODING)
            manager = MultiInstanceManager(yyx_dir=Path(tmp))
            manager.build_init_file(r"C:\New\Launch.exe")
            self.assertIn("C:\\New\\Launch.exe", ini.read_text(encoding=ENCODING))


class TestLaunchInstances(unittest.TestCase):
    def test_starts_n_times_with_interval(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "yyx-launcher.exe").write_bytes(b"MZ")
            manager = MultiInstanceManager(yyx_dir=Path(tmp))
            with mock.patch("OAT.tools.MultiInstanceManager.subprocess.Popen",
                            return_value=FakeProc()) as popen, \
                 mock.patch("OAT.tools.MultiInstanceManager.time.sleep") as sleep:
                launched = manager.launch_instances(r"D:\Games\Launch.exe", count=3, interval=0.01)
            self.assertEqual(popen.call_count, 3)
            self.assertEqual(sleep.call_count, 2)
            self.assertEqual(len(launched), 3)
            for inst in launched:
                self.assertEqual(inst.pid, 1234)
                self.assertEqual(inst.status, "运行中")
                self.assertTrue(inst.launched_at)
            self.assertIn(r"D:\Games\Launch.exe",
                          manager.launcher_ini.read_text(encoding=ENCODING))

    def test_failure_marks_instance_and_continues(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "yyx-launcher.exe").write_bytes(b"MZ")
            manager = MultiInstanceManager(yyx_dir=Path(tmp))
            with mock.patch("OAT.tools.MultiInstanceManager.subprocess.Popen",
                            side_effect=[FakeProc(), OSError("boom"), FakeProc()]):
                launched = manager.launch_instances("x", count=3, interval=0)
            self.assertEqual(launched[1].status, "失败: boom")
            self.assertIsNone(launched[1].pid)
            self.assertEqual(launched[2].pid, 1234)

    def test_missing_launcher_raises_without_writing_ini(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = MultiInstanceManager(yyx_dir=Path(tmp))
            with self.assertRaises(FileNotFoundError):
                manager.launch_instances("x", count=1, interval=0)
            self.assertFalse(manager.launcher_ini.exists())


class TestCloseAndStatus(unittest.TestCase):
    def _manager_with_instance(self, tmp, pid=111):
        Path(tmp, "yyx-launcher.exe").write_bytes(b"MZ")
        manager = MultiInstanceManager(yyx_dir=Path(tmp))
        inst = manager.launch_instances("x", count=1, interval=0)
        manager.instances[1].pid = pid
        return manager, inst[0]

    def test_close_kills_process_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, inst = self._manager_with_instance(tmp)
            child1, child2 = mock.Mock(), mock.Mock()
            parent = mock.Mock()
            parent.children.return_value = [child1, child2]
            with mock.patch("OAT.tools.MultiInstanceManager.psutil.pid_exists",
                            return_value=True) as pid_exists, \
                 mock.patch("OAT.tools.MultiInstanceManager.psutil.Process",
                            return_value=parent) as proc_cls, \
                 mock.patch("OAT.tools.MultiInstanceManager.psutil.wait_procs",
                            return_value=([child1, child2, parent], [])):
                result = manager.close_instance(1)
            self.assertTrue(result)
            self.assertEqual(inst.status, "已关闭")
            pid_exists.assert_called_once_with(111)
            proc_cls.assert_called_once_with(111)
            self.assertEqual(child1.terminate.call_count, 1)
            self.assertEqual(child2.terminate.call_count, 1)
            self.assertEqual(parent.terminate.call_count, 1)

    def test_close_dead_pid_marks_exited(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, inst = self._manager_with_instance(tmp)
            with mock.patch("OAT.tools.MultiInstanceManager.psutil.pid_exists",
                            return_value=False):
                result = manager.close_instance(1)
            self.assertTrue(result)
            self.assertEqual(inst.status, "已退出")

    def test_close_missing_instance_returns_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = MultiInstanceManager(yyx_dir=Path(tmp))
            self.assertFalse(manager.close_instance(99))

    def test_status_follows_pid_liveness(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, inst = self._manager_with_instance(tmp)
            with mock.patch("OAT.tools.MultiInstanceManager.psutil.pid_exists",
                            return_value=True):
                self.assertEqual(manager.get_instance_status(1), "运行中")
            with mock.patch("OAT.tools.MultiInstanceManager.psutil.pid_exists",
                            return_value=False):
                self.assertEqual(manager.get_instance_status(1), "已退出")

    def test_status_preserves_failed_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "yyx-launcher.exe").write_bytes(b"MZ")
            manager = MultiInstanceManager(yyx_dir=Path(tmp))
            manager.instances[1] = manager.launch_instances("x", count=1, interval=0)[0]
            manager.instances[1].pid = None
            manager.instances[1].status = "失败: x"
            self.assertEqual(manager.get_instance_status(1), "失败: x")

    def test_close_all_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, _ = self._manager_with_instance(tmp)
            manager.launch_instances("x", count=1, interval=0)
            with mock.patch("OAT.tools.MultiInstanceManager.psutil.pid_exists",
                            return_value=True), \
                 mock.patch("OAT.tools.MultiInstanceManager.psutil.Process",
                            return_value=mock.Mock()) as proc_cls, \
                 mock.patch("OAT.tools.MultiInstanceManager.psutil.wait_procs",
                            return_value=([], [])):
                closed = manager.close_all()
            self.assertEqual(closed, 2)
            self.assertEqual(proc_cls.call_count, 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试验证失败**

Run: `.venv\Scripts\python.exe -m unittest discover -s test -p "test_multi_instance_*.py" -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'OAT.tools.MultiInstanceManager'`（旧模块已删除或 import 失败）

- [ ] **Step 3: 重写实现**

整体替换 `OAT/tools/MultiInstanceManager.py`：

```python
import locale
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import psutil


@dataclass
class GameInstance:
    instance_id: int
    pid: Optional[int] = None
    status: str = "启动中"
    launched_at: str = ""


class MultiInstanceManager:
    def __init__(self, yyx_dir: Optional[Path] = None):
        self.yyx_dir = Path(yyx_dir) if yyx_dir else Path(__file__).parent.parent.parent / "yyx"
        self.launcher_exe = self.yyx_dir / "yyx-launcher.exe"
        self.launcher_ini = self.yyx_dir / "yyx-launcher.ini"

        self.instances: dict[int, GameInstance] = {}
        self.next_id = 1

    def build_init_file(self, exe_path: str) -> None:
        self.launcher_ini.write_text(
            f"[YYXLaucher]\r\nYYSLaunchPath={exe_path}\r\n",
            encoding=locale.getpreferredencoding(False)
        )

    def launch_instances(self, exe_path: str, count: int = 1, interval: float = 5.0) -> list[GameInstance]:
        if not self.launcher_exe.exists():
            raise FileNotFoundError(f"yyx-launcher.exe 不存在: {self.launcher_exe}")

        self.build_init_file(exe_path)

        launched = []
        for i in range(count):
            instance_id = self.next_id
            self.next_id += 1

            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0

            try:
                process = subprocess.Popen(
                    [str(self.launcher_exe)],
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                instance = GameInstance(
                    instance_id=instance_id,
                    pid=process.pid,
                    status="运行中",
                    launched_at=datetime.now().strftime("%H:%M:%S")
                )
            except Exception as e:
                instance = GameInstance(
                    instance_id=instance_id,
                    pid=None,
                    status=f"失败: {e}"
                )

            self.instances[instance_id] = instance
            launched.append(instance)

            if i < count - 1:
                time.sleep(interval)

        return launched

    def close_instance(self, instance_id: int) -> bool:
        instance = self.instances.get(instance_id)
        if not instance or not instance.pid:
            return False

        try:
            if not psutil.pid_exists(instance.pid):
                instance.status = "已退出"
                return True

            parent = psutil.Process(instance.pid)
            children = parent.children(recursive=True)
            for child in children:
                child.terminate()
            parent.terminate()

            gone, alive = psutil.wait_procs(children + [parent], timeout=3)
            for p in alive:
                p.kill()

            instance.status = "已关闭"
            return True
        except Exception:
            return False

    def close_all(self) -> int:
        closed = 0
        for instance_id in list(self.instances.keys()):
            if self.close_instance(instance_id):
                closed += 1
        return closed

    def get_instance_status(self, instance_id: int) -> str:
        instance = self.instances.get(instance_id)
        if not instance:
            return "不存在"

        if instance.status == "已关闭":
            return instance.status
        if not instance.pid:
            return instance.status

        try:
            if psutil.pid_exists(instance.pid):
                instance.status = "运行中"
            else:
                instance.status = "已退出"
        except Exception:
            instance.status = "已退出"
        return instance.status

    def refresh_all_status(self):
        for instance_id in self.instances:
            self.get_instance_status(instance_id)

    def get_all_instances(self) -> dict[int, GameInstance]:
        return self.instances.copy()
```

注意：旧文件中 `win32gui`/`win32process` import、`two_box_*` 字段、`_ensure_two_box_running`、`_find_window_for_instance`、`stop_two_box`、`_two_box_running` 全部删除。

- [ ] **Step 4: 运行测试验证通过**

Run: `.venv\Scripts\python.exe -m unittest discover -s test -p "test_multi_instance_*.py" -v`
Expected: PASS（11 个用例）

- [ ] **Step 5: 提交**

```bash
git add OAT/tools/MultiInstanceManager.py test/test_multi_instance_manager.py
git commit -m "feat: 多开管理器重写为 yyx-launcher 方案"
```

---

### Task 2: 多开页 UI 适配（间隔输入 + 表格列 + 信号链）

**Files:**
- Modify: `OAT/app/multi_instance_page.py`
- Modify: `OAT/app/main_window.py:1069-1073`（仅 emit 改为 4 参数）
- Create: `test/test_multi_instance_page.py`

**Interfaces:**
- Consumes: Task 1 的 `GameInstance(instance_id, pid, status, launched_at)`、`launch_instances(exe_path, count, interval)`
- Produces（Task 3 依赖）:
  - `MultiInstancePage.get_launch_interval() -> int`（0-120，默认 5）
  - `MultiInstancePage.instance_added = pyqtSignal(int, int, str, str)`（instance_id, pid, status, launched_at）
  - `MultiInstancePage.add_instance(instance_id, pid=0, status="运行中", launched_at="")`
  - `MultiInstancePage.update_instance(instance_id, pid=None, status=None, launched_at=None)`

- [ ] **Step 1: 写失败的测试**

创建 `test/test_multi_instance_page.py`：

```python
import os
import threading
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from OAT.app.multi_instance_page import MultiInstancePage


class TestMultiInstancePage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_launch_interval_default_and_range(self):
        page = MultiInstancePage()
        self.assertEqual(page.get_launch_interval(), 5)
        self.assertEqual(page.launch_interval.minimum(), 0)
        self.assertEqual(page.launch_interval.maximum(), 120)

    def test_table_has_six_columns(self):
        page = MultiInstancePage()
        self.assertEqual(page.instance_table.columnCount(), 6)

    def test_add_instance_fills_columns(self):
        page = MultiInstancePage()
        page.add_instance(7, pid=12345, status="运行中", launched_at="12:00:01")
        self.assertEqual(page.instance_table.rowCount(), 1)
        self.assertEqual(page.instance_table.item(0, 1).text(), "7")
        self.assertEqual(page.instance_table.item(0, 2).text(), "12345")
        self.assertEqual(page.instance_table.item(0, 3).text(), "运行中")
        self.assertEqual(page.instance_table.item(0, 4).text(), "12:00:01")
        self.assertIsNotNone(page.instance_table.cellWidget(0, 5))

    def test_worker_thread_emit_creates_rows_without_crash(self):
        page = MultiInstancePage()
        page.show()

        def worker():
            page.instance_added.emit(1, 100, "运行中", "00:00:01")
            page.instance_added.emit(2, 101, "运行中", "00:00:02")

        t = threading.Thread(target=worker)
        t.start()

        deadline = time.time() + 5
        while page.instance_table.rowCount() < 2 and time.time() < deadline:
            self.app.processEvents()
            time.sleep(0.02)
        t.join(timeout=2)
        self.app.processEvents()

        self.assertEqual(page.instance_table.rowCount(), 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试验证失败**

Run: `.venv\Scripts\python.exe -m unittest discover -s test -p "test_multi_instance_*.py" -v`
Expected: FAIL — `get_launch_interval` 不存在 / 列数 5 != 6 / signal 参数不匹配

- [ ] **Step 3: 修改多开页**

`OAT/app/multi_instance_page.py`：

a) 信号改为 4 参数，`__init__` 连接不变：
```python
    instance_added = QtCore.pyqtSignal(int, int, str, str)
```

b) 启动数量旁新增间隔输入（在 `_setup_ui` 的 config_layout 里，`launch_count` 之后）：
```python
        interval_label = BodyLabel("启动间隔(秒):")
        self.launch_interval = SpinBox(self)
        self.launch_interval.setRange(0, 120)
        self.launch_interval.setValue(5)
```
布局中紧跟 `config_layout.addWidget(self.launch_count)` 后添加三行 addWidget。

c) 新增方法：
```python
    def get_launch_interval(self) -> int:
        return self.launch_interval.value()
```

d) 表头 6 列：
```python
        self.instance_table.setColumnCount(6)
        self.instance_table.setHorizontalHeaderLabels(
            ["选择", "实例ID", "进程PID", "状态", "启动时间", "操作"]
        )
```
resize 模式：0/1/2/3 保持 ResizeToContents，4（启动时间）改 Stretch，5（操作）改 ResizeToContents。

e) `add_instance` 签名与内容：
```python
    def add_instance(self, instance_id: int, pid: int = 0, status: str = "运行中", launched_at: str = ""):
        row = self.instance_table.rowCount()
        self.instance_table.insertRow(row)

        self._instance_id_to_row[instance_id] = row

        checkbox_item = QtWidgets.QTableWidgetItem()
        checkbox_item.setFlags(checkbox_item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
        checkbox_item.setCheckState(QtCore.Qt.CheckState.Unchecked)
        self.instance_table.setItem(row, 0, checkbox_item)

        self.instance_table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(instance_id)))
        self.instance_table.setItem(row, 2, QtWidgets.QTableWidgetItem(str(pid) if pid else "-"))
        self.instance_table.setItem(row, 3, QtWidgets.QTableWidgetItem(status))
        self.instance_table.setItem(row, 4, QtWidgets.QTableWidgetItem(launched_at))

        close_btn = PushButton(FIF.CLOSE, "关闭", self)
        close_btn.setMinimumHeight(28)
        close_btn.clicked.connect(lambda checked, iid=instance_id: self._on_close_instance(iid))
        self.instance_table.setCellWidget(row, 5, close_btn)
```

f) `update_instance` 签名与内容：
```python
    def update_instance(self, instance_id: int, pid: int = None, status: str = None, launched_at: str = None):
        row = self._instance_id_to_row.get(instance_id)
        if row is None:
            return

        if pid is not None:
            pid_item = self.instance_table.item(row, 2)
            if pid_item:
                pid_item.setText(str(pid) if pid else "-")

        if status is not None:
            status_item = self.instance_table.item(row, 3)
            if status_item:
                status_item.setText(status)

        if launched_at is not None:
            time_item = self.instance_table.item(row, 4)
            if time_item:
                time_item.setText(launched_at)
```

- [ ] **Step 4: 同步 main_window 的 emit（4 参数）**

`OAT/app/main_window.py:1069-1073` 改为：
```python
                    self.ui.multi_instance_page.instance_added.emit(
                        instance.instance_id,
                        instance.pid or 0,
                        instance.status,
                        instance.launched_at
                    )
```

- [ ] **Step 5: 运行测试验证通过**

Run: `.venv\Scripts\python.exe -m unittest discover -s test -p "test_multi_instance_*.py" -v`
Expected: PASS（Task 1 + Task 2 全部用例）

- [ ] **Step 6: 提交**

```bash
git add OAT/app/multi_instance_page.py OAT/app/main_window.py test/test_multi_instance_page.py
git commit -m "feat: 多开页支持启动间隔输入与PID/启动时间列"
```

---

### Task 3: main_window 集成 + 移除 2box

**Files:**
- Modify: `OAT/app/main_window.py`（`launch_game_instances`、`refresh_instance_list`、`close_instance_by_id`）
- Delete: `OAT/tools/build_2box.py`
- Delete: `2box/`（整个目录，untracked）

**Interfaces:**
- Consumes: Task 1 的 `launch_instances(exe_path, count, interval)`、`GameInstance.pid`；Task 2 的 `get_launch_interval()`、`instance_added(4参数)`、`update_instance(pid=..., status=...)`

- [ ] **Step 1: 修改 `launch_game_instances`**

`OAT/app/main_window.py`（当前约 1052-1080 行）替换为：
```python
    def launch_game_instances(self):
        exe_path = self.ui.multi_instance_page.get_exe_path()
        if not exe_path:
            warning_box("请先选择游戏exe文件路径")
            return

        if not os.path.exists(exe_path):
            warning_box(f"文件不存在: {exe_path}")
            return

        count = self.ui.multi_instance_page.get_launch_count()
        interval = self.ui.multi_instance_page.get_launch_interval()
        logger.info(f"启动 {count} 个游戏实例: {exe_path}, 间隔 {interval}s")

        launch_btn = self.ui.multi_instance_page.launch_btn
        launch_btn.setEnabled(False)

        def launch_thread():
            try:
                instances = self.multi_instance_manager.launch_instances(exe_path, count, interval)
                for instance in instances:
                    self.ui.multi_instance_page.instance_added.emit(
                        instance.instance_id,
                        instance.pid or 0,
                        instance.status,
                        instance.launched_at
                    )
                    logger.info(f"实例 {instance.instance_id} 已启动, 状态: {instance.status}")
            except Exception as e:
                logger.error(f"启动实例失败: {e}")
                error_box(f"启动失败: {str(e)}")
            finally:
                launch_btn.setEnabled(True)

        thread = threading.Thread(target=launch_thread, daemon=True)
        thread.start()
```

- [ ] **Step 2: 修改 `refresh_instance_list` 与 `close_instance_by_id`**

`refresh_instance_list` 中 `update_instance(instance_id, hwnd=instance.hwnd, ...)` 改为：
```python
            self.ui.multi_instance_page.update_instance(
                instance_id,
                pid=instance.pid,
                status=instance.status
            )
```

`close_instance_by_id` 中 `update_instance(instance_id, status="已关闭")` 不变（新签名兼容）。

- [ ] **Step 3: 删除 2box 文件**

```powershell
Remove-Item -LiteralPath "2box" -Recurse -Force
Remove-Item -LiteralPath "OAT\tools\build_2box.py" -Force
```

- [ ] **Step 4: 静态验证**

Run: `.venv\Scripts\python.exe -m py_compile OAT\app\main_window.py OAT\app\multi_instance_page.py OAT\tools\MultiInstanceManager.py`
Expected: 无输出、exit code 0

Run（确认无残留 2box 引用，预期无输出）:
```powershell
Select-String -Path "OAT\app\main_window.py","OAT\app\multi_instance_page.py","OAT\tools\MultiInstanceManager.py" -Pattern "two_box|2box|hwnd|2Box"
```

- [ ] **Step 5: 跑全部测试**

Run: `.venv\Scripts\python.exe -m unittest discover -s test -p "test_multi_instance_*.py" -v`
Expected: PASS（15 个用例：Task 1 的 11 + Task 2 的 4）

- [ ] **Step 6: 手动验证清单（需要真实游戏环境）**

1. 管理员身份运行 OAT（`.venv\Scripts\python.exe main.py`）
2. 多开页：浏览选择游戏 exe 路径 → 检查 `yyx\yyx-launcher.ini` 已写入该路径
3. 数量 2、间隔 5 → 点击「启动实例」→ 启动按钮在启动期间置灰、结束后恢复；表格出现 2 行（PID/运行中/启动时间）
4. 约 5 秒间隔内两个游戏窗口先后出现
5. 勾选一行 → 「关闭选中」→ 该游戏进程被结束、状态变"已关闭"
6. 「全部关闭」→ 所有游戏进程结束
7. 「刷新列表」→ 状态正确反映运行/已退出
8. 关闭其中一个游戏窗口 → 「刷新列表」→ 状态变"已退出"

- [ ] **Step 7: 提交**

```bash
git add -A
git commit -m "feat: 多开迁移到 yyx-launcher，移除2box"
```

---

## Self-Review 记录

- 规格覆盖：ini 构建（Task 1 Step 1 测试 + 实现）、数量/间隔输入（Task 2）、后台批量启动（Task 1 + Task 3）、表格启动记录（Task 2）、关闭功能（Task 1 close_* + Task 3 按钮）、移除 2box（Task 3 Step 3）、信号线程安全（Task 2 测试）✓
- 类型一致性：`instance_added(int,int,str,str)` 在 Task 2 定义、Task 2 Step 4 与 Task 3 Step 1 使用一致；`update_instance(pid=,status=,launched_at=)` 与 Task 3 Step 2 调用一致；`launch_instances(exe_path,count,interval)` 顺序一致 ✓
- 编码约束：ini ANSI + CRLF，与原始 59 字节文件逐字节兼容（ASCII 路径时）✓
- 测试可运行性：unittest + discover 无需 test/__init__.py；OAT 包从项目根 import（`python -m` 时 cwd 在 sys.path）✓
