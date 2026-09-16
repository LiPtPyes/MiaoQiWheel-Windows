"""设置窗口：左侧分栏 + 右侧页面。

本模块由 main 在首次打开设置时导入，常驻时不占用内存。
页面改动统一通过 settings_changed 抛给 main，由 main 负责持久化与生效。
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from mqwheel.app_identity import APP_NAME, RESOURCES_DIR
from mqwheel.models.settings import WheelSettings
from mqwheel.services.symbol_icons import symbol_icon
from mqwheel.views.about_page import AboutPage
from mqwheel.views.actions_page import ActionsPage
from mqwheel.views.general_page import GeneralPage
from mqwheel.views.help_page import HelpPage

_PAGES = (
    ("通用", "fa6s.sliders"),
    ("轮盘选项", "fa6s.circle-dot"),
    ("帮助", "fa6s.circle-question"),
    ("关于", "fa6s.circle-info"),
)


class SettingsWindow(QtWidgets.QMainWindow):
    """macOS 版 SettingsView 的对应实现。"""

    settings_changed = QtCore.Signal(object)  # WheelSettings

    def __init__(self, settings: WheelSettings, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._loading = False
        self.setWindowTitle(APP_NAME)
        self._restore_geometry()
        self._build_ui()

    # region 构建
    def _build_ui(self) -> None:
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)

        self._sidebar = QtWidgets.QListWidget(splitter)
        self._sidebar.setFixedWidth(168)
        self._sidebar.setSpacing(2)
        self._sidebar.setIconSize(QtCore.QSize(18, 18))

        self._stack = QtWidgets.QStackedWidget(splitter)
        for index, (title, symbol) in enumerate(_PAGES):
            item = QtWidgets.QListWidgetItem(symbol_icon(symbol, "#C8D2DF") or QtGui.QIcon(), title)
            item.setSizeHint(QtCore.QSize(160, 34))
            item.setData(QtCore.Qt.ItemDataRole.UserRole, index)
            self._sidebar.addItem(item)

        self._general = GeneralPage(self._settings, self._stack)
        self._actions = ActionsPage(self._settings, self._stack)
        self._stack.addWidget(self._general)
        self._stack.addWidget(self._actions)
        self._stack.addWidget(HelpPage(self._stack))
        self._stack.addWidget(AboutPage(self._stack))

        self._sidebar.setCurrentRow(0)
        self._sidebar.currentRowChanged.connect(self._stack.setCurrentIndex)

        splitter.addWidget(self._sidebar)
        splitter.addWidget(self._stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([168, 640])
        self.setCentralWidget(splitter)
        self.resize(1020, 660)

        self._general.settings_changed.connect(self._on_changed)
        self._actions.settings_changed.connect(self._on_changed)

        icon_path = RESOURCES_DIR / "app.ico"
        if icon_path.exists():
            self.setWindowIcon(QtGui.QIcon(str(icon_path)))

    # endregion

    # region 对外
    @property
    def settings(self) -> WheelSettings:
        return self._settings

    def reload(self, settings: WheelSettings) -> None:
        """外部改动（如恢复默认）后同步所有页面。"""
        self._loading = True
        self._settings = settings
        self._general.reload(settings)
        self._actions.set_settings(settings)
        self._actions.reload()
        self._loading = False
    # endregion

    # region 事件
    def _on_changed(self) -> None:
        if self._loading:
            return
        if self.sender() is self._general:
            # 「恢复默认设置」等操作会整体替换选项列表，轮盘选项页需要跟着刷新
            self._actions.set_settings(self._settings)
            self._actions.reload()
        self.settings_changed.emit(self._settings)

    def _restore_geometry(self) -> None:
        settings = QtCore.QSettings()
        geometry = settings.value("settingsWindow/geometry")
        if isinstance(geometry, QtCore.QByteArray):
            self.restoreGeometry(geometry)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802
        settings = QtCore.QSettings()
        settings.setValue("settingsWindow/geometry", self.saveGeometry())
        self._actions.save_state()
        super().closeEvent(event)
    # endregion


__all__ = ["SettingsWindow"]
