"""内置动作：无法用命令行可靠表达的系统操作。

为什么不用 PowerShell 一把梭：cmd 与 PowerShell 的双引号嵌套规则冲突，
带空格或引号的参数极易被吃掉（`Set-Clipboard -Value "..."` 这类模板很脆）。
能用 Win32 API 直接做的就用 ctypes，必须起进程的改用环境变量传参（speak-text）。

注册表项：设置页切换深色模式走 HKCU\\…\\Themes\\Personalize，改完必须广播
WM_SETTINGCHANGE，否则资源管理器不刷新。
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import winreg
from ctypes import wintypes
from typing import Callable

from mqwheel.services.win32_ext import kernel32, user32

HWND_BROADCAST = 0xFFFF
WM_SYSCOMMAND = 0x0112
WM_SETTINGCHANGE = 0x001A
SC_MONITORPOWER = 0xF170
SC_SCREENSAVE = 0xF140
MONITOR_OFF = 2
SMTO_ABORTIFHUNG = 0x0002

PERSONALIZE_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalFree.restype = wintypes.HGLOBAL
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.argtypes = []
user32.EmptyClipboard.restype = wintypes.BOOL
user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = wintypes.BOOL

_last_error = ""


def get_last_error() -> str:
    return _last_error


def _fail(message: str) -> bool:
    global _last_error
    _last_error = message
    return False


def _send_broadcast(message: int, w_param: int, l_param: int, timeout_ms: int = 500) -> bool:
    user32.SendMessageTimeoutW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
        wintypes.UINT,
        wintypes.UINT,
        ctypes.POINTER(ctypes.c_ulonglong),
    ]
    user32.SendMessageTimeoutW.restype = ctypes.c_longlong
    result = ctypes.c_ulonglong(0)
    sent = user32.SendMessageTimeoutW(
        HWND_BROADCAST,
        message,
        w_param,
        l_param,
        SMTO_ABORTIFHUNG,
        timeout_ms,
        ctypes.byref(result),
    )
    return bool(sent)


def turn_off_display(params: dict[str, str]) -> bool:
    ok = _send_broadcast(WM_SYSCOMMAND, SC_MONITORPOWER, MONITOR_OFF)
    return ok or _fail("发送关闭显示器消息失败")


def start_screen_saver(params: dict[str, str]) -> bool:
    ok = _send_broadcast(WM_SYSCOMMAND, SC_SCREENSAVE, 0)
    return ok or _fail("没有设置屏幕保护程序，或发送启动消息失败")


def toggle_dark_mode(params: dict[str, str]) -> bool:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, PERSONALIZE_KEY, 0, winreg.KEY_READ | winreg.KEY_WRITE
        ) as key:
            apps_light, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            system_light, _ = winreg.QueryValueEx(key, "SystemUsesLightTheme")
            new_value = 0 if apps_light else 1
            winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, new_value)
            winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, new_value)
            # 系统栏与窗口标题栏颜色也跟着切，否则会一半深一半浅
            try:
                winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, new_value)
            except OSError:
                pass
    except OSError as exc:
        return _fail(f"读写个性化注册表失败：{exc}")

    buffer = ctypes.create_unicode_buffer("ImmersiveColorSet")
    _send_broadcast(WM_SETTINGCHANGE, 0, ctypes.cast(buffer, ctypes.c_void_p).value)
    return True


def set_volume(params: dict[str, str]) -> bool:
    raw = params.get("volume", "50")
    try:
        percent = max(0, min(int(raw), 100))
    except ValueError:
        return _fail(f"音量不是整数：{raw}")
    try:
        from pycaw.pycaw import AudioUtilities  # 延迟导入，常驻时不付代价
    except ImportError:
        return _fail("缺少 pycaw，无法设置精确音量")

    try:
        device = AudioUtilities.GetSpeakers()
        endpoint = device.EndpointVolume
        endpoint.SetMasterVolumeLevelScalar(percent / 100.0, None)
        if percent > 0:
            endpoint.SetMute(0, None)
        return True
    except Exception as exc:
        return _fail(f"设置音量失败：{exc}")


def copy_text(params: dict[str, str]) -> bool:
    text = params.get("text", "")
    if not text:
        return _fail("没有要复制的内容")

    if not user32.OpenClipboard(None):
        return _fail("打开剪贴板失败（可能被其它程序占用）")

    try:
        user32.EmptyClipboard()
        data = (text + "\0").encode("utf-16-le")
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            return _fail("分配剪贴板内存失败")
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            kernel32.GlobalFree(handle)
            return _fail("锁定剪贴板内存失败")
        ctypes.memmove(pointer, data, len(data))
        kernel32.GlobalUnlock(handle)
        # 成功后系统接管该句柄，不能再 GlobalFree
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            return _fail("写入剪贴板失败")
        return True
    finally:
        user32.CloseClipboard()


def clear_clipboard(params: dict[str, str] | None = None) -> bool:
    if not user32.OpenClipboard(None):
        return _fail("打开剪贴板失败（可能被其它程序占用）")
    try:
        user32.EmptyClipboard()
        return True
    finally:
        user32.CloseClipboard()


def speak_text(params: dict[str, str]) -> bool:
    text = params.get("text", "")
    if not text:
        return _fail("没有要朗读的内容")

    # 用环境变量传参：绕开 cmd 与 PowerShell 的引号嵌套问题
    env = dict(os.environ)
    env["MQWHEEL_SPEAK"] = text
    command = (
        "$voice = New-Object -ComObject SAPI.SpVoice; "
        "[void]$voice.Speak($env:MQWHEEL_SPEAK)"
    )
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except OSError as exc:
        return _fail(f"启动语音朗读失败：{exc}")


REGISTRY: dict[str, Callable[..., bool]] = {
    "turn-off-display": turn_off_display,
    "start-screen-saver": start_screen_saver,
    "toggle-dark-mode": toggle_dark_mode,
    "set-volume": set_volume,
    "copy-text": copy_text,
    "speak-text": speak_text,
}


def run(builtin_id: str, params: dict[str, str] | None = None) -> bool:
    handler = REGISTRY.get(builtin_id)
    if handler is None:
        return _fail(f"没有实现内置动作 {builtin_id}")
    try:
        return handler(params or {})
    except Exception as exc:
        return _fail(f"内置动作 {builtin_id} 执行异常：{exc}")
