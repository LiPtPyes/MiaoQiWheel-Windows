"""键盘事件注入：用 SendInput 补发被吞掉的按键、或触发系统快捷键。

注入的事件带 LLKHF_INJECTED 标记，低级钩子会据此忽略，不会自我触发。
"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", INPUTUNION)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT


def _make_input(vk: int, key_up: bool) -> INPUT:
    entry = INPUT()
    entry.type = INPUT_KEYBOARD
    entry.u.ki.wVk = vk
    entry.u.ki.wScan = 0
    entry.u.ki.dwFlags = KEYEVENTF_KEYUP if key_up else 0
    entry.u.ki.time = 0
    entry.u.ki.dwExtraInfo = None
    return entry


def _send(entries: list[INPUT]) -> int:
    array = (INPUT * len(entries))(*entries)
    return user32.SendInput(len(entries), array, ctypes.sizeof(INPUT))


def send_tap(vk: int, delay: float = 0.0) -> bool:
    """补发一次完整的按下 + 松开（用于短按 Tab 的透传）。

    在钩子回调中调用时 delay 必须为 0，否则会触发系统的钩子超时保护。
    """
    sent = _send([_make_input(vk, False), _make_input(vk, True)])
    if delay:
        time.sleep(delay)
    return sent == 2


def send_down(vk: int) -> bool:
    return _send([_make_input(vk, False)]) == 1


def send_up(vk: int) -> bool:
    return _send([_make_input(vk, True)]) == 1


def send_combo(vks: list[int], delay: float = 0.02) -> bool:
    """依次按下给定按键（含修饰键），再逆序松开。例如 Win+Shift+S。"""
    entries = [_make_input(vk, False) for vk in vks]
    entries += [_make_input(vk, True) for vk in reversed(vks)]
    sent = _send(entries)
    if delay:
        time.sleep(delay)
    return sent == len(entries)
