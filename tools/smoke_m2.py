"""M2 集成冒烟：真实组装 设置→热键→控制器→执行器，验证闭环并截图。

用法：
    .venv\\Scripts\\python.exe tools/smoke_m2.py

产出：docs/m2-wheel-active.png（呼出后选中第 2 项的效果）
打印：各环节的自检结果，全部为 PASS 才算通过。
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

from mqwheel.controllers.overlay_controller import WheelOverlayController  # noqa: E402
from mqwheel.models.action import WheelAction, WheelActionKind  # noqa: E402
from mqwheel.models.geometry import WheelGeometry  # noqa: E402
from mqwheel.models.settings import WheelSettings  # noqa: E402
from mqwheel.services.action_executor import ActionExecutor  # noqa: E402
from mqwheel.services.hotkey import HotKeyMonitor  # noqa: E402
from mqwheel.services.settings_store import SettingsStore  # noqa: E402

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{(' — ' + detail) if detail else ''}")


class RecordingExecutor(ActionExecutor):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[WheelAction] = []

    def execute(self, action: WheelAction) -> bool:
        self.calls.append(action)
        return True


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    app.setFont(QtGui.QFont("Microsoft YaHei UI", 9))

    # 1. 设置持久化
    store = SettingsStore(ROOT / "docs" / "_m2-settings.json")
    settings = store.load()
    check("设置文件生成", store.exists() and len(settings.actions) == 6,
          f"{len(settings.actions)} 个默认选项")

    settings.actions = [
        WheelAction(title=f"动作{i}", kind=WheelActionKind.SHELL_COMMAND, payload=f"echo {i}")
        for i in range(6)
    ]
    check("设置回写", store.save(settings) and len(store.load().actions) == 6)

    # 2. 控制器呼出与命中
    executor = RecordingExecutor()
    controller = WheelOverlayController(settings, executor)
    center = QtCore.QPoint(640, 400)
    controller.show(center)
    window = controller._window
    check("呼出轮盘", controller.visible and window.width() > 0, f"边长 {window.width()}")

    geometry = WheelGeometry(6)
    side = min(window.width(), window.height())
    dx, dy = geometry.icon_point(1, side, (0.0, 0.0))
    target = window.mapToGlobal(
        QtCore.QPoint(int(window.width() / 2 + dx), int(window.height() / 2 + dy))
    )
    controller._update_selection(target)
    check("指针命中第 2 项", controller.selected_index == 1, f"index={controller.selected_index}")

    app.processEvents()
    docs = ROOT / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    window.grab().save(str(docs / "m2-wheel-active.png"))

    # 3. 松开执行
    controller.release()
    check("松开执行", len(executor.calls) == 1 and executor.calls[0].title == "动作1")
    check("执行后自动隐藏", not controller.visible)

    # 4. 中心死区取消
    controller.show(center)
    controller._update_selection(
        window.mapToGlobal(QtCore.QPoint(window.width() // 2, window.height() // 2))
    )
    controller.release()
    check("中心死区取消", controller.selected_index is None and len(executor.calls) == 1)

    # 5. 热键钩子
    monitor = HotKeyMonitor(settings.hotkey)
    installed = monitor.start()
    check("热键钩子安装", installed, settings.hotkey.display_text())
    monitor.stop()
    check("热键钩子卸载", not monitor.installed)

    failed = [name for name, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
