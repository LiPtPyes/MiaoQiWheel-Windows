"""热键录入控件：点击后捕获下一次按键。"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from mqwheel.models.settings import name_from_vk
from mqwheel.views.common import SectionCard, hint_label, slider_row

_PUNCTUATION = {
    QtCore.Qt.Key.Key_QuoteLeft: 0xC0,  # `
    QtCore.Qt.Key.Key_Minus: 0xBD,
    QtCore.Qt.Key.Key_Equal: 0xBB,
    QtCore.Qt.Key.Key_BracketLeft: 0xDB,
    QtCore.Qt.Key.Key_BracketRight: 0xDD,
    QtCore.Qt.Key.Key_Backslash: 0xDC,
    QtCore.Qt.Key.Key_Semicolon: 0xBA,
    QtCore.Qt.Key.Key_Apostrophe: 0xDE,
    QtCore.Qt.Key.Key_Comma: 0xBC,
    QtCore.Qt.Key.Key_Period: 0xBE,
    QtCore.Qt.Key.Key_Slash: 0xBF,
    QtCore.Qt.Key.Key_Tab: 0x09,
    QtCore.Qt.Key.Key_Backspace: 0x08,
    QtCore.Qt.Key.Key_Return: 0x0D,
    QtCore.Qt.Key.Key_Enter: 0x0D,
    QtCore.Qt.Key.Key_Escape: 0x1B,
    QtCore.Qt.Key.Key_CapsLock: 0x14,
    QtCore.Qt.Key.Key_Delete: 0x2E,
    QtCore.Qt.Key.Key_Insert: 0x2D,
    QtCore.Qt.Key.Key_Home: 0x24,
    QtCore.Qt.Key.Key_End: 0x23,
    QtCore.Qt.Key.Key_PageUp: 0x21,
    QtCore.Qt.Key.Key_PageDown: 0x22,
    QtCore.Qt.Key.Key_Left: 0x25,
    QtCore.Qt.Key.Key_Up: 0x26,
    QtCore.Qt.Key.Key_Right: 0x27,
    QtCore.Qt.Key.Key_Down: 0x28,
    QtCore.Qt.Key.Key_Print: 0x2C,
}
for _i in range(1, 13):
    _PUNCTUATION[getattr(QtCore.Qt.Key, f"Key_F{_i}")] = 0x6F + _i

_MODIFIER_KEYS = (
    QtCore.Qt.Key.Key_Shift,
    QtCore.Qt.Key.Key_Control,
    QtCore.Qt.Key.Key_Alt,
    QtCore.Qt.Key.Key_Meta,
)


def vk_from_qt_key(key: int) -> int:
    """Qt 键码 → 虚拟键码；无法映射返回 0。

    字母、数字与空格的 Qt 键码恰好等于虚拟键码，其余走查表。
    """
    if 0x30 <= key <= 0x39 or 0x41 <= key <= 0x5A or key == 0x20:
        return key
    return _PUNCTUATION.get(key, 0)


_LABELS = {
    "tab": "Tab",
    "space": "空格",
    "capslock": "CapsLock",
    "escape": "Esc",
    "enter": "Enter",
    "backspace": "Backspace",
    "delete": "Delete",
    "insert": "Insert",
    "backquote": "`",
    "backslash": "\\",
    "comma": ",",
    "period": ".",
    "slash": "/",
    "semicolon": ";",
    "minus": "-",
    "equal": "=",
    "lbracket": "[",
    "rbracket": "]",
    "quote": "'",
    "up": "↑",
    "down": "↓",
    "left": "←",
    "right": "→",
    "home": "Home",
    "end": "End",
    "pageup": "PageUp",
    "pagedown": "PageDown",
    "printscreen": "PrintScreen",
}


def key_display(name: str) -> str:
    return _LABELS.get(name, name.upper())


class HotKeyCaptureButton(QtWidgets.QPushButton):
    """点一下进入录制态，下一次有效按键成为新的热键。"""

    key_changed = QtCore.Signal(str)

    def __init__(self, key: str = "tab", parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setMinimumWidth(120)
        self._key = key
        self.toggled.connect(self._on_toggled)
        self._refresh()

    def key_name(self) -> str:
        return self._key

    def set_key_name(self, name: str) -> None:
        if name == self._key:
            return
        self._key = name
        self._refresh()

    # region 内部
    def _refresh(self) -> None:
        self.setText("请按下按键…" if self.isChecked() else key_display(self._key))

    def _on_toggled(self, checked: bool) -> None:
        self._refresh()
        if checked:
            self.setFocus()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        if not self.isChecked():
            super().keyPressEvent(event)
            return
        key = event.key()
        if key in _MODIFIER_KEYS:
            event.accept()
            return
        vk = vk_from_qt_key(key)
        if vk == 0:
            event.accept()
            return
        name = name_from_vk(vk)
        self.setChecked(False)
        if name != self._key:
            self._key = name
            self.key_changed.emit(name)
        self._refresh()
        event.accept()

    def focusOutEvent(self, event: QtGui.QFocusEvent) -> None:  # noqa: N802
        if self.isChecked():
            self.setChecked(False)
        super().focusOutEvent(event)
    # endregion


class HotKeyEditor(QtWidgets.QWidget):
    """触发方式 + 主键 + 修饰键 + 阈值；任何改动都会发出 config_changed。"""

    config_changed = QtCore.Signal(object)  # HotKeyConfig

    def __init__(self, config, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._build()
        self._sync_visibility()

    # region 构建
    def _build(self) -> None:
        card = SectionCard("全局快捷键", self)
        form = card.form

        self._mode = QtWidgets.QComboBox()
        self._mode.addItem("长按（按住呼出，松开执行）", "hold")
        self._mode.addItem("双击（连按两次呼出）", "doubleTap")
        self._mode.addItem("组合键（按下即呼出）", "combo")
        self._mode.setCurrentIndex(max(self._mode.findData(self._config.mode), 0))
        card.add_row("触发方式", self._mode)

        self._key = HotKeyCaptureButton(self._config.key)
        card.add_row("主键", self._key)

        mods_box = QtWidgets.QWidget()
        mods_layout = QtWidgets.QHBoxLayout(mods_box)
        mods_layout.setContentsMargins(0, 0, 0, 0)
        mods_layout.setSpacing(12)
        self._mod_boxes: dict[str, QtWidgets.QCheckBox] = {}
        for token, label in (("ctrl", "Ctrl"), ("alt", "Alt"), ("shift", "Shift"), ("win", "Win")):
            box = QtWidgets.QCheckBox(label)
            box.setChecked(token in self._config.modifiers)
            self._mod_boxes[token] = box
            mods_layout.addWidget(box)
        mods_layout.addStretch(1)
        card.add_row("修饰键", mods_box)
        self._mods_label = form.labelForField(mods_box)
        self._mods_widget = mods_box

        self._hold_label, self._hold_row, self._hold_slider, self._hold_value = self._slider(
            "长按阈值", 80, 800, self._config.hold_ms, " ms"
        )
        card.add_row(self._hold_label, self._hold_row)
        card.add_full(
            hint_label("按住超过这个时长才呼出轮盘；短按会补发一次原按键，不影响正常输入。")
        )

        self._tap_label, self._tap_row, self._tap_slider, self._tap_value = self._slider(
            "双击间隔", 120, 600, self._config.double_tap_ms, " ms"
        )
        card.add_row(self._tap_label, self._tap_row)

        card.add_full(hint_label("提示：长按模式建议选 Tab、CapsLock 或 ` 这类左手单键。"))

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(card)

        self._mode.currentIndexChanged.connect(self._emit_changed)
        self._key.key_changed.connect(self._emit_changed)
        for box in self._mod_boxes.values():
            box.toggled.connect(self._emit_changed)
        self._hold_slider.valueChanged.connect(self._on_hold_changed)
        self._tap_slider.valueChanged.connect(self._on_tap_changed)

    @staticmethod
    def _slider(text: str, low: int, high: int, value: int, suffix: str):
        container, slider, value_label = slider_row(low, high, value, suffix, single_step=10)
        return QtWidgets.QLabel(text), container, slider, value_label
    # endregion

    # region 状态
    def config(self):
        return self._config

    def set_config(self, config) -> None:
        self._config = config
        self._mode.setCurrentIndex(max(self._mode.findData(config.mode), 0))
        self._key.set_key_name(config.key)
        for token, box in self._mod_boxes.items():
            box.setChecked(token in config.modifiers)
        self._hold_slider.setValue(config.hold_ms)
        self._tap_slider.setValue(config.double_tap_ms)
        self._sync_visibility()

    def _sync_visibility(self) -> None:
        mode = self._mode.currentData()
        self._mods_widget.setVisible(mode == "combo")
        if self._mods_label is not None:
            self._mods_label.setVisible(mode == "combo")
        for widgets, visible in (
            ((self._hold_label, self._hold_row), mode == "hold"),
            ((self._tap_label, self._tap_row), mode == "doubleTap"),
        ):
            for widget in widgets:
                widget.setVisible(visible)

    def _on_hold_changed(self, value: int) -> None:
        self._hold_value.setText(f"{value} ms")
        self._emit_changed()

    def _on_tap_changed(self, value: int) -> None:
        self._tap_value.setText(f"{value} ms")
        self._emit_changed()

    def _emit_changed(self) -> None:
        from mqwheel.models.settings import HotKeyConfig

        mode = self._mode.currentData() or "hold"
        modifiers = [token for token, box in self._mod_boxes.items() if box.isChecked()]
        self._config = HotKeyConfig(
            mode=mode,
            key=self._key.key_name(),
            modifiers=modifiers,
            hold_ms=self._hold_slider.value(),
            double_tap_ms=self._tap_slider.value(),
        )
        self._sync_visibility()
        self.config_changed.emit(self._config)
    # endregion


__all__ = ["HotKeyCaptureButton", "HotKeyEditor", "key_display", "vk_from_qt_key"]
