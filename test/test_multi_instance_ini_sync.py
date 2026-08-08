import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from OAT.app.main_window import MainWindow
from OAT.app.multi_instance_page import MultiInstancePage
from OAT.tools.MultiInstanceManager import MultiInstanceManager


class FakeSelf:
    pass


def make_manager(tmp):
    manager = MultiInstanceManager(yyx_dir=Path(tmp))
    Path(tmp, "yyx-launcher.exe").write_bytes(b"MZ")
    return manager


class TestIniSync(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_manual_input_writes_ini(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = make_manager(tmp)
            fake = FakeSelf()
            fake.multi_instance_manager = manager
            MainWindow.on_multi_path_changed(fake, r"D:\Games\Launch.exe")
            self.assertEqual(manager.get_saved_path(), r"D:\Games\Launch.exe")

    def test_empty_input_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = make_manager(tmp)
            manager.build_init_file(r"D:\Old\Launch.exe")
            fake = FakeSelf()
            fake.multi_instance_manager = manager
            MainWindow.on_multi_path_changed(fake, "")
            self.assertEqual(manager.get_saved_path(), r"D:\Old\Launch.exe")

    def test_browse_updates_ini_via_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = make_manager(tmp)
            fake = FakeSelf()
            fake.multi_instance_manager = manager
            page = MultiInstancePage()
            page.path_changed.connect(
                lambda path: MainWindow.on_multi_path_changed(fake, path)
            )
            with mock.patch(
                "OAT.app.multi_instance_page.QFileDialog.getOpenFileName",
                return_value=(r"D:\New\Launch.exe", "可执行文件 (*.exe)"),
            ):
                page.browse_btn.click()
            self.assertEqual(page.exe_path_input.text(), r"D:\New\Launch.exe")
            self.assertEqual(manager.get_saved_path(), r"D:\New\Launch.exe")

    def test_page_emits_path_changed_on_text_change(self):
        page = MultiInstancePage()
        emitted = []
        page.path_changed.connect(emitted.append)
        page.exe_path_input.setText(r"D:\Manual\Launch.exe")
        self.assertEqual(emitted, [r"D:\Manual\Launch.exe"])


if __name__ == "__main__":
    unittest.main()
