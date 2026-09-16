"""布局与外观参数测试。"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from mqwheel.models.layout import (
    SettingsSplitLayout,
    WheelAppearance,
    WheelLayout,
    WheelPresentationLayout,
)


@dataclass
class Item:
    id: str


def ids(items):
    return [item.id for item in items]


def test_moving_reorders_items():
    items = [Item("a"), Item("b"), Item("c"), Item("d")]
    assert ids(WheelLayout.moving(items, "a", 2)) == ["b", "c", "a", "d"]
    assert ids(WheelLayout.moving(items, "d", 0)) == ["d", "a", "b", "c"]


def test_moving_ignores_invalid_requests():
    items = [Item("a"), Item("b")]
    assert ids(WheelLayout.moving(items, "missing", 0)) == ["a", "b"]
    assert ids(WheelLayout.moving(items, "a", 9)) == ["a", "b"]
    assert ids(WheelLayout.moving(items, "a", 0)) == ["a", "b"]
    assert ids(items) == ["a", "b"], "不得修改原列表"


def test_clamped_count():
    assert WheelLayout.clamped_count(0) == 2
    assert WheelLayout.clamped_count(6) == 6
    assert WheelLayout.clamped_count(99) == 12


def test_scale_is_sanitized():
    assert WheelAppearance.sanitized_scale(1.0) == 1.0
    assert WheelAppearance.sanitized_scale(0.1) == 0.82
    assert WheelAppearance.sanitized_scale(9.0) == 1.20


def test_frame_keeps_wheel_inside_visible_area():
    visible = (0.0, 0.0, 1920.0, 1080.0)

    x, y, side = WheelPresentationLayout.frame((960.0, 540.0), 520.0, visible)
    assert side == 520.0
    assert x == 700.0 and y == 280.0

    # 靠近左上角时向内夹取
    x, y, side = WheelPresentationLayout.frame((10.0, 10.0), 520.0, visible)
    assert x == 0.0 and y == 0.0

    # 靠近右下角时向内夹取
    x, y, side = WheelPresentationLayout.frame((1910.0, 1070.0), 520.0, visible)
    assert x + side <= 1920.0
    assert y + side <= 1080.0

    # 可见区域比轮盘小时缩小
    _x, _y, side = WheelPresentationLayout.frame((100.0, 100.0), 520.0, (0.0, 0.0, 300.0, 200.0))
    assert side == 200.0


def test_dead_zone_scales_with_side():
    assert WheelPresentationLayout.dead_zone_for(520.0) == pytest.approx(98.8)


def test_split_ratio_is_clamped():
    assert SettingsSplitLayout.sanitized_ratio(0.1) == 0.35
    assert SettingsSplitLayout.sanitized_ratio(0.9) == 0.75
    assert SettingsSplitLayout.wheel_width(1000.0, 0.6) == pytest.approx((1000.0 - 8.0) * 0.6)

    # 宽度足够时才保证轮盘不小于最小宽度
    assert SettingsSplitLayout.wheel_width(900.0, 0.35) >= SettingsSplitLayout.MIN_WHEEL_WIDTH - 1e-6

    # 窗口过窄、两侧最小宽度无法同时满足时，退化为按比例分配
    narrow = SettingsSplitLayout.wheel_width(500.0, 0.6)
    assert narrow == pytest.approx((500.0 - 8.0) * 0.6)
