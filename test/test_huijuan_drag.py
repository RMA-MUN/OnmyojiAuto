"""绘卷后台拖拽：有 backend 时委托 engine.swipe，无 backend 时回落 PostMessage（mock，不碰真窗口）。"""
import unittest
from unittest import mock

import win32con

from OAT.source.huijuanshuafen.base import BaseBot


def make_bot(backend=None, sync_mode=False):
    engine = mock.Mock()
    engine.hwnd = 12345
    engine.backend = backend
    return BaseBot(engine, sync_mode=sync_mode)


class TestDragWithBackend(unittest.TestCase):
    def test_drag_delegates_to_engine_swipe(self):
        """有 backend 时走 engine.swipe（IPC/渲染子窗口通道），不再直发 PostMessage。"""
        bot = make_bot(backend=object())
        with mock.patch("OAT.source.huijuanshuafen.base.win32gui") as wg:
            bot.drag(800, 300, 200, 300, steps=20, step_interval=0.02)
            wg.PostMessage.assert_not_called()
        args, kwargs = bot.engine.swipe.call_args
        self.assertEqual(args, (800, 300, 200, 300))
        self.assertAlmostEqual(kwargs["duration"], 20 * 0.02)
        self.assertFalse(kwargs["sync_mode"])

    def test_drag_passes_sync_mode(self):
        bot = make_bot(backend=object(), sync_mode=True)
        bot.drag(800, 300, 200, 300)
        _, kwargs = bot.engine.swipe.call_args
        self.assertTrue(kwargs["sync_mode"])

    def test_drag_without_backend_still_syncs(self):
        """同步模式但无 backend 时也走 engine.swipe（synchronizer 分支）。"""
        bot = make_bot(backend=None, sync_mode=True)
        with mock.patch("OAT.source.huijuanshuafen.base.win32gui") as wg:
            bot.drag(800, 300, 200, 300)
            wg.PostMessage.assert_not_called()
        bot.engine.swipe.assert_called_once()


class TestDragWithoutBackend(unittest.TestCase):
    def test_drag_uses_postmessage_sequence(self):
        """无 backend（PC 桌面版后台）保持原 20 步消息拖拽。"""
        bot = make_bot(backend=None)
        with mock.patch("OAT.source.huijuanshuafen.base.win32gui") as wg, \
                mock.patch("OAT.source.huijuanshuafen.base.time.sleep"):
            wg.IsWindow.return_value = True
            bot.drag(10, 20, 30, 40, steps=3, step_interval=0.01)
            bot.engine.swipe.assert_not_called()
            msgs = [c.args[1] for c in wg.PostMessage.call_args_list]
        self.assertEqual(len(msgs), 6)
        self.assertEqual(msgs[0], win32con.WM_MOUSEMOVE)
        self.assertEqual(msgs[1], win32con.WM_LBUTTONDOWN)
        self.assertEqual(msgs[-1], win32con.WM_LBUTTONUP)


if __name__ == "__main__":
    unittest.main()
