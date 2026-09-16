"""单个轮盘选项的编辑器。

职责：把 WheelAction 拆成表单，编辑后原样回写并发出 action_changed。
预设相关逻辑在这里收敛：选预设 → 生成参数控件 → 参数变化重算 payload。
"""

from __future__ import annotations

import contextlib
from functools import partial
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from mqwheel.models.action import WheelAction, WheelActionKind
from mqwheel.models.presets import (
    BUILTIN_PREFIX,
    KIND_INTEGER,
    KIND_PATH,
    PresetParameter,
    ScriptPreset,
    by_category,
    by_id,
    matching,
    selection_id,
)
from mqwheel.services.app_icons import pixmap_for
from mqwheel.views.common import SectionCard, hint_label
from mqwheel.views.symbol_picker import SymbolButton

KIND_ORDER = (
    WheelActionKind.APPLICATION,
    WheelActionKind.WINDOW_TOGGLE,
    WheelActionKind.URL,
    WheelActionKind.KEYBOARD_SHORTCUT,
    WheelActionKind.SHELL_COMMAND,
    WheelActionKind.BUILTIN,
)

PRESET_KINDS = (
    WheelActionKind.KEYBOARD_SHORTCUT,
    WheelActionKind.SHELL_COMMAND,
    WheelActionKind.BUILTIN,
)

# 需要填可执行文件路径的类型。两个页面共用同一个控件类，见 _AppPathRow。
PATH_KINDS = (
    WheelActionKind.APPLICATION,
    WheelActionKind.WINDOW_TOGGLE,
)


class _AppPathRow(QtWidgets.QWidget):
    """可执行文件路径行：图标 + 输入框 + 浏览按钮。

    「应用」与「窗口切换」填的是同一种东西，所以抽成可复用控件，
    而不是把同一段布局写两遍（一个 QWidget 也不能同时挂在两个堆叠页上）。
    """

    changed = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._icon = QtWidgets.QLabel()
        self._icon.setFixedSize(24, 24)
        self._icon.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self._path = QtWidgets.QLineEdit()
        self._path.setPlaceholderText(r"例如 C:\Windows\System32\notepad.exe")

        browse = QtWidgets.QToolButton()
        browse.setText("…")

        layout.addWidget(self._icon, 0)
        layout.addWidget(self._path, 1)
        layout.addWidget(browse, 0)

        self._path.textChanged.connect(self._on_text_changed)
        browse.clicked.connect(self._browse)

    def path(self) -> str:
        return self._path.text().strip()

    def set_path(self, value: str) -> None:
        self._path.setText(value)

    def _on_text_changed(self) -> None:
        self._icon.setPixmap(pixmap_for(self.path(), 24))
        self.changed.emit()

    def _browse(self) -> None:
        start = self.path()
        directory = str(Path(start).parent) if start else ""
        chosen, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "选择应用", directory, "可执行文件 (*.exe *.lnk);;所有文件 (*.*)"
        )
        if chosen:
            self._path.setText(chosen)


class ActionEditor(QtWidgets.QWidget):
    """右侧详情编辑器；没有选中项时整体隐藏，由调用方显示占位。"""

    action_changed = QtCore.Signal(object)  # WheelAction

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._action: WheelAction | None = None
        self._loading = 0
        self._param_values: dict[str, str] = {}
        self._param_widgets: dict[str, QtWidgets.QWidget] = {}
        self._build()

    # region 构建
    def _build(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        basic = SectionCard("基本信息", self)
        self._title = QtWidgets.QLineEdit()
        self._title.setPlaceholderText("显示在轮盘上的名称")
        basic.add_row("名称", self._title)

        self._subtitle = QtWidgets.QLineEdit()
        self._subtitle.setPlaceholderText("可选，显示在中心区")
        basic.add_row("副标题", self._subtitle)

        self._symbol = SymbolButton()
        basic.add_row("图标", self._symbol)
        layout.addWidget(basic)

        action_card = SectionCard("动作", self)
        form = action_card.form

        self._kind = QtWidgets.QComboBox()
        for kind in KIND_ORDER:
            self._kind.addItem(kind.title, kind.value)
        action_card.add_row("类型", self._kind)

        self._preset = QtWidgets.QComboBox()
        self._preset.setMinimumWidth(200)
        self._preset_label = QtWidgets.QLabel("预设")
        action_card.add_row(self._preset_label, self._preset)

        self._params_box = QtWidgets.QWidget()
        self._params_form = QtWidgets.QFormLayout(self._params_box)
        self._params_form.setContentsMargins(0, 4, 0, 4)
        self._params_form.setLabelAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        action_card.add_full(self._params_box)

        self._stack = QtWidgets.QStackedWidget()
        # 页面顺序必须与 KIND_ORDER 一致，_sync_stack 直接用下标切换
        self._app_row = _AppPathRow()
        self._toggle_row = _AppPathRow()
        self._stack.addWidget(self._app_row)
        self._stack.addWidget(self._toggle_row)
        self._stack.addWidget(self._build_url_page())
        self._stack.addWidget(self._build_shortcut_page())
        self._stack.addWidget(self._build_command_page())
        self._stack.addWidget(self._build_builtin_page())
        action_card.add_full(self._stack)

        self._hint = hint_label("")
        action_card.add_full(self._hint)

        layout.addWidget(action_card, 1)

        self._title.textChanged.connect(self._emit)
        self._subtitle.textChanged.connect(self._emit)
        self._symbol.symbol_changed.connect(self._emit)
        self._app_row.changed.connect(self._emit)
        self._toggle_row.changed.connect(self._emit)
        self._kind.currentIndexChanged.connect(self._on_kind_changed)
        self._preset.currentIndexChanged.connect(self._on_preset_changed)

    def _path_row(self, kind: WheelActionKind) -> _AppPathRow:
        return self._toggle_row if kind == WheelActionKind.WINDOW_TOGGLE else self._app_row

    def _build_url_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self._url_edit = QtWidgets.QLineEdit()
        self._url_edit.setPlaceholderText("https://… 或 ms-settings: 等协议链接")
        self._url_edit.textChanged.connect(self._emit)
        layout.addWidget(self._url_edit)
        return page

    def _build_shortcut_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._shortcut_edit = QtWidgets.QLineEdit()
        self._shortcut_edit.setPlaceholderText("win+shift+s")
        self._shortcut_edit.textChanged.connect(self._on_command_edited)
        layout.addWidget(self._shortcut_edit)
        layout.addWidget(hint_label("可用修饰键：win、ctrl、alt、shift，用 + 连接，如 ctrl+alt+t"))
        return page

    def _build_command_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self._command_edit = QtWidgets.QPlainTextEdit()
        self._command_edit.setPlaceholderText("要执行的命令，例如 shutdown.exe /s /t 0")
        self._command_edit.setFixedHeight(84)
        self._command_edit.textChanged.connect(self._on_command_edited)
        layout.addWidget(self._command_edit)
        return page

    def _build_builtin_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self._builtin_label = hint_label("由程序直接调用系统接口，无需命令。")
        layout.addWidget(self._builtin_label)
        return page
    # endregion

    # region 载入
    def set_action(self, action: WheelAction | None) -> None:
        self._action = action
        if action is None:
            self.setEnabled(False)
            return
        self.setEnabled(True)
        with self._quiet():
            self._title.setText(action.title)
            self._subtitle.setText(action.subtitle)
            self._symbol.set_symbol(action.symbol)
            for kind in PATH_KINDS:
                self._path_row(kind).set_path(action.payload if action.kind == kind else "")
            self._url_edit.setText(action.payload if action.kind == WheelActionKind.URL else "")
            self._shortcut_edit.setText(
                action.payload if action.kind == WheelActionKind.KEYBOARD_SHORTCUT else ""
            )
            self._command_edit.setPlainText(
                action.payload if action.kind == WheelActionKind.SHELL_COMMAND else ""
            )
            self._sync_kind_combo(action)
            self._reload_presets(action)
            self._sync_stack(action)

    def _sync_kind_combo(self, action: WheelAction) -> None:
        index = self._kind.findData(action.kind.value)
        self._kind.setCurrentIndex(max(index, 0))

    def _reload_presets(self, action: WheelAction) -> None:
        """按当前类型重建预设下拉，并选中匹配项。"""
        self._preset.clear()
        self._preset.addItem("自定义", ScriptPreset.CUSTOM_ID)
        for category, presets in by_category().items():
            if not presets:
                continue
            # 用禁用的占位项充当分组标题
            header_index = self._preset.count()
            self._preset.addItem(f"— {category} —")
            self._preset.model().item(header_index).setEnabled(False)
            for preset in presets:
                self._preset.addItem(f"{preset.title}（{preset.subtitle}）", preset.id)

        target = selection_id(action)
        index = self._preset.findData(target)
        if index < 0:
            index = 0
        self._preset.setCurrentIndex(index)
        self._rebuild_params(action)

    def _rebuild_params(self, action: WheelAction) -> None:
        while self._params_form.rowCount():
            self._params_form.removeRow(0)

        self._param_widgets = {}
        preset = by_id(self._preset.currentData())
        if preset is None or not preset.parameters:
            self._params_box.setVisible(False)
            self._param_values = {}
            return

        values = dict(preset.default_parameters)
        if action.preset_params:
            values.update(action.preset_params)
        values = {p.id: p.sanitized(values.get(p.id, p.default)) for p in preset.parameters}
        self._param_values = values

        for parameter in preset.parameters:
            label, field, editor = self._make_param_field(parameter, values[parameter.id])
            self._param_widgets[parameter.id] = editor
            self._params_form.addRow(label, field)
        self._params_box.setVisible(True)

    def _make_param_field(self, parameter: PresetParameter, value: str):
        """返回 (标签, 放入表单的控件, 实际取值控件)。

        三者分开是因为复合控件（路径行）里真正存值的是内层的 QLineEdit；
        而 QSpinBox 自身就内含一个 QLineEdit，靠 findChildren 去找会取错。
        """
        if parameter.kind == KIND_INTEGER:
            spin = QtWidgets.QSpinBox()
            spin.setRange(parameter.minimum, parameter.maximum)
            spin.setValue(int(value) if value.isdigit() else parameter.minimum)
            spin.valueChanged.connect(partial(self._on_param_changed, parameter.id))
            return QtWidgets.QLabel(parameter.title), spin, spin

        if parameter.kind == KIND_PATH:
            row = QtWidgets.QWidget()
            layout = QtWidgets.QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(6)
            line = QtWidgets.QLineEdit(value)
            line.setPlaceholderText(parameter.placeholder)
            browse = QtWidgets.QToolButton()
            browse.setText("…")
            layout.addWidget(line, 1)
            layout.addWidget(browse, 0)
            line.textChanged.connect(partial(self._on_param_changed, parameter.id))
            browse.clicked.connect(partial(self._browse_path, line))
            return QtWidgets.QLabel(parameter.title), row, line

        edit = QtWidgets.QPlainTextEdit()
        edit.setPlainText(value)
        edit.setPlaceholderText(parameter.placeholder)
        edit.setFixedHeight(60)
        edit.textChanged.connect(lambda: self._on_param_changed(parameter.id))
        return QtWidgets.QLabel(parameter.title), edit, edit

    def _sync_stack(self, action: WheelAction) -> None:
        index = KIND_ORDER.index(action.kind) if action.kind in KIND_ORDER else 0
        self._stack.setCurrentIndex(index)
        self._stack.setVisible(action.kind != WheelActionKind.BUILTIN)
        self._preset.setVisible(action.kind in PRESET_KINDS)
        self._preset_label.setVisible(action.kind in PRESET_KINDS)
        self._hint.setText(self._hint_for(action))
        self._hint.setVisible(bool(self._hint.text()))

    @staticmethod
    def _hint_for(action: WheelAction) -> str:
        if action.kind == WheelActionKind.BUILTIN:
            return "内置操作由程序直接调用 Windows 接口，不经过命令行。"
        if action.kind == WheelActionKind.WINDOW_TOGGLE:
            return (
                "已打开就把它还原并最大化到最前；它已经在前台就最小化；"
                "真没打开才新建窗口。适合浏览器这类不想开第二个窗口的应用。"
            )
        if action.kind == WheelActionKind.SHELL_COMMAND:
            return "命令会交给系统执行；参数按 cmd 规则加引号。"
        if action.kind == WheelActionKind.KEYBOARD_SHORTCUT:
            return "模拟按键组合，适合系统自带快捷键。"
        return ""
    # endregion

    # region 编辑响应
    @contextlib.contextmanager
    def _quiet(self):
        self._loading += 1
        try:
            yield
        finally:
            self._loading -= 1

    def _emit(self) -> None:
        if self._loading or self._action is None:
            return
        self.action_changed.emit(self.collect())

    def collect(self) -> WheelAction:
        """把表单内容写回当前 action 并返回。"""
        action = self._action
        assert action is not None
        action.title = self._title.text().strip() or "未命名"
        action.subtitle = self._subtitle.text().strip()
        action.symbol = self._symbol.symbol()
        action.kind = WheelActionKind(self._kind.currentData())

        if action.kind == WheelActionKind.APPLICATION:
            action.payload = self._app_row.path()
        elif action.kind == WheelActionKind.WINDOW_TOGGLE:
            action.payload = self._toggle_row.path()
        elif action.kind == WheelActionKind.URL:
            action.payload = self._url_edit.text().strip()
        elif action.kind == WheelActionKind.KEYBOARD_SHORTCUT:
            action.payload = self._shortcut_edit.text().strip()
        elif action.kind == WheelActionKind.SHELL_COMMAND:
            action.payload = self._command_edit.toPlainText().strip()
        return action

    def _on_kind_changed(self) -> None:
        if self._loading or self._action is None:
            return
        previous = self._action.kind
        target = WheelActionKind(self._kind.currentData())
        self._action.kind = target
        with self._quiet():
            # 「应用」与「窗口切换」填的是同一个可执行文件路径。来回切时把它带过去，
            # 否则用户只是想改个触发方式，却要重新浏览一次文件。
            if previous != target and previous in PATH_KINDS and target in PATH_KINDS:
                self._path_row(target).set_path(self._path_row(previous).path())
            self._reload_presets(self._action)
            self._sync_stack(self._action)
        self._emit()

    def _on_preset_changed(self) -> None:
        if self._loading or self._action is None:
            return
        preset_id = self._preset.currentData()
        if preset_id is None or preset_id == ScriptPreset.CUSTOM_ID:
            self._action.preset_id = ScriptPreset.CUSTOM_ID
            self._action.preset_params = None
            with self._quiet():
                self._rebuild_params(self._action)
            self._emit()
            return

        preset = by_id(preset_id)
        if preset is None:
            return

        action = self._action
        had_preset = action.preset_id is not None and action.preset_id != ScriptPreset.CUSTOM_ID
        values = {p.id: p.sanitized(self._param_values.get(p.id, p.default)) for p in preset.parameters}

        action.kind = WheelActionKind(preset.kind)
        action.preset_id = preset.id
        action.preset_params = values
        action.payload = (
            BUILTIN_PREFIX + preset.id
            if action.kind == WheelActionKind.BUILTIN
            else preset.command(values)
        )
        if not action.title or had_preset:
            action.title = preset.title
            action.subtitle = preset.subtitle
            action.symbol = preset.symbol

        with self._quiet():
            self._title.setText(action.title)
            self._subtitle.setText(action.subtitle)
            self._symbol.set_symbol(action.symbol)
            self._sync_kind_combo(action)
            self._sync_stack(action)
            self._rebuild_params(action)
            self._write_payload(action)
        self._emit()

    def _on_param_changed(self, parameter_id: str, *_args) -> None:
        """参数控件回调；SpinBox 会额外带上数值，用 *_args 吞掉。"""
        if self._loading or self._action is None:
            return
        preset = by_id(self._preset.currentData())
        if preset is None:
            return
        widget = self._param_widgets.get(parameter_id)
        if widget is None:
            return

        if isinstance(widget, QtWidgets.QSpinBox):
            self._param_values[parameter_id] = str(widget.value())
        elif isinstance(widget, QtWidgets.QPlainTextEdit):
            self._param_values[parameter_id] = widget.toPlainText()
        else:
            self._param_values[parameter_id] = widget.text()

        values = {
            p.id: p.sanitized(self._param_values.get(p.id, p.default)) for p in preset.parameters
        }
        action = self._action
        action.preset_id = preset.id
        action.preset_params = values
        if action.kind != WheelActionKind.BUILTIN:
            action.payload = preset.command(values)
            with self._quiet():
                self._write_payload(action)
        self._emit()

    def _write_payload(self, action: WheelAction) -> None:
        """把 payload 同步到对应的输入框（不触发回环）。"""
        if action.kind == WheelActionKind.SHELL_COMMAND:
            if self._command_edit.toPlainText() != action.payload:
                self._command_edit.setPlainText(action.payload)
        elif action.kind == WheelActionKind.KEYBOARD_SHORTCUT:
            if self._shortcut_edit.text() != action.payload:
                self._shortcut_edit.setText(action.payload)

    def _on_command_edited(self) -> None:
        if self._loading or self._action is None:
            return
        action = self.collect()
        preset = matching(action.payload)
        if preset is not None and preset.id != self._preset.currentData():
            action.preset_id = preset.id
            action.preset_params = preset.parameter_values(action.payload) or {}
            index = self._preset.findData(preset.id)
            if index >= 0:
                with self._quiet():
                    self._preset.setCurrentIndex(index)
                    self._rebuild_params(action)
        elif preset is None:
            action.preset_id = ScriptPreset.CUSTOM_ID
            action.preset_params = None
        if not self._loading:
            self._emit()

    @staticmethod
    def _browse_path(line: QtWidgets.QLineEdit) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(line, "选择文件夹", line.text())
        if not path:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(line, "选择文件", line.text())
        if path:
            line.setText(path)
    # endregion


__all__ = ["ActionEditor", "KIND_ORDER", "PATH_KINDS", "PRESET_KINDS"]
