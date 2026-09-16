"""通用页：快捷键、轮盘外观、启动方式。"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from mqwheel.models.layout import WheelAppearance
from mqwheel.models.settings import WheelSettings
from mqwheel.services import autostart
from mqwheel.views.common import PageWidget, SectionCard, hint_label, slider_row
from mqwheel.views.hotkey_capture import HotKeyEditor


class GeneralPage(PageWidget):
    settings_changed = QtCore.Signal()

    def __init__(self, settings: WheelSettings, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._loading = False
        self._build()

    # region 构建
    def _build(self) -> None:
        self.set_header("通用", "调整呼出方式、轮盘大小与启动行为。")

        self._hotkey = HotKeyEditor(self._settings.hotkey, self)
        self._hotkey.config_changed.connect(self._on_hotkey_changed)
        self.add_card(self._hotkey)

        appearance_card = SectionCard("轮盘外观", self)
        self._labels = QtWidgets.QCheckBox("显示选项名称")
        self._labels.setChecked(self._settings.appearance.show_labels)
        appearance_card.add_row("选项名称", self._labels)

        container, slider, value_label = slider_row(
            int(WheelAppearance.SCALE_RANGE[0] * 100),
            int(WheelAppearance.SCALE_RANGE[1] * 100),
            int(self._settings.appearance.scale * 100),
            "%",
        )
        self._scale = slider
        self._scale_value = value_label
        self._scale.valueChanged.connect(self._on_scale_changed)
        appearance_card.add_row("轮盘大小", container)

        self._blur = QtWidgets.QCheckBox("毛玻璃背景")
        self._blur.setToolTip(
            "呼出时抓取盘面背后的屏幕内容并模糊，观感接近 macOS 的 Material。\n"
            "关闭后使用纯色半透明底盘，呼出更快、占用更低。"
        )
        self._blur.setChecked(self._settings.appearance.blur_background)
        appearance_card.add_row("背景效果", self._blur)

        self._animate = QtWidgets.QCheckBox("呼出与收起动画")
        self._animate.setToolTip("关闭后轮盘瞬间出现/消失，进一步压缩呼出延迟。")
        self._animate.setChecked(self._settings.appearance.animate)
        appearance_card.add_row("动画", self._animate)

        self.add_card(appearance_card)

        startup = SectionCard("启动", self)
        self._autostart = QtWidgets.QCheckBox("开机时自动启动")
        self._autostart.setToolTip("写入当前用户的注册表启动项，不需要管理员权限。")
        startup.add_row("开机自启", self._autostart)
        self._autostart_hint = hint_label("")
        startup.add_full(self._autostart_hint)
        self.add_card(startup)

        danger = QtWidgets.QWidget()
        danger_layout = QtWidgets.QHBoxLayout(danger)
        danger_layout.setContentsMargins(0, 0, 0, 0)
        self._reset = QtWidgets.QPushButton("恢复默认设置")
        self._reset.setProperty("danger", True)
        self._reset.setStyleSheet("QPushButton { color: #FF8A8A; }")
        danger_layout.addWidget(self._reset)
        danger_layout.addStretch(1)
        self.add_card(danger)

        self.finish()

        self._labels.toggled.connect(self._on_labels_changed)
        self._blur.toggled.connect(self._on_blur_changed)
        self._animate.toggled.connect(self._on_animate_changed)
        self._autostart.toggled.connect(self._on_autostart_changed)
        self._reset.clicked.connect(self._on_reset)

        self._refresh_autostart()

    # endregion

    # region 刷新
    def reload(self, settings: WheelSettings) -> None:
        self._settings = settings
        self._loading = True
        self._hotkey.set_config(settings.hotkey)
        self._labels.setChecked(settings.appearance.show_labels)
        self._blur.setChecked(settings.appearance.blur_background)
        self._animate.setChecked(settings.appearance.animate)
        self._scale.setValue(int(settings.appearance.scale * 100))
        self._scale_value.setText(f"{int(settings.appearance.scale * 100)}%")
        self._refresh_autostart()
        self._loading = False

    def _refresh_autostart(self) -> None:
        enabled = autostart.is_enabled()
        self._autostart.setChecked(enabled)
        self._settings.general.launch_at_login = enabled
        if enabled:
            self._autostart_hint.setText(f"当前启动命令：{autostart.command_line()}")
        else:
            self._autostart_hint.setText("关闭时不影响已运行的实例，下次开机不再自动启动。")
    # endregion

    # region 响应
    def _changed(self) -> None:
        if not self._loading:
            self.settings_changed.emit()

    def _on_hotkey_changed(self, config) -> None:
        self._settings.hotkey = config
        self._changed()

    def _on_scale_changed(self, value: int) -> None:
        self._scale_value.setText(f"{value}%")
        self._settings.appearance.scale = WheelAppearance.sanitized_scale(value / 100.0)
        self._changed()

    def _on_labels_changed(self, checked: bool) -> None:
        self._settings.appearance.show_labels = checked
        self._changed()

    def _on_blur_changed(self, checked: bool) -> None:
        self._settings.appearance.blur_background = checked
        self._changed()

    def _on_animate_changed(self, checked: bool) -> None:
        self._settings.appearance.animate = checked
        self._changed()

    def _on_autostart_changed(self, checked: bool) -> None:
        if self._loading:
            return
        ok = autostart.set_enabled(checked)
        if not ok:
            self._autostart.setChecked(not checked)
            QtWidgets.QMessageBox.warning(
                self, "无法修改开机自启", autostart.last_error or "写入注册表失败。"
            )
            return
        self._settings.general.launch_at_login = checked
        self._autostart_hint.setText(
            f"当前启动命令：{autostart.command_line()}" if checked else "已关闭开机自启。"
        )
        self._changed()

    def _on_reset(self) -> None:
        answer = QtWidgets.QMessageBox.question(
            self,
            "恢复默认设置",
            "将恢复默认快捷键、外观与轮盘选项，自定义内容会丢失。继续吗？",
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        fresh = WheelSettings()
        self._settings.hotkey = fresh.hotkey
        self._settings.appearance = fresh.appearance
        self._settings.actions = fresh.actions
        self.reload(self._settings)
        self.settings_changed.emit()
    # endregion


__all__ = ["GeneralPage"]
