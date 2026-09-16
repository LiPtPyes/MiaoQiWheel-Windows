"""轮盘几何测试：对齐 macOS 版 WheelGeometryTests 的断言。"""

from __future__ import annotations

import math

import pytest

from mqwheel.models.geometry import WheelGeometry
from mqwheel.models.layout import polygon_contains_point

SIDE = 520.0
CENTER = (0.0, 0.0)


def inset_boundary_point(angle, radius, offset, center=CENTER):
    """Swift 版 `insetBoundaryPoint` 的参考实现，用于校验采样法结果。"""
    off = max(min(offset, radius * 0.99), -radius * 0.99)
    distance = math.sqrt(max(radius * radius - off * off, 0.0))
    return (
        center[0] + math.cos(angle) * distance - math.sin(angle) * off,
        center[1] + math.sin(angle) * distance + math.cos(angle) * off,
    )


def test_sector_centers_are_evenly_distributed():
    geometry = WheelGeometry(item_count=8)
    for index in range(8):
        start, end = geometry.sector_angles(index)
        assert (start + end) / 2 == pytest.approx(
            -math.pi / 2 + index * (math.pi / 4), abs=1e-9
        )


def test_annular_segments_fit_one_shared_ring():
    geometry = WheelGeometry(item_count=6)
    inner, middle, outer = geometry.radii(SIDE)

    for index in range(geometry.item_count):
        points = geometry.segment_points(index, SIDE, CENTER)
        angle = -math.pi / 2 + index * geometry.sweep

        assert polygon_contains_point(
            points, geometry.point_at(angle, middle, CENTER)
        ), f"扇区 {index} 必须包含自己的中轴线"
        assert not polygon_contains_point(
            points, geometry.point_at(angle, inner - 2, CENTER)
        ), f"扇区 {index} 必须保留中心孔"
        assert not polygon_contains_point(
            points, geometry.point_at(angle, outer + 2, CENTER)
        ), f"扇区 {index} 不得超出外环"

        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        assert max(abs(x) for x in xs) <= outer + 1e-6
        assert max(abs(y) for y in ys) <= outer + 1e-6


def test_gap_separates_adjacent_segments():
    geometry = WheelGeometry(item_count=6, gap=8)
    inner, middle, outer = geometry.radii(SIDE)
    boundary_angle = -math.pi / 2 + geometry.sweep / 2
    boundary_point = geometry.point_at(boundary_angle, middle, CENTER)

    first = geometry.segment_points(0, SIDE, CENTER)
    second = geometry.segment_points(1, SIDE, CENTER)

    assert not polygon_contains_point(first, boundary_point)
    assert not polygon_contains_point(second, boundary_point)

    # 间隙宽度在内圈与外圈应基本一致（等宽间隙）
    half = geometry.half_gap(inner)
    assert half > 0
    assert abs(half - min(half, inner * math.sin(geometry.sweep / 2) * 0.8)) < 1e-9


def test_sampled_boundary_matches_analytic_offset():
    """采样多边形必须与 Swift 的 insetBoundaryPoint 解析结果一致。"""
    geometry = WheelGeometry(item_count=6)
    center = (137.0, 246.0)
    inner, _middle, outer = geometry.radii(SIDE)
    start, end = geometry.sector_angles(0)
    half = geometry.half_gap(inner)

    points = geometry.segment_points(0, SIDE, center, samples=96)
    assert points[0] == pytest.approx(inset_boundary_point(start, outer, half, center), abs=1e-6)
    assert points[96] == pytest.approx(inset_boundary_point(end, outer, -half, center), abs=1e-6)

    inner_first = points[97]
    assert inner_first == pytest.approx(inset_boundary_point(end, inner, -half, center), abs=1e-6)


def test_selection_index_maps_clockwise_from_top():
    geometry = WheelGeometry(item_count=6)
    radius = 100.0

    for index in range(6):
        point = geometry.point_at(geometry.sector_center_angle(index), radius, CENTER)
        assert geometry.selection_index(point, CENTER, 0.0) == index

    # 正上方属于第 0 项，正下方属于中间项
    assert geometry.selection_index((0.0, -radius), CENTER, 0.0) == 0
    assert geometry.selection_index((0.0, radius), CENTER, 0.0) == 3


def test_selection_index_respects_dead_zone():
    geometry = WheelGeometry(item_count=6)
    assert geometry.selection_index((0.0, 0.0), CENTER, 50.0) is None
    assert geometry.selection_index((0.0, -49.0), CENTER, 50.0) is None
    assert geometry.selection_index((0.0, -60.0), CENTER, 50.0) == 0


def test_selection_index_wraps_around_zero():
    geometry = WheelGeometry(item_count=12)
    radius = 100.0
    for index in range(12):
        point = geometry.point_at(geometry.sector_center_angle(index), radius, CENTER)
        assert geometry.selection_index(point, CENTER, 10.0) == index


def test_item_count_is_at_least_one():
    geometry = WheelGeometry(item_count=0)
    assert geometry.item_count == 1
    assert geometry.sweep == pytest.approx(math.tau)
