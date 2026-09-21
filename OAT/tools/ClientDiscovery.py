"""客户端发现：按进程枚举本机游戏客户端（与窗口标题无关，用户改名仍可识别）。

- 模拟器：MuMuNxDevice.exe（每开一台一个进程）→ mumu-cli 给权威 HWND，缺失时按句柄树兜底。
- 桌面版：onmyoji.exe 游戏本体优先（启动器启动完通常已退出）；Launch.exe 兜底。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import win32con
import win32gui

ClientKind = Literal["emulator", "pc"]

# 进程名统一小写比对（Windows 进程名大小写不敏感）
EMULATOR_PROC_NAMES = ("mumunxdevice.exe",)
PC_GAME_PROC_NAMES = ("onmyoji.exe",)
PC_LAUNCHER_PROC_NAMES = ("launch.exe",)
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


def _proc_name(info: dict) -> str:
    try:
        return str(info.get("name") or "").lower()
    except Exception:
        return ""


def _rank_windows(pid: int) -> list[tuple[int, str]]:
    """进程的可见顶层窗口按“像游戏主窗口”排序：有标题 > 无 owner > 客户区面积大。

    游戏进程常挂着无标题的小辅助窗（如 24x24 的 Win32Window0title），
    直接取第一个可见窗口会挑错，所以按上面的优先级排序后取首个。
    """
    rows: list[tuple[tuple[bool, bool, int], int, str]] = []
    for hwnd in windows_of_pid(pid):
        try:
            title = win32gui.GetWindowText(hwnd) or ""
        except Exception:
            title = ""
        try:
            top_level = win32gui.GetWindow(hwnd, win32con.GW_OWNER) == 0
        except Exception:
            top_level = False
        try:
            rect = win32gui.GetClientRect(hwnd)
            area = max(0, rect[2] - rect[0]) * max(0, rect[3] - rect[1])
        except Exception:
            area = 0
        rows.append(((bool(title), top_level, area), hwnd, title))
    rows.sort(key=lambda row: row[0], reverse=True)
    return [(hwnd, title) for _key, hwnd, title in rows]


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
    """发现结果 → 下拉框条目 [(label, ClientInfo|None)]。

    有发现项时只列发现项（进程识别为准，窗口改名不影响）；一个都没发现
    （游戏没开）才退回静态标题，其 ClientInfo 为 None，选中时按旧标题链路处理。
    """
    items: list[tuple[str, ClientInfo | None]] = []
    seen: set[str] = set()
    for c in clients or []:
        label = client_label(c)
        if label in seen:
            continue
        seen.add(label)
        items.append((label, c))
    if items:
        return items
    for t in fallback_titles or []:
        t = (t or "").strip()
        if not t or t in seen:
            continue
        seen.add(t)
        items.append((t, None))
    return items


def build_window_rows(clients: list[ClientInfo]) -> list[tuple[int, str]]:
    """同步器窗口表格行：[(hwnd, 展示文案)]，与首页下拉同一套进程发现结果。"""
    rows: list[tuple[int, str]] = []
    for c in clients or []:
        try:
            hwnd = int(c.hwnd)
        except (TypeError, ValueError):
            continue
        if hwnd:
            rows.append((hwnd, client_label(c)))
    return rows


def discover_clients(mumu_folder: str = "") -> list[ClientInfo]:
    """扫描进程列出客户端：emulator 在前，pc 在后；同类按 pid 排序。

    模拟器三级定位（与窗口标题无关）：
    1. mumu-cli 的 main_wnd（最权威，直接是游戏根窗口 HWND）；
    2. MuMu 进程的窗口经 build_handle 句柄树校验（cli 缺失时兜底）；
    桌面版优先认游戏本体 onmyoji.exe，找不到才退回 Launch.exe（启动器）。
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

    procs = list(_iter_procs())

    for info in procs:
        try:
            name = _proc_name(info)
            pid = int(info.get("pid") or 0)
        except (ValueError, TypeError):
            continue
        if not name or not pid:
            continue
        if name not in EMULATOR_PROC_NAMES:
            continue
        for hwnd, _win_title in _rank_windows(pid):
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

    # 桌面版：游戏本体优先（启动器启动完通常已退出），找不到才退回启动器窗口
    pc_procs = [i for i in procs if PC_PATH_HINT in _exe_lower(i)]
    game_procs = [i for i in pc_procs if _proc_name(i) in PC_GAME_PROC_NAMES]
    launcher_procs = [i for i in pc_procs if _proc_name(i) in PC_LAUNCHER_PROC_NAMES]
    for info in (game_procs or launcher_procs):
        try:
            pid = int(info.get("pid") or 0)
        except (ValueError, TypeError):
            continue
        ranked = _rank_windows(pid) if pid else []
        if not ranked:
            continue
        hwnd, title = ranked[0]
        if hwnd in used:
            continue
        used.add(hwnd)
        found.append(ClientInfo(kind="pc", pid=pid, hwnd=hwnd,
                                title=title, index=None, detail=title))

    found.sort(key=lambda c: (0 if c.kind == "emulator" else 1, c.pid))
    return found
