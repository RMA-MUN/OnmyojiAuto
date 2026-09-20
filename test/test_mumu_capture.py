"""Task 4: 归一化数学（不依赖真窗口；capture 通道用假对象）。"""
import numpy as np

from OAT.tools.emulator.mumu_capture import (
    REF_H, REF_W, normalize_to, normalize_to_ref,
)


def test_ref_consts():
    assert (REF_W, REF_H) == (1280, 720)


def test_normalize_resizes():
    img = np.zeros((360, 640, 3), dtype=np.uint8)
    out = normalize_to_ref(img)
    assert out.shape == (720, 1280, 3)


def test_normalize_passthrough():
    img = np.zeros((720, 1280, 3), dtype=np.uint8)
    assert normalize_to_ref(img) is img


def test_normalize_to_custom_size():
    """模板按窗口客户区尺度制作：IPC 原生帧要缩放到客户区尺寸。"""
    img = np.zeros((720, 1280, 3), dtype=np.uint8)
    out = normalize_to(img, 1386, 780)
    assert out.shape[:2] == (780, 1386)
    bad = normalize_to(img, 0, 0)
    assert bad is img


def test_is_black_gate():
    from OAT.tools.emulator.mumu_capture import _is_black
    assert _is_black(np.zeros((4, 4, 3), dtype=np.uint8)) is True
    assert _is_black(np.full((4, 4, 3), 200, dtype=np.uint8)) is False
