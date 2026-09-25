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


def test_resolve_mumu_folder_uses_valid_config(monkeypatch):
    """配置路径有效时直接返回，不触发探测。"""
    called = []
    monkeypatch.setattr("OAT.tools.settings._is_valid_mumu_folder", lambda f: True)
    monkeypatch.setattr("OAT.tools.settings._detect_mumu_folder_safe",
                        lambda: called.append(1) or "D:\\MuMu12")
    assert settings.resolve_mumu_folder() == "E:\\MuMuPlayer"
    assert called == []


def test_resolve_mumu_folder_detects_and_persists(monkeypatch):
    """配置无效时走进程反推，并把结果回写 settings.json。"""
    raw_before = _json_path().read_bytes()
    try:
        monkeypatch.setattr("OAT.tools.settings._is_valid_mumu_folder", lambda f: False)
        monkeypatch.setattr("OAT.tools.settings._detect_mumu_folder_safe",
                            lambda: "D:\\MuMu12")
        assert settings.resolve_mumu_folder() == "D:\\MuMu12"
        assert settings.MUMU_FOLDER == "D:\\MuMu12"
        assert settings.settings_data.get("mumu_folder") == "D:\\MuMu12"
    finally:
        settings.update_settings("mumu_folder", "E:\\MuMuPlayer")
        _json_path().write_bytes(raw_before)
    assert _json_path().read_bytes() == raw_before


def test_resolve_mumu_folder_falls_back_when_no_detection(monkeypatch):
    """探测失败时回落配置值（空则回落默认路径）。"""
    raw_before = _json_path().read_bytes()
    try:
        monkeypatch.setattr("OAT.tools.settings._is_valid_mumu_folder", lambda f: False)
        monkeypatch.setattr("OAT.tools.settings._detect_mumu_folder_safe", lambda: None)
        assert settings.resolve_mumu_folder() == "E:\\MuMuPlayer"
    finally:
        _json_path().write_bytes(raw_before)
    assert _json_path().read_bytes() == raw_before


def test_resolve_mumu_folder_survives_detect_exception(monkeypatch):
    """探测抛异常时按失败处理，不向上抛。"""
    raw_before = _json_path().read_bytes()
    try:
        monkeypatch.setattr("OAT.tools.settings._is_valid_mumu_folder", lambda f: False)
        monkeypatch.setattr("OAT.tools.settings._detect_mumu_folder_safe",
                            lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        assert settings.resolve_mumu_folder() == "E:\\MuMuPlayer"
    finally:
        _json_path().write_bytes(raw_before)
    assert _json_path().read_bytes() == raw_before
