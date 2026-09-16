"""M4 自检：渲染四页设置窗口截图，并逐个验证精选图标名是否有效。

用法：
    .venv\\Scripts\\python.exe tools\\smoke_m4.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402

from mqwheel.models.settings import WheelSettings  # noqa: E402
from mqwheel.services.symbol_icons import symbol_pixmap  # noqa: E402
from mqwheel.views import theme  # noqa: E402
from mqwheel.views.settings_window import SettingsWindow  # noqa: E402
from mqwheel.views.symbol_picker import CURATED  # noqa: E402

DOCS = ROOT / "docs"


def _has_ink(pixmap: QtGui.QPixmap) -> bool:
    """图标是否真的画出了东西（防止字体缺字画成空白）。"""
    image = pixmap.toImage().convertToFormat(QtGui.QImage.Format.Format_ARGB32)
    for y in range(0, image.height(), 2):
        for x in range(0, image.width(), 2):
            if image.pixelColor(x, y).alpha() > 16:
                return True
    return False


def check_symbols() -> int:
    missing = []
    for name in CURATED:
        pixmap = symbol_pixmap(f"fa6s.{name}", 32, "#FFFFFF")
        if pixmap is None or pixmap.isNull() or not _has_ink(pixmap):
            missing.append(name)
    total = len(CURATED)
    print(f"[图标] 精选列表 {total} 个，无效 {len(missing)} 个")
    if missing:
        print("       无效：", ", ".join(missing))
    return 0 if not missing else 1


def shoot(window: QtWidgets.QMainWindow, name: str) -> bool:
    DOCS.mkdir(exist_ok=True)
    path = DOCS / name
    pixmap = window.grab()
    ok = pixmap.save(str(path))
    print(f"[截图] {name} {pixmap.width()}x{pixmap.height()} -> {'ok' if ok else 'FAIL'}")
    return ok


def main() -> int:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setFont(QtGui.QFont("Microsoft YaHei UI", 9))
    theme.apply(app)

    failed = check_symbols()

    settings = WheelSettings()
    window = SettingsWindow(settings)
    window.resize(1020, 660)
    window.show()
    app.processEvents()

    shots = ["m4-general.png", "m4-actions.png", "m4-help.png", "m4-about.png"]
    for index, name in enumerate(shots):
        window._sidebar.setCurrentRow(index)
        app.processEvents()
        if not shoot(window, name):
            failed = 1

    # 选中一个有预设参数的选项，确认参数表单能渲染出来
    window._sidebar.setCurrentRow(1)
    app.processEvents()
    page = window._actions
    page._list.setCurrentRow(0)
    app.processEvents()
    editor = page._editor
    preset_box = editor.findChildren(QtWidgets.QComboBox)[1]
    index = preset_box.findData("shutdown")
    if index >= 0:
        preset_box.setCurrentIndex(index)
        app.processEvents()
        shoot(window, "m4-action-preset.png")
        print(f"[预设] shutdown payload = {editor.collect().payload!r}")

    window.close()
    print("SMOKE", "FAIL" if failed else "PASS")
    return failed


if __name__ == "__main__":
    sys.exit(main())
