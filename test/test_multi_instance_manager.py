import locale
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from OAT.tools.MultiInstanceManager import MultiInstanceManager

ENCODING = locale.getpreferredencoding(False)


class FakeProc:
    pid = 1234


class TestBuildInitFile(unittest.TestCase):
    def test_writes_expected_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = MultiInstanceManager(yyx_dir=Path(tmp))
            manager.build_init_file(r"D:\Games\Launch.exe")
            expected = "[YYXLaucher]\r\nYYSLaunchPath=D:\\Games\\Launch.exe\r\n"
            self.assertEqual(
                manager.launcher_ini.read_bytes(),
                expected.encode(ENCODING),
            )

    def test_overwrites_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            ini = Path(tmp) / "yyx-launcher.ini"
            ini.write_text("old", encoding=ENCODING)
            manager = MultiInstanceManager(yyx_dir=Path(tmp))
            manager.build_init_file(r"C:\New\Launch.exe")
            self.assertIn("C:\\New\\Launch.exe", ini.read_text(encoding=ENCODING))


class TestLaunchInstances(unittest.TestCase):
    def test_starts_n_times_with_interval(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "yyx-launcher.exe").write_bytes(b"MZ")
            manager = MultiInstanceManager(yyx_dir=Path(tmp))
            with mock.patch("OAT.tools.MultiInstanceManager.subprocess.Popen",
                            return_value=FakeProc()) as popen, \
                 mock.patch("OAT.tools.MultiInstanceManager.time.sleep") as sleep:
                launched = manager.launch_instances(r"D:\Games\Launch.exe", count=3, interval=0.01)
            self.assertEqual(popen.call_count, 3)
            self.assertEqual(sleep.call_count, 2)
            self.assertEqual(len(launched), 3)
            for inst in launched:
                self.assertEqual(inst.pid, 1234)
                self.assertEqual(inst.status, "运行中")
                self.assertTrue(inst.launched_at)
            self.assertIn(r"D:\Games\Launch.exe",
                          manager.launcher_ini.read_text(encoding=ENCODING))

    def test_on_launched_callback_called_per_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "yyx-launcher.exe").write_bytes(b"MZ")
            manager = MultiInstanceManager(yyx_dir=Path(tmp))
            called = []
            with mock.patch("OAT.tools.MultiInstanceManager.subprocess.Popen",
                            return_value=FakeProc()), \
                 mock.patch("OAT.tools.MultiInstanceManager.time.sleep"):
                manager.launch_instances("x", count=3, interval=0.01,
                                         on_launched=lambda inst: called.append(inst))
            self.assertEqual(len(called), 3)
            self.assertEqual([i.instance_id for i in called], [1, 2, 3])
            self.assertEqual(called[0].status, "运行中")

    def test_failure_marks_instance_and_continues(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "yyx-launcher.exe").write_bytes(b"MZ")
            manager = MultiInstanceManager(yyx_dir=Path(tmp))
            with mock.patch("OAT.tools.MultiInstanceManager.subprocess.Popen",
                            side_effect=[FakeProc(), OSError("boom"), FakeProc()]):
                launched = manager.launch_instances("x", count=3, interval=0)
            self.assertEqual(launched[1].status, "失败: boom")
            self.assertIsNone(launched[1].pid)
            self.assertEqual(launched[2].pid, 1234)

    def test_missing_launcher_raises_without_writing_ini(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = MultiInstanceManager(yyx_dir=Path(tmp))
            with self.assertRaises(FileNotFoundError):
                manager.launch_instances("x", count=1, interval=0)
            self.assertFalse(manager.launcher_ini.exists())


class TestCloseAndStatus(unittest.TestCase):
    def _manager_with_instance(self, tmp, pid=111):
        Path(tmp, "yyx-launcher.exe").write_bytes(b"MZ")
        manager = MultiInstanceManager(yyx_dir=Path(tmp))
        inst = manager.launch_instances("x", count=1, interval=0)
        manager.instances[1].pid = pid
        return manager, inst[0]

    def test_close_kills_process_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, inst = self._manager_with_instance(tmp)
            child1, child2 = mock.Mock(), mock.Mock()
            parent = mock.Mock()
            parent.children.return_value = [child1, child2]
            with mock.patch("OAT.tools.MultiInstanceManager.psutil.pid_exists",
                            return_value=True) as pid_exists, \
                 mock.patch("OAT.tools.MultiInstanceManager.psutil.Process",
                            return_value=parent) as proc_cls, \
                 mock.patch("OAT.tools.MultiInstanceManager.psutil.wait_procs",
                            return_value=([child1, child2, parent], [])):
                result = manager.close_instance(1)
            self.assertTrue(result)
            self.assertEqual(inst.status, "已关闭")
            pid_exists.assert_called_once_with(111)
            proc_cls.assert_called_once_with(111)
            self.assertEqual(child1.terminate.call_count, 1)
            self.assertEqual(child2.terminate.call_count, 1)
            self.assertEqual(parent.terminate.call_count, 1)

    def test_close_dead_pid_marks_exited(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, inst = self._manager_with_instance(tmp)
            with mock.patch("OAT.tools.MultiInstanceManager.psutil.pid_exists",
                            return_value=False):
                result = manager.close_instance(1)
            self.assertTrue(result)
            self.assertEqual(inst.status, "已退出")

    def test_close_missing_instance_returns_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = MultiInstanceManager(yyx_dir=Path(tmp))
            self.assertFalse(manager.close_instance(99))

    def test_status_follows_pid_liveness(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, inst = self._manager_with_instance(tmp)
            with mock.patch("OAT.tools.MultiInstanceManager.psutil.pid_exists",
                            return_value=True):
                self.assertEqual(manager.get_instance_status(1), "运行中")
            with mock.patch("OAT.tools.MultiInstanceManager.psutil.pid_exists",
                            return_value=False):
                self.assertEqual(manager.get_instance_status(1), "已退出")

    def test_status_preserves_failed_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "yyx-launcher.exe").write_bytes(b"MZ")
            manager = MultiInstanceManager(yyx_dir=Path(tmp))
            manager.instances[1] = manager.launch_instances("x", count=1, interval=0)[0]
            manager.instances[1].pid = None
            manager.instances[1].status = "失败: x"
            self.assertEqual(manager.get_instance_status(1), "失败: x")

    def test_close_all_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager, _ = self._manager_with_instance(tmp)
            manager.launch_instances("x", count=1, interval=0)
            with mock.patch("OAT.tools.MultiInstanceManager.psutil.pid_exists",
                            return_value=True), \
                 mock.patch("OAT.tools.MultiInstanceManager.psutil.Process",
                            return_value=mock.Mock()) as proc_cls, \
                 mock.patch("OAT.tools.MultiInstanceManager.psutil.wait_procs",
                            return_value=([], [])):
                closed = manager.close_all()
            self.assertEqual(closed, 2)
            self.assertEqual(proc_cls.call_count, 2)


if __name__ == "__main__":
    unittest.main()
