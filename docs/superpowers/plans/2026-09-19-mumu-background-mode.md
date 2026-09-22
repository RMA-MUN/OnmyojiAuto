# MuMu 免 ADB 后台模式 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 不连 ADB，仅凭窗口句柄 + Windows 消息实现 MuMu 手游阴阳师的后台截图与后台输入（点击/长按/滑动 + 双开同步）。

**Architecture:** 新增 `OAT/tools/emulator/` 包（`backend.py` 接口 + `mumu_handle/capture/input.py` + `nemu_ipc.py`），`OnmyojiAuto` / `OpenCVRecognitionEngine` / `WindowSynchronizer` 改为持有 backend；截图 `nemu_ipc → PrintWindow → BitBlt` 三级降级，输入 `SendMessage` 打 MuMu 子句柄。

**Tech Stack:** Python ≥3.12（64 位），pywin32==310，ctypes（NemuIPC DLL），opencv-python 4.8，numpy<2，pytest（`test/` 目录）。

**Spec:** `docs/superpowers/specs/2026-09-19-mumu-background-mode-design.md`

## Global Constraints

- MuMu ≥ 3.8.13 才有可用 NemuIPC（stderr 含 `error: 1783/1745` 即版本过旧，降级 Win32）。
- 必须加载 64 位 `external_renderer_ipc.dll`（不带 `_32` 后缀那份；本机 Python 为 64 位）。
- 截图只认 `external_renderer_ipc.dll`，`nrd_renderer_ipc.dll` 禁用。
- 控制进程需管理员身份运行（`IsUserAnAdmin` 自检，非 admin 弹框引导）。
- 截图统一输出 BGR、`1280x720` 参考系；点击坐标统一为客户区逻辑坐标（1280x720 空间）。
- 旧 `hidden_window: bool` 参数保留并映射到 backend，旧任务零改可跑。
- 雷电/夜神/蓝叠/ADB/minitouch 均不做（YAGNI）。

---

## File Structure

| 文件 | 职责 |
|---|---|
| Create `OAT/tools/emulator/__init__.py` | 导出 `EmulatorBackend`、`create_backend` |
| Create `OAT/tools/emulator/backend.py` | `EmulatorBackend` 抽象、`PcBackend` 适配器、`create_backend` 工厂 |
| Create `OAT/tools/emulator/mumu_handle.py` | 枚举 + 句柄树 + 家族判定 + `window_scale_rate` + `MumuHandle` 数据类 |
| Create `OAT/tools/emulator/nemu_ipc.py` | DLL 候选定位 + `ctypes` 封装（connect/capture/down/up）+ 异常类型 |
| Create `OAT/tools/emulator/mumu_capture.py` | 三级截图 + 1280x720 归一化，吐 BGR |
| Create `OAT/tools/emulator/mumu_input.py` | click / long_click / swipe 消息序列 |
| Modify `OAT/tools/settings.py` + `OAT/tools/settings.json` | 新增 5 个配置键及导出变量 |
| Modify `OAT/pipeline/recognition_opencv.py` | 引擎经 backend 截图/点击 |
| Modify `OAT/tools/OnmyojiAuto.py` | 经 backend 截图/点击，保留旧签名 |
| Modify `OAT/tools/WindowSynchronizer.py` | 同步点击经 backend 子句柄 |
| Test `test/test_mumu_handle.py` 等 6 个新测试文件 | 见各 Task |

---

### Task 1: backend 接口 + PcBackend + 工厂

**Files:**
- Create: `OAT/tools/emulator/__init__.py`
- Create: `OAT/tools/emulator/backend.py`
- Test: `test/test_emulator_backend.py`

**Interfaces:**
- Consumes: 无（首个 Task；`settings` 只在 Task 6 后接入，工厂本 Task 接受显式参数）。
- Produces（后续 Task 必须原样使用）:
  - `class EmulatorBackend(abc.ABC)` 方法签名：
    `screenshot(self) -> Optional[numpy.ndarray]`（BGR，1280x720 参考系）
    `click(self, x: int, y: int) -> None`
    `long_click(self, x: int, y: int, duration: float) -> None`
    `swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> None`
    `instance_hwnds(self) -> list[int]`
    `close(self) -> None`
  - `class PcBackend(EmulatorBackend)`：`__init__(self, hwnd: int)`，复用现有前台/Win32 行为的薄适配。
  - `def create_backend(emulator_type: str, **kwargs) -> EmulatorBackend`：`emulator_type == "pc"` 返回 `PcBackend(hwnd=kwargs["hwnd"])`；`"mumu12"` 在 Task 7 前抛 `NotImplementedError("mumu backend in Task 7")`；其他值抛 `ValueError(f"unknown emulator_type: {emulator_type}")`。

- [ ] **Step 1: Write the failing test**

```python
"""Task 1: backend 接口与工厂（不碰 win32）。"""
import numpy as np
import pytest

from OAT.tools.emulator.backend import PcBackend, create_backend


class _StubPc(PcBackend):
    def __init__(self):
        super().__init__(hwnd=12345)

    def screenshot(self):
        return np.zeros((720, 1280, 3), dtype=np.uint8)


def test_create_pc_backend():
    b = create_backend("mumu_will_fail", hwnd=1) if False else create_backend("pc", hwnd=12345)
    assert isinstance(b, PcBackend)
    assert b.instance_hwnds() == [12345]


def test_create_unknown_raises():
    with pytest.raises(ValueError, match="unknown emulator_type"):
        create_backend("nox")


def test_mumu_not_yet_implemented():
    with pytest.raises(NotImplementedError):
        create_backend("mumu12")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test/test_emulator_backend.py -v`
Expected: FAIL with "No module named 'OAT.tools.emulator'"（或 `ModuleNotFoundError`）。

- [ ] **Step 3: Write minimal implementation**

```python
"""Backend 抽象：截图统一 BGR 1280x720；坐标统一客户区逻辑坐标。"""
import abc
from typing import Optional

import numpy as np


class EmulatorBackend(abc.ABC):
    @abc.abstractmethod
    def screenshot(self) -> Optional[np.ndarray]:
        """后台截图，BGR，1280x720 参考系；失败返回 None。"""

    @abc.abstractmethod
    def click(self, x: int, y: int) -> None:
        """客户区逻辑坐标点击。"""

    @abc.abstractmethod
    def long_click(self, x: int, y: int, duration: float) -> None:
        """客户区逻辑坐标长按，duration 秒。"""

    @abc.abstractmethod
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> None:
        """客户区逻辑坐标滑动。"""

    @abc.abstractmethod
    def instance_hwnds(self) -> list[int]:
        """本 backend 覆盖的实例顶层 HWND。"""

    def close(self) -> None:
        """释放连接（默认空实现）。"""


class PcBackend(EmulatorBackend):
    """旧 PC/前台行为的薄适配，具体截图/点击在 Task 7 接入现有代码。"""

    def __init__(self, hwnd: int):
        self._hwnd = int(hwnd)

    def screenshot(self) -> Optional[np.ndarray]:
        raise NotImplementedError("pc screenshot wired in Task 7")

    def click(self, x: int, y: int) -> None:
        raise NotImplementedError("pc click wired in Task 7")

    def long_click(self, x: int, y: int, duration: float) -> None:
        raise NotImplementedError("pc long_click wired in Task 7")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> None:
        raise NotImplementedError("pc swipe wired in Task 7")

    def instance_hwnds(self) -> list[int]:
        return [self._hwnd]


def create_backend(emulator_type: str, **kwargs) -> EmulatorBackend:
    if emulator_type == "pc":
        return PcBackend(hwnd=kwargs["hwnd"])
    if emulator_type == "mumu12":
        raise NotImplementedError("mumu backend in Task 7")
    raise ValueError(f"unknown emulator_type: {emulator_type}")
```

`OAT/tools/emulator/__init__.py` 内容：

```python
from .backend import EmulatorBackend, PcBackend, create_backend

__all__ = ["EmulatorBackend", "PcBackend", "create_backend"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test/test_emulator_backend.py -v`
Expected: 3 passed（`_StubPc` 未被直接使用仅作类型占位，不影响结果）。

- [ ] **Step 5: Commit**

```bash
git add OAT/tools/emulator/__init__.py OAT/tools/emulator/backend.py test/test_emulator_backend.py
git commit -m "feat(emulator): add backend interface, PcBackend stub and factory"
```

---

### Task 2: mumu_handle（枚举 + 句柄树 + 家族判定 + 缩放）

**Files:**
- Create: `OAT/tools/emulator/mumu_handle.py`
- Test: `test/test_mumu_handle.py`

**Interfaces:**
- Consumes: 无 win32 真调用（本 Task 用 monkeypatch 注入假 win32 函数，保证无 MuMu 也可测）。
- Produces:
  - `@dataclass class MumuHandle: root_hwnd: int; root_title: str; shot_hwnd: int; control_hwnds: list[int]; scale_rate: float; client_w: int; client_h: int`
  - `MUMU_TITLES = ("MuMu模拟器12", "MuMu安卓设备", "MuMuPlayer")`（auto 匹配优先级即此顺序）
  - `SHOT_CHILD_NAMES = ("MuMuPlayer", "MuMuNxDevice", "NemuPlayer")`
  - `def window_scale_rate() -> float`
  - `def enum_mumu_windows() -> list[tuple[int, str]]`（按 MUMU_TITLES 优先级、HWND 排序，`_title_priority` 取首个命中的下标）
  - `def build_handle(title_or_hwnd: str | int) -> MumuHandle`（`auto` 取排序后第 N 个；树未就绪重试 10×1s，`time.sleep` 可被 monkeypatch）
  - `def is_window(hwnd: int) -> bool`

- [ ] **Step 1: Write the failing test**

```python
"""Task 2: 句柄树与家族判定（monkeypatch 假 win32，无需真 MuMu）。"""
import OAT.tools.emulator.mumu_handle as mh


class _FakeWin:
    # 桌面：两个 MuMu 顶层窗口；100 下挂 MuMuPlayer 子树
    tops = {100: "MuMu模拟器12", 200: "MuMu安卓设备"}
    children = {100: [110], 110: [], 200: [210], 210: []}
    names = {110: "MuMuPlayer", 210: "MuMuPlayer"}

    def EnumWindows(self, cb, param):
        for h in self.tops:
            cb(h, param)

    def GetWindowText(self, h):
        return self.tops.get(h, self.names.get(h, ""))

    def EnumChildWindows(self, h, cb, param):
        for c in self.children.get(h, []):
            cb(c, param)

    def GetParent(self, h):
        for p, cs in self.children.items():
            if h in cs:
                return p
        return 0

    def IsWindow(self, h):
        return h in self.tops or h in self.names

    def GetWindowRect(self, h):
        return (0, 0, 1280, 800)

    def GetClientRect(self, h):
        return (0, 0, 1280, 720)


def _patch(monkeypatch):
    fake = _FakeWin()
    monkeypatch.setattr(mh, "_gui", fake)
    monkeypatch.setattr(mh, "time", __import__("time"))
    return fake


def test_enum_sorted(monkeypatch):
    _patch(monkeypatch)
    wins = mh.enum_mumu_windows()
    assert wins == sorted(wins)
    assert [h for h, _ in wins] == [100, 200]


def test_build_handle_auto_picks_first(monkeypatch):
    _patch(monkeypatch)
    h = mh.build_handle("auto")
    assert isinstance(h, mh.MumuHandle)
    assert (h.root_hwnd, h.shot_hwnd) == (100, 110)
    assert h.control_hwnds == [100, 110]


def test_build_handle_numeric(monkeypatch):
    _patch(monkeypatch)
    h = mh.build_handle(200)
    assert (h.root_hwnd, h.shot_hwnd) == (200, 210)


def test_scale_rate(monkeypatch):
    _patch(monkeypatch)
    monkeypatch.setattr(mh, "_sysmetrics", lambda i: 1280 if i == 0 else 720)
    monkeypatch.setattr(mh, "_deskhres", lambda: 1280)
    assert mh.window_scale_rate() == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test/test_mumu_handle.py -v`
Expected: FAIL with "No module named 'OAT.tools.emulator.mumu_handle'"。

- [ ] **Step 3: Write minimal implementation**

```python
"""MuMu 句柄层：枚举 + 句柄树 + 家族判定 + 系统缩放。

OAS 对应逻辑：module/device/handle.py（Handle.handle_tree / emulator_family /
screenshot_handle_num / window_scale_rate）。
本机差异：DLL 探测见 nemu_ipc.py；本文件只管 HWND。
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional, Union

import win32api
import win32gui
from win32print import GetDeviceCaps
from win32con import DESKTOPHORZRES

# 供测试整体替换的 win32 门面（默认即真实 win32gui）
_gui = win32gui


def _sysmetrics(i: int) -> int:
    return win32api.GetSystemMetrics(i)


def _deskhres() -> int:
    hdc = _gui.GetDC(0)
    try:
        return GetDeviceCaps(hdc, DESKTOPHORZRES)
    finally:
        try:
            _gui.ReleaseDC(0, hdc)
        except Exception:
            pass


MUMU_TITLES = ("MuMu模拟器12", "MuMu安卓设备", "MuMuPlayer")
SHOT_CHILD_NAMES = ("MuMuPlayer", "MuMuNxDevice", "NemuPlayer")


@dataclass
class MumuHandle:
    root_hwnd: int
    root_title: str
    shot_hwnd: int
    control_hwnds: list[int]
    scale_rate: float
    client_w: int
    client_h: int


def window_scale_rate() -> float:
    try:
        return round(_deskhres() / _sysmetrics(0), 2)
    except Exception:
        return 1.0


def is_window(hwnd: int) -> bool:
    try:
        return bool(_gui.IsWindow(int(hwnd)))
    except Exception:
        return False


def enum_mumu_windows() -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []

    def _cb(hwnd: int, _p) -> bool:
        try:
            title = _gui.GetWindowText(hwnd)
        except Exception:
            return True
        for key in MUMU_TITLES:
            if key and key in (title or ""):
                found.append((hwnd, title))
                break
        return True

    _gui.EnumWindows(_cb, None)
    found.sort(key=lambda t: (_title_priority(t[1]), t[0]))
    return found


def _title_priority(title: str) -> int:
    for i, key in enumerate(MUMU_TITLES):
        if key and key in (title or ""):
            return i
    return len(MUMU_TITLES)


def _child_hwnds(hwnd: int) -> list[int]:
    out: list[int] = []
    _gui.EnumChildWindows(hwnd, lambda h, p: p.append(h) or True, out)
    return [h for h in out if _gui.GetParent(h) == hwnd]


def _wait_children(root: int, tries: int = 10) -> list[int]:
    kids = _child_hwnds(root)
    for _ in range(tries - 1):
        if kids:
            return kids
        time.sleep(1.0)
        kids = _child_hwnds(root)
    return kids


def _resolve_root(spec: Union[str, int]) -> tuple[int, str]:
    if isinstance(spec, int) or (isinstance(spec, str) and spec.lstrip("-").isdigit()):
        hwnd = int(spec)
        if not is_window(hwnd):
            raise ValueError(f"handle {hwnd} is not a valid window")
        return hwnd, _gui.GetWindowText(hwnd)
    if spec == "auto":
        wins = enum_mumu_windows()
        if not wins:
            raise ValueError("auto: no MuMu window found")
        return wins[0]
    hwnd = _gui.FindWindow(None, spec)
    if not hwnd:
        raise ValueError(f"window title not found: {spec}")
    return hwnd, spec


def build_handle(title_or_hwnd: Union[str, int]) -> MumuHandle:
    root, title = _resolve_root(title_or_hwnd)
    kids = _wait_children(root)
    if not kids:
        raise ValueError(f"window {root} has no child windows yet")
    name0 = _gui.GetWindowText(kids[0])
    if name0 not in SHOT_CHILD_NAMES:
        raise ValueError(f"not a MuMu12 window tree (first child={name0!r})")
    shot = kids[0]
    try:
        cr = _gui.GetClientRect(shot)
        cw, ch = cr[2] - cr[0], cr[3] - cr[1]
    except Exception:
        cw, ch = (1280, 720)
    return MumuHandle(
        root_hwnd=root,
        root_title=title,
        shot_hwnd=shot,
        control_hwnds=[root, shot],
        scale_rate=window_scale_rate(),
        client_w=cw,
        client_h=ch,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test/test_mumu_handle.py -v`
Expected: 4 passed。

- [ ] **Step 5: Commit**

```bash
git add OAT/tools/emulator/mumu_handle.py test/test_mumu_handle.py
git commit -m "feat(emulator): add MuMu handle tree, family check and scale rate"
```

---

### Task 3: nemu_ipc（DLL 定位 + ctypes 封装）

**Files:**
- Create: `OAT/tools/emulator/nemu_ipc.py`
- Test: `test/test_nemu_ipc.py`

**Interfaces:**
- Consumes: Task 2 的 `MumuHandle`（仅取 `shot_hwnd` 做日志，不强依赖）。
- Produces:
  - `class NemuIpcIncompatible(Exception)` / `class NemuIpcError(Exception)`
  - `DLL_CANDIDATES = ("nx_main/sdk/external_renderer_ipc.dll", "nx_device/12.0/shell/sdk/external_renderer_ipc.dll", "nx_device/15.0/shell/sdk/external_renderer_ipc.dll", "shell/sdk/external_renderer_ipc.dll")`（相对 `mumu_folder` 的有序候选；顺序即优先级，不可调换）
  - `def find_ipc_dll(mumu_folder: str, override: str = "") -> Optional[str]`（`override` 非空且存在则直接返回；否则按序返回首个存在项；全缺返回 None）
  - `class NemuIpc: __init__(self, dll_path: str, instance_id: int)`（`ctypes.CDLL` 加载失败 → `NemuIpcIncompatible`；只声明 `nemu_connect / nemu_disconnect / nemu_capture_display / nemu_input_event_touch_down / nemu_input_event_touch_up` 五个符号的 argtypes/restype）
  - 方法：`connect(self) -> None` / `disconnect(self) -> None` / `capture(self) -> numpy.ndarray`（RGBA `h×w×4`，**倒置**，调用方翻转）/ `down(self, x: int, y: int) -> None` / `up(self) -> None` / `convert_xy(self, x: int, y: int) -> tuple[int, int]`（`(height-y, x)`；`height` 为 0 时先 `get_resolution`）
  - `def serial_to_instance_id(serial: str) -> Optional[int]`（`127.0.0.1:16384+32*i` → i；解析失败返回 None；Win32 主链路可忽略，仅保留做兼容）

- [ ] **Step 1: Write the failing test**

```python
"""Task 3: DLL 定位顺序 + IPC 坐标翻转（不加载真 DLL）。"""
import OAT.tools.emulator.nemu_ipc as ni


def test_candidate_order():
    assert ni.DLL_CANDIDATES[0] == "nx_main/sdk/external_renderer_ipc.dll"
    assert len(ni.DLL_CANDIDATES) == 4


def test_find_prefers_first(tmp_path):
    root = tmp_path / "MuMuPlayer"
    second = root / ni.DLL_CANDIDATES[1]
    second.parent.mkdir(parents=True)
    second.write_bytes(b"x")
    assert ni.find_ipc_dll(str(root)).replace("\\", "/").endswith(ni.DLL_CANDIDATES[1])


def test_find_first_wins(tmp_path):
    root = tmp_path / "MuMuPlayer"
    for c in (ni.DLL_CANDIDATES[0], ni.DLL_CANDIDATES[1]):
        p = root / c
        p.parent.mkdir(parents=True)
        p.write_bytes(b"x")
    assert ni.find_ipc_dll(str(root)).replace("\\", "/").endswith(ni.DLL_CANDIDATES[0])


def test_find_none(tmp_path):
    assert ni.find_ipc_dll(str(tmp_path / "empty")) is None


def test_override(tmp_path):
    dll = tmp_path / "custom.dll"
    dll.write_bytes(b"x")
    assert ni.find_ipc_dll("whatever", override=str(dll)) == str(dll)


def test_convert_xy():
    ipc = ni.NemuIpc.__new__(ni.NemuIpc)
    ipc.height = 720
    assert ipc.convert_xy(100, 200) == (520, 100)


def test_bad_dll_raises():
    try:
        ni.NemuIpc("definitely-not-exist.dll", 0)
    except ni.NemuIpcIncompatible:
        return
    raise AssertionError("expected NemuIpcIncompatible")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test/test_nemu_ipc.py -v`
Expected: FAIL with "No module named 'OAT.tools.emulator.nemu_ipc'"。

- [ ] **Step 3: Write minimal implementation**

```python
"""NemuIPC：DLL 定位 + ctypes 封装（MuMu ≥ 3.8.13）。

OAS 对应逻辑：module/device/method/nemu_ipc.py（NemuIpcImpl / serial_to_id）。
本机差异：候选首位为 nx_main/sdk（OAS 缺失的新版主路径）。
注意：capture 返回倒置 RGBA，调用方必须 flip(0) 后转 BGR。
"""
from __future__ import annotations

import ctypes
import os
from typing import Optional

import numpy as np


class NemuIpcIncompatible(Exception):
    pass


class NemuIpcError(Exception):
    pass


DLL_CANDIDATES = (
    "nx_main/sdk/external_renderer_ipc.dll",
    "nx_device/12.0/shell/sdk/external_renderer_ipc.dll",
    "nx_device/15.0/shell/sdk/external_renderer_ipc.dll",
    "shell/sdk/external_renderer_ipc.dll",
)


def find_ipc_dll(mumu_folder: str, override: str = "") -> Optional[str]:
    if override and os.path.isfile(override):
        return override
    root = (mumu_folder or "").strip()
    if not root:
        return None
    for rel in DLL_CANDIDATES:
        cand = os.path.join(root, *rel.split("/"))
        if os.path.isfile(cand):
            return os.path.abspath(cand)
    return None


def serial_to_instance_id(serial: str) -> Optional[int]:
    try:
        port = int(str(serial).split(":")[1])
    except (IndexError, ValueError):
        return None
    index, offset = divmod(port - 16384, 32)
    if 0 <= index < 32 and offset in (0, 1, 2):
        return index
    return None


class NemuIpc:
    def __init__(self, dll_path: str, instance_id: int):
        try:
            self.lib = ctypes.CDLL(dll_path)
        except OSError as e:
            raise NemuIpcIncompatible(f"cannot load {dll_path}: {e}") from e
        lib = self.lib
        lib.nemu_connect.argtypes = [ctypes.c_char_p, ctypes.c_int]
        lib.nemu_connect.restype = ctypes.c_int
        lib.nemu_disconnect.argtypes = [ctypes.c_int]
        lib.nemu_disconnect.restype = ctypes.c_int
        lib.nemu_capture_display.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
            ctypes.c_void_p,
        ]
        lib.nemu_capture_display.restype = ctypes.c_int
        lib.nemu_input_event_touch_down.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        lib.nemu_input_event_touch_down.restype = ctypes.c_int
        lib.nemu_input_event_touch_up.argtypes = [ctypes.c_int, ctypes.c_int]
        lib.nemu_input_event_touch_up.restype = ctypes.c_int
        self.instance_id = int(instance_id)
        self.connect_id = 0
        self.width = 0
        self.height = 0
        self._dll_path = dll_path

    def connect(self) -> None:
        if self.connect_id > 0:
            return
        folder = os.path.dirname(os.path.dirname(self._dll_path))
        cid = self.lib.nemu_connect(folder.encode("utf-8"), self.instance_id)
        if cid == 0:
            raise NemuIpcError("nemu_connect failed: emulator not running or folder wrong")
        self.connect_id = int(cid)

    def disconnect(self) -> None:
        if self.connect_id:
            try:
                self.lib.nemu_disconnect(self.connect_id)
            finally:
                self.connect_id = 0

    def get_resolution(self) -> None:
        if not self.connect_id:
            self.connect()
        w = ctypes.pointer(ctypes.c_int(0))
        h = ctypes.pointer(ctypes.c_int(0))
        ret = self.lib.nemu_capture_display(self.connect_id, 0, 0, w, h, None)
        if ret > 0:
            raise NemuIpcError("nemu_capture_display failed in get_resolution")
        self.width, self.height = w.contents.value, h.contents.value

    def capture(self) -> np.ndarray:
        if not self.connect_id:
            self.connect()
        if self.width <= 0 or self.height <= 0:
            self.get_resolution()
        length = self.width * self.height * 4
        buf = (ctypes.c_ubyte * length)()
        w = ctypes.pointer(ctypes.c_int(self.width))
        h = ctypes.pointer(ctypes.c_int(self.height))
        ret = self.lib.nemu_capture_display(
            self.connect_id, 0, length, w, h, ctypes.cast(buf, ctypes.c_void_p))
        if ret > 0:
            raise NemuIpcError("nemu_capture_display failed in capture")
        return np.ctypeslib.as_array(buf).reshape((self.height, self.width, 4))

    def convert_xy(self, x: int, y: int) -> tuple[int, int]:
        if self.height <= 0:
            self.get_resolution()
        return (self.height - int(y), int(x))

    def down(self, x: int, y: int) -> None:
        if not self.connect_id:
            self.connect()
        cx, cy = self.convert_xy(x, y)
        if self.lib.nemu_input_event_touch_down(self.connect_id, 0, cx, cy) > 0:
            raise NemuIpcError("nemu_input_event_touch_down failed")

    def up(self) -> None:
        if not self.connect_id:
            self.connect()
        if self.lib.nemu_input_event_touch_up(self.connect_id, 0) > 0:
            raise NemuIpcError("nemu_input_event_touch_up failed")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test/test_nemu_ipc.py -v`
Expected: 7 passed。

- [ ] **Step 5: Commit**

```bash
git add OAT/tools/emulator/nemu_ipc.py test/test_nemu_ipc.py
git commit -m "feat(emulator): add NemuIPC dll locator and ctypes wrapper"
```

---

### Task 4: mumu_capture（三级截图 + 归一化）

**Files:**
- Create: `OAT/tools/emulator/mumu_capture.py`
- Test: `test/test_mumu_capture.py`

**Interfaces:**
- Consumes: Task 2 `MumuHandle`（`shot_hwnd/scale_rate/client_w/client_h`），Task 3 `NemuIpc`（可为 None）。
- Produces:
  - `REF_W, REF_H = 1280, 720`
  - `def normalize_to_ref(img: numpy.ndarray) -> numpy.ndarray`（BGR 任意尺寸 → `cv2.resize` 到 1280x720；已是该尺寸则原样返回）
  - `class MumuCapture: __init__(self, handle: MumuHandle, ipc: Optional[NemuIpc])`；`capture(self) -> Optional[numpy.ndarray]`（IPC → PrintWindow(PW_CLIENTONLY→RENDERFULLCONTENT) → BitBlt；IPC 图 `cv2.flip(img,0)` + `COLOR_BGRA2BGR`；Win32 图 `COLOR_BGRA2BGR`；全黑 `mean<5` 视为失败换通道；成功图经 `normalize_to_ref` 返回；全失败返回 None）

- [ ] **Step 1: Write the failing test**

```python
"""Task 4: 归一化数学（不依赖真窗口；capture 通道用假对象）。"""
import numpy as np

from OAT.tools.emulator.mumu_capture import REF_H, REF_W, normalize_to_ref


def test_ref_consts():
    assert (REF_W, REF_H) == (1280, 720)


def test_normalize_resizes():
    img = np.zeros((360, 640, 3), dtype=np.uint8)
    out = normalize_to_ref(img)
    assert out.shape == (720, 1280, 3)


def test_normalize_passthrough():
    img = np.zeros((720, 1280, 3), dtype=np.uint8)
    assert normalize_to_ref(img) is img


def test_is_black_gate():
    from OAT.tools.emulator.mumu_capture import _is_black
    assert _is_black(np.zeros((4, 4, 3), dtype=np.uint8)) is True
    assert _is_black(np.full((4, 4, 3), 200, dtype=np.uint8)) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test/test_mumu_capture.py -v`
Expected: FAIL with "No module named 'OAT.tools.emulator.mumu_capture'"。

- [ ] **Step 3: Write minimal implementation**

```python
"""MuMu 截图：nemu_ipc → PrintWindow → BitBlt，统一 BGR 1280x720。

Win32 部分复用 OAT/tools/GetDC.py 的 PW_CLIENTONLY→RENDERFULLCONTENT 策略，
黑屏门限 mean<5 与 GetDC.capture_window_bitblt 一致。
"""
from __future__ import annotations

from typing import Optional

import cv2
import numpy as np
import win32con
import win32gui
import win32ui

from .mumu_handle import MumuHandle
from .nemu_ipc import NemuIpc

REF_W, REF_H = 1280, 720
PW_CLIENTONLY = 1
PW_RENDERFULLCONTENT = 2


def _is_black(img: np.ndarray) -> bool:
    try:
        return float(np.mean(img)) < 5.0
    except Exception:
        return True


def normalize_to_ref(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    if (w, h) == (REF_W, REF_H):
        return img
    return cv2.resize(img, (REF_W, REF_H), interpolation=cv2.INTER_LINEAR)


class MumuCapture:
    def __init__(self, handle: MumuHandle, ipc: Optional[NemuIpc] = None):
        self.handle = handle
        self.ipc = ipc

    def capture(self) -> Optional[np.ndarray]:
        img = self._via_ipc() if self.ipc is not None else None
        if img is not None:
            return normalize_to_ref(img)
        img = self._via_printwindow()
        if img is not None:
            return normalize_to_ref(img)
        img = self._via_bitblt()
        if img is not None:
            return normalize_to_ref(img)
        return None

    def _via_ipc(self) -> Optional[np.ndarray]:
        try:
            raw = self.ipc.capture()
        except Exception:
            return None
        try:
            img = cv2.flip(raw, 0)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        except Exception:
            return None
        return None if _is_black(img) else img

    def _grab(self, use_printwindow: bool, flag: int = PW_CLIENTONLY) -> Optional[np.ndarray]:
        hwnd = self.handle.shot_hwnd
        try:
            cr = win32gui.GetClientRect(hwnd)
            w, h = cr[2] - cr[0], cr[3] - cr[1]
            if w <= 0 or h <= 0:
                return None
            hdc = win32gui.GetDC(hwnd)
            mfc = win32ui.CreateDCFromHandle(hdc)
            mem = mfc.CreateCompatibleDC()
            bmp = win32ui.CreateBitmap()
            bmp.CreateCompatibleBitmap(mfc, w, h)
            mem.SelectObject(bmp)
            try:
                if use_printwindow:
                    ok = win32gui.PrintWindow(hwnd, mem.GetSafeHdc(), flag)
                    if not ok and flag == PW_CLIENTONLY:
                        ok = win32gui.PrintWindow(hwnd, mem.GetSafeHdc(), PW_RENDERFULLCONTENT)
                    if not ok:
                        return None
                else:
                    mem.BitBlt((0, 0), (w, h), mfc, (0, 0), win32con.SRCCOPY)
                bits = bmp.GetBitmapBits(True)
            finally:
                try:
                    win32gui.DeleteObject(bmp.GetHandle())
                except Exception:
                    pass
                try:
                    mem.DeleteDC()
                except Exception:
                    pass
                try:
                    mfc.DeleteDC()
                except Exception:
                    pass
                try:
                    win32gui.ReleaseDC(hwnd, hdc)
                except Exception:
                    pass
            img = np.frombuffer(bits, dtype=np.uint8).reshape((h, w, 4))
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        except Exception:
            return None

    def _via_printwindow(self) -> Optional[np.ndarray]:
        img = self._grab(use_printwindow=True)
        return None if img is None or _is_black(img) else img

    def _via_bitblt(self) -> Optional[np.ndarray]:
        img = self._grab(use_printwindow=False)
        return None if img is None or _is_black(img) else img
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test/test_mumu_capture.py -v`
Expected: 4 passed。

- [ ] **Step 5: Commit**

```bash
git add OAT/tools/emulator/mumu_capture.py test/test_mumu_capture.py
git commit -m "feat(emulator): add three-tier MuMu screenshot with 1280x720 normalize"
```

---

### Task 5: mumu_input（Send 主 + Post 辅）

**Files:**
- Create: `OAT/tools/emulator/mumu_input.py`
- Test: `test/test_mumu_input.py`

**Interfaces:**
- Consumes: Task 2 `MumuHandle`（`control_hwnds/scale_rate`），Task 3 `NemuIpc`（可为 None；非 None 时 click/long 走 IPC，swipe 仍走消息以保贝塞尔手感——与 spec 一致则 swipe 优先 IPC 连续 down；此处锁定：**IPC 可用时三者全走 IPC**，无 IPC 才走消息）。
- Produces:
  - `def pack_lparam(x: int, y: int) -> int`（`x | (y << 16)`，入参强转 int）
  - `def phys(handle: MumuHandle, x: float, y: float) -> tuple[int, int]`（逻辑→物理：`int(x / scale)`，scale≤0 按 1）
  - `class MumuInput: __init__(self, handle: MumuHandle, ipc=None)`；
    `click(x, y, fast=False)`（消息链：`SendMessage(ACTIVATE)`→`SendMessage(DOWN)`→sleep 0.01–0.04/0.1–0.2→`SendMessage(UP)`，打 `control_hwnds[1]`；IPC 链：`down→sleep→down(±2px)→up`）；
    `long_click(x, y, duration)`（DOWN 与 UP 间隔 duration）；
    `swipe(x1, y1, x2, y2, duration=0.5)`（`Send(NCHITTEST/SETCURSOR)` 预热 → `Post(DOWN)` → 逐点 `Post(MOUSEMOVE, MK_LBUTTON)` 间隔 ~10ms → `Post(UP)`；点列由 `build_trace` 生成）；
    `def build_trace(x1, y1, x2, y2, n=20) -> list[tuple[int,int]]`（直线插值 + ±3px 抖动；贝塞尔在集成阶段按需替换，接口不变）

- [ ] **Step 1: Write the failing test**

```python
"""Task 5: lparam 打包 + 物理换算 + 消息序列（全 mock win32/IPC）。"""
import OAT.tools.emulator.mumu_input as mi


def _handle(scale=2.0):
    return type("H", (), {
        "control_hwnds": [100, 110], "scale_rate": scale})()


def test_pack_lparam():
    assert mi.pack_lparam(0x1234, 0x00AB) == (0x00AB << 16 | 0x1234)


def test_phys_divides_scale():
    assert mi.phys(_handle(2.0), 100, 50) == (50, 25)


def test_phys_zero_scale_guards():
    assert mi.phys(_handle(0), 100, 50) == (100, 50)


def test_click_uses_ipc_when_present():
    calls = []

    class _Ipc:
        def down(self, x, y):
            calls.append(("down", x, y))

        def up(self):
            calls.append(("up",))

    inp = mi.MumuInput(_handle(), ipc=_Ipc())
    inp.click(1280, 720)
    assert calls[0][0] == "down" and calls[-1] == ("up",)


def test_click_posts_send_sequence_without_ipc(monkeypatch):
    seq = []
    monkeypatch.setattr(mi, "_send", lambda h, m, w, l: seq.append((h, m)))
    monkeypatch.setattr(mi, "_sleep", lambda s: None)
    import win32con
    inp = mi.MumuInput(_handle(1.0), ipc=None)
    inp.click(10, 20)
    msgs = [m for _, m in seq]
    assert msgs[0] == win32con.WM_ACTIVATE
    assert win32con.WM_LBUTTONDOWN in msgs and win32con.WM_LBUTTONUP in msgs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test/test_mumu_input.py -v`
Expected: FAIL with "No module named 'OAT.tools.emulator.mumu_input'"。

- [ ] **Step 3: Write minimal implementation**

```python
"""MuMu 输入：Send 主 + Post 辅，打控制子句柄。

OAS 对应逻辑：module/device/method/windows_impl.py（click/long/swipe_window_message）。
差异：IPC 可用时三者全走 IPC down/up；无 IPC 才走消息。
"""
from __future__ import annotations

import random
import time
from typing import Optional

import win32con
from win32api import PostMessage, SendMessage

from .mumu_handle import MumuHandle


def _send(hwnd: int, msg: int, w: int, l: int) -> None:
    SendMessage(hwnd, msg, w, l)


def _post(hwnd: int, msg: int, w: int, l: int) -> None:
    PostMessage(hwnd, msg, w, l)


def _sleep(s: float) -> None:
    time.sleep(max(0.0, s))


def pack_lparam(x: int, y: int) -> int:
    from win32api import MAKELONG
    return MAKELONG(int(x), int(y))


def phys(handle: MumuHandle, x: float, y: float) -> tuple[int, int]:
    s = getattr(handle, "scale_rate", 1.0) or 1.0
    if s <= 0:
        s = 1.0
    return (int(float(x) / s), int(float(y) / s))


def build_trace(x1: int, y1: int, x2: int, y2: int, n: int = 20) -> list[tuple[int, int]]:
    n = max(2, int(n))
    pts: list[tuple[int, int]] = []
    for i in range(n):
        t = i / (n - 1)
        px = x1 + (x2 - x1) * t + random.uniform(-3, 3)
        py = y1 + (y2 - y1) * t + random.uniform(-3, 3)
        pts.append((int(px), int(py)))
    pts[0] = (int(x1), int(y1))
    pts[-1] = (int(x2), int(y2))
    return pts


class MumuInput:
    def __init__(self, handle: MumuHandle, ipc: Optional[object] = None):
        self.handle = handle
        self.ipc = ipc

    def _target(self) -> int:
        hwnds = self.handle.control_hwnds
        return hwnds[1] if len(hwnds) > 1 else hwnds[0]

    def click(self, x: int, y: int, fast: bool = False) -> None:
        if self.ipc is not None:
            self.ipc.down(int(x), int(y))
            _sleep(random.uniform(0.05, 0.11))
            self.ipc.down(int(x) + random.randint(-2, 2), int(y) + random.randint(-2, 2))
            _sleep(random.uniform(0.008, 0.02))
            self.ipc.up()
            return
        px, py = phys(self.handle, x, y)
        lp = pack_lparam(px, py)
        t = self._target()
        _send(t, win32con.WM_ACTIVATE, 1, 0)
        _send(t, win32con.WM_LBUTTONDOWN, 0, lp)
        _sleep(random.uniform(0.01, 0.04) if fast else random.uniform(0.1, 0.2))
        _send(t, win32con.WM_LBUTTONUP, 0, lp)

    def long_click(self, x: int, y: int, duration: float) -> None:
        duration = max(0.0, float(duration))
        if self.ipc is not None:
            self.ipc.down(int(x), int(y))
            _sleep(duration)
            self.ipc.up()
            return
        px, py = phys(self.handle, x, y)
        lp = pack_lparam(px, py)
        t = self._target()
        _send(t, win32con.WM_ACTIVATE, 1, 0)
        _send(t, win32con.WM_LBUTTONDOWN, 0, lp)
        _sleep(duration)
        _send(t, win32con.WM_LBUTTONUP, 0, lp)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> None:
        if self.ipc is not None:
            for px, py in build_trace(int(x1), int(y1), int(x2), int(y2)):
                self.ipc.down(px, py)
                _sleep(random.uniform(0.006, 0.015))
            self.ipc.up()
            return
        t = self._target()
        p1 = phys(self.handle, x1, y1)
        p2 = phys(self.handle, x2, y2)
        trace = build_trace(*p1, *p2)
        first = pack_lparam(*trace[0])
        _send(t, win32con.WM_NCHITTEST, 0, first)
        _send(t, win32con.WM_SETCURSOR, t, pack_lparam(1, win32con.WM_LBUTTONDOWN))
        _post(t, win32con.WM_LBUTTONDOWN, 0, first)
        for px, py in trace:
            _post(t, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON, pack_lparam(px, py))
            _sleep(0.01)
        _post(t, win32con.WM_LBUTTONUP, 0, pack_lparam(*trace[-1]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test/test_mumu_input.py -v`
Expected: 5 passed。

- [ ] **Step 5: Commit**

```bash
git add OAT/tools/emulator/mumu_input.py test/test_mumu_input.py
git commit -m "feat(emulator): add MuMu background input via SendMessage/IPC"
```

---

### Task 6: settings 新增 5 键

**Files:**
- Modify: `OAT/tools/settings.py`
- Modify: `OAT/tools/settings.json`
- Test: `test/test_emulator_settings.py`

**Interfaces:**
- Consumes: 无（独立；工厂在 Task 7 才读这些键）。
- Produces（Task 7 原样使用）:
  - `EMULATOR_TYPE`（默认 `"pc"`，旧行为不变）、`HANDLE_SPEC`（默认 `"auto"`）、
    `SCREENSHOT_METHOD`（默认 `"nemu_ipc"`）、`CONTROL_METHOD`（默认 `"window_message"`）、
    `MUMU_FOLDER`（默认 `"E:\\MuMuPlayer"`）
  - `update_settings` 支持键：`emulator_type/handle_spec/screenshot_method/control_method/mumu_folder`
    与旧键 `capture_window_mode` 的联动保持不变。

- [ ] **Step 1: Write the failing test**

```python
"""Task 6: 新配置键默认值与 update_settings 联动。"""
from OAT.tools import settings


def test_defaults_keep_old_behavior():
    assert settings.EMULATOR_TYPE == "pc"
    assert settings.HANDLE_SPEC == "auto"
    assert settings.SCREENSHOT_METHOD == "nemu_ipc"
    assert settings.CONTROL_METHOD == "window_message"
    assert settings.MUMU_FOLDER == "E:\\MuMuPlayer"


def test_update_roundtrip_emulator_type():
    old = settings.EMULATOR_TYPE
    try:
        assert settings.update_settings("emulator_type", "mumu12") is True
        assert settings.EMULATOR_TYPE == "mumu12"
    finally:
        settings.update_settings("emulator_type", old)
    assert settings.EMULATOR_TYPE == old
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test/test_emulator_settings.py -v`
Expected: FAIL with "has no attribute 'EMULATOR_TYPE'"。

- [ ] **Step 3: Write minimal implementation**

`settings.json` 追加（保持原有键不动）：

```json
{
  "emulator_type": "pc",
  "handle_spec": "auto",
  "screenshot_method": "nemu_ipc",
  "control_method": "window_message",
  "mumu_folder": "E:\\MuMuPlayer"
}
```

`settings.py` 在 `BACKEND_GET_IMG_MODE` 之后追加：

```python
# 模拟器后台模式（MuMu 免 ADB）
EMULATOR_TYPE = settings_data.get('emulator_type', 'pc')
HANDLE_SPEC = settings_data.get('handle_spec', 'auto')
SCREENSHOT_METHOD = settings_data.get('screenshot_method', 'nemu_ipc')
CONTROL_METHOD = settings_data.get('control_method', 'window_message')
MUMU_FOLDER = settings_data.get('mumu_folder', 'E:\\MuMuPlayer')
```

`update_settings` 内按现有 `elif` 链追加 5 个分支（逐字仿照 `capture_window_mode` 分支）：

```python
        elif key == 'emulator_type':
            global EMULATOR_TYPE
            EMULATOR_TYPE = value
        elif key == 'handle_spec':
            global HANDLE_SPEC
            HANDLE_SPEC = value
        elif key == 'screenshot_method':
            global SCREENSHOT_METHOD
            SCREENSHOT_METHOD = value
        elif key == 'control_method':
            global CONTROL_METHOD
            CONTROL_METHOD = value
        elif key == 'mumu_folder':
            global MUMU_FOLDER
            MUMU_FOLDER = value
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test/test_emulator_settings.py -v`
Expected: 2 passed（且 `test_pipeline_config_roundtrip.py` 等旧测试仍通过）。

- [ ] **Step 5: Commit**

```bash
git add OAT/tools/settings.py OAT/tools/settings.json test/test_emulator_settings.py
git commit -m "feat(settings): add MuMu backend keys with pc-safe defaults"
```

---

### Task 7: 接线（MumuBackend + 三处调用方 + 管理员自检）

**Files:**
- Create: `OAT/tools/emulator/mumu_backend.py`
- Modify: `OAT/tools/emulator/backend.py`
- Modify: `OAT/tools/emulator/__init__.py`
- Modify: `OAT/pipeline/recognition_opencv.py`
- Modify: `OAT/tools/OnmyojiAuto.py`
- Modify: `OAT/tools/WindowSynchronizer.py`
- Test: `test/test_mumu_backend.py`

**Interfaces:**
- Consumes: Task 1（`EmulatorBackend/create_backend`）、Task 2（`build_handle/is_window`）、
  Task 3（`find_ipc_dll/NemuIpc/NemuIpcIncompatible/NemuIpcError`）、Task 4（`MumuCapture`）、
  Task 5（`MumuInput`）、Task 6（`EMULATOR_TYPE/HANDLE_SPEC/MUMU_FOLDER/...`）。
- Produces:
  - `class MumuBackend(EmulatorBackend)`：`__init__(self, handle_spec="auto", instance_index=0, mumu_folder="", ipc_dll_override="")`；`screenshot/click/long_click/swipe/instance_hwnds/close` 实现；`reconnect()`（IPC 断线重连，3 次后抛 `RuntimeError("nemu ipc unreachable, take over manually")`）；`is_admin() -> bool`（`shell32.IsUserAnAdmin`，异常按 False）。
  - `create_backend("mumu12", ...)` 不再抛 NotImplementedError，改为返回 `MumuBackend`。
  - 调用方：`OpenCVRecognitionEngine.__init__` 新增 `backend=None` 参数（显式传入优先；否则 `EMULATOR_TYPE=="mumu12"` 时 `create_backend("mumu12", ...)` 延迟创建，`pc` 时保持原 `WindowCapture` 行为）；`capture_screenshot()` 优先 `self.backend.screenshot()`；`click/swipe` 的 hidden 分支优先 backend，`hidden_window=False` 保持原前台行为。`OnmyojiAuto.perform_action(hidden_window=True)` 同理。`WindowSynchronizer.send_click_message` 保持签名，内部若 backend 为 MumuBackend 则转调（多开同步遍历 `instance_hwnds`）。

- [ ] **Step 1: Write the failing test**

```python
"""Task 7: MumuBackend 组装（假 handle/假 capture/假 input/假 IPC，全 mock）。"""
import numpy as np

from OAT.tools.emulator import backend as B
from OAT.tools.emulator.mumu_backend import MumuBackend, is_admin


class _H:
    root_hwnd = 100
    root_title = "MuMu模拟器12"
    shot_hwnd = 110
    control_hwnds = [100, 110]
    scale_rate = 1.0
    client_w, client_h = 1280, 720


class _Cap:
    def __init__(self, h, ipc=None):
        self.calls = 0

    def capture(self):
        self.calls += 1
        return np.zeros((720, 1280, 3), dtype=np.uint8)


class _Inp:
    def __init__(self, h, ipc=None):
        self.clicked = []

    def click(self, x, y, fast=False):
        self.clicked.append((x, y))

    def long_click(self, x, y, d):
        self.clicked.append(("long", x, y, d))

    def swipe(self, x1, y1, x2, y2, duration=0.5):
        self.clicked.append(("swipe", x1, y1, x2, y2))


def _make(monkeypatch):
    monkeypatch.setattr("OAT.tools.emulator.mumu_backend.build_handle", lambda s: _H())
    monkeypatch.setattr("OAT.tools.emulator.mumu_backend.MumuCapture", _Cap)
    monkeypatch.setattr("OAT.tools.emulator.mumu_backend.MumuInput", _Inp)
    monkeypatch.setattr("OAT.tools.emulator.mumu_backend.find_ipc_dll", lambda *a, **k: None)
    return MumuBackend(handle_spec="auto", instance_index=0, mumu_folder="X")


def test_screenshot_shape(monkeypatch):
    b = _make(monkeypatch)
    img = b.screenshot()
    assert img.shape == (720, 1280, 3)
    assert b.instance_hwnds() == [100]


def test_click_delegates(monkeypatch):
    b = _make(monkeypatch)
    b.click(100, 200)
    assert (100, 200) in b._input.clicked


def test_factory_returns_mumu(monkeypatch):
    _make(monkeypatch)
    b = B.create_backend("mumu12", handle_spec="auto")
    assert isinstance(b, MumuBackend)


def test_is_admin_bool():
    assert isinstance(is_admin(), bool)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test/test_mumu_backend.py -v`
Expected: FAIL with "No module named 'OAT.tools.emulator.mumu_backend'"。

- [ ] **Step 3: Write minimal implementation**

`OAT/tools/emulator/mumu_backend.py`：

```python
"""MumuBackend：组装 handle + capture + input + IPC，对外实现 EmulatorBackend。"""
from __future__ import annotations

import ctypes
from typing import Optional

import numpy as np

from .backend import EmulatorBackend
from .mumu_capture import MumuCapture
from .mumu_handle import build_handle, is_window
from .mumu_input import MumuInput
from .nemu_ipc import NemuIpc, NemuIpcError, NemuIpcIncompatible, find_ipc_dll


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


class MumuBackend(EmulatorBackend):
    def __init__(self, handle_spec: str = "auto", instance_index: int = 0,
                 mumu_folder: str = "", ipc_dll_override: str = ""):
        from . import mumu_handle as _mh
        if str(handle_spec) == "auto":
            wins = _mh.enum_mumu_windows()
            if instance_index >= len(wins):
                raise ValueError(f"instance_index {instance_index} out of range ({len(wins)} windows)")
            spec: object = wins[instance_index][0]
        else:
            spec = handle_spec
        self._handle = build_handle(spec)
        self._folder = mumu_folder
        self._override = ipc_dll_override
        self._ipc: Optional[NemuIpc] = None
        self._connect_ipc()
        self._cap = MumuCapture(self._handle, self._ipc)
        self._input = MumuInput(self._handle, self._ipc)

    def _connect_ipc(self) -> None:
        dll = find_ipc_dll(self._folder, self._override)
        if not dll:
            self._ipc = None
            return
        try:
            ipc = NemuIpc(dll, 0)
            ipc.connect()
            self._ipc = ipc
        except (NemuIpcIncompatible, NemuIpcError, Exception):
            self._ipc = None

    def reconnect(self) -> None:
        last: Optional[Exception] = None
        for _ in range(3):
            try:
                if self._ipc is not None:
                    try:
                        self._ipc.disconnect()
                    except Exception:
                        pass
                self._connect_ipc()
                if self._ipc is not None:
                    return
            except Exception as e:
                last = e
        raise RuntimeError("nemu ipc unreachable, take over manually") from last

    def screenshot(self) -> Optional[np.ndarray]:
        if not is_window(self._handle.root_hwnd):
            self._handle = build_handle(self._handle.root_hwnd)
            self._cap = MumuCapture(self._handle, self._ipc)
            self._input = MumuInput(self._handle, self._ipc)
        try:
            return self._cap.capture()
        except Exception:
            return None

    def click(self, x: int, y: int) -> None:
        self._input.click(int(x), int(y))

    def long_click(self, x: int, y: int, duration: float) -> None:
        self._input.long_click(int(x), int(y), float(duration))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> None:
        self._input.swipe(int(x1), int(y1), int(x2), int(y2), float(duration))

    def instance_hwnds(self) -> list[int]:
        return [self._handle.root_hwnd]

    def close(self) -> None:
        if self._ipc is not None:
            try:
                self._ipc.disconnect()
            except Exception:
                pass
```

`backend.py` 工厂改动（替换 `mumu12` 分支）：

```python
    if emulator_type == "mumu12":
        from .mumu_backend import MumuBackend
        return MumuBackend(
            handle_spec=kwargs.get("handle_spec", "auto"),
            instance_index=int(kwargs.get("instance_index", 0)),
            mumu_folder=kwargs.get("mumu_folder", ""),
            ipc_dll_override=kwargs.get("ipc_dll_override", ""),
        )
```

`__init__.py` 追加 `MumuBackend` 导出。调用方三处按“backend 优先、原逻辑保底”接线：
`recognition_opencv.py`（`__init__` 加 `backend=None`；`capture_screenshot` 首选 backend；
`click/swipe` hidden 分支首选 backend；`hidden_window=False` 不动）、`OnmyojiAuto.py`
（`__init__` 同样延迟创建；`perform_action(hidden_window=True)` 首选 backend）、
`WindowSynchronizer.send_click_message`（backend 为 MumuBackend 时转调 + 遍历副窗口）。
非 admin 时首次创建 MumuBackend 记录 `logger.warning` 并弹 `warning_box`（复用
`OAT/utils/warning_box.py`），不阻断。

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test/test_mumu_backend.py test/test_emulator_backend.py -v`
Expected: 全部通过；另跑全量旧测试 `pytest test/ -x -q` 无回归。

- [ ] **Step 5: Commit**

```bash
git add OAT/tools/emulator/mumu_backend.py OAT/tools/emulator/backend.py OAT/tools/emulator/__init__.py OAT/pipeline/recognition_opencv.py OAT/tools/OnmyojiAuto.py OAT/tools/WindowSynchronizer.py test/test_mumu_backend.py
git commit -m "feat(emulator): wire MumuBackend into engine, auto and synchronizer"
```

---

### Task 8: 真机集成验证（手动清单，非自动化）

**Files:** 无新增代码；产物为本 Task 的验证记录（跑完后在 commit message 注明结论）。

- [ ] **Step 1: IPC 截图验证** — 启动 MuMu12（12.0-0 实例开阴阳师），管理员运行，
  `create_backend("mumu12", handle_spec="auto", instance_index=0, mumu_folder="E:\\MuMuPlayer")`，
  `screenshot()` 非 None、shape `(720,1280,3)`、非黑（mean>5）。遮挡窗口后重截仍成功；
  最小化后 Win32 应失败而 IPC 仍成功。
- [ ] **Step 2: 点击/长按/滑动验证** — `click(640,360)` 庭院有响应；`long_click` 持续生效；
  `swipe` 探索界面可拖动。`find_ipc_dll` 返回 `nx_main\sdk\...`（本机主路径命中）。
- [ ] **Step 3: 双开同步验证** — 12.0 与 15.0 各开一实例（instance_index 0/1），
  两 backend `click` 同一坐标，两窗口同动；`WindowSynchronizer` 多开同步一致。
- [ ] **Step 4: 降级验证** — 改名 DLL（模拟缺失）→ 自动走 PrintWindow；最小化 + 删 DLL →
  返回 None + 冷却不刷屏；MuMu 重启后 `screenshot()` 触发重枚举恢复。
- [ ] **Step 5: 性能记录** — IPC 截图 <100ms、Win32 <250ms（`time.perf_counter` 实测 20 次取均值），
  写入本 Task 备注；回归 `pytest test/ -q` 全绿后 commit。

```bash
pytest test/ -q
git add -A
git commit -m "verify(emulator): MuMu background mode integration checklist passed"
```
