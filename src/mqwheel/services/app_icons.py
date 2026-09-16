"""从可执行文件 / 快捷方式取系统图标。

用 Qt 自带的 QFileIconProvider：不必手写 SHGetFileInfo 的 ctypes 结构，
且 Qt 在 Windows 上会把 .lnk 当作符号链接解析（symLinkTarget 即目标路径）。
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

_provider: QtWidgets.QFileIconProvider | None = None
_cache: dict[tuple[str, int], QtGui.QPixmap] = {}


def _ensure_provider() -> QtWidgets.QFileIconProvider:
    global _provider
    if _provider is None:
        _provider = QtWidgets.QFileIconProvider()
    return _provider


def _empty(size: int) -> QtGui.QPixmap:
    pixmap = QtGui.QPixmap(int(size), int(size))
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    return pixmap


def resolve_target(path: str) -> str:
    """快捷方式返回指向的目标，其他路径原样返回。"""
    if not path:
        return ""
    info = QtCore.QFileInfo(path)
    if info.isSymLink() or path.lower().endswith(".lnk"):
        target = info.symLinkTarget()
        if target:
            return target
    return path


def pixmap_for(path: str, size: int = 32) -> QtGui.QPixmap:
    """取指定文件在资源管理器里显示的那个图标；失败返回透明图。"""
    key = (path, int(size))
    cached = _cache.get(key)
    if cached is not None:
        return cached

    pixmap = _empty(size)
    if not path:
        return pixmap

    info = QtCore.QFileInfo(path)
    icon = _ensure_provider().icon(info)
    if not icon.isNull():
        rendered = icon.pixmap(int(size), int(size))
        if not rendered.isNull():
            pixmap = rendered
    _cache[key] = pixmap
    return pixmap


def icon_for(path: str) -> QtGui.QIcon:
    if not path:
        return QtGui.QIcon()
    icon = _ensure_provider().icon(QtCore.QFileInfo(path))
    return icon if not icon.isNull() else QtGui.QIcon()


__all__ = ["icon_for", "pixmap_for", "resolve_target"]
