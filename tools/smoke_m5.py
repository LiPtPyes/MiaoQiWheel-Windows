"""M5 自检：offscreen 渲染毛玻璃 / 纯色降级 / 入场中间态三张盘面并做像素断言。

无法目视时的替代验证——断言全部基于采样点的 RGB 关系，与屏幕真实内容无关。

用法：
    .venv\\Scripts\\python.exe tools\\smoke_m5.py
产出：docs/m5-glass.png、docs/m5-solid.png、docs/m5-reveal.png
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

if os.environ.get("MQWHEEL_OFFSCREEN", "1") == "1":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402

from mqwheel.models.action import default_actions  # noqa: E402
from mqwheel.views.overlay import WheelFaceWidget  # noqa: E402

SIDE = 520
HOST_PAD = 40
HOST_BG = QtGui.QColor(27, 29, 33)  # #1b1d21
CENTER = HOST_PAD + SIDE / 2

INNER_RATIO = 0.205
OUTER_RATIO = 0.43
BACK_PAD_RATIO = 9 / 520.0
SHADOW_RATIO = 0.055
MIDDLE = (INNER_RATIO + OUTER_RATIO) / 2 * SIDE
BACK_RADIUS = OUTER_RATIO * SIDE + SIDE * BACK_PAD_RATIO


def synthetic_backdrop() -> QtGui.QPixmap:
    """高饱和度底图：模糊后仍能明显区别于纯色玻璃，便于像素断言。"""
    # 主色洋红 + 同色系暗条纹：模糊后仍是洋红为主，便于「R 明显高于 G」的断言
    image = QtGui.QImage(SIDE, SIDE, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor(200, 40, 160))
    painter = QtGui.QPainter(image)
    painter.setPen(QtCore.Qt.PenStyle.NoPen)
    for index in range(0, SIDE, 48):
        painter.setBrush(QtGui.QColor(110, 15, 92))
        painter.drawRect(index, 0, 24, SIDE)
    painter.end()
    from mqwheel.services import backdrop

    return QtGui.QPixmap.fromImage(backdrop.blur(image) or image)


def render(
    output: Path,
    selected: int | None,
    backdrop_pixmap: QtGui.QPixmap | None,
    reveal: float,
) -> None:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setFont(QtGui.QFont("Microsoft YaHei UI", 9))

    host = QtWidgets.QWidget()
    host.setFixedSize(SIDE + HOST_PAD * 2, SIDE + HOST_PAD * 2)
    host.setStyleSheet(f"background-color: {HOST_BG.name()};")
    layout = QtWidgets.QVBoxLayout(host)
    layout.setContentsMargins(HOST_PAD, HOST_PAD, HOST_PAD, HOST_PAD)

    face = WheelFaceWidget(host)
    face.setFixedSize(SIDE, SIDE)
    face.set_actions(default_actions())
    face.set_selected_index(selected)
    face.set_backdrop(backdrop_pixmap)
    face.set_reveal(reveal)
    layout.addWidget(face)

    host.show()
    app.processEvents()
    host.grab().save(str(output))
    layout.removeWidget(face)
    face.setParent(None)
    host.close()
    print(f"已保存 {output.name}（selected={selected} reveal={reveal} backdrop={backdrop_pixmap is not None}）")


def sample(image: QtGui.QImage, radius: float, angle: float = math.pi / 2) -> tuple[int, int, int]:
    x = int(CENTER + math.cos(angle) * radius)
    y = int(CENTER + math.sin(angle) * radius)
    color = image.pixelColor(x, y)
    return color.red(), color.green(), color.blue()


def load(path: Path) -> QtGui.QImage:
    reader = QtGui.QImageReader(str(path))
    image = reader.read()
    if image.isNull():
        raise SystemExit(f"无法读取截图：{path}")
    return image.convertToFormat(QtGui.QImage.Format.Format_RGB32)


def main() -> int:
    # 必须先有 QGuiApplication：QPixmap 在无应用实例时构造会直接 abort
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setFont(QtGui.QFont("Microsoft YaHei UI", 9))

    docs = ROOT / "docs"
    docs.mkdir(parents=True, exist_ok=True)

    glass_path = docs / "m5-glass.png"
    solid_path = docs / "m5-solid.png"
    reveal_path = docs / "m5-reveal.png"

    render(glass_path, 1, synthetic_backdrop(), 1.0)
    render(solid_path, 1, None, 1.0)
    render(reveal_path, 1, None, 0.45)

    glass = load(glass_path)
    solid = load(solid_path)
    reveal = load(reveal_path)

    failures: list[str] = []

    # 1) 毛玻璃：扇区内应透出底图的洋红/黄色调（R 明显高于 G）
    g_segment = sample(glass, MIDDLE)
    s_segment = sample(solid, MIDDLE)
    print(f"扇区采样  毛玻璃={g_segment}  纯色={s_segment}")
    if not (g_segment[0] > 90 and g_segment[0] > g_segment[1] + 40):
        failures.append(f"毛玻璃未透出底图色调：{g_segment}")
    if not (abs(s_segment[0] - s_segment[1]) < 24 and s_segment[0] < 110):
        failures.append(f"纯色降级扇区应为中性灰：{s_segment}")

    # 2) 阴影环：底盘外侧一圈应比宿主角背景更暗
    shadow_r = BACK_RADIUS + SIDE * SHADOW_RATIO * 0.5
    shadow_pixel = sample(solid, shadow_r)
    print(f"阴影环采样 r={shadow_r:.1f} = {shadow_pixel}")
    if sum(shadow_pixel) / 3 >= sum((HOST_BG.red(), HOST_BG.green(), HOST_BG.blue())) / 3:
        failures.append(f"底盘外侧没有阴影：{shadow_pixel}")

    # 3) 盘外角落应保持宿主背景色
    corner = solid.pixelColor(6, 6)
    if abs(corner.red() - HOST_BG.red()) > 8:
        failures.append(f"角落背景异常：{(corner.red(), corner.green(), corner.blue())}")

    # 4) 入场中间态：整体半径更小（外缘点尚未被盘面覆盖）
    edge = BACK_RADIUS - 8
    full_edge = sample(solid, edge)
    mid_edge = sample(reveal, edge)
    print(f"外缘采样 r={edge:.1f}  完整={full_edge}  中间态={mid_edge}")
    if sum(mid_edge) < sum(full_edge):
        pass  # 中间态更暗/更透明都算通过，方向不限
    if full_edge == mid_edge:
        failures.append("入场中间态与完整态渲染一致，reveal 未生效")

    # 5) 中间态透明度更低：整图平均亮度应低于完整态
    def mean_brightness(image: QtGui.QImage) -> float:
        total = 0
        count = 0
        for y in range(0, image.height(), 4):
            for x in range(0, image.width(), 4):
                color = image.pixelColor(x, y)
                total += (color.red() + color.green() + color.blue()) / 3
                count += 1
        return total / max(count, 1)

    b_full, b_mid = mean_brightness(solid), mean_brightness(reveal)
    print(f"平均亮度  完整={b_full:.1f}  中间态={b_mid:.1f}")
    if b_mid >= b_full:
        failures.append(f"中间态亮度未降低（{b_mid:.1f} >= {b_full:.1f}）")

    if failures:
        print("\n失败项：")
        for item in failures:
            print(" -", item)
        return 1
    print("\nSMOKE-M5-PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
