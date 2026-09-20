"""MumuBackend：组装 handle + capture + input + IPC，对外实现 EmulatorBackend。"""
from __future__ import annotations

import ctypes
from typing import Optional

import numpy as np

from OAT.utils.logging import logger

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
    _admin_warned = False

    def __init__(self, handle_spec: str = "auto", instance_index: int = 0,
                 mumu_folder: str = "", ipc_dll_override: str = "",
                 app_package: str = ""):
        from . import mumu_handle as _mh
        if str(handle_spec) == "auto":
            # resolve_auto 返回 HWND；build_handle 校验句柄树
            spec, self._instance_id = _mh.resolve_auto(instance_index, mumu_folder)
        else:
            spec = handle_spec
            self._instance_id = int(instance_index)
            # 显式句柄时用 cli 反查真实实例号（多开/改名场景下 IPC 才对得上号）
            try:
                spec_int = int(spec)
            except (ValueError, TypeError):
                spec_int = None
            if spec_int is not None:
                try:
                    for hwnd, iid, _n in _mh.query_cli_windows(mumu_folder):
                        if int(hwnd) == spec_int:
                            self._instance_id = int(iid)
                            break
                except Exception:
                    pass
        self._handle = build_handle(spec)
        self._folder = mumu_folder
        self._override = ipc_dll_override
        self._ipc: Optional[NemuIpc] = None
        self._connect_ipc()
        self._app_package = app_package
        if self._ipc is not None:
            # v6 真前台在 "default" display（如 5）上，不主动解析则停留在桌面 display 0
            try:
                self._ipc.refresh_display_id((app_package or "").strip() or "default")
            except Exception:
                pass
        self.is_elevated = is_admin()
        if not self.is_elevated and not MumuBackend._admin_warned:
            MumuBackend._admin_warned = True
            logger.warning("not running as admin; SendMessage to MuMu child window may fail — prefer NemuIPC input or relaunch elevated")
        self._cap = MumuCapture(self._handle, self._ipc)
        self._input = MumuInput(self._handle, self._ipc)

    def _connect_ipc(self) -> None:
        dll = find_ipc_dll(self._folder, self._override)
        if not dll:
            self._ipc = None
            return
        try:
            ipc = NemuIpc(dll, self._instance_id, self._folder or "E:\\MuMuPlayer")
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
