"""应用窗口的「呼出 / 最小化」控制。

为什么单独做这件事：浏览器这类单实例应用，再执行一次「打开」只会多出一个
窗口；用户真正想要的是——已经开着就把它拉回最前，已经在前台就收起来。

四个关键取舍：

- **按进程可执行文件名判定「同一个应用」，不按窗口类名。** Chromium 系的窗口
  类都是 `Chrome_WidgetWin_1`，按类名匹配会把 VS Code、Electron 应用一起算进来。
- **先 SW_RESTORE 再 SW_SHOWMAXIMIZED。** 窗口处于最小化状态时直接
  SHOWMAXIMIZED 不保证离开最小化；先还原一步更稳。
- **呼出优先还原「上次收起的那个窗口」**，没有记忆时才挑 Z 序里最靠前、且
  没被最小化的那个。多个浏览器窗口并存时，「收起 → 再按一次」才是原样还原，
  而不是莫名换到另一个窗口上去。
- **SetForegroundWindow 有前台锁定限制**：只有当前前台进程才允许抢焦点。
  本程序呼出轮盘时窗口带 WindowDoesNotAcceptFocus，前台仍是用户原来那个应用，
  所以通常能直接成功；失败时依次退化为 TopMost 翻转与 AttachThreadInput。

只依赖标准库，便于在无 Qt 环境下单测。
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from mqwheel.services.win32_ext import kernel32, user32

# toggle() 的返回值
RESULT_ACTIVATED = "activated"  # 已把已有窗口拉到最前并最大化
RESULT_MINIMIZED = "minimized"  # 该应用本来就在前台，已收起
RESULT_NOT_RUNNING = "notRunning"  # 没有窗口，调用方应正常启动它
RESULT_FAILED = "failed"  # 参数不合法等

SW_SHOWMAXIMIZED = 3
SW_MINIMIZE = 6
SW_RESTORE = 9

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080

DWMWA_CLOAKED = 14
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

_HWND_TOPMOST = -1
_HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)

user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_uint,
]
user32.SetWindowPos.restype = wintypes.BOOL
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = wintypes.DWORD

# 上次被收起的窗口。再按一次时优先把它拉回来，比"猜一个"更符合直觉。
# 进程重启后归零，届时退回 Z 序启发式。
_last_window: int = 0


def reset() -> None:
    """清掉记忆的窗口（测试用）。"""
    global _last_window
    _last_window = 0


def _hwnd(handle: object) -> int:
    """把 ctypes 句柄统一成 int，便于比较与存进列表。"""
    if not handle:
        return 0
    value = getattr(handle, "value", handle)
    return int(value or 0)


def _is_cloaked(hwnd: int) -> bool:
    """被 DWM 隐藏的窗口（UWP 挂起后留下的空壳）不算数。"""
    value = ctypes.c_int(0)
    result = dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(hwnd), ctypes.c_uint(DWMWA_CLOAKED), ctypes.byref(value), ctypes.sizeof(value)
    )
    return result == 0 and value.value != 0


def _is_candidate(hwnd: int) -> bool:
    if not user32.IsWindowVisible(wintypes.HWND(hwnd)):
        return False
    if user32.GetWindowTextLengthW(wintypes.HWND(hwnd)) <= 0:
        return False  # 无标题的多半是隐藏消息窗
    if user32.GetWindowLongW(wintypes.HWND(hwnd), GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
        return False  # 托盘图标、浮动工具条
    return not _is_cloaked(hwnd)


def process_name_of_window(hwnd: int) -> str:
    """窗口所属进程的可执行文件名（小写）；拿不到返回空串。"""
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
    if not pid.value:
        return ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ""  # 权限不足（如提权进程）时当作不认识
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(buffer))
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return ""
        return os.path.basename(buffer.value).lower()
    finally:
        kernel32.CloseHandle(handle)


def list_windows(process_name: str) -> list[int]:
    """按 Z 序（最前的排最前）返回该进程的可见顶层窗口。"""
    target = process_name.lower()
    if not target:
        return []
    found: list[int] = []

    def _collect(hwnd, _lparam):
        value = _hwnd(hwnd)
        if value and _is_candidate(value) and process_name_of_window(value) == target:
            found.append(value)
        return True

    callback = WNDENUMPROC(_collect)
    user32.EnumWindows(callback, 0)
    return found


def foreground_window() -> int:
    return _hwnd(user32.GetForegroundWindow())


def _try_foreground(hwnd: int) -> bool:
    user32.SetForegroundWindow(wintypes.HWND(hwnd))
    if foreground_window() == hwnd:
        return True
    # 前台锁定：先把窗口顶到 TOPMOST 再撤回来，通常会把它带到最前
    user32.SetWindowPos(
        wintypes.HWND(hwnd), wintypes.HWND(_HWND_TOPMOST), 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE
    )
    user32.SetWindowPos(
        wintypes.HWND(hwnd),
        wintypes.HWND(_HWND_NOTOPMOST),
        0,
        0,
        0,
        0,
        SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE,
    )
    user32.BringWindowToTop(wintypes.HWND(hwnd))
    user32.SetForegroundWindow(wintypes.HWND(hwnd))
    if foreground_window() == hwnd:
        return True
    return _attach_and_focus(hwnd)


def _attach_and_focus(hwnd: int) -> bool:
    """把本线程的输入队列挂到当前前台线程上，再抢一次焦点。

    AttachThreadInput 之后两个线程共享输入状态，前台锁定检查就会放行。
    用完必须解挂，否则两边会互相影响键盘状态。
    """
    current = kernel32.GetCurrentThreadId()
    foreground = foreground_window()
    target_thread = user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), None)
    foreground_thread = (
        user32.GetWindowThreadProcessId(wintypes.HWND(foreground), None) if foreground else 0
    )

    attached: list[int] = []
    try:
        for thread in (foreground_thread, target_thread):
            if thread and thread != current:
                if user32.AttachThreadInput(current, thread, True):
                    attached.append(thread)
        user32.BringWindowToTop(wintypes.HWND(hwnd))
        user32.SetForegroundWindow(wintypes.HWND(hwnd))
        return foreground_window() == hwnd
    finally:
        for thread in attached:
            user32.AttachThreadInput(current, thread, False)


def _pick(windows: list[int]) -> int:
    """选一个要呼出的窗口。

    优先上次收起过的那个——这样「收起 → 再按一次」是原样还原。多窗口并存时
    若改用「挑一个没最小化的」，第二下就会莫名换到另一个窗口上去。
    进程重启后没有记忆，退化为 Z 序里最靠前、且没被最小化的那个。
    """
    remembered = _last_window
    if remembered in windows:
        return remembered
    for hwnd in windows:
        if not user32.IsIconic(wintypes.HWND(hwnd)):
            return hwnd
    return windows[0]


def activate(hwnd: int) -> bool:
    """还原（必要时）并最大化，然后拉到最前。"""
    handle = wintypes.HWND(hwnd)
    if user32.IsIconic(handle):
        user32.ShowWindow(handle, SW_RESTORE)
    user32.ShowWindow(handle, SW_SHOWMAXIMIZED)
    return _try_foreground(hwnd)


def toggle(exe_path: str) -> str:
    """浏览器式切换：后台→呼出并最大化，前台→最小化，没开→交给调用方启动。

    `exe_path` 与「应用」类型一样是可执行文件路径，取文件名来匹配进程。
    """
    global _last_window

    process_name = os.path.basename(exe_path or "").strip().lower()
    if not process_name:
        return RESULT_FAILED

    windows = list_windows(process_name)
    if not windows:
        _last_window = 0
        return RESULT_NOT_RUNNING

    foreground = foreground_window()
    # 必须同时要求「没被最小化」：窗口最小化之后 GetForegroundWindow 仍可能返回它
    # （系统没找到别的窗口来接手前台）。只看句柄相等的话，再按一次会又走最小化分支，
    # 表现成"按了没反应"。
    if (
        foreground
        and foreground in windows
        and not user32.IsIconic(wintypes.HWND(foreground))
    ):
        user32.ShowWindow(wintypes.HWND(foreground), SW_MINIMIZE)
        _last_window = foreground
        return RESULT_MINIMIZED

    target = _pick(windows)
    activate(target)
    _last_window = target
    return RESULT_ACTIVATED


__all__ = [
    "RESULT_ACTIVATED",
    "RESULT_FAILED",
    "RESULT_MINIMIZED",
    "RESULT_NOT_RUNNING",
    "activate",
    "foreground_window",
    "list_windows",
    "process_name_of_window",
    "reset",
    "toggle",
]
