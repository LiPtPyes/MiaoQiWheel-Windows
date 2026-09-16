"""M3 自检：预设清单 + 图标可渲染性 + 内置动作实现完整性。

用法：
    .venv\\Scripts\\python.exe tools/smoke_m3.py              # 只检查，不执行任何动作
    .venv\\Scripts\\python.exe tools/smoke_m3.py --run copy-text --param text=你好

产出：docs/m3-presets.png（所有预设图标一览，用于肉眼确认图标是否对得上）
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

from mqwheel.models.action import WheelActionKind  # noqa: E402
from mqwheel.models.presets import BUILTINS, by_category  # noqa: E402
from mqwheel.services import builtin_actions  # noqa: E402
from mqwheel.services.symbol_icons import symbol_pixmap  # noqa: E402

CELL = 120
COLUMNS = 6
ICON_SIZE = 44


def print_inventory() -> None:
    print("== 预设清单 ==")
    for category, presets in by_category().items():
        print(f"\n[{category}] {len(presets)} 项")
        for preset in presets:
            kind = WheelActionKind(preset.kind).title
            params = ",".join(f"{p.id}={p.default}" for p in preset.parameters) or "-"
            print(f"  {preset.id:<22} {kind:<6} 参数[{params}]")
            print(f"      {preset.command()}")


def render_grid(output: Path) -> list[str]:
    """把所有预设图标画成网格，返回渲染失败的预设 id。"""
    rows = (len(BUILTINS) + COLUMNS - 1) // COLUMNS
    image = QtGui.QImage(
        CELL * COLUMNS, CELL * rows + 10, QtGui.QImage.Format.Format_ARGB32
    )
    image.fill(QtGui.QColor("#1b1d21"))

    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    font = QtGui.QFont("Microsoft YaHei UI", 9)
    painter.setFont(font)
    failures: list[str] = []

    for index, preset in enumerate(BUILTINS):
        column, row = index % COLUMNS, index // COLUMNS
        left, top = column * CELL, row * CELL + 10

        pixmap = symbol_pixmap(preset.symbol, ICON_SIZE, "#FFFFFF")
        if pixmap is None or pixmap.isNull():
            failures.append(preset.id)
        else:
            # 统计非透明像素，防止字体缺字导致画出空白
            opaque = sum(
                1
                for x in range(0, pixmap.width(), 2)
                for y in range(0, pixmap.height(), 2)
                if pixmap.toImage().pixelColor(x, y).alpha() > 16
            )
            if opaque < 8:
                failures.append(f"{preset.id}(空图标)")
            painter.drawPixmap(
                left + (CELL - ICON_SIZE) // 2, top + 18, pixmap
            )

        painter.setPen(QtGui.QColor("#D6E6F5"))
        painter.drawText(
            QtCore.QRect(left, top + 70, CELL, 18),
            QtCore.Qt.AlignmentFlag.AlignHCenter,
            preset.title,
        )
        painter.setPen(QtGui.QColor("#7C8896"))
        painter.drawText(
            QtCore.QRect(left, top + 88, CELL, 16),
            QtCore.Qt.AlignmentFlag.AlignHCenter,
            preset.id,
        )
    painter.end()

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(output))
    return failures


def check_implementations() -> list[str]:
    missing = []
    for preset in BUILTINS:
        if preset.kind == WheelActionKind.BUILTIN.value and preset.id not in builtin_actions.REGISTRY:
            missing.append(preset.id)
    return missing


def main() -> int:
    if "--run" in sys.argv:
        return run_preset()

    # qtawesome 依赖 QFontDatabase，必须先有 QApplication
    QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

    print_inventory()

    missing = check_implementations()
    print(f"\n内置动作实现：{'全部齐全' if not missing else '缺失 ' + str(missing)}")

    output = ROOT / "docs" / "m3-presets.png"
    failures = render_grid(output)
    print(f"图标渲染：{len(BUILTINS) - len(failures)}/{len(BUILTINS)} 通过 -> {output.name}")
    if failures:
        print(f"  失败：{failures}")

    return 1 if (missing or failures) else 0


def run_preset() -> int:
    """手动试跑一个预设：--run <id> [--param key=value ...]"""
    preset_id = sys.argv[sys.argv.index("--run") + 1]
    preset = next((p for p in BUILTINS if p.id == preset_id), None)
    if preset is None:
        print(f"没有预设 {preset_id}")
        return 1

    values: dict[str, str] = {}
    for argument in sys.argv[sys.argv.index("--run") + 2 :]:
        if argument.startswith("--param="):
            key, _, value = argument[len("--param=") :].partition("=")
            values[key] = value

    action = preset.make_action(values)
    print(f"预设：{preset.title}")
    print(f"类型：{WheelActionKind(action.kind).title}")
    print(f"命令：{action.payload}")
    print(f"参数：{action.preset_params}")

    from mqwheel.services.action_executor import ActionExecutor

    executor = ActionExecutor()
    ok = executor.execute(action)
    print(f"执行：{'成功' if ok else '失败 — ' + (executor.last_error or '')}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
