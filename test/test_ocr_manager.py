"""OCRManager 回归测试：早退 bug（任何输入都返回未找到）不得复现。"""
import numpy as np

from OAT.tools.OCRManager import OCRManager


class _FakeResults:
    def __init__(self, txts, scores, boxes):
        self.txts = txts
        self.scores = scores
        self.boxes = boxes


class _FakeBox:
    def __init__(self, pts):
        self._pts = pts

    def tolist(self):
        return self._pts


def _manager_with(results):
    mgr = OCRManager()
    mgr._init_reader = lambda: None
    mgr.reader = lambda img: results
    return mgr


def _img():
    return np.zeros((64, 64, 3), dtype=np.uint8)


def test_find_text_returns_match():
    """回归：txts 非空时必须走匹配循环并返回命中区域。"""
    box = _FakeBox([[10.0, 20.0], [40.0, 20.0], [40.0, 40.0], [10.0, 40.0]])
    results = _FakeResults(txts=["组队", "进攻"], scores=[0.99, 0.98], boxes=[box, box])
    mgr = _manager_with(results)
    found, area, real_text = mgr.find_text_offline(_img(), "进攻")
    assert found is True
    assert real_text == "进攻"
    assert area == [[10.0, 20.0], [40.0, 20.0], [40.0, 40.0], [10.0, 40.0]]


def test_find_text_substring_match():
    box = _FakeBox([[1.0, 1.0], [2.0, 1.0], [2.0, 2.0], [1.0, 2.0]])
    results = _FakeResults(txts=["点击进攻按钮"], scores=[0.9], boxes=[box])
    mgr = _manager_with(results)
    found, _area, real_text = mgr.find_text_offline(_img(), "进攻")
    assert found is True and real_text == "点击进攻按钮"


def test_find_text_no_match():
    box = _FakeBox([[1.0, 1.0], [2.0, 1.0], [2.0, 2.0], [1.0, 2.0]])
    results = _FakeResults(txts=["组队"], scores=[0.9], boxes=[box])
    mgr = _manager_with(results)
    assert mgr.find_text_offline(_img(), "进攻") == (False, None, None)


def test_find_text_empty_txts():
    """txts 为 None 时直接早退，不抛异常。"""
    results = _FakeResults(txts=None, scores=None, boxes=None)
    mgr = _manager_with(results)
    assert mgr.find_text_offline(_img(), "进攻") == (False, None, None)
