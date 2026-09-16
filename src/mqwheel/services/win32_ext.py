"""Win32 API 轻量封装（ctypes，避免引入 QtNetwork 等额外模块）。

约定：
- 本模块只依赖标准库，可被任何模块安全导入。
- 所有句柄与结构体按需定义，不为未使用的 API 付出导入成本。
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

ERROR_ALREADY_EXISTS = 183

# 虚拟键码
VK_LBUTTON = 0x01
VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_PAUSE = 0x13
VK_CAPITAL = 0x14  # CapsLock
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_LWIN = 0x5B
VK_RWIN = 0x5C

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012

HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


class SingleInstanceGuard:
    """基于命名互斥量的单实例保护，无需 QtNetwork。"""

    def __init__(self, name: str) -> None:
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        self._handle = kernel32.CreateMutexW(None, True, name)
        self._owned = bool(self._handle) and ctypes.get_last_error() != ERROR_ALREADY_EXISTS

    @property
    def already_running(self) -> bool:
        return not self._owned

    def release(self) -> None:
        if self._handle:
            kernel32.CloseHandle(self._handle)
            self._handle = None  # type: ignore[assignment]


def get_cursor_pos() -> tuple[int, int]:
    """返回物理像素坐标的鼠标位置。Qt 侧请用 QCursor.pos() 保持逻辑坐标一致。"""
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y
