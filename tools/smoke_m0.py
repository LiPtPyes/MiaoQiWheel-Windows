"""M0 冒烟测试：启动 Qt、弹出设置窗口、截图并报告内存占用。

用法：
    .venv\\Scripts\\python.exe tools\\smoke_m0.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import os

# 自检环境（CI / 无桌面会话）下用 offscreen 平台渲染，避免创建真实窗口。
# 本地真实运行时请勿设置该变量。
if os.environ.get("MQWHEEL_OFFSCREEN", "1") == "1":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import psutil  # noqa: E402


def rss_mb() -> float:
    return psutil.Process().memory_info().rss / 1024 / 1024


def main() -> int:
    print(f"[{rss_mb():6.1f} MB] 进程启动（仅 psutil）")

    from PySide6 import QtCore, QtGui, QtWidgets

    print(f"[{rss_mb():6.1f} MB] 导入 PySide6 后")

    from mqwheel.app_identity import APP_NAME, ORG_NAME

    QtCore.QCoreApplication.setApplicationName(APP_NAME)
    QtCore.QCoreApplication.setOrganizationName(ORG_NAME)
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QtGui.QFont("Microsoft YaHei UI", 9))
    print(f"[{rss_mb():6.1f} MB] QApplication 创建后")

    from mqwheel.models.settings import WheelSettings
    from mqwheel.views.settings_window import SettingsWindow

    print(f"[{rss_mb():6.1f} MB] 导入设置窗口模块后")

    window = SettingsWindow(WheelSettings())
    window.show()
    print(f"[{rss_mb():6.1f} MB] 设置窗口显示后")

    output = ROOT / "docs" / "m0-settings.png"
    output.parent.mkdir(parents=True, exist_ok=True)

    def finish() -> None:
        window.grab().save(str(output))
        print(f"[{rss_mb():6.1f} MB] 截图已保存 {output}")
        app.quit()

    QtCore.QTimer.singleShot(1200, finish)
    app.exec()
    print(f"[{rss_mb():6.1f} MB] 退出前")
    return 0


if __name__ == "__main__":
    sys.exit(main())
