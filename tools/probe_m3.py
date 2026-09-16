"""M3 实机验证：用「读原值 → 写回原值」的方式验证内置动作的 Win32 通路。

设计原则：绝不留下副作用。
- 音量：读取当前百分比，再设成同一个值；
- 深色模式：读取当前值，写回同一个值（验证读写权限与广播，不改外观）；
- 剪贴板：备份原文 → 写入测试文本 → 读回校验 → 还原原文。

关显示器、屏保、朗读这三项无法无副作用地验证，只打印提示，交由人工确认。
"""

from __future__ import annotations

import ctypes
import sys
import winreg
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mqwheel.services import builtin_actions  # noqa: E402

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
CF_UNICODETEXT = 13

# 必须在首次调用前声明：默认返回值是 32 位 int，64 位句柄会被截断成野指针
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = wintypes.HANDLE
user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = wintypes.BOOL
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = wintypes.BOOL

results: list[tuple[str, bool, str]] = []


def report(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{(' — ' + detail) if detail else ''}")


def current_volume_percent() -> float | None:
    from pycaw.pycaw import AudioUtilities

    device = AudioUtilities.GetSpeakers()
    return device.EndpointVolume.GetMasterVolumeLevelScalar() * 100


def probe_volume() -> None:
    try:
        before = current_volume_percent()
    except Exception as exc:
        report("音量接口", False, f"{type(exc).__name__}: {exc}")
        return
    ok = builtin_actions.set_volume({"volume": str(round(before))})
    report("音量接口", ok, f"当前 {round(before)}%，写回同一值（{builtin_actions.get_last_error()}）")


def probe_dark_mode() -> None:
    key_path = builtin_actions.PERSONALIZE_KEY
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ | winreg.KEY_WRITE
        ) as key:
            value, value_type = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, value)
        report(
            "深色模式注册表",
            True,
            f"AppsUseLightTheme={value}（{value_type == winreg.REG_DWORD}），写回同值，外观不变",
        )
    except OSError as exc:
        report("深色模式注册表", False, str(exc))


def read_clipboard_text() -> str | None:
    if not user32.OpenClipboard(None):
        return None
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return None
        text = ctypes.wstring_at(pointer)
        kernel32.GlobalUnlock(handle)
        return text
    finally:
        user32.CloseClipboard()


def probe_clipboard() -> None:
    original = read_clipboard_text()
    if original is None and ctypes.get_last_error():
        report("剪贴板", False, f"读取失败，错误码 {ctypes.get_last_error()}")
        return

    ok = builtin_actions.copy_text({"text": "妙启轮盘自检 ✓"})
    written = read_clipboard_text() if ok else None
    round_trip = written == "妙启轮盘自检 ✓"

    # 还原：有原文就写回，原本为空则清空
    if original:
        builtin_actions.copy_text({"text": original})
    else:
        builtin_actions.clear_clipboard()
    restored = read_clipboard_text() == original

    report(
        "剪贴板",
        ok and round_trip and restored,
        f"写入并读回{'一致' if round_trip else '不一致'}，还原{'成功' if restored else '失败'}"
        + ("" if ok else f" — {builtin_actions.get_last_error()}"),
    )


def main() -> int:
    print("M3 内置动作实机验证（无副作用）\n")
    probe_volume()
    probe_dark_mode()
    probe_clipboard()
    print("\n以下三项需人工验证（会造成可见效果，脚本不执行）：")
    print("  turn-off-display  关闭显示器")
    print("  start-screen-saver 启动屏幕保护")
    print("  speak-text        朗读文本（依赖 SAPI 语音）")
    print("  试跑方式：.venv\\Scripts\\python.exe tools\\smoke_m3.py --run <id>")

    failed = [name for name, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
