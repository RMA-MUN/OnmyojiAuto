"""更新程序「启动 OAT」按钮：OAT.exe 路径解析（纯逻辑，无需界面）。"""
import os

from OAT_Updater_GUI.ui.update_gui import resolve_oat_exe


def test_resolve_prefers_install_dir(tmp_path):
    oat = tmp_path / "OAT.exe"
    oat.write_bytes(b"x")
    assert resolve_oat_exe(str(tmp_path), str(tmp_path)) == str(oat)


def test_resolve_falls_back_to_exe_dir(tmp_path):
    exe_dir = tmp_path / "exe_dir"
    exe_dir.mkdir()
    oat = exe_dir / "OAT.exe"
    oat.write_bytes(b"x")
    assert resolve_oat_exe(str(tmp_path), str(exe_dir)) == str(oat)


def test_resolve_missing_returns_none(tmp_path):
    assert resolve_oat_exe(str(tmp_path), str(tmp_path)) is None
