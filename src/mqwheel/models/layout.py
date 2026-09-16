"""布局与外观参数：不依赖 Qt，可单测。"""

from __future__ import annotations

import math

Rect = tuple[float, float, float, float]  # x, y, width, height
Point = tuple[float, float]

MAX_ITEM_COUNT = 12
MIN_ITEM_COUNT = 2


class WheelLayout:
    @staticmethod
    def moving(items: list, source_id, target_index: int, id_of=lambda item: item.id) -> list:
        """把指定 id 的项移动到目标下标，越界或原地不动时原样返回。"""
        result = list(items)
        source_index = next(
            (i for i, item in enumerate(result) if id_of(item) == source_id), None
        )
        if source_index is None:
            return result
        if not 0 <= target_index < len(result) or source_index == target_index:
            return result
        item = result.pop(source_index)
        result.insert(min(target_index, len(result)), item)
        return result

    @staticmethod
    def clamped_count(count: int) -> int:
        return max(MIN_ITEM_COUNT, min(int(count), MAX_ITEM_COUNT))


class WheelAppearance:
    DEFAULT_SCALE = 1.0
    SCALE_RANGE = (0.82, 1.20)

    @classmethod
    def sanitized_scale(cls, scale: float) -> float:
        low, high = cls.SCALE_RANGE
        return min(max(float(scale), low), high)


class WheelPresentationLayout:
    """把轮盘窗口摆到光标处，并保证完整落在可见区域内（对应 macOS 的 visibleFrame）。"""

    @staticmethod
    def frame(center: Point, requested_side: float, visible: Rect) -> tuple[float, float, float]:
        vx, vy, vw, vh = visible
        side = max(min(requested_side, vw, vh), 1.0)
        x = min(max(center[0] - side / 2, vx), max(vx, vx + vw - side))
        y = min(max(center[1] - side / 2, vy), max(vy, vy + vh - side))
        return x, y, side

    @staticmethod
    def dead_zone_for(side: float) -> float:
        """中心死区半径，落在其中的指针位置视为取消。"""
        return side * 0.19


class SettingsSplitLayout:
    DEFAULT_RATIO = 0.6
    MIN_STORED_RATIO = 0.35
    MAX_STORED_RATIO = 0.75
    DIVIDER_WIDTH = 8.0
    MIN_WHEEL_WIDTH = 440.0
    MIN_EDITOR_WIDTH = 280.0

    @classmethod
    def sanitized_ratio(cls, ratio: float) -> float:
        return min(max(float(ratio), cls.MIN_STORED_RATIO), cls.MAX_STORED_RATIO)

    @classmethod
    def clamped_ratio(cls, ratio: float, total_width: float) -> float:
        content = max(total_width - cls.DIVIDER_WIDTH, 1.0)
        low = cls.MIN_WHEEL_WIDTH / content
        high = 1 - cls.MIN_EDITOR_WIDTH / content
        if low > high:
            return cls.sanitized_ratio(ratio)
        return min(max(cls.sanitized_ratio(ratio), low), high)

    @classmethod
    def wheel_width(cls, total_width: float, ratio: float) -> float:
        content = max(total_width - cls.DIVIDER_WIDTH, 0.0)
        return content * cls.clamped_ratio(ratio, total_width)


def polygon_contains_point(points: list[Point], point: Point) -> bool:
    """射线法判断点是否在多边形内（测试用）。"""
    x, y = point
    inside = False
    count = len(points)
    for i in range(count):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % count]
        if (y1 > y) != (y2 > y):
            x_cross = x1 + (y - y1) / (y2 - y1) * (x2 - x1)
            if x < x_cross:
                inside = not inside
    return inside


def distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])
