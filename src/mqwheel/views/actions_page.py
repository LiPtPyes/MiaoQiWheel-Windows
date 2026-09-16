"""轮盘选项页：左侧预览 + 列表（可拖拽排序），右侧详情编辑器。"""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from mqwheel.models.action import WheelAction, WheelActionKind
from mqwheel.models.geometry import WheelGeometry
from mqwheel.models.layout import MAX_ITEM_COUNT, MIN_ITEM_COUNT, WheelPresentationLayout
from mqwheel.models.presets import ScriptPreset
from mqwheel.models.settings import WheelSettings
from mqwheel.services.symbol_icons import symbol_icon
from mqwheel.views.action_editor import ActionEditor
from mqwheel.views.common import PageWidget, hint_label
from mqwheel.views.overlay import WheelFaceWidget

DROP_SUFFIXES = (".exe", ".lnk", ".msc", ".bat", ".cmd", ".ps1")


class ActionListWidget(QtWidgets.QListWidget):
    """支持内部拖拽排序，也接受从资源管理器拖入可执行文件。"""

    order_changed = QtCore.Signal(list)  # 新的 id 顺序
    files_dropped = QtCore.Signal(list)  # 本地路径列表

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setDropIndicatorShown(True)
        self.setAcceptDrops(True)
        self.setIconSize(QtCore.QSize(22, 22))
        self.setSpacing(1)
        self.setUniformItemSizes(False)

    def ids(self) -> list[str]:
        return [self.item(row).data(QtCore.Qt.ItemDataRole.UserRole) for row in range(self.count())]

    def dropEvent(self, event: QtGui.QDropEvent) -> None:  # noqa: N802
        if event.source() is self:
            super().dropEvent(event)
            self.order_changed.emit(self.ids())
            return
        paths = [url.toLocalFile() for url in event.mimeData().urls()]
        paths = [p for p in paths if p]
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:  # noqa: N802
        if event.source() is not self and event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:  # noqa: N802
        if event.source() is not self and event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)


class WheelPreviewWidget(WheelFaceWidget):
    """预览用的轮盘：悬停高亮、点击选中。"""

    sector_clicked = QtCore.Signal(int)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(240, 240)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding
        )
        self._current: int | None = None
        self._hover: int | None = None

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(360, 360)

    def set_current_index(self, index: int | None) -> None:
        self._current = index
        self._apply()

    def _apply(self) -> None:
        super().set_selected_index(
            self._hover if self._hover is not None else self._current
        )

    def _index_at(self, pos: QtCore.QPointF) -> int | None:
        if not self._actions:
            return None
        side = min(self.width(), self.height())
        if side <= 0:
            return None
        geometry = WheelGeometry(len(self._actions))
        index = geometry.selection_index(
            (pos.x(), pos.y()),
            (self.width() / 2.0, self.height() / 2.0),
            WheelPresentationLayout.dead_zone_for(side),
        )
        if index is None or not 0 <= index < len(self._actions):
            return None
        return index

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        self._hover = self._index_at(event.position())
        self._apply()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        index = self._index_at(event.position())
        if index is not None:
            self.sector_clicked.emit(index)
        super().mousePressEvent(event)

    def leaveEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        self._hover = None
        self._apply()
        super().leaveEvent(event)


class ActionsPage(PageWidget):
    """设置窗口的「轮盘选项」页。所有改动都会发出 settings_changed。"""

    settings_changed = QtCore.Signal()

    def __init__(self, settings: WheelSettings, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._loading = False
        self._build()
        self.reload()

    # region 构建
    def _build(self) -> None:
        self.set_header(
            "轮盘选项", "拖动列表可调整顺序；点击轮盘扇区或列表项进行编辑。最多 12 项。"
        )

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)

        left = QtWidgets.QWidget(splitter)
        left_layout = QtWidgets.QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        self._preview = WheelPreviewWidget(left)
        left_layout.addWidget(self._preview, 3)

        toolbar = QtWidgets.QWidget(left)
        tools = QtWidgets.QHBoxLayout(toolbar)
        tools.setContentsMargins(0, 0, 0, 0)
        tools.setSpacing(6)
        self._add_button = QtWidgets.QPushButton("添加")
        self._remove_button = QtWidgets.QPushButton("删除")
        self._up_button = QtWidgets.QToolButton()
        self._up_button.setText("↑")
        self._down_button = QtWidgets.QToolButton()
        self._down_button.setText("↓")
        self._count_label = QtWidgets.QLabel("")
        self._count_label.setStyleSheet("color: #9AA3B0;")
        tools.addWidget(self._add_button)
        tools.addWidget(self._remove_button)
        tools.addWidget(self._up_button)
        tools.addWidget(self._down_button)
        tools.addStretch(1)
        tools.addWidget(self._count_label)
        left_layout.addWidget(toolbar, 0)

        self._list = ActionListWidget(left)
        left_layout.addWidget(self._list, 2)

        right = QtWidgets.QWidget(splitter)
        right_layout = QtWidgets.QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self._stack = QtWidgets.QStackedWidget(right)
        self._stack.addWidget(self._build_placeholder())
        self._editor = ActionEditor()
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setWidget(self._editor)
        self._stack.addWidget(scroll)
        right_layout.addWidget(self._stack, 1)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        self.root.addWidget(splitter, 1)
        self._splitter = splitter

        self._add_button.clicked.connect(self._add)
        self._remove_button.clicked.connect(self._remove)
        self._up_button.clicked.connect(lambda: self._move(-1))
        self._down_button.clicked.connect(lambda: self._move(1))
        self._list.currentRowChanged.connect(self._on_row_changed)
        self._list.order_changed.connect(self._on_order_changed)
        self._list.files_dropped.connect(self._on_files_dropped)
        self._preview.sector_clicked.connect(self._select_index)
        self._editor.action_changed.connect(self._on_edited)

        self._restore_splitter()

    def _build_placeholder(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.addStretch(1)
        label = QtWidgets.QLabel("选择一个轮盘选项")
        label.setStyleSheet("font-size: 15px; font-weight: 600;")
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(label)
        layout.addWidget(hint_label("在左侧列表或轮盘中点选一项，即可编辑名称、图标与动作。"))
        layout.addStretch(1)
        return page
    # endregion

    # region 刷新
    def set_settings(self, settings: WheelSettings) -> None:
        self._settings = settings

    def reload(self) -> None:
        self._loading = True
        current = self._current_id()
        self._list.clear()
        for action in self._settings.actions:
            icon = symbol_icon(action.symbol, "#E4E8EE")
            item = QtWidgets.QListWidgetItem(icon or QtGui.QIcon(), action.title)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, action.id)
            item.setToolTip(f"{action.kind.title}：{action.payload or '—'}")
            self._list.addItem(item)

        self._preview.set_actions(self._settings.actions)
        self._preview.set_current_index(None)

        row = next(
            (i for i, a in enumerate(self._settings.actions) if a.id == current),
            0 if self._settings.actions else -1,
        )
        self._loading = False
        self._list.setCurrentRow(row)
        self._sync_editor()

    def _sync_editor(self) -> None:
        index = self._list.currentRow()
        count = len(self._settings.actions)
        self._remove_button.setEnabled(count > MIN_ITEM_COUNT)
        self._up_button.setEnabled(0 < index < count)
        self._down_button.setEnabled(0 <= index < count - 1)
        self._add_button.setEnabled(count < MAX_ITEM_COUNT)
        self._count_label.setText(f"{count} / {MAX_ITEM_COUNT}")

        self._preview.set_current_index(index if 0 <= index < count else None)
        if 0 <= index < count:
            self._editor.set_action(self._settings.actions[index])
            self._stack.setCurrentIndex(1)
        else:
            self._editor.set_action(None)
            self._stack.setCurrentIndex(0)

    def _current_id(self) -> str | None:
        index = self._list.currentRow()
        if 0 <= index < len(self._settings.actions):
            return self._settings.actions[index].id
        return None
    # endregion

    # region 操作
    def _on_row_changed(self, row: int) -> None:
        if self._loading:
            return
        self._sync_editor()

    def _select_index(self, index: int) -> None:
        self._list.setCurrentRow(index)

    def _on_edited(self, action: WheelAction) -> None:
        row = self._list.currentRow()
        if not 0 <= row < len(self._settings.actions):
            return
        self._settings.actions[row] = action
        item = self._list.item(row)
        if item is not None:
            icon = symbol_icon(action.symbol, "#E4E8EE")
            if icon is not None:
                item.setIcon(icon)
            item.setText(action.title)
            item.setToolTip(f"{action.kind.title}：{action.payload or '—'}")
        self._preview.set_actions(self._settings.actions)
        self._preview.set_current_index(row)
        self.settings_changed.emit()

    def _add(self) -> None:
        if len(self._settings.actions) >= MAX_ITEM_COUNT:
            return
        self._settings.actions.append(
            WheelAction(
                title=f"新选项 {len(self._settings.actions) + 1}",
                subtitle="未设置动作",
                symbol="fa6s.circle",
                kind=WheelActionKind.APPLICATION,
                payload="",
                preset_id=ScriptPreset.CUSTOM_ID,
            )
        )
        self.reload()
        self._list.setCurrentRow(len(self._settings.actions) - 1)
        self.settings_changed.emit()

    def _remove(self) -> None:
        index = self._list.currentRow()
        if not 0 <= index < len(self._settings.actions):
            return
        if len(self._settings.actions) <= MIN_ITEM_COUNT:
            return
        self._settings.actions.pop(index)
        self.reload()
        self.settings_changed.emit()

    def _move(self, delta: int) -> None:
        index = self._list.currentRow()
        actions = self._settings.actions
        if not 0 <= index < len(actions):
            return
        target = index + delta
        if not 0 <= target < len(actions):
            return
        actions[index], actions[target] = actions[target], actions[index]
        self.reload()
        self._list.setCurrentRow(target)
        self.settings_changed.emit()

    def _on_order_changed(self, ids: list[str]) -> None:
        by_id_map = {a.id: a for a in self._settings.actions}
        reordered = [by_id_map[i] for i in ids if i in by_id_map]
        if len(reordered) != len(self._settings.actions):
            return
        self._settings.actions = reordered
        self.reload()
        self.settings_changed.emit()

    def _on_files_dropped(self, paths: list[str]) -> None:
        added = False
        for path in paths:
            if len(self._settings.actions) >= MAX_ITEM_COUNT:
                break
            if Path(path).suffix.lower() not in DROP_SUFFIXES:
                continue
            self._settings.actions.append(
                WheelAction(
                    title=Path(path).stem or "应用",
                    subtitle=Path(path).name,
                    symbol="fa6s.window-maximize",
                    kind=WheelActionKind.APPLICATION,
                    payload=path,
                )
            )
            added = True
        if not added:
            return
        self.reload()
        self._list.setCurrentRow(len(self._settings.actions) - 1)
        self.settings_changed.emit()
    # endregion

    # region 分栏比例
    def _restore_splitter(self) -> None:
        settings = QtCore.QSettings()
        state = settings.value("settingsWindow/actionsSplitter")
        if isinstance(state, QtCore.QByteArray):
            self._splitter.restoreState(state)

    def save_state(self) -> None:
        settings = QtCore.QSettings()
        settings.setValue("settingsWindow/actionsSplitter", self._splitter.saveState())
    # endregion


__all__ = ["ActionListWidget", "ActionsPage", "WheelPreviewWidget"]
