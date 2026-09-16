"""热键录入控件与通用页的纯逻辑测试。"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from mqwheel.models.settings import HotKeyConfig
from mqwheel.views.hotkey_capture import HotKeyEditor, HotKeyCaptureButton, key_display, vk_from_qt_key


def test_vk_from_qt_key_letters_and_digits() -> None:
    assert vk_from_qt_key(ord("A")) == 0x41
    assert vk_from_qt_key(ord("0")) == 0x30
    assert vk_from_qt_key(QtCore.Qt.Key.Key_Space) == 0x20


def test_vk_from_qt_key_punctuation_uses_oem_codes() -> None:
    # ` 的 Qt 键码是 0x60，但虚拟键码是 0xC0，必须走查表
    assert vk_from_qt_key(QtCore.Qt.Key.Key_QuoteLeft) == 0xC0
    assert vk_from_qt_key(QtCore.Qt.Key.Key_Minus) == 0xBD
    assert vk_from_qt_key(QtCore.Qt.Key.Key_Tab) == 0x09
    assert vk_from_qt_key(QtCore.Qt.Key.Key_F5) == 0x74


def test_vk_from_qt_key_unsupported_returns_zero() -> None:
    assert vk_from_qt_key(QtCore.Qt.Key.Key_MediaPlay) == 0


def test_capture_button_updates_text(qapp) -> None:
    button = HotKeyCaptureButton("tab")
    assert button.text() == key_display("tab")
    button.set_key_name("capslock")
    assert button.text() == "CapsLock"


def test_editor_mode_switch_changes_config(qapp) -> None:
    editor = HotKeyEditor(HotKeyConfig())
    config = editor.config()
    assert config.mode == "hold"

    mode_box = editor.findChild(QtWidgets.QComboBox)
    mode_box.setCurrentIndex(mode_box.findData("combo"))

    assert editor.config().mode == "combo"
    assert editor.config().key == "tab"


def test_editor_threshold_clamped(qapp) -> None:
    editor = HotKeyEditor(HotKeyConfig(hold_ms=200))
    slider = editor.findChildren(QtWidgets.QSlider)[0]
    slider.setValue(5000)  # 超出滑块上限时应被夹在上限
    assert editor.config().hold_ms == slider.value()
