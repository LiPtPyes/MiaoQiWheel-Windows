"""轮盘悬浮窗控制器：对应 macOS 版的 WheelOverlayController。

关键约束（Windows 与 macOS 差异最大的地方）：
- 悬浮窗绝不能抢焦点，否则每次呼出都会打断用户正在输入的应用；
- 窗口必须对所有鼠标事件穿透，否则指针会被自己画的盘面挡住；
- 窗口不进任务栏、不进 Alt+Tab（Qt.Tool）。

M5 新增：
- 毛玻璃：呼出前抓取盘面背后的屏幕区域并模糊，交给盘面作为底图（可关闭）；
- 入场/退场动画：QPropertyAnimation 驱动盘面的 reveal 属性（缩放 + 淡入一起做），
  不用 QGraphicsOpacityEffect——那会在半透明无边框窗口上多出一层开销；
- 多屏 / 高 DPI：每次呼出按光标所在屏幕计算可用区与 devicePixelRatio，
  截图按物理像素抓取后再还原成逻辑尺寸。
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from mqwheel.models.geometry import WheelGeometry
from mqwheel.models.layout import WheelPresentationLayout
from mqwheel.models.settings import WheelSettings
from mqwheel.services.action_executor import ActionExecutor
from mqwheel.services.win32_ext import VK_ESCAPE
from mqwheel.views.overlay import WheelFaceWidget

_WINDOW_FLAGS = (
    QtCore.Qt.WindowType.Tool
    | QtCore.Qt.WindowType.FramelessWindowHint
    | QtCore.Qt.WindowType.WindowStaysOnTopHint
    | QtCore.Qt.WindowType.WindowDoesNotAcceptFocus
    | QtCore.Qt.WindowType.WindowTransparentForInput
)


class WheelOverlayWindow(QtWidgets.QWidget):
    """无边框、置顶、穿透、不接受焦点的圆形悬浮层。"""

    def __init__(self) -> None:
        super().__init__(None, _WINDOW_FLAGS)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._face = WheelFaceWidget(self)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._face)
        self.resize(520, 520)

    @property
    def face(self) -> WheelFaceWidget:
        return self._face


class WheelOverlayController(QtCore.QObject):
    BASE_SIDE = 520.0
    POLL_INTERVAL_MS = 16
    REVEAL_MS = 130
    FADE_OUT_MS = 90

    action_executed = QtCore.Signal(object, bool)  # WheelAction, 是否成功
    cancelled = QtCore.Signal()
    visibility_changed = QtCore.Signal(bool)

    def __init__(
        self,
        settings: WheelSettings,
        executor: ActionExecutor | None = None,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._executor = executor or ActionExecutor()
        self._window: WheelOverlayWindow | None = None
        self._animation: QtCore.QPropertyAnimation | None = None
        self._pending_hide = False
        self._selected: int | None = None
        self._visible = False

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(self.POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._on_tick)

    # region 外部接口
    @property
    def visible(self) -> bool:
        return self._visible

    @property
    def selected_index(self) -> int | None:
        return self._selected

    def set_settings(self, settings: WheelSettings) -> None:
        self._settings = settings
        if self._window is None:
            return
        self._window.face.set_show_labels(settings.appearance.show_labels)
        self._window.face.set_actions(settings.actions)
        if not settings.appearance.blur_background:
            self._window.face.set_backdrop(None)

    def show(self, center: QtCore.QPoint | None = None) -> None:
        window = self._ensure_window()
        if center is None:
            center = QtGui.QCursor.pos()

        screen = QtGui.QGuiApplication.screenAt(center) or QtGui.QGuiApplication.primaryScreen()
        available = screen.availableGeometry() if screen else QtCore.QRect(0, 0, 1920, 1080)
        requested = self.BASE_SIDE * self._settings.appearance.scale
        x, y, side = WheelPresentationLayout.frame(
            (center.x(), center.y()),
            requested,
            (available.x(), available.y(), available.width(), available.height()),
        )

        self._bind_screen(window, screen)
        window.setGeometry(int(round(x)), int(round(y)), int(round(side)), int(round(side)))
        window.face.set_show_labels(self._settings.appearance.show_labels)
        window.face.set_actions(self._settings.actions)
        window.face.set_selected_index(None)
        self._selected = None

        self._apply_backdrop(window, screen, x, y, side)

        animation = self._animation
        if animation is not None:
            animation.stop()
        self._pending_hide = False

        if self._settings.appearance.animate and animation is not None:
            # 只有「从隐藏到出现」才从 0 起；淡出途中再次呼出则从当前值续上
            if not window.isVisible():
                window.face.set_reveal(0.0)
            animation.setDuration(self.REVEAL_MS)
            animation.setStartValue(window.face.reveal)
            animation.setEndValue(1.0)
            window.show()
            window.raise_()
            animation.start()
        else:
            window.face.set_reveal(1.0)
            window.show()
            window.raise_()

        self._visible = True
        self.visibility_changed.emit(True)
        self._timer.start()
        self._update_selection(center)

    def hide(self) -> None:
        self._timer.stop()
        window = self._window
        if window is not None:
            window.face.set_selected_index(None)
            if self._settings.appearance.animate and self._animation is not None and window.isVisible():
                self._pending_hide = True
                self._animation.stop()
                self._animation.setDuration(self.FADE_OUT_MS)
                self._animation.setStartValue(window.face.reveal)
                self._animation.setEndValue(0.0)
                self._animation.start()
            else:
                self._finish_hide()
        self._selected = None
        if self._visible:
            self._visible = False
            self.visibility_changed.emit(False)

    def cancel(self) -> None:
        if not self._visible:
            return
        self.hide()
        self.cancelled.emit()

    def release(self) -> None:
        """热键松开：执行选中项；落在中心死区则取消。"""
        if not self._visible:
            return
        index = self._selected
        actions = self._settings.actions
        self.hide()
        if index is None or not (0 <= index < len(actions)):
            self.cancelled.emit()
            return
        action = actions[index]
        ok = self._executor.execute(action)
        self.action_executed.emit(action, ok)

    def handle_key(self, vk: int, is_down: bool) -> None:
        """轮盘显示期间的按键处理（目前只需要 Esc 取消）。"""
        if is_down and vk == VK_ESCAPE and self._visible:
            self.cancel()
    # endregion

    # region 内部
    def _ensure_window(self) -> WheelOverlayWindow:
        if self._window is None:
            self._window = WheelOverlayWindow()
            self._animation = QtCore.QPropertyAnimation(self._window.face, b"reveal", self)
            self._animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
            self._animation.finished.connect(self._on_animation_finished)
        return self._window

    @staticmethod
    def _bind_screen(window: WheelOverlayWindow, screen: QtGui.QScreen | None) -> None:
        """把窗口挂到光标所在屏幕，保证多屏不同 DPI 下按该屏比例渲染。"""
        if screen is None:
            return
        handle = window.windowHandle()
        if handle is None or handle.screen() is screen:
            return
        try:
            handle.setScreen(screen)
        except Exception:
            pass  # 换屏失败不致命，Qt 会在窗口移动后自行纠正

    def _apply_backdrop(
        self,
        window: WheelOverlayWindow,
        screen: QtGui.QScreen | None,
        x: float,
        y: float,
        side: float,
    ) -> None:
        if not self._settings.appearance.blur_background:
            window.face.set_backdrop(None)
            return
        try:
            from mqwheel.services import backdrop

            ratio = screen.devicePixelRatio() if screen is not None else 1.0
            window.face.set_backdrop(backdrop.capture(x, y, side, ratio))
        except Exception:
            window.face.set_backdrop(None)  # 截图失败静默降级为纯色玻璃

    def _on_animation_finished(self) -> None:
        if self._pending_hide:
            self._finish_hide()

    def _finish_hide(self) -> None:
        self._pending_hide = False
        if self._animation is not None:
            self._animation.stop()
        if self._window is not None:
            self._window.hide()
            self._window.face.set_backdrop(None)  # 释放背景贴图，常驻期不占内存

    def _on_tick(self) -> None:
        if not self._visible:
            self._timer.stop()
            return
        self._update_selection(QtGui.QCursor.pos())

    def _update_selection(self, global_point: QtCore.QPoint) -> None:
        window = self._window
        if window is None:
            return
        local = window.mapFromGlobal(global_point)
        side = min(window.width(), window.height())
        if side <= 0:
            return
        center = (window.width() / 2.0, window.height() / 2.0)
        count = max(len(self._settings.actions), 1)
        geometry = WheelGeometry(count)
        index = geometry.selection_index(
            (local.x(), local.y()), center, WheelPresentationLayout.dead_zone_for(side)
        )
        if index is not None and not (0 <= index < len(self._settings.actions)):
            index = None
        self._selected = index
        window.face.set_selected_index(index)
    # endregion
