import os
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
        self.assertEqual(page.launch_interval.minimum(), 3)
        self.assertEqual(page.launch_interval.maximum(), 120)

    def test_launch_count_default_and_range(self):
        page = MultiInstancePage()
        self.assertEqual(page.get_launch_count(), 1)
        self.assertEqual(page.launch_count.minimum(), 1)
        self.assertEqual(page.launch_count.maximum(), 20)


if __name__ == "__main__":
    unittest.main()
