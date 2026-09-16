"""轮盘绘制：QPainter 实现，对应 macOS 版的 WheelOverlayView / WheelFaceView。

层次（M5 起与 SwiftUI 版的 Material 观感对齐）：
外阴影环 → 玻璃底盘（模糊背景贴图 + 色调）→ 扇区 → 中心玻璃盘 → 图标与文字。

本模块不负责窗口属性（无边框/置顶/穿透），那部分在 controllers/overlay_controller.py。
入场动画通过 `reveal` 属性驱动（0→1 同时控制缩放与不透明度），由 QPropertyAnimation 调用，
避免 QGraphicsOpacityEffect 在半透明无边框窗口上的额外开销与层级问题。
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from mqwheel.models.action import WheelAction
from mqwheel.models.geometry import WheelGeometry
from mqwheel.services.symbol_icons import fallback_pixmap, symbol_pixmap

ACCENT = "#3FA9FF"
ICON_SIZE_RATIO = 28 / 520.0  # 原版在 520pt 轮盘上使用 28pt 图标
CENTER_ICON_RATIO = 27 / 520.0
LABEL_MAX_WIDTH_RATIO = 86 / 520.0

# M5 视觉参数
BACKDROP_PAD_RATIO = 9 / 520.0  # 玻璃底盘相对外缘的外扩量
SHADOW_RATIO = 0.055  # 阴影环宽度 / 边长
SHADOW_ALPHA = 150
REVEAL_MIN_SCALE = 0.90  # 入场动画起始缩放

# 毛玻璃色调：贴了背景时用较淡的暗色（透出背景纹理），无背景时加深保证白字可读。
# 色调刻意保持中性偏冷而非纯蓝——check_render.py 会用「未选中扇区不应偏蓝」做回归断言。
GLASS_TINT_BLURRED = QtGui.QColor(16, 18, 24, 118)
GLASS_TINT_SOLID = QtGui.QColor(28, 30, 36, 198)
CENTER_TINT_BLURRED = QtGui.QColor(20, 23, 30, 128)
CENTER_TINT_SOLID = QtGui.QColor(34, 36, 43, 210)


class WheelFaceWidget(QtWidgets.QWidget):
    """轮盘盘面。尺寸由外部给定，绘制始终以 min(width, height) 为边长居中。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._actions: list[WheelAction] = []
        self._selected_index: int | None = None
        self._show_labels = True
        self._reveal = 1.0
        self._backdrop: QtGui.QPixmap | None = None

    # region 外部状态
    def set_actions(self, actions: list[WheelAction]) -> None:
        self._actions = list(actions)
        self.update()

    def set_selected_index(self, index: int | None) -> None:
        if index == self._selected_index:
            return
        self._selected_index = index
        self.update()

    def set_show_labels(self, value: bool) -> None:
        self._show_labels = value
        self.update()

    def set_backdrop(self, pixmap: QtGui.QPixmap | None) -> None:
        """设置模糊背景贴图；None 表示降级为纯色玻璃。"""
        self._backdrop = pixmap
        self.update()

    # endregion

    # region 入场动画属性
    def get_reveal(self) -> float:
        return self._reveal

    def set_reveal(self, value: float) -> None:
        clamped = min(max(float(value), 0.0), 1.0)
        if abs(clamped - self._reveal) < 0.001:
            return
        self._reveal = clamped
        self.update()

    reveal = QtCore.Property(float, get_reveal, set_reveal, user=True)
    # endregion

    # region 绘制
    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        if not self._actions:
            return

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)

        rect = self.rect()
        side = min(rect.width(), rect.height())
        center = (rect.width() / 2, rect.height() / 2)
        geometry = WheelGeometry(len(self._actions))
        inner, _middle, outer = geometry.radii(side)
        back_radius = outer + side * BACKDROP_PAD_RATIO

        if self._reveal < 1.0:
            scale = REVEAL_MIN_SCALE + (1.0 - REVEAL_MIN_SCALE) * self._reveal
            painter.translate(center[0], center[1])
            painter.scale(scale, scale)
            painter.translate(-center[0], -center[1])
            painter.setOpacity(self._reveal)

        self._draw_shadow(painter, center, back_radius, side)
        self._draw_glass(painter, center, back_radius, side)
        for index in range(len(self._actions)):
            self._draw_segment(painter, geometry, index, side, center)
        self._draw_center_surface(painter, center, inner * 0.91, side)
        self._draw_foreground(painter, geometry, side, center)

        painter.end()

    def _ellipse_path(
        self, center: tuple[float, float], radius: float
    ) -> QtGui.QPainterPath:
        path = QtGui.QPainterPath()
        path.addEllipse(
            center[0] - radius, center[1] - radius, radius * 2, radius * 2
        )
        return path

    def _polygon(self, points: list[tuple[float, float]]) -> QtGui.QPainterPath:
        path = QtGui.QPainterPath()
        path.moveTo(points[0][0], points[0][1])
        for x, y in points[1:]:
            path.lineTo(x, y)
        path.closeSubpath()
        return path

    def _draw_shadow(
        self,
        painter: QtGui.QPainter,
        center: tuple[float, float],
        radius: float,
        side: float,
    ) -> None:
        """只在底盘外侧绘制阴影环，避免把模糊背景整体压暗。"""
        pad = side * SHADOW_RATIO
        outer = radius + pad
        if outer <= radius:
            return
        gradient = QtGui.QRadialGradient(center[0], center[1], outer)
        gradient.setColorAt(0.0, QtGui.QColor(0, 0, 0, SHADOW_ALPHA))
        gradient.setColorAt(radius / outer, QtGui.QColor(0, 0, 0, SHADOW_ALPHA))
        gradient.setColorAt(1.0, QtGui.QColor(0, 0, 0, 0))

        ring = self._ellipse_path(center, outer)
        ring.addEllipse(center[0] - radius, center[1] - radius, radius * 2, radius * 2)
        ring.setFillRule(QtCore.Qt.FillRule.OddEvenFill)
        painter.setBrush(gradient)
        painter.drawPath(ring)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)

    def _draw_backdrop(self, painter: QtGui.QPainter, side: float) -> bool:
        """铺满整个盘面矩形（真正的裁剪由调用方的 clipPath 完成）。无贴图返回 False。"""
        pixmap = self._backdrop
        if pixmap is None or pixmap.isNull():
            return False
        # PySide6 的 drawPixmap 没有 (QRectF, QPixmap) 重载，必须显式给出源矩形
        painter.drawPixmap(
            QtCore.QRectF(0.0, 0.0, side, side), pixmap, QtCore.QRectF(pixmap.rect())
        )
        return True

    def _draw_glass(
        self,
        painter: QtGui.QPainter,
        center: tuple[float, float],
        radius: float,
        side: float,
    ) -> None:
        path = self._ellipse_path(center, radius)
        painter.save()
        painter.setClipPath(path)
        if self._draw_backdrop(painter, side):
            painter.fillPath(path, GLASS_TINT_BLURRED)
        else:
            painter.fillPath(path, GLASS_TINT_SOLID)
        painter.restore()

        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 52), 1.0))
        painter.drawPath(path)
        # 顶部高光弧（Qt 角度：0 在 3 点方向，逆时针为正，单位 1/16 度）
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 86), 1.4))
        painter.drawArc(
            int(center[0] - radius), int(center[1] - radius), int(radius * 2), int(radius * 2),
            36 * 16, 108 * 16,
        )
        painter.setPen(QtCore.Qt.PenStyle.NoPen)

    def _draw_segment(
        self,
        painter: QtGui.QPainter,
        geometry: WheelGeometry,
        index: int,
        side: float,
        center: tuple[float, float],
    ) -> None:
        selected = self._selected_index == index
        path = self._polygon(geometry.segment_points(index, side, center))

        painter.setBrush(QtGui.QColor(255, 255, 255, 34 if not selected else 12))
        painter.drawPath(path)

        if selected:
            accent = QtGui.QColor(ACCENT)
            gradient = QtGui.QLinearGradient(
                center[0], center[1] - side / 2, center[0], center[1] + side / 2
            )
            gradient.setColorAt(0.0, QtGui.QColor(accent.red(), accent.green(), accent.blue(), 205))
            gradient.setColorAt(1.0, QtGui.QColor(accent.red(), accent.green(), accent.blue(), 150))
            painter.setBrush(gradient)
            painter.drawPath(path)

        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        if selected:
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 128), 1.2))
        else:
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 36), 0.8))
        painter.drawPath(path)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)

    def _draw_center_surface(
        self,
        painter: QtGui.QPainter,
        center: tuple[float, float],
        radius: float,
        side: float,
    ) -> None:
        path = self._ellipse_path(center, radius)
        painter.save()
        painter.setClipPath(path)
        if self._draw_backdrop(painter, side):
            painter.fillPath(path, CENTER_TINT_BLURRED)
        else:
            painter.fillPath(path, CENTER_TINT_SOLID)
        painter.restore()

        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 51), 1.0))
        painter.drawPath(path)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)

    def _draw_foreground(
        self,
        painter: QtGui.QPainter,
        geometry: WheelGeometry,
        side: float,
        center: tuple[float, float],
    ) -> None:
        icon_size = side * ICON_SIZE_RATIO
        label_width = side * LABEL_MAX_WIDTH_RATIO

        for index, action in enumerate(self._actions):
            selected = self._selected_index == index
            point = geometry.icon_point(index, side, center)
            color = "#FFFFFF" if selected else "#D6E6F5"
            pixmap = symbol_pixmap(action.symbol, int(icon_size), color) or fallback_pixmap(
                int(icon_size), color
            )
            painter.drawPixmap(
                point[0] - icon_size / 2, point[1] - icon_size / 2, pixmap
            )

            if not self._show_labels:
                continue

            font = QtGui.QFont("Microsoft YaHei UI", max(int(side * 12 / 520.0), 8))
            font.setWeight(QtGui.QFont.Weight.DemiBold)
            painter.setFont(font)
            painter.setPen(QtGui.QColor(color))

            metrics = QtGui.QFontMetrics(font)
            text = metrics.elidedText(
                action.title, QtCore.Qt.TextElideMode.ElideRight, int(label_width)
            )
            text_rect = QtCore.QRectF(
                point[0] - label_width / 2,
                point[1] + icon_size / 2 + side * 5 / 520.0,
                label_width,
                metrics.height(),
            )
            painter.drawText(text_rect, QtCore.Qt.AlignmentFlag.AlignHCenter, text)

        self._draw_center_content(painter, side, center)

    def _draw_center_content(
        self, painter: QtGui.QPainter, side: float, center: tuple[float, float]
    ) -> None:
        selected = self._selected_index
        action = self._actions[selected] if selected is not None else None

        if action is not None:
            icon_size = side * CENTER_ICON_RATIO
            pixmap = symbol_pixmap(action.symbol, int(icon_size), "#FFFFFF") or fallback_pixmap(
                int(icon_size), "#FFFFFF"
            )
            painter.drawPixmap(center[0] - icon_size / 2, center[1] - icon_size * 1.1, pixmap)

            title_font = QtGui.QFont("Microsoft YaHei UI", max(int(side * 14 / 520.0), 9))
            title_font.setWeight(QtGui.QFont.Weight.DemiBold)
            painter.setFont(title_font)
            painter.setPen(QtGui.QColor("#FFFFFF"))
            metrics = QtGui.QFontMetrics(title_font)
            width = side * 0.30
            title = metrics.elidedText(action.title, QtCore.Qt.TextElideMode.ElideRight, int(width))
            painter.drawText(
                QtCore.QRectF(center[0] - width / 2, center[1] + icon_size * 0.15, width, metrics.height()),
                QtCore.Qt.AlignmentFlag.AlignHCenter,
                title,
            )

            subtitle_font = QtGui.QFont("Microsoft YaHei UI", max(int(side * 10 / 520.0), 7))
            painter.setFont(subtitle_font)
            painter.setPen(QtGui.QColor(210, 222, 234, 210))
            sub_metrics = QtGui.QFontMetrics(subtitle_font)
            subtitle = sub_metrics.elidedText(
                action.subtitle, QtCore.Qt.TextElideMode.ElideRight, int(width)
            )
            painter.drawText(
                QtCore.QRectF(
                    center[0] - width / 2,
                    center[1] + icon_size * 0.15 + metrics.height() + 2,
                    width,
                    sub_metrics.height(),
                ),
                QtCore.Qt.AlignmentFlag.AlignHCenter,
                subtitle,
            )
            return

        icon_size = side * CENTER_ICON_RATIO
        pixmap = symbol_pixmap("fa6s.computer-mouse", int(icon_size), "#CFE3F5") or fallback_pixmap(
            int(icon_size), "#CFE3F5"
        )
        painter.drawPixmap(center[0] - icon_size / 2, center[1] - icon_size * 1.0, pixmap)

        font = QtGui.QFont("Microsoft YaHei UI", max(int(side * 13 / 520.0), 9))
        font.setWeight(QtGui.QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QtGui.QColor("#FFFFFF"))
        metrics = QtGui.QFontMetrics(font)
        width = side * 0.30
        painter.drawText(
            QtCore.QRectF(center[0] - width / 2, center[1] + icon_size * 0.15, width, metrics.height()),
            QtCore.Qt.AlignmentFlag.AlignHCenter,
            "指向选项",
        )

        hint_font = QtGui.QFont("Microsoft YaHei UI", max(int(side * 10 / 520.0), 7))
        painter.setFont(hint_font)
        painter.setPen(QtGui.QColor(200, 214, 228, 190))
        hint_metrics = QtGui.QFontMetrics(hint_font)
        painter.drawText(
            QtCore.QRectF(
                center[0] - width / 2,
                center[1] + icon_size * 0.15 + metrics.height() + 2,
                width,
                hint_metrics.height(),
            ),
            QtCore.Qt.AlignmentFlag.AlignHCenter,
            "松开快捷键执行",
        )
    # endregion


__all__ = ["WheelFaceWidget"]
