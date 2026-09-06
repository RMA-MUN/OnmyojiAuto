"""探索打完回28章：OCR 优先，k28 模板兜底（mock，不碰真窗口/真OCR）。"""
import os
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from OAT.source.huijuanshuafen.explore import ExploreManager


def make_mgr():
    return ExploreManager(engine=mock.Mock(), explore_count=3)


def tpl_hit(x=100, y=200, w=60, h=24, confidence=0.9):
    return SimpleNamespace(found=True, region=(x, y, w, h), confidence=confidence)


class TestFindChapter28Ocr(unittest.TestCase):
    def test_ocr_hit_returns_center(self):
        mgr = make_mgr()
        mgr._raw_capture = mock.Mock(return_value=object())
        mgr._ocr_on = mock.Mock(return_value=((111, 222), [(0, 0)]))
        self.assertEqual(mgr._find_chapter28_ocr(), (111, 222))

    def test_ocr_miss_returns_none(self):
        mgr = make_mgr()
        mgr._raw_capture = mock.Mock(return_value=object())
        mgr._ocr_on = mock.Mock(return_value=(None, None))
        self.assertIsNone(mgr._find_chapter28_ocr())

    def test_no_screenshot_returns_none(self):
        mgr = make_mgr()
        mgr._raw_capture = mock.Mock(return_value=None)
        mgr._ocr_on = mock.Mock()
        self.assertIsNone(mgr._find_chapter28_ocr())
        mgr._ocr_on.assert_not_called()


class TestEnterChapter28FromList(unittest.TestCase):
    def test_ocr_hit_clicks_ocr_point(self):
        mgr = make_mgr()
        mgr._find_chapter28_ocr = mock.Mock(return_value=(111, 222))
        mgr.find_img = mock.Mock(return_value=tpl_hit())  # title_28 一次命中
        mgr.click = mock.Mock()
        self.assertTrue(mgr._enter_chapter28_from_list(timeout=5))
        mgr.click.assert_called_once_with(111, 222)

    def test_ocr_miss_falls_back_to_template(self):
        mgr = make_mgr()
        mgr._find_chapter28_ocr = mock.Mock(return_value=None)

        def fake_find(name, *a, **k):
            return tpl_hit(100, 200, 60, 24) if name in ("k28", "title_28") else None

        mgr.find_img = mock.Mock(side_effect=fake_find)
        mgr.click = mock.Mock()
        self.assertTrue(mgr._enter_chapter28_from_list(timeout=5))
        mgr.click.assert_called_once_with(130, 212)  # 模板中心

    def test_both_miss_returns_false_without_click(self):
        mgr = make_mgr()
        mgr._find_chapter28_ocr = mock.Mock(return_value=None)
        mgr.find_img = mock.Mock(return_value=None)
        mgr.click = mock.Mock()
        self.assertFalse(mgr._enter_chapter28_from_list(timeout=5))
        mgr.click.assert_not_called()

    def test_clicked_but_no_title_returns_false(self):
        mgr = make_mgr()
        mgr._find_chapter28_ocr = mock.Mock(return_value=(111, 222))
        mgr.find_img = mock.Mock(return_value=None)  # title_28 始终无
        mgr.click = mock.Mock()
        self.assertFalse(mgr._enter_chapter28_from_list(timeout=0.5))
        mgr.click.assert_called_once_with(111, 222)


if __name__ == "__main__":
    unittest.main()
