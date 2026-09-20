"""Task 6: 新配置键默认值与 update_settings 联动（不污染 settings.json 文件）。"""
from pathlib import Path

from OAT.tools import settings


def _json_path() -> Path:
    return Path(settings.settings_file_path)


def test_defaults_keep_old_behavior():
    assert settings.EMULATOR_TYPE == "pc"
    assert settings.HANDLE_SPEC == "auto"
    assert settings.SCREENSHOT_METHOD == "nemu_ipc"
    assert settings.CONTROL_METHOD == "window_message"
    assert settings.MUMU_FOLDER == "E:\\MuMuPlayer"


def test_update_roundtrip_emulator_type():
    raw_before = _json_path().read_bytes()
    old = settings.EMULATOR_TYPE
    try:
        assert settings.update_settings("emulator_type", "mumu12") is True
        assert settings.EMULATOR_TYPE == "mumu12"
    finally:
        settings.update_settings("emulator_type", old)
        _json_path().write_bytes(raw_before)
    assert settings.EMULATOR_TYPE == old
    assert _json_path().read_bytes() == raw_before
