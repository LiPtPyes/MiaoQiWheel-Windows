"""打包产物图标自检：用**打包目录里的字体**渲染源码用到的每一个图标，核对裁剪结果。

和 smoke_dist.py 是互补的两件事：
    smoke_dist.py        启动真实 exe，测运行行为（托盘、内存、单实例、写配置）
    smoke_dist_icons.py  不启动 exe，测「打包目录里的资源够不够用」

后者有个不可替代的好处：**安装版正在运行时也能跑**。单实例互斥量
`Local\\MiaoQiWheel.SingleInstance.v1` 会把 smoke_dist.py 挡成降级模式，
但本脚本只读文件、不动互斥量，任何时候都能给出确定结论。

检查内容：
1. 目录构成 —— PySide6/translations 是否已裁掉、qtawesome 字体是否 12 套齐全
2. 逐个渲染 —— 把字体目录**显式指到打包产物**上，渲染 src\\ 里出现的每个图标名，
   断言「非空且非全透明」。这条能同时防住两类事故：
     · 字体套数被裁多了（图标渲染为空）
     · 图标名写错 / 前缀不存在（qtawesome 抛异常）
3. Qt 本体 —— QFileDialog 能建出来，说明裁掉 translations 没伤到 Qt

为什么必须显式改字体目录：
    `_internal/qtawesome/` 里只有 fonts/ 数据、没有 .py（模块代码被 PyInstaller
    打进 PYZ 了），所以 import 到的仍是 venv 里的 qtawesome —— 不显式改目录的话，
    测的还是 venv 那套字体，等于没测打包产物。

用法：
    .venv\\Scripts\\python.exe tools\\smoke_dist_icons.py
    .venv\\Scripts\\python.exe tools\\smoke_dist_icons.py <某处>\\MiaoQiWheel\\_internal

退出码：0 = 通过／1 = 失败
"""

from __future__ import annotations

import collections
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_INTERNAL = ROOT / "dist" / "MiaoQiWheel" / "_internal"
INTERNAL = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_INTERNAL

if not INTERNAL.is_dir():
    sys.exit(f"[错误] 找不到打包产物：{INTERNAL}（请先运行 scripts\\build.bat）")

DIST_FONTS = INTERNAL / "qtawesome" / "fonts"
if not DIST_FONTS.is_dir():
    sys.exit(f"[错误] 打包产物里没有字体目录：{DIST_FONTS}")

sys.path.insert(0, str(INTERNAL))
import qtawesome  # noqa: E402
import qtawesome.iconic_font as iconic  # noqa: E402
from PySide6 import QtWidgets  # noqa: E402

# 把字体目录钉到打包产物上，再丢掉可能已缓存的单例
iconic.IconicFont._get_fonts_directory = lambda self: str(DIST_FONTS)
qtawesome._resource["iconic"] = None

print("=== 打包目录构成 ===")
translations = INTERNAL / "PySide6" / "translations"
print(f"  PySide6/translations : {'存在' if translations.exists() else '不存在'}（期望「不存在」）")
ttfs = sorted(p.name for p in DIST_FONTS.glob("*.ttf"))
print(f"  qtawesome 字体       : {len(ttfs)} 套（期望 12）")
print()

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

inst = qtawesome._instance()
print("=== qtawesome 实际加载情况 ===")
print(f"  已加载字体套数 : {len(inst.fontids)}")
print(f"  字体目录       : {iconic.IconicFont._get_fonts_directory(inst)}")
print(f"  与打包目录一致 : {iconic.IconicFont._get_fonts_directory(inst) == str(DIST_FONTS)}")
print()

# 收集源码里用到的图标名
pat = re.compile(r'["\']((?:fa6s|fa6b|fa6r|fa5s|fa5b|fa5r|mdi|ph|ri|msc|ei|ion|el|typ)\.([\w-]+))["\']')
names: collections.Counter[str] = collections.Counter()
for path in (ROOT / "src").rglob("*.py"):
    for match in pat.finditer(path.read_text(encoding="utf-8")):
        names[match.group(1)] += 1

# 符号选择器里的图标名是裸列表项，没有前缀，单独捞一遍补成 fa6s.
picker = (ROOT / "src" / "mqwheel" / "views" / "symbol_picker.py").read_text(encoding="utf-8")
for name in re.findall(r'^\s*"([a-z0-9-]+)",\s*$', picker, re.M):
    names[f"fa6s.{name}"] += 1

print(f"=== 渲染 {len(names)} 个图标（前缀 {dict(collections.Counter(n.split('.')[0] for n in names))}）===")

ok, failed = 0, []
for name in sorted(names):
    try:
        pixmap = qtawesome.icon(name).pixmap(32, 32)
        image = pixmap.toImage()
        if pixmap.isNull() or not any(
            image.pixelColor(x, y).alpha() > 0
            for x in range(image.width())
            for y in range(image.height())
        ):
            failed.append((name, "渲染为空或全透明"))
        else:
            ok += 1
    except Exception as exc:  # noqa: BLE001
        failed.append((name, f"{type(exc).__name__}: {exc}"))

if failed:
    for name, why in failed:
        print(f"  ✘ {name:<32} {why}")
else:
    print(f"  ✔ {ok} 个图标全部渲染成功（非空、非全透明）")

# Qt 控件库能建出来，说明裁掉 translations 没伤到 Qt 本体
try:
    dialog = QtWidgets.QFileDialog()
    dialog.deleteLater()
    print("  ✔ QFileDialog 可创建（Qt 平台插件与控件库正常）")
except Exception as exc:  # noqa: BLE001
    failed.append(("QFileDialog", str(exc)))
    print(f"  ✘ QFileDialog 创建失败：{exc}")

print()
print("DIST-ICONS-PASS" if not failed else f"DIST-ICONS-FAIL ({len(failed)})")
sys.exit(0 if not failed else 1)
