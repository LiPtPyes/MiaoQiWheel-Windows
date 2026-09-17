"""图标名自检：确认程序里引用的 FontAwesome 名字都真实存在。

**为什么需要它**：`symbol_icon()` 在拿不到图标时返回 `None`，调用方回退成
`fallback_pixmap()` 画的**描边圆环**。也就是说拼错图标名**不会报错、不会崩**，
只是那个位置安静地变成一个圆圈 —— 靠肉眼翻界面很难发现。

**为什么不能查 `qta._instance().charmap`**：qtawesome 6.x 里那个属性是**空 dict**，
拿它做成员判断会把 `lock` / `terminal` / `window-maximize` 这类有效名全判成无效。
唯一可靠的判据是真正构造一次图标：无效名会抛
`Exception: Invalid icon name "xxx" in font "fa6s"`。

**为什么要连运行时清单一起查**：图标名有两种存在形式 ——
- 源码字面量 `"fa6s.lock"`（正则扫得到）；
- **裸名字 + 前缀拼接**，如 `symbol_picker.CURATED` 里写 `"lock"`，
  再由 `f"fa6s.{name}"` 拼出来（正则只能扫到模板，清单本身是盲区）。
所以两种来源都要覆盖，缺一不可。

用法：`.venv/Scripts/python.exe tools/check_icons.py`
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

LITERAL_RE = re.compile(r"fa6s\.([a-z0-9-]+)")
# 裸名字列表：`CURATED: tuple[str, ...] = (...)` 这类模块级清单
PROBE_NAME = "definitely-not-a-real-icon"


def literal_names() -> set[str]:
    """源码里写死的 `fa6s.xxx`。"""
    names: set[str] = set()
    for path in SRC.rglob("*.py"):
        names.update(LITERAL_RE.findall(path.read_text(encoding="utf-8")))
    return names


def runtime_names() -> tuple[set[str], list[str]]:
    """程序自己会去取的图标名（含裸名字拼接出来的），以及收集过程中的问题。"""
    notes: list[str] = []
    names: set[str] = set()

    from PySide6 import QtWidgets

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    from mqwheel.views.symbol_picker import CURATED, symbol_names

    # 选择器清单：这是裸名字，正则扫不到，必须从运行时拿。
    names.update(name.removeprefix("fa6s.") for name in symbol_names())
    notes.append(f"图标选择器清单 CURATED {len(CURATED)} 项")

    # 动作类型自带的默认符号
    from mqwheel.models.action import WheelAction, WheelActionKind

    kinds = [m for m in vars(WheelActionKind).values() if isinstance(m, str)]
    for kind in kinds:
        action = WheelAction(title="探针", kind=kind, payload="")
        if action.symbol.startswith("fa6s."):
            names.add(action.symbol.removeprefix("fa6s."))
    notes.append(f"动作类型默认符号 {len(kinds)} 个 kind")

    return names, notes


def main() -> int:
    names = literal_names()
    literal_count = len(names)

    runtime, notes = runtime_names()
    names |= runtime

    import qtawesome as qta

    bad: list[tuple[str, str]] = []
    for name in sorted(names):
        try:
            qta.icon(f"fa6s.{name}")
        except Exception as exc:  # noqa: BLE001 - 判据就是「抛没抛」
            bad.append((name, f"{type(exc).__name__}: {exc}"))

    # 判据自检：故意塞一个不存在的名字，必须抛异常。
    # 否则说明这版 qtawesome 不校验名字，整个脚本就是在走过场。
    try:
        qta.icon(f"fa6s.{PROBE_NAME}")
        print("判据自检：失败 —— 无效名没抛异常，这个方法测不到东西")
        return 3
    except Exception:
        pass

    print("=" * 62)
    print(f"源码字面量 {literal_count} 个 / 运行时清单补充 {len(names) - literal_count} 个")
    for note in notes:
        print(f"  · {note}")
    print(f"合计检查 {len(names)} 个图标名，无效 {len(bad)} 个")
    for name, err in bad:
        print(f"  ✗ fa6s.{name}")
        print(f"      {err}")
    print("=" * 62)

    if bad:
        print("CHECK-ICONS-FAIL：上面这些名字会被静默替换成占位圆环")
        return 1
    print("CHECK-ICONS-PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
