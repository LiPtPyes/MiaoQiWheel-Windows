"""设置模型与持久化测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mqwheel.models.action import WheelActionKind
from mqwheel.models.settings import (
    MODE_COMBO,
    MODE_HOLD,
    HotKeyConfig,
    WheelSettings,
    vk_from_name,
)
from mqwheel.services.settings_store import SettingsStore


def test_default_settings_have_actions() -> None:
    settings = WheelSettings()
    assert len(settings.actions) == 6
    assert settings.hotkey.mode == MODE_HOLD
    assert settings.hotkey.key == "tab"


def test_hotkey_config_sanitizes_values() -> None:
    config = HotKeyConfig(mode="bogus", key="unknown", modifiers=["ctrl", "ctrl", "nope"], hold_ms=99999)
    assert config.mode == MODE_HOLD
    assert config.key == "tab"
    assert config.modifiers == ["ctrl"]
    assert config.hold_ms == 800


def test_hotkey_display_text() -> None:
    assert "长按" in HotKeyConfig(mode=MODE_HOLD, key="tab").display_text()
    assert "双击" in HotKeyConfig(mode="doubleTap", key="tab").display_text()
    assert HotKeyConfig(mode=MODE_COMBO, key="space", modifiers=["ctrl", "alt"]).display_text() == (
        "Ctrl+Alt+空格"
    )


def test_vk_lookup() -> None:
    assert vk_from_name("tab") == 0x09
    assert vk_from_name("a") == 0x41
    assert vk_from_name("space") == 0x20


def test_round_trip(tmp_path) -> None:
    settings = WheelSettings()
    settings.hotkey.hold_ms = 150
    settings.appearance.scale = 1.2
    settings.actions[0].title = "改过的标题"

    store = SettingsStore(tmp_path / "settings.json")
    assert store.save(settings)
    loaded = store.load()

    assert loaded.hotkey.hold_ms == 150
    assert loaded.appearance.scale == 1.2
    assert loaded.actions[0].title == "改过的标题"
    assert loaded.actions[0].kind == WheelActionKind.SHELL_COMMAND


def test_load_creates_default_file(tmp_path) -> None:
    store = SettingsStore(tmp_path / "nested" / "settings.json")
    assert not store.exists()
    settings = store.load()
    assert store.exists()
    assert len(settings.actions) == 6


def test_load_tolerates_corrupted_file(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{ not json", encoding="utf-8")
    settings = SettingsStore(path).load()
    assert len(settings.actions) == 6


def test_load_drops_unknown_kind(tmp_path) -> None:
    path = tmp_path / "settings.json"
    payload = {
        "version": 1,
        "actions": [
            {"title": "好的", "kind": "url", "payload": "https://example.com"},
            {"title": "坏的", "kind": "mystery", "payload": "x"},
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    settings = SettingsStore(path).load()
    assert len(settings.actions) == 1
    assert settings.actions[0].title == "好的"


def test_save_is_atomic(tmp_path) -> None:
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.save(WheelSettings())
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.startswith(".settings-")]
    assert leftovers == []


@pytest.mark.parametrize("scale", [0.1, 0.9, 5.0])
def test_scale_is_clamped(scale: float) -> None:
    settings = WheelSettings.from_dict({"appearance": {"scale": scale}})
    assert 0.82 <= settings.appearance.scale <= 1.20


# region v1 → v2 迁移


def test_default_browser_action_reuses_window() -> None:
    browser = next(a for a in WheelSettings().actions if a.title == "浏览器")
    assert browser.kind == WheelActionKind.WINDOW_TOGGLE


def test_default_terminal_action_still_launches_new() -> None:
    terminal = next(a for a in WheelSettings().actions if a.title == "终端")
    assert terminal.kind == WheelActionKind.APPLICATION


def test_v1_browser_migrates_to_window_toggle() -> None:
    """老配置里存的是 application，不迁移的话升级后行为根本没变。"""
    settings = WheelSettings.from_dict(
        {
            "version": 1,
            "actions": [
                {
                    "title": "浏览器",
                    "kind": "application",
                    "payload": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                },
                {
                    "title": "终端",
                    "kind": "application",
                    "payload": r"C:\Users\me\AppData\Local\Microsoft\WindowsApps\wt.exe",
                },
            ],
        }
    )
    assert settings.actions[0].kind == WheelActionKind.WINDOW_TOGGLE
    assert settings.actions[1].kind == WheelActionKind.APPLICATION, "终端必须保持每次新建"
    assert settings.version == 2, "迁移后要写回新版本号，免得每次加载都重跑"


def test_migration_leaves_other_apps_alone() -> None:
    settings = WheelSettings.from_dict(
        {
            "version": 1,
            "actions": [{"title": "编辑器", "kind": "application", "payload": r"C:\Tools\code.exe"}],
        }
    )
    assert settings.actions[0].kind == WheelActionKind.APPLICATION


def test_migrated_settings_are_not_touched_again() -> None:
    """已是 v2 就不再动：用户手动把浏览器改回「应用」也不会被反复纠正。"""
    settings = WheelSettings.from_dict(
        {
            "version": 2,
            "actions": [{"title": "浏览器", "kind": "application", "payload": "msedge.exe"}],
        }
    )
    assert settings.actions[0].kind == WheelActionKind.APPLICATION


def test_config_dir_is_a_single_source_of_truth(monkeypatch, tmp_path) -> None:
    """设置存储、「关于」页、崩溃日志必须算出同一个配置目录。

    这个逻辑一度被抄了四遍，其中「关于」页那遍是错的：它写的是
    ``os.environ.get("APPDATA", os.path.expanduser("~"))`` —— 变量存在但为**空串**时
    ``get`` 返回的是空串而不是默认值，``os.path.join("", APP_ID)`` 会得到一个
    **相对路径**，于是「关于」页显示的目录和实际写入的目录不是同一个。
    """
    from mqwheel.app_identity import config_dir
    from mqwheel.views.about_page import config_dir_str

    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert config_dir() == tmp_path / "MiaoQiWheel"
    assert SettingsStore().path.parent == config_dir()
    assert config_dir_str() == str(config_dir())


def test_config_dir_falls_back_when_appdata_missing_or_empty(monkeypatch) -> None:
    """APPDATA 缺失**或为空串**时都要走兜底，且结果必须是绝对路径。

    实测 Windows 上 ``%APPDATA%`` 在 Git Bash / 精简环境里会**整批缺失**
    （和 ``%ProgramFiles%`` 一样），此时应用写的是 ``~\\.miaoqiwheel\\``。
    """
    from mqwheel.app_identity import config_dir

    monkeypatch.delenv("APPDATA", raising=False)
    assert config_dir() == Path.home() / ".miaoqiwheel"

    monkeypatch.setenv("APPDATA", "")
    assert config_dir().is_absolute(), "空串必须走兜底，否则会得到相对路径"
    assert config_dir() == Path.home() / ".miaoqiwheel"


# endregion
