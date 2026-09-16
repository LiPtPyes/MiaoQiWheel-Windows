"""全局热键：WH_KEYBOARD_LL 低级钩子 + 长按状态机。

为什么不用 RegisterHotKey：Windows 的 RegisterHotKey 只有按下通知、没有释放通知，
而轮盘的核心交互是「按住—移动—松开执行」，必须拿到 keyup。低级钩子能拿到 down/up
两个事件，代价是必须自己维护状态机并自建消息泵。

线程模型：
- 钩子线程（threading.Thread）负责装钩子并跑 GetMessageW 消息泵；
- 回调里只做整数判断与状态机推进，耗时操作一律通过 Signal 抛回主线程；
- 进度回调（呼出/执行）用 Qt 信号 emit，Qt 会自动转为 QueuedConnection，线程安全。
"""

from __future__ import annotations

import ctypes
import os
import threading
import time
from ctypes import wintypes

from PySide6 import QtCore

from mqwheel.models.settings import (
    MODE_COMBO,
    MODE_DOUBLE_TAP,
    MODE_HOLD,
    HotKeyConfig,
)
from mqwheel.services import input_sender
from mqwheel.services.win32_ext import (
    HOOKPROC,
    VK_CONTROL,
    VK_LWIN,
    VK_MENU,
    VK_RWIN,
    VK_SHIFT,
    WH_KEYBOARD_LL,
    WM_KEYDOWN,
    WM_KEYUP,
    WM_QUIT,
    WM_SYSKEYDOWN,
    WM_SYSKEYUP,
    kernel32,
    user32,
)

PASS_THROUGH = 0  # 交给系统继续分发
SWALLOW = 1  # 吞掉，不传给其它程序

LLKHF_UP = 0x80
LLKHF_INJECTED = 0x10
LLKHF_LOWER_IL_INJECTED = 0x02

_MODIFIER_VKS = (VK_CONTROL, VK_MENU, VK_SHIFT, VK_LWIN, VK_RWIN)

# 自检开关：仅 tools/hotkey_probe.py 的合成按键测试使用。
# 打开后钩子会把本进程 SendInput 注入的事件当作真实按键处理（并禁用补发，避免自我循环）。
SYNTHETIC_MODE = os.environ.get("MQWHEEL_SYNTHETIC", "") == "1"


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


# 64 位下 lParam 是 8 字节指针，未声明 argtypes 会被当成 32 位 int 而溢出，
# 必须显式声明（ctypes 报错会直接从钩子回调抛出，导致进程崩溃）。
user32.CallNextHookEx.argtypes = [
    wintypes.HHOOK,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.CallNextHookEx.restype = ctypes.c_longlong  # LRESULT


def _call_next(n_code: int, w_param: int, l_param: int) -> int:
    """交给下一个钩子。失败时返回 0（不吞事件），宁可漏拦也不要卡住键盘。"""
    try:
        return int(user32.CallNextHookEx(None, n_code, w_param, l_param))
    except Exception:
        return 0


def _now_ms() -> int:
    return int(time.perf_counter() * 1000)


class HotKeyStateMachine:
    """纯逻辑状态机，不接触 Win32，可直接单测。

    状态：idle → armed（已按下，等待长按阈值）→ active（轮盘已呼出）。
    """

    def __init__(
        self,
        config: HotKeyConfig,
        on_activate,
        on_release,
        on_reemit,
        on_schedule,
        on_cancel,
        now_fn=_now_ms,
    ) -> None:
        self.config = config
        self._on_activate = on_activate
        self._on_release = on_release
        self._on_reemit = on_reemit
        self._on_schedule = on_schedule
        self._on_cancel = on_cancel
        self._now = now_fn
        self._state = "idle"
        self._last_tap_ms: int | None = None

    @property
    def state(self) -> str:
        return self._state

    def reset(self) -> None:
        self._state = "idle"
        self._last_tap_ms = None

    # region 事件
    def on_key_down(self, vk: int, mods: set[int], now: int | None = None) -> int:
        now = self._now() if now is None else now
        if vk != self.config.key_vk:
            return PASS_THROUGH

        if self._state == "active":
            return SWALLOW  # 自动重复，不打扰前台应用

        if self.config.mode == MODE_HOLD:
            if self._state == "armed":
                return SWALLOW  # 自动重复
            # 有修饰键按下时放行，保住 Alt+Tab / Ctrl+Tab 等系统组合
            if mods:
                return PASS_THROUGH
            self._state = "armed"
            self._on_schedule(self.config.hold_ms)
            return SWALLOW

        if self.config.mode == MODE_DOUBLE_TAP:
            if mods:
                return PASS_THROUGH
            window = self.config.double_tap_ms
            last = self._last_tap_ms
            if last is not None and now - last <= window:
                self._last_tap_ms = None
                self._state = "active"
                self._on_activate()
                return SWALLOW
            self._last_tap_ms = now
            return PASS_THROUGH  # 第一次点按必须放行，否则 Tab 就废了

        # combo
        required = set(self.config.modifier_vks)
        if not required or not required.issubset(mods):
            return PASS_THROUGH
        self._state = "active"
        self._on_activate()
        return SWALLOW

    def on_key_up(self, vk: int, now: int | None = None) -> int:
        now = self._now() if now is None else now
        if vk != self.config.key_vk:
            if self._state == "active" and self.config.mode == MODE_COMBO:
                if vk in set(self.config.modifier_vks):
                    self._state = "idle"
                    self._on_release()
                    return SWALLOW
            return PASS_THROUGH

        if self._state == "active":
            self._state = "idle"
            self._on_release()
            return SWALLOW

        if self._state == "armed":
            # 短按：补发一次原生按键，保留 Tab 的导航能力
            self._state = "idle"
            self._on_cancel()
            self._on_reemit(vk)
            return SWALLOW

        return PASS_THROUGH

    def on_tick(self, now: int | None = None) -> None:
        """长按计时到点。"""
        now = self._now() if now is None else now
        if self._state == "armed":
            self._state = "active"
            self._on_activate()
    # endregion


class HotKeyMonitor(QtCore.QObject):
    """在独立线程中安装低级键盘钩子，把结果以信号抛回主线程。"""

    activated = QtCore.Signal()
    released = QtCore.Signal()
    key_event = QtCore.Signal(int, bool)  # vk, is_down（仅 forward 打开时上报）
    failed = QtCore.Signal(str)

    def __init__(self, config: HotKeyConfig, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._lock = threading.Lock()
        self._config = config
        self._machine = self._build_machine(config)
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._hook = None
        self._hook_proc = None
        self._timer: threading.Timer | None = None
        self._forward_keys = False
        self._stopping = False

    # region 生命周期
    def _build_machine(self, config: HotKeyConfig) -> HotKeyStateMachine:
        return HotKeyStateMachine(
            config,
            on_activate=self._emit_activate,
            on_release=self._emit_release,
            on_reemit=self._reemit,
            on_schedule=self._schedule,
            on_cancel=self._cancel_hold,
        )

    def start(self) -> bool:
        if self._thread is not None:
            return True
        self._stopping = False
        self._thread = threading.Thread(target=self._run, name="HotKeyHook", daemon=True)
        self._thread.start()
        # 等钩子真正装好，最多 2 秒
        for _ in range(200):
            if self._hook is not None or not self._thread.is_alive():
                break
            time.sleep(0.01)
        return self._hook is not None

    def stop(self) -> None:
        self._stopping = True
        self._cancel_hold()
        tid = self._thread_id
        thread = self._thread
        if tid is not None:
            try:
                kernel32.PostThreadMessageW.argtypes = [
                    wintypes.DWORD,
                    wintypes.UINT,
                    wintypes.WPARAM,
                    wintypes.LPARAM,
                ]
                kernel32.PostThreadMessageW.restype = wintypes.BOOL
                kernel32.PostThreadMessageW(tid, WM_QUIT, 0, 0)
            except (OSError, AttributeError):
                pass
        if thread is not None:
            thread.join(timeout=3.0)
        self._thread = None
        self._thread_id = None
        self._hook = None
        self._hook_proc = None

    def update_config(self, config: HotKeyConfig) -> None:
        with self._lock:
            self._config = config
            self._machine = self._build_machine(config)

    @property
    def installed(self) -> bool:
        return self._hook is not None

    def set_forward_keys(self, enabled: bool) -> None:
        self._forward_keys = bool(enabled)
    # endregion

    # region 回调桥接
    def _emit_activate(self) -> None:
        self.activated.emit()

    def _emit_release(self) -> None:
        self.released.emit()

    def _reemit(self, vk: int) -> None:
        if SYNTHETIC_MODE:
            return  # 自检模式下补发会与注入事件互相触发，直接跳过
        input_sender.send_tap(vk, delay=0.0)

    def _schedule(self, delay_ms: int) -> None:
        self._cancel_hold()
        timer = threading.Timer(delay_ms / 1000.0, self._hold_elapsed)
        timer.daemon = True
        with self._lock:
            self._timer = timer
        timer.start()

    def _cancel_hold(self) -> None:
        with self._lock:
            timer, self._timer = self._timer, None
        if timer is not None:
            timer.cancel()

    def _hold_elapsed(self) -> None:
        with self._lock:
            self._timer = None
            machine = self._machine
        machine.on_tick()
    # endregion

    # region 钩子线程
    def _run(self) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()
        kernel32.GetCurrentThreadId.restype = wintypes.DWORD

        proc = HOOKPROC(self._hook_callback)
        self._hook_proc = proc
        try:
            user32.SetWindowsHookExW.argtypes = [
                ctypes.c_int,
                HOOKPROC,
                wintypes.HINSTANCE,
                wintypes.DWORD,
            ]
            user32.SetWindowsHookExW.restype = wintypes.HHOOK
            hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, proc, None, 0)
        except (OSError, AttributeError) as exc:  # pragma: no cover - 平台相关
            self.failed.emit(str(exc))
            return

        if not hook:
            error = ctypes.get_last_error()
            self.failed.emit(f"SetWindowsHookEx 失败，错误码 {error}")
            return
        self._hook = hook

        msg = wintypes.MSG()
        pointer = ctypes.byref(msg)
        while user32.GetMessageW(pointer, None, 0, 0) > 0:
            user32.TranslateMessage(pointer)
            user32.DispatchMessageW(pointer)

        user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
        user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        user32.UnhookWindowsHookEx(hook)

    def _hook_callback(self, n_code: int, w_param: int, l_param: int) -> int:
        # 注意：此函数运行在钩子线程，禁止执行耗时操作。
        try:
            if n_code < 0:
                return _call_next(n_code, w_param, l_param)

            if w_param not in (WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP):
                return _call_next(n_code, w_param, l_param)

            info = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            flags = info.flags
            if not SYNTHETIC_MODE and flags & (LLKHF_INJECTED | LLKHF_LOWER_IL_INJECTED):
                return _call_next(n_code, w_param, l_param)

            vk = int(info.vkCode)
            is_up = bool(flags & LLKHF_UP)

            with self._lock:
                machine = self._machine
            if is_up:
                verdict = machine.on_key_up(vk)
            else:
                verdict = machine.on_key_down(vk, self._mods_mask())

            if self._forward_keys:
                self.key_event.emit(vk, not is_up)

            if verdict == SWALLOW:
                return 1
        except Exception:  # 钩子回调里抛出会导致进程直接崩溃，必须兜住
            return 0
        return _call_next(n_code, w_param, l_param)

    def _mods_mask(self) -> set[int]:
        user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        user32.GetAsyncKeyState.restype = ctypes.c_short
        pressed = set()
        for vk in _MODIFIER_VKS:
            if user32.GetAsyncKeyState(vk) & 0x8000:
                pressed.add(vk)
        return pressed
    # endregion
