"""M1 自检：offscreen 渲染轮盘盘面并截图。

用法：
    .venv\\Scripts\\python.exe tools\\smoke_wheel.py
产出：docs/m1-wheel.png（未选中）、docs/m1-wheel-selected.png（选中第 2 项）
"""

from __future__ import annotations

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


def render(selected: int | None, output: Path) -> None:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setFont(QtGui.QFont("Microsoft YaHei UI", 9))

    host = QtWidgets.QWidget()
    host.setFixedSize(SIDE + 80, SIDE + 80)
    host.setStyleSheet("background-color: #1b1d21;")
    layout = QtWidgets.QVBoxLayout(host)
    layout.setContentsMargins(40, 40, 40, 40)

    face = WheelFaceWidget(host)
    face.setFixedSize(SIDE, SIDE)
    face.set_actions(default_actions())
    face.set_selected_index(selected)
    layout.addWidget(face)

    host.show()
    app.processEvents()
    shot = host.grab()
    # 空白守卫：轮盘本体是半透明绘制的，一旦宿主底色没铺上、或入场动画的 reveal
    # 还停在 0（painter.setOpacity(0)），截出来就是一张纯色图，肉眼在缩略图里根本
    # 看不出来。这里按颜色数做断言，宁可让自检失败也不要提交空白截图。
    image = shot.toImage()
    distinct = {
        image.pixel(x, y)
        for y in range(0, image.height(), 5)
        for x in range(0, image.width(), 5)
    }
    if len(distinct) <= 20:
        raise SystemExit(f"渲染结果疑似空白：{output} 只有 {len(distinct)} 种颜色")
    shot.save(str(output))
    print(f"已保存 {output}（selected={selected}，{len(distinct)} 种颜色）")


def main() -> int:
    docs = ROOT / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    render(None, docs / "m1-wheel.png")
    render(1, docs / "m1-wheel-selected.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
