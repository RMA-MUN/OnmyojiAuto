import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from OAT.tools.edit_mode_and_img import (
    _normalize_dest_filename,
    _plan_image_file_replace,
    _apply_image_file_replace,
)


class TestNormalizeDestFilename(unittest.TestCase):
    def test_keeps_extension_and_strips(self):
        self.assertEqual(
            _normalize_dest_filename("  boss.png ", "/tmp/a.jpg", "old.png"),
            "boss.png",
        )

    def test_no_ext_inherits_pending_source_ext(self):
        self.assertEqual(
            _normalize_dest_filename("boss", "/tmp/a.jpg", "old.png"),
            "boss.jpg",
        )

    def test_no_ext_no_pending_inherits_old_ext(self):
        self.assertEqual(
            _normalize_dest_filename("boss", None, "old.bmp"),
            "boss.bmp",
        )

    def test_no_ext_anywhere_defaults_png(self):
        self.assertEqual(
            _normalize_dest_filename("boss", None, ""),
            "boss.png",
        )

    def test_empty_name_returns_empty(self):
        self.assertEqual(_normalize_dest_filename("   ", "/tmp/a.png", "old.png"), "")


class TestPlanImageFileReplace(unittest.TestCase):
    def test_replace_with_new_source_and_rename(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "src_new.png")
            open(src, "wb").write(b"new")
            old = os.path.join(tmp, "mode", "old.png")
            os.makedirs(os.path.dirname(old), exist_ok=True)
            open(old, "wb").write(b"old")
            mode_dir = os.path.dirname(old)
            plan = _plan_image_file_replace(mode_dir, "old.png", "boss.png", src)
            self.assertTrue(plan["need_copy"])
            self.assertTrue(plan["remove_old"])
            self.assertEqual(os.path.basename(plan["dest_path"]), "boss.png")

    def test_replace_same_file_no_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            mode_dir = os.path.join(tmp, "mode")
            os.makedirs(mode_dir, exist_ok=True)
            dest = os.path.join(mode_dir, "old.png")
            open(dest, "wb").write(b"x")
            plan = _plan_image_file_replace(mode_dir, "old.png", "old.png", dest)
            self.assertFalse(plan["need_copy"])
            self.assertFalse(plan["remove_old"])

    def test_pure_rename_no_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            mode_dir = os.path.join(tmp, "mode")
            os.makedirs(mode_dir, exist_ok=True)
            plan = _plan_image_file_replace(mode_dir, "old.png", "boss.png", None)
            self.assertFalse(plan["need_copy"])
            self.assertTrue(plan["remove_old"])

    def test_no_change_no_op(self):
        with tempfile.TemporaryDirectory() as tmp:
            mode_dir = os.path.join(tmp, "mode")
            os.makedirs(mode_dir, exist_ok=True)
            plan = _plan_image_file_replace(mode_dir, "old.png", "old.png", None)
            self.assertFalse(plan["need_copy"])
            self.assertFalse(plan["remove_old"])


class TestApplyImageFileReplace(unittest.TestCase):
    def test_copy_and_remove_old(self):
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = os.path.join(tmp, "src")
            mode_dir = os.path.join(tmp, "mode")
            os.makedirs(src_dir, exist_ok=True)
            os.makedirs(mode_dir, exist_ok=True)
            src = os.path.join(src_dir, "shot.jpg")
            with open(src, "wb") as f:
                f.write(b"new-bytes")
            old = os.path.join(mode_dir, "old.png")
            with open(old, "wb") as f:
                f.write(b"old-bytes")
            plan = _plan_image_file_replace(mode_dir, "old.png", "boss.jpg", src)
            _apply_image_file_replace(plan)
            self.assertTrue(os.path.exists(os.path.join(mode_dir, "boss.jpg")))
            self.assertFalse(os.path.exists(old))
            with open(os.path.join(mode_dir, "boss.jpg"), "rb") as f:
                self.assertEqual(f.read(), b"new-bytes")

    def test_overwrite_same_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = os.path.join(tmp, "src")
            mode_dir = os.path.join(tmp, "mode")
            os.makedirs(src_dir, exist_ok=True)
            os.makedirs(mode_dir, exist_ok=True)
            src = os.path.join(src_dir, "new.png")
            with open(src, "wb") as f:
                f.write(b"v2")
            old = os.path.join(mode_dir, "old.png")
            with open(old, "wb") as f:
                f.write(b"v1")
            plan = _plan_image_file_replace(mode_dir, "old.png", "old.png", src)
            _apply_image_file_replace(plan)
            with open(old, "rb") as f:
                self.assertEqual(f.read(), b"v2")


if __name__ == "__main__":
    unittest.main()
