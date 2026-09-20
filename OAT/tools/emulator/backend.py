"""Backend 抽象：截图统一 BGR 1280x720；坐标统一客户区逻辑坐标。"""
import abc
from typing import Optional

import numpy as np


class EmulatorBackend(abc.ABC):
    @abc.abstractmethod
    def screenshot(self) -> Optional[np.ndarray]:
        """后台截图，BGR，1280x720 参考系；失败返回 None."""

    @abc.abstractmethod
    def click(self, x: int, y: int) -> None:
        """客户区逻辑坐标点击."""

    @abc.abstractmethod
    def long_click(self, x: int, y: int, duration: float) -> None:
        """客户区逻辑坐标长按，duration 秒."""

    @abc.abstractmethod
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> None:
        """客户区逻辑坐标滑动."""

    @abc.abstractmethod
    def instance_hwnds(self) -> list[int]:
        """本 backend 覆盖的实例顶层 HWND."""

    def close(self) -> None:
        """释放连接（默认空实现）."""


class PcBackend(EmulatorBackend):
    """旧 PC/前台行为的薄适配，具体截图/点击在 Task 7 接入现有代码.
    factory-only stub by design: methods raise NotImplementedError.
    call-sites keep backend=None under default pc mode."""

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
        from .mumu_backend import MumuBackend
        return MumuBackend(
            handle_spec=kwargs.get("handle_spec", "auto"),
            instance_index=int(kwargs.get("instance_index", 0)),
            mumu_folder=kwargs.get("mumu_folder", ""),
            ipc_dll_override=kwargs.get("ipc_dll_override", ""),
        )
    raise ValueError(f"unknown emulator_type: {emulator_type}")
