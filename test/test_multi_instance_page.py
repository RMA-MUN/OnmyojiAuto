import os
import threading
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from OAT.app.multi_instance_page import MultiInstancePage


class TestMultiInstancePage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_launch_interval_default_and_range(self):
        page = MultiInstancePage()
        self.assertEqual(page.get_launch_interval(), 5)
        self.assertEqual(page.launch_interval.minimum(), 0)
        self.assertEqual(page.launch_interval.maximum(), 120)

    def test_table_has_six_columns(self):
        page = MultiInstancePage()
        self.assertEqual(page.instance_table.columnCount(), 6)

    def test_add_instance_fills_columns(self):
        page = MultiInstancePage()
        page.add_instance(7, pid=12345, status="运行中", launched_at="12:00:01")
        self.assertEqual(page.instance_table.rowCount(), 1)
        self.assertEqual(page.instance_table.item(0, 1).text(), "7")
        self.assertEqual(page.instance_table.item(0, 2).text(), "12345")
        self.assertEqual(page.instance_table.item(0, 3).text(), "运行中")
        self.assertEqual(page.instance_table.item(0, 4).text(), "12:00:01")
        self.assertIsNotNone(page.instance_table.cellWidget(0, 5))

    def test_worker_thread_emit_creates_rows_without_crash(self):
        page = MultiInstancePage()
        page.show()

        def worker():
            page.instance_added.emit(1, 100, "运行中", "00:00:01")
            page.instance_added.emit(2, 101, "运行中", "00:00:02")

        t = threading.Thread(target=worker)
        t.start()

        deadline = time.time() + 5
        while page.instance_table.rowCount() < 2 and time.time() < deadline:
            self.app.processEvents()
            time.sleep(0.02)
        t.join(timeout=2)
        self.app.processEvents()

        self.assertEqual(page.instance_table.rowCount(), 2)


    def test_update_instance_updates_columns(self):
        page = MultiInstancePage()
        page.add_instance(1, pid=100, status="运行中", launched_at="00:00:01")
        page.update_instance(1, pid=200, status="已关闭")
        self.assertEqual(page.instance_table.item(0, 2).text(), "200")
        self.assertEqual(page.instance_table.item(0, 3).text(), "已关闭")
        self.assertEqual(page.instance_table.item(0, 4).text(), "00:00:01")

    def test_update_instance_unknown_id_noop(self):
        page = MultiInstancePage()
        page.add_instance(1, pid=100, status="运行中")
        page.update_instance(99, status="已关闭")
        self.assertEqual(page.instance_table.item(0, 3).text(), "运行中")


if __name__ == "__main__":
    unittest.main()
