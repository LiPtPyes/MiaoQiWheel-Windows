"""应用入口：单实例保护 + 系统托盘 + 热键闭环 + 延迟加载的设置窗口。

低内存策略：
- 常驻时只导入 QtCore/QtGui/QtWidgets 与标准库；
- 设置窗口在首次打开时才导入（qtawesome 等重依赖同理）；
- 单实例使用 Win32 互斥量，不引入 QtNetwork。
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # 允许以脚本方式直接运行
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mqwheel.app_identity import (  # noqa: E402
    APP_ICON_PATH,
    APP_NAME,
    ORG_NAME,
    SINGLE_INSTANCE_MUTEX,
    config_dir,
)
from mqwheel.services.win32_ext import SingleInstanceGuard  # noqa: E402


def _install_crash_hook() -> None:
    """打包为 windowed 后没有控制台，未捕获异常必须落盘，否则无从反馈。"""
    import traceback
    from datetime import datetime

    def write(text: str) -> None:
        try:
            base = config_dir()
            base.mkdir(parents=True, exist_ok=True)
            with open(base / "crash.log", "a", encoding="utf-8") as handle:
                handle.write(f"\n=== {datetime.now():%Y-%m-%d %H:%M:%S} ===\n{text}")
        except OSError:
            pass

    def handler(exc_type, exc, tb) -> None:
        write("".join(traceback.format_exception(exc_type, exc, tb)))
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = handler


def _configure_high_dpi() -> None:
    """多屏不同缩放比时不要取整 DPR，否则 125%/150% 屏上轮盘会偏小或模糊。

    必须在 QApplication 构造之前设置；不同 Qt 版本枚举挂载位置不同，逐个尝试。
    """
    from PySide6 import QtCore, QtGui

    policy = None
    for holder in (QtCore.Qt, QtGui):
        enum = getattr(holder, "HighDpiScaleFactorRoundingPolicy", None)
        if enum is not None:
            policy = getattr(enum, "PassThrough", None)
            if policy is not None:
                break
    if policy is None:
        return
    try:
        QtGui.QGuiApplication.setHighDpiScaleFactorRoundingPolicy(policy)
    except Exception:
        pass


def _build_application() -> "object":
    from PySide6 import QtCore, QtGui, QtWidgets

    _configure_high_dpi()

    QtCore.QCoreApplication.setApplicationName(APP_NAME)
    QtCore.QCoreApplication.setOrganizationName(ORG_NAME)
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)

    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QtGui.QFont("Microsoft YaHei UI", 9))

    from mqwheel.views import theme

    theme.apply(app)
    return app


def _load_icon() -> "object":
    from PySide6 import QtGui, QtWidgets

    if APP_ICON_PATH.exists():
        return QtGui.QIcon(str(APP_ICON_PATH))
    return QtWidgets.QApplication.style().standardIcon(
        QtWidgets.QStyle.StandardPixmap.SP_ComputerIcon
    )


def main() -> int:
    _install_crash_hook()

    guard = SingleInstanceGuard(SINGLE_INSTANCE_MUTEX)
    if guard.already_running:
        # 已有实例在托盘中运行，直接退出即可。
        return 0

    app = _build_application()

    from PySide6 import QtWidgets

    from mqwheel.controllers.overlay_controller import WheelOverlayController
    from mqwheel.services.action_executor import ActionExecutor
    from mqwheel.services.hotkey import HotKeyMonitor
    from mqwheel.services.settings_store import SettingsStore

    store = SettingsStore()
    settings = store.load()
    executor = ActionExecutor()
    controller = WheelOverlayController(settings, executor)
    monitor = HotKeyMonitor(settings.hotkey)

    tray = QtWidgets.QSystemTrayIcon(_load_icon(), None)
    tray.setToolTip(APP_NAME)

    menu = QtWidgets.QMenu()
    action_settings = menu.addAction("打开设置…")
    action_test = menu.addAction("显示轮盘（测试）")
    menu.addSeparator()
    action_quit = menu.addAction(f"退出{APP_NAME}")
    tray.setContextMenu(menu)

    settings_window: QtWidgets.QMainWindow | None = None

    def show_settings() -> None:
        nonlocal settings_window
        if settings_window is None:
            from mqwheel.views.settings_window import SettingsWindow

            settings_window = SettingsWindow(settings)
            settings_window.settings_changed.connect(on_settings_changed)
        settings_window.show()
        settings_window.raise_()
        settings_window.activateWindow()

    def on_settings_changed(updated) -> None:
        """设置页改动：落盘 → 立即生效 → 按需重配热键。"""
        nonlocal settings
        hotkey_changed = updated.hotkey.to_dict() != settings.hotkey.to_dict()
        settings = updated
        if not store.save(settings):
            notify("设置保存失败", f"无法写入 {store.path}", QtWidgets.QSystemTrayIcon.MessageIcon.Warning)
        controller.set_settings(settings)
        if hotkey_changed:
            monitor.update_config(settings.hotkey)
            if not monitor.installed and not monitor.start():
                on_hook_failed("切换快捷键后钩子未能重新安装")

    def notify(title: str, text: str, icon=None) -> None:
        tray.showMessage(
            title,
            text,
            icon or QtWidgets.QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    def on_activated() -> None:
        controller.show()
        monitor.set_forward_keys(True)

    def on_released() -> None:
        monitor.set_forward_keys(False)
        controller.release()

    def on_key(vk: int, is_down: bool) -> None:
        controller.handle_key(vk, is_down)

    def on_executed(action, ok: bool) -> None:
        if not ok:
            notify("执行失败", f"{action.title}：{executor.last_error or '未知错误'}",
                   QtWidgets.QSystemTrayIcon.MessageIcon.Warning)

    def on_hook_failed(reason: str) -> None:
        notify("热键不可用", f"{reason}\n请以普通权限重启应用，或在设置中更换触发方式。",
               QtWidgets.QSystemTrayIcon.MessageIcon.Critical)

    monitor.activated.connect(on_activated)
    monitor.released.connect(on_released)
    monitor.key_event.connect(on_key)
    monitor.failed.connect(on_hook_failed)
    controller.action_executed.connect(on_executed)

    action_test.triggered.connect(controller.show)
    action_settings.triggered.connect(show_settings)
    action_quit.triggered.connect(app.quit)

    def on_tray_activated(reason: QtWidgets.QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QtWidgets.QSystemTrayIcon.ActivationReason.Trigger,
            QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            show_settings()

    tray.activated.connect(on_tray_activated)
    tray.show()

    if not monitor.start():
        on_hook_failed("低级键盘钩子安装失败")
    else:
        notify(
            APP_NAME,
            f"已在后台运行：{settings.hotkey.display_text()} 呼出轮盘",
        )

    app.aboutToQuit.connect(monitor.stop)
    exit_code = app.exec()
    guard.release()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
