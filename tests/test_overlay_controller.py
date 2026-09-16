"""悬浮窗控制器测试：几何命中、死区取消、松开执行。

平台差异说明：本测试运行在 offscreen 插件下，窗口属性（置顶/穿透）无法验证，
但命中测试与执行流程是纯逻辑，可以完整覆盖。
"""

from __future__ import annotations

import math

import pytest

from mqwheel.controllers.overlay_controller import WheelOverlayController
from mqwheel.models.action import WheelAction, WheelActionKind
from mqwheel.models.geometry import WheelGeometry
from mqwheel.models.settings import WheelSettings

PySide6 = pytest.importorskip("PySide6")
from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402


@pytest.fixture(scope="module")
def app():
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield application


class FakeExecutor:
    def __init__(self) -> None:
        self.executed: list[WheelAction] = []

    def execute(self, action: WheelAction) -> bool:
        self.executed.append(action)
        return True


def _make_settings(count: int = 6) -> WheelSettings:
    settings = WheelSettings()
    settings.actions = [
        WheelAction(title=f"选项{i}", kind=WheelActionKind.SHELL_COMMAND, payload=f"cmd{i}")
        for i in range(count)
    ]
    return settings


def _point_for_sector(window: QtWidgets.QWidget, index: int, count: int = 6) -> QtCore.QPoint:
    side = min(window.width(), window.height())
    geometry = WheelGeometry(count)
    dx, dy = geometry.icon_point(index, side, (0.0, 0.0))
    local = QtCore.QPointF(window.width() / 2 + dx, window.height() / 2 + dy)
    return window.mapToGlobal(local.toPoint())


def test_show_places_window_around_cursor(app) -> None:
    settings = _make_settings()
    controller = WheelOverlayController(settings, FakeExecutor())
    center = QtCore.QPoint(400, 300)
    controller.show(center)

    window = controller._window
    assert window is not None
    assert controller.visible

    screen = QtGui.QGuiApplication.primaryScreen()
    available = screen.availableGeometry()
    assert available.contains(window.geometry()) or window.width() <= available.width()

    # 盘面中心尽量贴近光标
    geo = window.geometry()
    assert abs(geo.center().x() - center.x()) <= 2
    assert abs(geo.center().y() - center.y()) <= 2
    controller.hide()


def test_hover_selects_sector(app) -> None:
    settings = _make_settings()
    executor = FakeExecutor()
    controller = WheelOverlayController(settings, executor)
    controller.show(QtCore.QPoint(400, 300))
    window = controller._window

    for index in range(6):
        controller._update_selection(_point_for_sector(window, index))
        assert controller.selected_index == index, f"扇区 {index} 命中错误"

    controller.hide()


def test_center_dead_zone_cancels(app) -> None:
    settings = _make_settings()
    executor = FakeExecutor()
    controller = WheelOverlayController(settings, executor)
    controller.show(QtCore.QPoint(400, 300))
    window = controller._window

    controller._update_selection(window.mapToGlobal(QtCore.QPoint(window.width() // 2, window.height() // 2)))
    assert controller.selected_index is None

    controller.release()
    assert executor.executed == []
    controller.hide()


def test_release_executes_selected(app) -> None:
    settings = _make_settings()
    executor = FakeExecutor()
    controller = WheelOverlayController(settings, executor)
    controller.show(QtCore.QPoint(400, 300))
    window = controller._window

    controller._update_selection(_point_for_sector(window, 3))
    controller.release()

    assert len(executor.executed) == 1
    assert executor.executed[0].title == "选项3"
    assert not controller.visible


def test_escape_cancels(app) -> None:
    settings = _make_settings()
    executor = FakeExecutor()
    controller = WheelOverlayController(settings, executor)
    controller.show(QtCore.QPoint(400, 300))
    window = controller._window
    controller._update_selection(_point_for_sector(window, 2))

    controller.handle_key(0x1B, True)  # Esc
    assert not controller.visible
    assert executor.executed == []


def test_scale_changes_window_size(app) -> None:
    settings = _make_settings()
    settings.appearance.scale = 0.82
    controller = WheelOverlayController(settings, FakeExecutor())
    controller.show(QtCore.QPoint(400, 300))
    small = controller._window.width()
    controller.hide()

    settings.appearance.scale = 1.20
    controller.show(QtCore.QPoint(400, 300))
    large = controller._window.width()
    controller.hide()

    assert small < large


def test_selection_uses_actual_action_count(app) -> None:
    settings = _make_settings(count=3)
    controller = WheelOverlayController(settings, FakeExecutor())
    controller.show(QtCore.QPoint(400, 300))
    window = controller._window
    for index in range(3):
        controller._update_selection(_point_for_sector(window, index, count=3))
        assert controller.selected_index == index
    controller.hide()


def test_points_outside_wheel_are_clamped_to_nearest_sector(app) -> None:
    """光标跑到盘外时仍应落在最近扇区，而不是崩溃或返回 None。"""
    settings = _make_settings()
    controller = WheelOverlayController(settings, FakeExecutor())
    controller.show(QtCore.QPoint(400, 300))
    window = controller._window
    far = window.mapToGlobal(QtCore.QPoint(window.width() // 2, -400))
    controller._update_selection(far)
    assert controller.selected_index is not None
    controller.hide()
