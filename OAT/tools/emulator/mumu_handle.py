"""MuMu 句柄层：枚举 + 句柄树 + 家族判定 + 系统缩放。

OAS 对应逻辑：module/device/handle.py（Handle.handle_tree / emulator_family /
screenshot_handle_num / window_scale_rate）。
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Union

import psutil
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
# updater/托盘残留窗口（如 NxUpdaterMessageWndMuMuPlayer）含 MuMuPlayer 子串但不是游戏窗口，必须排除
IGNORED_TITLE_SUBSTRINGS = ("MessageWnd",)
# 游戏窗口所属进程（与窗口标题无关，用户改名后仍可识别）
MUMU_PROCESS_NAMES = ("MuMuNxDevice.exe", "MuMuPlayer.exe", "NemuPlayer.exe")


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
        title = title or ""
        lowered = title.lower()
        if any(ign.lower() in lowered for ign in IGNORED_TITLE_SUBSTRINGS):
            return True
        for key in MUMU_TITLES:
            if key and key in title:
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


def query_cli_instances(mumu_folder: str) -> dict[str, int]:
    """`mumu-cli info --vmindex all` → {窗口标题: 真实 instance id}；失败返回 {}。

    窗口顺序≠instance id（只开 15.0 时它是唯一的窗口但 id 为 1），cli 是权威映射。
    """
    import json
    import os
    import subprocess
    try:
        cli = os.path.join((mumu_folder or "").strip(), "nx_main", "mumu-cli.exe")
        if not os.path.isfile(cli):
            return {}
        proc = subprocess.run([cli, "info", "--vmindex", "all"],
                              capture_output=True, timeout=10)
        data = json.loads((proc.stdout or b"").decode("utf-8", "replace"))
    except Exception:
        return {}
    out: dict[str, int] = {}
    if isinstance(data, dict):
        for key, val in data.items():
            try:
                name = (val or {}).get("name", "")
                if name:
                    out[str(name)] = int(key)
            except (ValueError, TypeError):
                continue
    return out


def order_windows(wins: list[tuple[int, str]],
                  cli_map: dict[str, int] | None = None) -> list[tuple[int, str]]:
    """cli 映射命中时按真实 instance id 排；否则沿用（优先级，HWND）顺序。"""
    cli_map = cli_map or {}

    def _key(t: tuple[int, str]):
        if t[1] in cli_map:
            return (0, cli_map[t[1]], t[0])
        return (1, _title_priority(t[1]), t[0])

    return sorted(wins, key=_key)


def _pid_of(hwnd: int) -> int:
    import win32process
    return win32process.GetWindowThreadProcessId(hwnd)[1]


def _exe_of(pid: int) -> str:
    try:
        return psutil.Process(pid).name() or ""
    except Exception:
        return ""


def enum_mumu_by_process() -> list[int]:
    """按所属进程枚举（与窗口标题无关，用户改名后仍可识别）。"""
    found: list[int] = []

    def _cb(hwnd: int, _p) -> bool:
        try:
            if _exe_of(_pid_of(hwnd)) in MUMU_PROCESS_NAMES:
                found.append(hwnd)
        except Exception:
            pass
        return True

    try:
        _gui.EnumWindows(_cb, None)
    except Exception:
        return []
    return sorted(set(found))


def query_cli_windows(mumu_folder: str) -> list[tuple[int, int, str]]:
    """mumu-cli → [(HWND, instance id, name)]；标题无关的最权威映射。"""
    import json
    import os
    import subprocess
    try:
        cli = os.path.join((mumu_folder or "").strip(), "nx_main", "mumu-cli.exe")
        if not os.path.isfile(cli):
            return []
        proc = subprocess.run([cli, "info", "--vmindex", "all"],
                              capture_output=True, timeout=10)
        data = json.loads((proc.stdout or b"").decode("utf-8", "replace"))
    except Exception:
        return []
    out: list[tuple[int, int, str]] = []
    if isinstance(data, dict):
        for key, val in data.items():
            try:
                v = val or {}
                hwnd = int(str(v.get("main_wnd", "") or ""), 16)
                if hwnd and is_window(hwnd):
                    out.append((hwnd, int(key), str(v.get("name", ""))))
            except (ValueError, TypeError):
                continue
    return out


def _suffix_id(title: str, fallback: int) -> int:
    """标题尾部 -N（如 MuMu安卓设备-1）→ N；无后缀沿用 fallback。"""
    m = re.search(r"-(\d+)\s*$", title or "")
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return fallback


def resolve_auto(instance_index: int = 0, mumu_folder: str = "") -> tuple[int, int]:
    """auto 解析 → (HWND, instance id)，三级递进：cli HWND → 进程扫描 → 标题枚举。"""
    idx = int(instance_index)
    cli = query_cli_windows(mumu_folder)
    if cli:
        ordered = sorted(cli, key=lambda t: t[1])
        if idx >= len(ordered):
            raise ValueError(f"instance_index {idx} out of range ({len(ordered)} running instances)")
        hwnd, iid, _ = ordered[idx]
        return hwnd, iid
    valid: list[MumuHandle] = []
    for hwnd in enum_mumu_by_process():
        try:
            valid.append(build_handle(hwnd))
        except Exception:
            continue
    if valid:
        valid.sort(key=lambda h: h.root_hwnd)
        if idx >= len(valid):
            raise ValueError(f"instance_index {idx} out of range ({len(valid)} emulator windows)")
        h = valid[idx]
        return h.root_hwnd, _suffix_id(h.root_title, idx)
    wins = order_windows(enum_mumu_windows(), query_cli_instances(mumu_folder))
    if idx >= len(wins):
        raise ValueError(f"instance_index {idx} out of range ({len(wins)} windows)")
    hwnd, title = wins[idx]
    return hwnd, _suffix_id(title, idx)


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


def build_handle(title_or_hwnd: Union[str, int], wait_tries: int = 10) -> MumuHandle:
    root, title = _resolve_root(title_or_hwnd)
    kids = _wait_children(root, tries=max(1, int(wait_tries)))
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
