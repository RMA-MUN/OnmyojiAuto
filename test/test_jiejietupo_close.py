"""结界突破收尾：点关闭后必须验证真退出了，没退就重试，不行返回False。"""
import os
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from OAT.source.huijuanshuafen.huijuan import HuiJuan


def make_bot(**kw):
    params = dict(rounds=1, explore_count=1, templates={}, images_dir="",
                  config={}, window_title="t")
    params.update(kw)
    return HuiJuan(engine=mock.Mock(), **params)


def tpl_hit():
    return SimpleNamespace(found=True, region=(10, 20, 30, 40),
                           confidence=0.9)


class TestVerifyClosed(unittest.TestCase):
    def test_gone_immediately_returns_true_without_extra_click(self):
        bot = make_bot()
        bot.tpl_exists = mock.Mock(return_value=True)
        bot.find_img = mock.Mock(return_value=None)
        bot.click_center = mock.Mock()
        with mock.patch("time.sleep"):
            self.assertTrue(bot._verify_jiejietupo_closed(retries=3, interval=0))
        bot.click_center.assert_not_called()

    def test_still_there_then_gone_retries_and_returns_true(self):
        bot = make_bot()
        bot.tpl_exists = mock.Mock(return_value=True)
        # 第1轮校验：close命中(还在)→补点点击命中；第2轮：close无+title无(已退出)
        bot.find_img = mock.Mock(side_effect=[tpl_hit(), tpl_hit(), None, None])
        bot.click_center = mock.Mock()
        with mock.patch("time.sleep"):
            self.assertTrue(bot._verify_jiejietupo_closed(retries=3, interval=0))
        self.assertGreaterEqual(bot.click_center.call_count, 1)

    def test_always_there_returns_false(self):
        bot = make_bot()
        bot.tpl_exists = mock.Mock(return_value=True)
        bot.find_img = mock.Mock(return_value=tpl_hit())
        bot.click_center = mock.Mock()
        with mock.patch("time.sleep"):
            self.assertFalse(bot._verify_jiejietupo_closed(retries=2, interval=0))

    def test_no_anchor_templates_skips_verification(self):
        bot = make_bot()
        bot.tpl_exists = mock.Mock(return_value=False)
        bot.find_img = mock.Mock()
        with mock.patch("time.sleep"):
            self.assertTrue(bot._verify_jiejietupo_closed(retries=2, interval=0))
        bot.find_img.assert_not_called()


class TestWaitCloseAfterLastBattle(unittest.TestCase):
    def test_close_verified_returns_true(self):
        bot = make_bot()
        bot._click_blank = mock.Mock()
        bot.find_img = mock.Mock(return_value=tpl_hit())
        bot.click_center = mock.Mock()
        bot._verify_jiejietupo_closed = mock.Mock(return_value=True)
        with mock.patch("time.sleep"):
            self.assertTrue(bot._wait_close_after_last_battle(settle_wait=0, timeout=30))

    def test_close_not_verified_returns_false(self):
        bot = make_bot()
        bot._click_blank = mock.Mock()
        bot.find_img = mock.Mock(return_value=tpl_hit())
        bot.click_center = mock.Mock()
        bot._verify_jiejietupo_closed = mock.Mock(return_value=False)
        with mock.patch("time.sleep"):
            # 校验一直不过 → 耗尽 timeout 后返回 False（sleep 已 patch，1秒即超时）
            self.assertFalse(bot._wait_close_after_last_battle(settle_wait=0, timeout=1))


if __name__ == "__main__":
    unittest.main()
