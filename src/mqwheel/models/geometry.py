"""轮盘几何：与渲染、命中测试共用的纯数学，不依赖 Qt。

坐标系约定（与 Qt 一致，y 轴向下）：
- 角度 0 指向右，角度增大方向为**顺时针**；
- 第 0 个扇区的中心在正上方（角度 -π/2）。

间隙（gap）按原 macOS 实现处理为**线性偏移**而非角度：相邻扇区的分界边各向内平移 half_gap，
因此从内圈到外圈的间隙宽度恒定。

采样法说明：Qt 的 QPainterPath.arcTo 采用「逆时针为正、单位 1/16 度」的角度语义，
与上面的约定相反，直接移植易错；这里改为在圆弧上采样生成多边形，数学上与
Swift 版的 `insetBoundaryPoint` + `addArc` 完全等价（见 tests/test_geometry.py）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Point = tuple[float, float]
TAU = math.tau


@dataclass
class WheelGeometry:
    item_count: int = 6
    inner_radius_ratio: float = 0.205
    outer_radius_ratio: float = 0.43
    gap: float = 7.0

    def __post_init__(self) -> None:
        self.item_count = max(int(self.item_count), 1)

    # region 基本量
    @property
    def sweep(self) -> float:
        """单个扇区占据的角度。"""
        return TAU / self.item_count

    def radii(self, side: float) -> tuple[float, float, float]:
        """给定正方形边长，返回 (内半径, 中半径, 外半径)。"""
        inner = side * self.inner_radius_ratio
        outer = side * self.outer_radius_ratio
        return inner, (inner + outer) / 2.0, outer

    def sector_center_angle(self, index: int) -> float:
        return -math.pi / 2 + index * self.sweep

    def sector_angles(self, index: int) -> tuple[float, float]:
        center = self.sector_center_angle(index)
        return center - self.sweep / 2, center + self.sweep / 2

    def half_gap(self, inner_radius: float) -> float:
        return min(max(self.gap, 0.0) / 2.0, inner_radius * math.sin(self.sweep / 2) * 0.8)

    # endregion

    def point_at(self, angle: float, radius: float, center: Point = (0.0, 0.0)) -> Point:
        return (center[0] + math.cos(angle) * radius, center[1] + math.sin(angle) * radius)

    def icon_point(self, index: int, side: float, center: Point = (0.0, 0.0)) -> Point:
        """图标（含标签）应绘制的位置。"""
        _, middle, _ = self.radii(side)
        return self.point_at(self.sector_center_angle(index), middle, center)

    def segment_points(
        self,
        index: int,
        side: float,
        center: Point = (0.0, 0.0),
        samples: int = 48,
    ) -> list[Point]:
        """返回扇区多边形顶点：外弧（顺时针）→ 内弧（逆时针）。

        外弧两端各内缩 outer_inset，内弧两端各内缩 inner_inset，
        使得两条径向分界边平行且相距 gap。
        """
        inner, _, outer = self.radii(side)
        start, end = self.sector_angles(index)
        half = self.half_gap(inner)
        outer_inset = math.asin(min(half / outer, 1.0)) if outer > 0 else 0.0
        inner_inset = math.asin(min(half / inner, 1.0)) if inner > 0 else 0.0

        points: list[Point] = []
        outer_start, outer_end = start + outer_inset, end - outer_inset
        for step in range(samples + 1):
            angle = outer_start + (outer_end - outer_start) * step / samples
            points.append(self.point_at(angle, outer, center))

        inner_start, inner_end = end - inner_inset, start + inner_inset
        for step in range(samples + 1):
            angle = inner_start + (inner_end - inner_start) * step / samples
            points.append(self.point_at(angle, inner, center))
        return points

    def selection_index(
        self,
        point: Point,
        center: Point,
        dead_zone: float = 0.0,
    ) -> int | None:
        """把光标位置解析为顺时针扇区索引；落在中心死区内返回 None（取消）。"""
        dx = point[0] - center[0]
        dy = point[1] - center[1]
        if math.hypot(dx, dy) < dead_zone:
            return None

        # 以正上方为 0 的顺时针角：屏幕坐标 y 向下，故取 -dy。
        angle = math.atan2(dx, -dy)
        if angle < 0:
            angle += TAU
        return int(math.floor((angle + self.sweep / 2) / self.sweep)) % self.item_count
