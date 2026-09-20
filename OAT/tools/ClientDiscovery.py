"""客户端发现：按进程枚举本机游戏客户端（与窗口标题无关，用户改名仍可识别）。

- 模拟器：MuMuNxDevice.exe（每开一台一个进程）→ HWND 经 pid 反查，index 经 mumu-cli。
- 桌面版：Launch.exe 且 exe 路径含 Onmyoji（yyx-launcher.ini 的 YYSLaunchPath 同目录）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

import win32gui

from OAT.utils.logging import logger

ClientKind = Literal["emulator", "pc"]

EMULATOR_PROC_NAMES = ("MuMuNxDevice.exe",)
PC_PROC_NAMES = ("Launch.exe",)
PC_PATH_HINT = "onmyoji"


@dataclass
class ClientInfo:
    kind: ClientKind
    pid: int
    hwnd: int
    title: str
    index: Optional[int] = None
    detail: str = ""


def _gui_enum_windows() -> list[int]:
    out: list[int] = []
    try:
        win32gui.EnumWindows(lambda h, p: p.append(h) or True, out)
    except Exception:
        pass
    return out


def _pid_of_window(hwnd: int) -> int:
    import win32process
    try:
        return win32process.GetWindowThreadProcessId(hwnd)[1]
    except Exception:
        return 0


def windows_of_pid(pid: int, visible_only: bool = True) -> list[int]:
    """pid 反查顶层窗口 HWND（IsWindow 校验；默认只要可见窗口）。"""
    found: list[int] = []
    for hwnd in _gui_enum_windows():
        try:
            if _pid_of_window(hwnd) != pid:
                continue
            if not win32gui.IsWindow(hwnd):
                continue
            if visible_only and not win32gui.IsWindowVisible(hwnd):
                continue
            found.append(hwnd)
        except Exception:
            continue
    return found


def _iter_procs():
    import psutil
    try:
        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                info = proc.info or {}
            except Exception:
                continue
            yield info
    except Exception:
        return


def _exe_lower(info: dict) -> str:
    try:
        return str(info.get("exe") or "").lower()
    except Exception:
        return ""


def client_label(client: ClientInfo) -> str:
    """下拉框展示文案：模拟器/PC 前缀 + 可辨识名称 + 实例号。"""
    if client.kind == "emulator":
        name = client.detail or client.title or f"PID {client.pid}"
        suffix = f" (实例{client.index})" if client.index is not None else ""
        return f"模拟器 · {name}{suffix}"
    name = client.title or client.detail or f"PID {client.pid}"
    return f"PC桌面版 · {name}"


def build_client_items(clients: list[ClientInfo],
                       fallback_titles: list[str] | None = None
                       ) -> list[tuple[str, "ClientInfo | None"]]:
    """发现结果 + 静态标题兜底 → 下拉框条目 [(label, ClientInfo|None)]。

    发现项在前（进程识别，窗口改名不影响），未被覆盖的静态标题随后
    （ClientInfo 为 None，选中时按旧标题链路处理）。
    """
    items: list[tuple[str, ClientInfo | None]] = []
    seen: set[str] = set()
    for c in clients or []:
        label = client_label(c)
        if label in seen:
            continue
        seen.add(label)
        items.append((label, c))
    for t in fallback_titles or []:
        t = (t or "").strip()
        if not t or t in seen:
            continue
        seen.add(t)
        items.append((t, None))
    return items


def discover_clients(mumu_folder: str = "") -> list[ClientInfo]:
    """扫描进程列出客户端：emulator 在前，pc 在后；同类按 pid 排序。

    模拟器三级定位（与窗口标题无关）：
    1. mumu-cli 的 main_wnd（最权威，直接是游戏根窗口 HWND）；
    2. MuMu 进程的窗口经 build_handle 句柄树校验（cli 缺失时兜底）；
    桌面版走 Launch.exe + Onmyoji 路径双认。
    """
    from OAT.tools.emulator import mumu_handle as _mh

    found: list[ClientInfo] = []
    used: set[int] = set()

    try:
        cli_rows = _mh.query_cli_windows(mumu_folder or "")
    except Exception:
        cli_rows = []
    for hwnd, iid, name in cli_rows:
        try:
            if hwnd in used or not _mh.is_window(hwnd):
                continue
            try:
                title = win32gui.GetWindowText(hwnd)
            except Exception:
                title = ""
            try:
                pid = _pid_of_window(hwnd)
            except Exception:
                pid = 0
            used.add(hwnd)
            found.append(ClientInfo(kind="emulator", pid=pid, hwnd=hwnd,
                                    title=title, index=iid,
                                    detail=name or title))
        except Exception:
            continue

    for info in _iter_procs():
        try:
            name = str(info.get("name") or "")
            pid = int(info.get("pid") or 0)
        except (ValueError, TypeError):
            continue
        if not name or not pid:
            continue
        if name in EMULATOR_PROC_NAMES:
            for hwnd in windows_of_pid(pid):
                if hwnd in used:
                    continue
                try:
                    handle = _mh.build_handle(hwnd, wait_tries=1)
                except Exception:
                    continue
                used.add(handle.root_hwnd)
                try:
                    used.add(handle.shot_hwnd)
                except Exception:
                    pass
                iid = _mh._suffix_id(handle.root_title, -1)
                found.append(ClientInfo(
                    kind="emulator", pid=pid, hwnd=handle.root_hwnd,
                    title=handle.root_title, index=None if iid < 0 else iid,
                    detail=handle.root_title))
        elif name in PC_PROC_NAMES and PC_PATH_HINT in _exe_lower(info):
            for hwnd in windows_of_pid(pid):
                if hwnd in used:
                    continue
                used.add(hwnd)
                try:
                    title = win32gui.GetWindowText(hwnd)
                except Exception:
                    title = ""
                found.append(ClientInfo(kind="pc", pid=pid, hwnd=hwnd,
                                        title=title, index=None, detail=title))
    found.sort(key=lambda c: (0 if c.kind == "emulator" else 1, c.pid))
    return found
