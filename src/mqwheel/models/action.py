"""轮盘动作模型（M1 仅含绘制所需字段，执行逻辑在 M3 的 action_executor 中）。"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from enum import Enum


class WheelActionKind(str, Enum):
    APPLICATION = "application"
    WINDOW_TOGGLE = "windowToggle"  # 呼出已打开的窗口 / 已在前台则最小化
    URL = "url"
    KEYBOARD_SHORTCUT = "keyboardShortcut"
    SHELL_COMMAND = "shellCommand"
    BUILTIN = "builtin"  # 内置动作，payload 形如 builtin:<id>

    @property
    def title(self) -> str:
        return {
            WheelActionKind.APPLICATION: "应用",
            WheelActionKind.WINDOW_TOGGLE: "窗口切换",
            WheelActionKind.URL: "链接",
            WheelActionKind.KEYBOARD_SHORTCUT: "快捷操作",
            WheelActionKind.SHELL_COMMAND: "脚本",
            WheelActionKind.BUILTIN: "内置操作",
        }[self]


@dataclass
class WheelAction:
    title: str
    subtitle: str = ""
    symbol: str = "fa6s.circle"
    kind: WheelActionKind = WheelActionKind.APPLICATION
    payload: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    preset_id: str | None = None
    preset_params: dict[str, str] | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "subtitle": self.subtitle,
            "symbol": self.symbol,
            "kind": self.kind.value,
            "payload": self.payload,
            "presetId": self.preset_id,
            "presetParams": self.preset_params,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WheelAction":
        return cls(
            id=data.get("id") or uuid.uuid4().hex,
            title=data.get("title", ""),
            subtitle=data.get("subtitle", ""),
            symbol=data.get("symbol", "fa6s.circle"),
            kind=WheelActionKind(data.get("kind", WheelActionKind.APPLICATION.value)),
            payload=data.get("payload", ""),
            preset_id=data.get("presetId"),
            preset_params=data.get("presetParams"),
        )


_EDGE_RELATIVE = r"Microsoft\Edge\Application\msedge.exe"


def _edge_path() -> str:
    """探测 Edge 的安装位置。

    不写死 `%ProgramFiles(x86)%`：这两个环境变量在从某些宿主（Git Bash、部分
    启动器）拉起时可能整批缺失，拼出来的就是一条不存在的路径，用户看到的是
    「点了没反应」。逐个候选探一遍，取第一个真实存在的。
    """
    roots = (
        os.environ.get("ProgramFiles(x86)"),
        os.environ.get("ProgramFiles"),
        r"C:\Program Files (x86)",
        r"C:\Program Files",
        os.environ.get("LOCALAPPDATA"),
    )
    candidates = [os.path.join(root, _EDGE_RELATIVE) for root in roots if root]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return candidates[0]


def default_actions() -> list[WheelAction]:
    """全新安装的六个选项，按顺时针排列。前两项直接取自预设库。"""
    from mqwheel.models.presets import by_id  # 延迟导入，避免循环依赖

    lock = by_id("lock-screen")
    shot = by_id("screenshot")

    return [
        lock.make_action() if lock else WheelAction(
            title="锁定屏幕",
            subtitle="立即锁定",
            symbol="fa6s.lock",
            kind=WheelActionKind.SHELL_COMMAND,
            payload=r"rundll32.exe user32.dll,LockWorkStation",
            preset_id="lock-screen",
        ),
        shot.make_action() if shot else WheelAction(
            title="截图",
            subtitle="区域截图",
            symbol="fa6s.camera",
            kind=WheelActionKind.KEYBOARD_SHORTCUT,
            payload="win+shift+s",
        ),
        WheelAction(
            title="浏览器",
            subtitle="Microsoft Edge",
            symbol="fa6s.globe",
            # 浏览器走「窗口切换」而不是「应用」：已经开着就把它拉回最前并最大化，
            # 已经在前台就收起来，只有真没开才新建窗口。再点一次「打开」多出一个
            # 窗口不是用户想要的。
            kind=WheelActionKind.WINDOW_TOGGLE,
            payload=_edge_path(),
        ),
        WheelAction(
            title="终端",
            subtitle="Windows 终端",
            symbol="fa6s.terminal",
            kind=WheelActionKind.APPLICATION,
            payload=os.path.join(
                os.environ.get("LOCALAPPDATA", ""),
                r"Microsoft\WindowsApps\wt.exe",
            ),
        ),
        WheelAction(
            title="文件资源管理器",
            subtitle="文件与文件夹",
            symbol="fa6s.folder-open",
            kind=WheelActionKind.APPLICATION,
            payload=r"C:\Windows\explorer.exe",
        ),
        WheelAction(
            title="记事本",
            subtitle="快速记录",
            symbol="fa6s.file-lines",
            kind=WheelActionKind.APPLICATION,
            payload=r"C:\Windows\System32\notepad.exe",
        ),
    ]
