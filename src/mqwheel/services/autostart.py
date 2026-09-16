"""开机自启：写入当前用户注册表 Run 键。

只用标准库；失败时返回 False 并把原因放进 last_error，由界面提示。
"""

from __future__ import annotations

import sys
import winreg
from pathlib import Path

from mqwheel.app_identity import APP_ID

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = APP_ID

last_error = ""


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def command_line() -> str:
    """自启命令行。

    - 打包后：直接指向 exe；
    - 源码运行：指向 `pythonw.exe src/mqwheel/main.py`（main.py 自带 sys.path 处理，
      无需依赖 PYTHONPATH；优先 pythonw 以免弹出控制台窗口）。
    """
    executable = Path(sys.executable)
    if is_frozen():
        return f'"{executable}"'

    pythonw = executable.with_name("pythonw.exe")
    runner = pythonw if pythonw.exists() else executable
    entry = Path(__file__).resolve().parents[1] / "main.py"
    return f'"{runner}" "{entry}"'


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
    except OSError:
        return False
    return bool(value)


def set_enabled(enabled: bool) -> bool:
    """开启或关闭自启；关闭时若值不存在也算成功。"""
    global last_error
    last_error = ""
    try:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command_line())
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                except OSError:
                    pass
        return True
    except OSError as exc:
        last_error = str(exc)
        return False


__all__ = ["RUN_KEY", "VALUE_NAME", "command_line", "is_enabled", "is_frozen", "set_enabled"]
