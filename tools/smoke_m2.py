"""M2 集成冒烟：真实组装 设置→热键→控制器→执行器，验证闭环并截图。

用法：
    .venv\\Scripts\\python.exe tools/smoke_m2.py

产出：docs/m2-wheel-active.png（呼出后命中第 2 项的效果，会镜像到
      website/assets/img/ 供 README 与官网引用）
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

from PySide6 import QtCore, QtGui, QtTest, QtWidgets  # noqa: E402

from mqwheel.controllers.overlay_controller import WheelOverlayController  # noqa: E402
from mqwheel.models.action import default_actions  # noqa: E402
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

    # 用真实默认项而不是「动作0…动作5」的桩数据：这个脚本顺手产出的
    # docs/m2-wheel-active.png 会镜像到 website/assets/img/，用默认项截图才像产品界面。
    # 功能断言不受影响 —— 执行器是 RecordingExecutor，不会真的去开 Edge 或终端。
    settings.actions = default_actions()
    check("设置回写", store.save(settings) and len(store.load().actions) == 6)

    # 2. 控制器呼出与命中
    executor = RecordingExecutor()
    controller = WheelOverlayController(settings, executor)
    center = QtCore.QPoint(640, 400)
    controller.show(center)
    window = controller._window
    check("呼出轮盘", controller.visible and window.width() > 0, f"边长 {window.width()}")

    # 先等入场动画跑完再落命中。呼出时 reveal 从 0 动画到 1，而 paintEvent 拿它当
    # painter.setOpacity()；offscreen 平台的定时器精度远低于真实窗口，processEvents()
    # 之后 reveal 往往还停在 0 附近，此时 render 出来是一张空白图（曾经就这样把纯色
    # 空白图当截图提交进仓库过，所以下面还加了非空断言）。
    docs = ROOT / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    deadline = QtCore.QElapsedTimer()
    deadline.start()
    while window.face.reveal < 0.999 and deadline.elapsed() < 3000:
        app.processEvents()
        QtTest.QTest.qWait(10)
    check("入场动画完成", window.face.reveal >= 0.999, f"reveal={window.face.reveal:.3f}")

    # 动画期间控制器的 16ms 轮询一直在按真实光标位置刷新选中项，而 offscreen 下光标
    # 并不在轮盘上，会把选中清空 —— 所以命中必须在动画稳定之后再落一次。
    geometry = WheelGeometry(6)
    side = min(window.width(), window.height())
    dx, dy = geometry.icon_point(1, side, (0.0, 0.0))
    target = window.mapToGlobal(
        QtCore.QPoint(int(window.width() / 2 + dx), int(window.height() / 2 + dy))
    )
    controller._update_selection(target)
    check("指针命中第 2 项", controller.selected_index == 1, f"index={controller.selected_index}")

    # 截图：窗口带 WA_TranslucentBackground，直接 grab() 拿到的是全透明位图，必须先铺一层
    # 不透明底色再 render（底色取主题面板色，与 m1-wheel.png 保持一致）。
    # 注意 render() 不处理事件，所以下面到 release() 之间不会有轮询把选中冲掉。
    shot = QtGui.QPixmap(window.size())
    shot.fill(QtGui.QColor("#1B1D21"))
    window.render(shot)
    shot.save(str(docs / "m2-wheel-active.png"))

    image = shot.toImage()
    distinct = {
        image.pixel(x, y)
        for y in range(0, image.height(), 5)
        for x in range(0, image.width(), 5)
    }
    check("截图非空白", len(distinct) > 20, f"{len(distinct)} 种颜色")

    # 3. 松开执行
    controller.release()
    # 用 is 比较而不是比标题：默认项标题可能随版本调整，这里要验证的是「执行的就是命中
    # 的那一项」，用同一性判断更贴题，也不会因为改文案而误报。
    executed = executor.calls[0] if executor.calls else None
    check(
        "松开执行",
        len(executor.calls) == 1 and executed is settings.actions[1],
        executed.title if executed is not None else "(未执行)",
    )
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
