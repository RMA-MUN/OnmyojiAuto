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
    b = create_backend("pc", hwnd=12345)
    assert isinstance(b, PcBackend)
    assert b.instance_hwnds() == [12345]


def test_create_unknown_raises():
    with pytest.raises(ValueError, match="unknown emulator_type"):
        create_backend("nox")


def test_mumu_invalid_handle_raises():
    with pytest.raises(ValueError, match="not a valid window"):
        create_backend("mumu12", handle_spec=99999999)
