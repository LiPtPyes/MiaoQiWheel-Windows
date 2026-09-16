"""符号图标：用 FontAwesome 6（qtawesome）替代 macOS 的 SF Symbols。

qtawesome 属于「按需导入」的重依赖，只在轮盘或设置窗口首次绘制时加载。
"""

from __future__ import annotations

import os

from PySide6 import QtCore, QtGui

DEFAULT_SYMBOL = "fa6s.circle"
_QT_API_CONFIGURED = False
_cache: dict[tuple[str, str], QtGui.QIcon] = {}


def _qta():
    global _QT_API_CONFIGURED
    if not _QT_API_CONFIGURED:
        os.environ.setdefault("QT_API", "pyside6")
        _QT_API_CONFIGURED = True
    import qtawesome as qta

    return qta


def symbol_icon(name: str, color: str = "#FFFFFF") -> QtGui.QIcon | None:
    """按 `fa6s.lock` 这样的名字取图标；失败返回 None，由调用方回退。"""
    key = (name, color)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    prefix, _, glyph = name.partition(".")
    if not prefix or not glyph:
        return None

    try:
        icon = _qta().icon(f"{prefix}.{glyph}", color=color)
    except Exception:
        return None

    if icon is None or icon.isNull():
        return None
    _cache[key] = icon
    return icon


def symbol_pixmap(name: str, size: int, color: str = "#FFFFFF") -> QtGui.QPixmap | None:
    icon = symbol_icon(name, color)
    if icon is None:
        return None
    return icon.pixmap(size, size)


def fallback_pixmap(size: int, color: str = "#FFFFFF") -> QtGui.QPixmap:
    """图标缺失时的占位：一个描边圆环。"""
    pixmap = QtGui.QPixmap(int(size), int(size))
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    pen = QtGui.QPen(QtGui.QColor(color))
    pen.setWidthF(max(size * 0.08, 1.0))
    painter.setPen(pen)
    painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
    painter.drawEllipse(size * 0.15, size * 0.15, size * 0.7, size * 0.7)
    painter.end()
    return pixmap
