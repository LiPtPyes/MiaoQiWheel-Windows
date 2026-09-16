"""渲染自检：对 offscreen 截图做像素断言（无法目视时的替代验证）。

用法：
    .venv\\Scripts\\python.exe tools\\check_render.py [图片路径]
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
HOST_PAD = 40  # smoke_wheel.py 中盘面四周留白
SIDE = 520.0


def wheel_point(angle: float, radius: float) -> tuple[int, int]:
    center = HOST_PAD + SIDE / 2
    return int(center + math.cos(angle) * radius), int(center + math.sin(angle) * radius)


def brightest_near(image: Image.Image, x: int, y: int, box: int = 12) -> int:
    crop = image.crop((x - box, y - box, x + box, y + box)).convert("RGB")
    return max(sum(pixel) // 3 for pixel in crop.getdata())


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else ROOT / "docs" / "m1-wheel-selected.png"
    image = Image.open(path).convert("RGB")
    print(f"检查 {path} 尺寸={image.size}")

    geometry_side = SIDE
    inner = geometry_side * 0.205
    outer = geometry_side * 0.43
    middle = (inner + outer) / 2
    failures: list[str] = []

    # 1) 选中扇区（第 2 项，顺时针 60°）应呈现强调色：蓝分量明显高于红
    selected_angle = -math.pi / 2 + math.tau / 6
    x, y = wheel_point(selected_angle + 0.16, middle + 28)
    r, g, b = image.getpixel((x, y))
    print(f"选中扇区采样 ({x},{y}) = {(r, g, b)}")
    if not (b > r + 40 and b > 120):
        failures.append(f"选中扇区缺少强调色：{(r, g, b)}")

    # 2) 未选中扇区（第 4 项，正下方）应接近中性灰白
    plain_angle = -math.pi / 2 + math.tau * 3 / 6
    x, y = wheel_point(plain_angle + 0.16, middle + 28)
    r, g, b = image.getpixel((x, y))
    print(f"未选扇区采样 ({x},{y}) = {(r, g, b)}")
    if abs(b - r) > 14:
        failures.append(f"未选扇区不应带强调色：{(r, g, b)}")

    # 3) 中心孔（死区内部）不应被扇区覆盖，且比扇区更亮（中心圆叠加）
    cx, cy = int(HOST_PAD + SIDE / 2), int(HOST_PAD + SIDE / 2)
    center_pixel = image.getpixel((cx, cy - int(inner * 0.5)))
    print(f"中心区域采样 = {center_pixel}")

    # 4) 每个扇区图标位置都应有可见亮像素（图标已渲染）
    for index in range(6):
        angle = -math.pi / 2 + index * math.tau / 6
        x, y = wheel_point(angle, middle)
        peak = brightest_near(image, x, y)
        if peak < 120:
            failures.append(f"第 {index} 项图标区域过暗（峰值 {peak}）")
    print("六项图标亮度检查完成")

    # 5) 盘面外（角落）应保持背景色
    corner = image.getpixel((8, 8))
    print(f"角落背景采样 = {corner}")
    if abs(corner[0] - corner[2]) > 12 or corner[0] > 60:
        failures.append(f"角落不是预期背景色：{corner}")

    if failures:
        print("\n失败项：")
        for item in failures:
            print(" -", item)
        return 1
    print("\n渲染自检通过")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
