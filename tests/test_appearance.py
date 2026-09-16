"""M5 视觉项测试：毛玻璃开关、入场动画、reveal 属性夹取、背景贴图释放。"""

from __future__ import annotations

import pytest

from mqwheel.controllers.overlay_controller import WheelOverlayController
from mqwheel.models.action import WheelAction, WheelActionKind
from mqwheel.models.settings import AppearanceConfig, WheelSettings
from mqwheel.services import backdrop

PySide6 = pytest.importorskip("PySide6")
from PySide6 import QtCore, QtGui  # noqa: E402

from mqwheel.views.overlay import WheelFaceWidget  # noqa: E402


class FakeExecutor:
    def __init__(self) -> None:
        self.executed: list[WheelAction] = []

    def execute(self, action: WheelAction) -> bool:
        self.executed.append(action)
        return True


def _settings() -> WheelSettings:
    settings = WheelSettings()
    settings.actions = [
        WheelAction(title=f"选项{i}", kind=WheelActionKind.SHELL_COMMAND, payload=f"cmd{i}")
        for i in range(6)
    ]
    return settings


# region 设置模型
def test_appearance_defaults_enable_visuals() -> None:
    config = AppearanceConfig()
    assert config.blur_background is True
    assert config.animate is True


def test_appearance_roundtrip_preserves_flags() -> None:
    settings = _settings()
    settings.appearance.blur_background = False
    settings.appearance.animate = False
    restored = WheelSettings.from_dict(settings.to_dict())
    assert restored.appearance.blur_background is False
    assert restored.appearance.animate is False
    assert restored.appearance.show_labels is True


def test_appearance_missing_keys_default_to_enabled() -> None:
    restored = AppearanceConfig.from_dict({})
    assert restored.blur_background is True
    assert restored.animate is True


# endregion


# region 盘面绘制属性
def test_reveal_is_clamped(qapp) -> None:
    face = WheelFaceWidget()
    assert face.reveal == 1.0
    face.set_reveal(0.5)
    assert face.reveal == 0.5
    face.set_reveal(5.0)
    assert face.reveal == 1.0
    face.set_reveal(-2.0)
    assert face.reveal == 0.0


def test_set_backdrop_accepts_none(qapp) -> None:
    face = WheelFaceWidget()
    face.set_backdrop(QtGui.QPixmap(8, 8))
    face.set_backdrop(None)
    face.set_actions(_settings().actions)
    face.set_selected_index(2)
    face.repaint()  # 降级路径必须能完整绘制一遍
    assert face.reveal == 1.0


# endregion


# region 控制器
def test_animation_disabled_shows_at_full_reveal(qapp) -> None:
    settings = _settings()
    settings.appearance.animate = False
    controller = WheelOverlayController(settings, FakeExecutor())
    controller.show(QtCore.QPoint(400, 300))
    try:
        assert controller._window.face.reveal == 1.0
    finally:
        controller.hide()
    assert controller._window.isVisible() is False


def test_animation_enabled_animates_in(qapp) -> None:
    settings = _settings()
    settings.appearance.animate = True
    controller = WheelOverlayController(settings, FakeExecutor())
    controller.show(QtCore.QPoint(400, 300))
    try:
        animation = controller._animation
        assert animation is not None
        assert float(animation.endValue()) == 1.0
        assert animation.duration() == controller.REVEAL_MS
        assert controller._window.face.reveal < 1.0  # 事件循环未推进，仍在起点
    finally:
        animation = controller._animation
        if animation is not None:
            animation.stop()
        controller._finish_hide()


def test_finish_hide_releases_backdrop(qapp) -> None:
    controller = WheelOverlayController(_settings(), FakeExecutor())
    controller.show(QtCore.QPoint(400, 300))
    face = controller._window.face
    face.set_backdrop(QtGui.QPixmap(8, 8))
    controller._animation.stop() if controller._animation else None
    controller._finish_hide()
    assert face._backdrop is None
    assert controller._window.isVisible() is False


def test_blur_disabled_captures_nothing(qapp) -> None:
    settings = _settings()
    settings.appearance.blur_background = False
    settings.appearance.animate = False
    controller = WheelOverlayController(settings, FakeExecutor())
    controller.show(QtCore.QPoint(400, 300))
    try:
        assert controller._window.face._backdrop is None
    finally:
        controller.hide()


def test_blur_enabled_uses_capture_result(qapp, monkeypatch) -> None:
    sentinel = QtGui.QPixmap(4, 4)
    seen: dict[str, float] = {}

    def fake_capture(x, y, side, dpr):
        seen["x"], seen["y"], seen["side"], seen["dpr"] = x, y, side, dpr
        return sentinel

    monkeypatch.setattr(backdrop, "capture", fake_capture)

    settings = _settings()
    settings.appearance.blur_background = True
    settings.appearance.animate = False
    controller = WheelOverlayController(settings, FakeExecutor())
    controller.show(QtCore.QPoint(400, 300))
    try:
        assert controller._window.face._backdrop is sentinel
        # 抓取区域应是盘面窗口本身（逻辑坐标），DPR 取所在屏幕
        assert seen["side"] == pytest.approx(controller.BASE_SIDE * settings.appearance.scale)
        assert seen["dpr"] > 0
    finally:
        controller.hide()


def test_set_settings_drops_backdrop_when_blur_turned_off(qapp, monkeypatch) -> None:
    monkeypatch.setattr(backdrop, "capture", lambda *args: QtGui.QPixmap(4, 4))
    settings = _settings()
    settings.appearance.animate = False
    controller = WheelOverlayController(settings, FakeExecutor())
    controller.show(QtCore.QPoint(400, 300))
    try:
        assert controller._window.face._backdrop is not None
        settings.appearance.blur_background = False
        controller.set_settings(settings)
        assert controller._window.face._backdrop is None
    finally:
        controller.hide()


def test_capture_failure_degrades_gracefully(qapp, monkeypatch) -> None:
    def boom(*args):
        raise RuntimeError("截屏被拒绝")

    monkeypatch.setattr(backdrop, "capture", boom)
    settings = _settings()
    settings.appearance.animate = False
    controller = WheelOverlayController(settings, FakeExecutor())
    controller.show(QtCore.QPoint(400, 300))
    try:
        assert controller._window.face._backdrop is None
        assert controller.visible is True  # 截图炸了也必须能呼出
    finally:
        controller.hide()


# endregion
