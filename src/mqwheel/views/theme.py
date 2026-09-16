"""应用外观：Fusion 风格 + 深色调色板。

轮盘盘面由 QPainter 自绘，不受调色板影响；这里只负责让设置窗口、菜单、
对话框在 Windows 上有一致的深色外观。设置环境变量 MQWHEEL_LIGHT_THEME=1
可跳过（用于排查外观问题）。
"""

from __future__ import annotations

import os

from PySide6 import QtGui, QtWidgets

ACCENT = "#3FA9FF"

_WINDOW = QtGui.QColor(0x1E, 0x21, 0x27)
_PANEL = QtGui.QColor(0x26, 0x2A, 0x31)
_INPUT = QtGui.QColor(0x1A, 0x1D, 0x22)
_TEXT = QtGui.QColor(0xE4, 0xE8, 0xEE)
_MUTED = QtGui.QColor(0x9A, 0xA3, 0xB0)
_BORDER = QtGui.QColor(0x38, 0x3E, 0x48)


def _palette() -> QtGui.QPalette:
    palette = QtGui.QPalette()
    accent = QtGui.QColor(ACCENT)

    palette.setColor(QtGui.QPalette.ColorRole.Window, _WINDOW)
    palette.setColor(QtGui.QPalette.ColorRole.WindowText, _TEXT)
    palette.setColor(QtGui.QPalette.ColorRole.Base, _INPUT)
    palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, _PANEL)
    palette.setColor(QtGui.QPalette.ColorRole.Text, _TEXT)
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, _PANEL)
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, _TEXT)
    palette.setColor(QtGui.QPalette.ColorRole.Button, _PANEL)
    palette.setColor(QtGui.QPalette.ColorRole.ButtonText, _TEXT)
    palette.setColor(QtGui.QPalette.ColorRole.BrightText, QtGui.QColor("#FFFFFF"))
    palette.setColor(QtGui.QPalette.ColorRole.Highlight, accent)
    palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor("#0E1620"))
    palette.setColor(QtGui.QPalette.ColorRole.Link, accent)
    palette.setColor(QtGui.QPalette.ColorRole.PlaceholderText, _MUTED)

    disabled = QtGui.QColor(0x6B, 0x73, 0x80)
    for role in (
        QtGui.QPalette.ColorRole.Text,
        QtGui.QPalette.ColorRole.WindowText,
        QtGui.QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QtGui.QPalette.ColorGroup.Disabled, role, disabled)
    return palette


_STYLESHEET = """
QToolTip { border: 1px solid #383E48; padding: 4px 6px; }
QGroupBox {
    border: 1px solid #383E48;
    border-radius: 6px;
    margin-top: 14px;
    padding: 6px 4px 4px 4px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    color: #C8D2DF;
}
QSplitter::handle { background: #383E48; }
QStatusBar, QMenuBar { background: #262A31; }
QMenu { border: 1px solid #383E48; }
"""


def apply(app: QtWidgets.QApplication) -> None:
    if os.environ.get("MQWHEEL_LIGHT_THEME") == "1":
        return
    app.setStyle("Fusion")
    app.setPalette(_palette())
    app.setStyleSheet(_STYLESHEET)


__all__ = ["ACCENT", "apply"]
