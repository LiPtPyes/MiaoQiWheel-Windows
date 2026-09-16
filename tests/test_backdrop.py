"""毛玻璃背景：降级开关、模糊算法、抓取失败处理。

不依赖真实屏幕内容——抓取失败在测试机上同样会发生，所以断言只覆盖「形状正确」，
不覆盖「内容正确」。
"""

from __future__ import annotations

import pytest

from mqwheel.services import backdrop

PySide6 = pytest.importorskip("PySide6")
from PySide6 import QtGui  # noqa: E402


def _checkerboard(size: int = 120, block: int = 4) -> QtGui.QImage:
    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_RGB32)
    for y in range(size):
        for x in range(size):
            value = 255 if ((x // block) + (y // block)) % 2 == 0 else 0
            image.setPixel(x, y, QtGui.qRgb(value, value, value))
    return image


def _spread(image: QtGui.QImage, box: int = 4, center: int = 60) -> int:
    values = [
        image.pixelColor(x, y).red()
        for y in range(center - box, center + box)
        for x in range(center - box, center + box)
    ]
    return max(values) - min(values)


def test_is_disabled_follows_env(monkeypatch) -> None:
    monkeypatch.delenv(backdrop.DISABLE_ENV, raising=False)
    assert backdrop.is_disabled() is False
    monkeypatch.setenv(backdrop.DISABLE_ENV, "1")
    assert backdrop.is_disabled() is True


def test_capture_is_noop_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv(backdrop.DISABLE_ENV, "1")
    assert backdrop.capture(0, 0, 520, 1.0) is None


def test_capture_rejects_empty_region() -> None:
    monkeypatched = backdrop.grab_region(0, 0, 0, 0)
    assert monkeypatched is None


def test_blur_preserves_size_and_smooths() -> None:
    source = _checkerboard()
    result = backdrop.blur(source)
    assert result is not None
    assert (result.width(), result.height()) == (source.width(), source.height())
    # 棋盘格中心处原图黑白交替，模糊后应收敛到中间灰
    assert _spread(result) < _spread(source)


def test_blur_returns_none_for_null_image() -> None:
    assert backdrop.blur(QtGui.QImage()) is None


def test_grab_returns_something_or_none_without_crashing() -> None:
    """在无权截屏的环境（锁屏/安全桌面）应返回 None 而不是抛异常。"""
    result = backdrop.grab_region(0, 0, 16, 16)
    assert result is None or (result.width() == 16 and result.height() == 16)
