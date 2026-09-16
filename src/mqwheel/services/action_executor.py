"""动作执行器：把轮盘选项落到 Windows 上（M2 基础版，M3 扩展脚本预设）。"""

from __future__ import annotations

import ctypes
import os
import subprocess
from ctypes import wintypes
from pathlib import Path

from mqwheel.models.action import WheelAction, WheelActionKind
from mqwheel.models.settings import vk_from_name
from mqwheel.services import input_sender, window_control

shell32 = ctypes.WinDLL("shell32", use_last_error=True)
shell32.ShellExecuteW.argtypes = [
    wintypes.HWND,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    ctypes.c_int,
]
shell32.ShellExecuteW.restype = wintypes.HINSTANCE

SW_SHOWNORMAL = 1
_ERROR_THRESHOLD = 32  # ShellExecute 返回值 <=32 表示失败

_MODIFIER_ALIASES = {
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "win": 0x5B,
    "meta": 0x5B,
    "cmd": 0x5B,
}


def parse_shortcut(text: str) -> list[int]:
    """把 'win+shift+s' 解析为虚拟键码序列（修饰键在前）。"""
    tokens = [t.strip().lower() for t in text.replace(" ", "").split("+") if t.strip()]
    if not tokens:
        return []
    vks: list[int] = []
    main = tokens[-1]
    for token in tokens[:-1]:
        if token in _MODIFIER_ALIASES:
            vks.append(_MODIFIER_ALIASES[token])
    if main in _MODIFIER_ALIASES:
        main_vk = _MODIFIER_ALIASES[main]
    elif len(main) == 1:
        main_vk = ord(main.upper())
    else:
        main_vk = vk_from_name(main)
    if not main_vk:
        return []  # 主键无法识别时宁可不动，也不要发出残缺组合
    vks.append(main_vk)
    return vks


class ActionExecutor:
    def __init__(self) -> None:
        self.last_error: str = ""

    def execute(self, action: WheelAction) -> bool:
        try:
            if action.kind == WheelActionKind.APPLICATION:
                return self._open_application(action.payload)
            if action.kind == WheelActionKind.WINDOW_TOGGLE:
                return self._toggle_window(action.payload)
            if action.kind == WheelActionKind.URL:
                return self._open_url(action.payload)
            if action.kind == WheelActionKind.KEYBOARD_SHORTCUT:
                return input_sender.send_combo(parse_shortcut(action.payload))
            if action.kind == WheelActionKind.SHELL_COMMAND:
                return self._run_command(action.payload)
            if action.kind == WheelActionKind.BUILTIN:
                return self._run_builtin(action)
        except Exception as exc:  # 执行失败不应影响常驻
            self.last_error = str(exc)
            return False
        self.last_error = f"未知类型 {action.kind}"
        return False

    def _run_builtin(self, action: WheelAction) -> bool:
        from mqwheel.models.presets import builtin_id_of
        from mqwheel.services import builtin_actions

        builtin_id = builtin_id_of(action)
        if not builtin_id:
            self.last_error = f"无法识别的内置动作：{action.payload}"
            return False
        ok = builtin_actions.run(builtin_id, action.preset_params or {})
        if not ok:
            self.last_error = builtin_actions.get_last_error() or f"内置动作 {builtin_id} 失败"
        return ok

    def _open_application(self, payload: str) -> bool:
        if not payload:
            self.last_error = "未指定应用"
            return False
        path = Path(payload)
        if not path.exists():
            self.last_error = f"路径不存在：{payload}"
            return False
        result = shell32.ShellExecuteW(None, "open", str(path), None, str(path.parent), SW_SHOWNORMAL)
        if result <= _ERROR_THRESHOLD:
            self.last_error = f"启动失败（代码 {result}）：{payload}"
            return False
        return True

    def _toggle_window(self, payload: str) -> bool:
        """已打开就呼出（必要时最大化），已在前台就收起，真没开才新建。

        与 `_open_application` 的区别只在这最后一步：只有拿到「没在运行」才落回
        启动流程，所以路径不存在也不会误报——应用正开着时根本用不到路径。
        """
        if not payload:
            self.last_error = "未指定应用"
            return False
        result = window_control.toggle(payload)
        if result == window_control.RESULT_NOT_RUNNING:
            return self._open_application(payload)
        if result == window_control.RESULT_FAILED:
            self.last_error = f"无法识别的应用：{payload}"
            return False
        return True

    def _open_url(self, payload: str) -> bool:
        if not payload:
            self.last_error = "未指定链接"
            return False
        if "://" not in payload:
            payload = "https://" + payload
        result = shell32.ShellExecuteW(None, "open", payload, None, None, SW_SHOWNORMAL)
        if result <= _ERROR_THRESHOLD:
            self.last_error = f"打开链接失败（代码 {result}）：{payload}"
            return False
        return True

    def _run_command(self, payload: str) -> bool:
        if not payload:
            self.last_error = "未指定命令"
            return False
        subprocess.Popen(
            payload,
            shell=True,
            cwd=str(Path.home()),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
