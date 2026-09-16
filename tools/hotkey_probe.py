"""热键探针：安装低级钩子并打印真实按键事件，用于在本机验证钩子可用性与时序。

用法（双击或在终端执行）：
    .venv\\Scripts\\python.exe tools\\hotkey_probe.py [秒数]

观察点：
1. 是否正确打印「钩子已安装」；
2. 随便按几个键，确认能收到 down/up；
3. 按住 Tab 观察 armed → activate 的延迟是否符合预期。
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

if "selftest" in sys.argv:
    os.environ["MQWHEEL_SYNTHETIC"] = "1"  # 必须在导入 hotkey 之前设置

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6 import QtCore, QtWidgets  # noqa: E402

from mqwheel.models.settings import HotKeyConfig  # noqa: E402
from mqwheel.services.hotkey import HotKeyMonitor  # noqa: E402

KEY_NAMES = {
    0x09: "Tab",
    0x1B: "Esc",
    0x20: "Space",
    0x11: "Ctrl",
    0x12: "Alt",
    0x10: "Shift",
    0x5B: "Win",
}


def label(vk: int) -> str:
    return KEY_NAMES.get(vk, f"0x{vk:02X}")


def _self_test() -> int:
    """合成按键自检：用 SendInput 模拟一次长按与一次短按，验证整条链路。

    需要 MQWHEEL_SYNTHETIC=1（模块顶部根据 argv 设置），钩子才会把注入事件当作真实按键。
    """
    from mqwheel.services import input_sender

    app = QtWidgets.QApplication(sys.argv)

    def wait(seconds: float) -> None:
        """等待期间必须驱动事件循环，否则跨线程的信号送不进来。"""
        deadline = time.perf_counter() + seconds
        while time.perf_counter() < deadline:
            app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 20)
            time.sleep(0.005)

    config = HotKeyConfig(mode="hold", key="tab", hold_ms=200)
    monitor = HotKeyMonitor(config)

    log: list[str] = []
    monitor.activated.connect(lambda: log.append("activate"))
    monitor.released.connect(lambda: log.append("release"))
    monitor.failed.connect(lambda r: log.append(f"failed:{r}"))

    if not monitor.start():
        print("SELFTEST-FAIL 钩子未安装")
        return 1

    # 用例 1：长按 400ms 应呼出，松开应执行
    input_sender.send_down(0x09)
    wait(0.4)
    activated = "activate" in log
    input_sender.send_up(0x09)
    wait(0.2)

    # 用例 2：短按 50ms 不应呼出
    log.clear()
    input_sender.send_down(0x09)
    wait(0.05)
    input_sender.send_up(0x09)
    wait(0.4)

    monitor.stop()
    short_tap_silent = "activate" not in log

    print(f"SELFTEST 长按呼出={activated} 短按不误触={short_tap_silent}")
    ok = activated and short_tap_silent
    print("SELFTEST-PASS" if ok else "SELFTEST-FAIL")
    return 0 if ok else 1


def main() -> int:
    if "selftest" in sys.argv:
        return _self_test()

    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
    app = QtWidgets.QApplication(sys.argv)

    config = HotKeyConfig(mode="hold", key="tab", hold_ms=200)
    monitor = HotKeyMonitor(config)
    monitor.set_forward_keys(True)

    started = time.perf_counter()
    monitor.activated.connect(lambda: print(f"[{time.perf_counter() - started:6.2f}s] ACTIVATE（呼出轮盘）", flush=True))
    monitor.released.connect(lambda: print(f"[{time.perf_counter() - started:6.2f}s] RELEASE（执行）", flush=True))
    monitor.key_event.connect(
        lambda vk, down: print(f"[{time.perf_counter() - started:6.2f}s] key {label(vk)} {'down' if down else 'up'}", flush=True)
    )
    monitor.failed.connect(lambda reason: print(f"钩子安装失败：{reason}", flush=True))

    if not monitor.start():
        print("钩子未安装，请检查权限或以普通用户身份运行。", flush=True)
        return 1
    print(f"钩子已安装，监听 {seconds} 秒，请按键测试（按住 Tab 超过 200ms）…", flush=True)

    timer = QtCore.QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(app.quit)
    timer.start(int(seconds * 1000))
    app.exec()

    monitor.stop()
    print("已退出。", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
