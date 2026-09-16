"""图标选择：FontAwesome 6 常用符号网格，可搜索。

macOS 版让用户直接填 SF Symbol 名字，Windows 上没有等价的官方符号表，
所以改为从精选列表里挑——列表覆盖全部预设用到的图标 + 常用图标。
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from mqwheel.services.symbol_icons import symbol_icon

# 预设用到的符号排在前面，其余按常用度排列
CURATED: tuple[str, ...] = (
    # 预设
    "lock", "display", "images", "moon", "bed", "power-off", "arrows-rotate",
    "right-from-bracket", "circle-half-stroke", "volume-xmark", "volume-high",
    "camera", "border-all", "desktop", "terminal", "clipboard", "bell",
    "trash-can", "gear", "folder-open", "copy", "comment-dots", "globe",
    "file-lines",
    # 常用
    "circle", "circle-dot", "square", "star", "heart", "house", "house-chimney",
    "magnifying-glass", "plus", "minus", "xmark", "check", "play", "pause",
    "stop", "forward", "backward", "rotate-right", "rotate-left", "repeat",
    "shuffle", "expand", "compress", "maximize", "window-maximize",
    "window-minimize", "window-restore", "cube", "cubes", "box", "box-open",
    "gift", "tag", "tags", "cart-shopping", "credit-card", "money-bill",
    "wallet", "chart-line", "chart-simple", "briefcase", "building", "flask",
    "graduation-cap", "palette", "paintbrush", "pencil", "pen", "pen-to-square",
    "code", "laptop", "tv", "mobile-screen", "tablet-screen-button", "gamepad",
    "headphones", "keyboard", "computer-mouse", "print", "server", "database",
    "cloud", "wifi", "battery-full", "bolt", "plug", "satellite-dish",
    "sun", "cloud-sun", "droplet", "fire", "leaf", "bug", "rocket",
    "lightbulb", "wand-magic-sparkles", "hammer", "wrench", "screwdriver",
    "book", "bookmark", "newspaper", "envelope", "calendar", "clock",
    "hourglass", "stopwatch", "user", "users", "user-gear", "address-card",
    "list", "list-check", "table", "thumbs-up", "flag", "map", "location-dot",
    "image", "file", "file-code", "file-pdf", "file-word", "file-excel",
    "file-zipper", "folder", "folder-plus", "download", "upload",
    "share-nodes", "link", "paperclip", "scissors", "eraser", "trash",
    "arrow-up", "arrow-down", "arrow-left", "arrow-right", "arrows-up-down",
    "microphone", "music", "film", "photo-film", "camera-retro", "volume-low",
    "volume-off", "circle-play", "circle-info", "circle-question",
    "circle-exclamation", "triangle-exclamation", "shield", "shield-halved",
    "eye", "eye-slash", "font", "bold", "italic", "align-left",
)


def symbol_names() -> list[str]:
    return [f"fa6s.{name}" for name in CURATED]


class SymbolPickerDialog(QtWidgets.QDialog):
    """可搜索的图标网格。"""

    def __init__(self, current: str = "", parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("选择图标")
        self.resize(560, 420)
        self._selected = current

        search = QtWidgets.QLineEdit()
        search.setPlaceholderText("搜索图标名，例如 lock / 锁")
        search.setClearButtonEnabled(True)

        self._grid = QtWidgets.QListWidget()
        self._grid.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
        self._grid.setMovement(QtWidgets.QListView.Movement.Static)
        self._grid.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
        self._grid.setUniformItemSizes(True)
        self._grid.setSpacing(6)
        self._grid.setIconSize(QtCore.QSize(28, 28))
        self._grid.setGridSize(QtCore.QSize(108, 54))
        self._grid.setWordWrap(True)

        for name in CURATED:
            symbol = f"fa6s.{name}"
            item = QtWidgets.QListWidgetItem(symbol_icon(symbol, "#E4E8EE") or QtGui.QIcon(), name)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, symbol)
            item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
            item.setToolTip(symbol)
            self._grid.addItem(item)
            if symbol == current:
                self._grid.setCurrentItem(item)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(search)
        layout.addWidget(self._grid, 1)
        layout.addWidget(buttons)

        search.textChanged.connect(self._apply_filter)
        self._grid.itemDoubleClicked.connect(lambda _item: self.accept())

    def _apply_filter(self, text: str) -> None:
        keyword = text.strip().lower()
        for row in range(self._grid.count()):
            item = self._grid.item(row)
            item.setHidden(bool(keyword) and keyword not in item.text().lower())

    def selected_symbol(self) -> str:
        item = self._grid.currentItem()
        if item is None:
            return self._selected
        return item.data(QtCore.Qt.ItemDataRole.UserRole)


class SymbolButton(QtWidgets.QToolButton):
    """显示当前图标，点击弹出选择器。"""

    symbol_changed = QtCore.Signal(str)

    def __init__(self, symbol: str = "fa6s.circle", parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._symbol = symbol
        self.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setIconSize(QtCore.QSize(20, 20))
        self.setMinimumWidth(160)
        self.clicked.connect(self._pick)
        self._refresh()

    def symbol(self) -> str:
        return self._symbol

    def set_symbol(self, symbol: str) -> None:
        if symbol == self._symbol:
            return
        self._symbol = symbol
        self._refresh()

    def _refresh(self) -> None:
        icon = symbol_icon(self._symbol, "#E4E8EE")
        if icon is not None:
            self.setIcon(icon)
        self.setText(self._symbol)

    def _pick(self) -> None:
        dialog = SymbolPickerDialog(self._symbol, self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        symbol = dialog.selected_symbol()
        if symbol and symbol != self._symbol:
            self._symbol = symbol
            self._refresh()
            self.symbol_changed.emit(symbol)


__all__ = ["CURATED", "SymbolButton", "SymbolPickerDialog", "symbol_names"]
