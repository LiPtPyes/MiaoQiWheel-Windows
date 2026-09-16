"""设置数据模型：纯 dataclass，不依赖 Qt 与 Win32，可单测。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from mqwheel.models.action import WheelAction, WheelActionKind, default_actions
from mqwheel.models.layout import WheelAppearance

SETTINGS_VERSION = 2

# v2 起，「浏览器」这类单实例应用改用 WINDOW_TOGGLE（已打开就呼出、已在前台就
# 最小化），不再是每次新建窗口的 APPLICATION。
#
# 为什么必须迁移：老配置里存的就是 application，只改 default_actions() 只对新装
# 生效——升级上来的用户按下去还是老行为，等于功能没上。这里只认「单实例体验明显
# 更好」的那几个可执行文件，别的应用一概不动；用户想改回每次新建，在设置里把
# 类型换回「应用」即可。
REUSABLE_EXES = ("msedge.exe",)


def _migrate_actions(actions: list[WheelAction], stored_version: int) -> None:
    if stored_version >= 2:
        return
    for action in actions:
        if action.kind != WheelActionKind.APPLICATION:
            continue
        if os.path.basename(action.payload or "").lower() in REUSABLE_EXES:
            action.kind = WheelActionKind.WINDOW_TOGGLE


# 热键模式
MODE_HOLD = "hold"  # 长按单键（默认）
MODE_DOUBLE_TAP = "doubleTap"  # 双击单键
MODE_COMBO = "combo"  # 修饰键组合

VALID_MODES = (MODE_HOLD, MODE_DOUBLE_TAP, MODE_COMBO)

# 按键名 → 虚拟键码（与 services/win32_ext.py 的 VK_* 保持一致）
KEY_CODES: dict[str, int] = {
    "tab": 0x09,
    "space": 0x20,
    "enter": 0x0D,
    "return": 0x0D,
    "backspace": 0x08,
    "capslock": 0x14,
    "escape": 0x1B,
    "esc": 0x1B,
    "delete": 0x2E,
    "del": 0x2E,
    "insert": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "printscreen": 0x2C,
    "volume_mute": 0xAD,
    "volume_down": 0xAE,
    "volume_up": 0xAF,
    "media_next": 0xB0,
    "media_prev": 0xB1,
    "media_stop": 0xB2,
    "media_play_pause": 0xB3,
    "backquote": 0xC0,  # ` 反引号，Tab 正上方
    "backslash": 0xDC,
    "comma": 0xBC,
    "period": 0xBE,
    "slash": 0xBF,
    "semicolon": 0xBA,
    "minus": 0xBD,
    "equal": 0xBB,
    "lbracket": 0xDB,
    "rbracket": 0xDD,
    "quote": 0xDE,
}
for _i in range(1, 13):
    KEY_CODES[f"f{_i}"] = 0x6F + _i
for _c in range(ord("a"), ord("z") + 1):
    KEY_CODES[chr(_c)] = ord(chr(_c)) - 32  # A..Z 的虚拟键码
for _d in range(10):
    KEY_CODES[str(_d)] = 0x30 + _d

MODIFIER_CODES: dict[str, int] = {
    "ctrl": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "win": 0x5B,
}

MODIFIER_LABELS = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Win"}


def vk_from_name(name: str) -> int:
    """未知键名返回 0（调用方应视为无效），绝不静默回退到 Tab。"""
    return KEY_CODES.get(name.lower(), 0)


def name_from_vk(vk: int) -> str:
    for name, code in KEY_CODES.items():
        if code == vk:
            return name
    return f"vk{vk}"


@dataclass
class HotKeyConfig:
    """热键配置。

    - hold：按住单键 `hold_ms` 毫秒后呼出，松开执行；短按补发原按键。
    - doubleTap：`double_tap_ms` 内连按两次呼出，再次松开执行。
    - combo：修饰键 + 主键，按下即呼出，松开主键或任一修饰键即执行。
    """

    mode: str = MODE_HOLD
    key: str = "tab"
    modifiers: list[str] = field(default_factory=list)
    hold_ms: int = 200
    double_tap_ms: int = 250

    def __post_init__(self) -> None:
        self.mode = self.mode if self.mode in VALID_MODES else MODE_HOLD
        self.key = self.key.lower()
        if self.key not in KEY_CODES:
            self.key = "tab"
        cleaned: list[str] = []
        for item in self.modifiers:
            token = item.lower()
            if token in MODIFIER_CODES and token not in cleaned:
                cleaned.append(token)
        self.modifiers = cleaned
        self.hold_ms = max(80, min(int(self.hold_ms), 800))
        self.double_tap_ms = max(120, min(int(self.double_tap_ms), 600))

    @property
    def key_vk(self) -> int:
        return vk_from_name(self.key)

    @property
    def modifier_vks(self) -> list[int]:
        return [MODIFIER_CODES[m] for m in self.modifiers]

    def display_text(self) -> str:
        key_label = {
            "tab": "Tab",
            "space": "空格",
            "capslock": "CapsLock",
            "backquote": "`",
            "escape": "Esc",
        }.get(self.key, self.key.upper())
        mods = "+".join(MODIFIER_LABELS[m] for m in self.modifiers)
        prefix = f"{mods}+" if mods else ""
        if self.mode == MODE_HOLD:
            return f"长按 {prefix}{key_label}"
        if self.mode == MODE_DOUBLE_TAP:
            return f"双击 {prefix}{key_label}"
        return f"{prefix}{key_label}"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "key": self.key,
            "modifiers": list(self.modifiers),
            "holdMs": self.hold_ms,
            "doubleTapMs": self.double_tap_ms,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "HotKeyConfig":
        data = data or {}
        return cls(
            mode=data.get("mode", MODE_HOLD),
            key=data.get("key", "tab"),
            modifiers=list(data.get("modifiers", [])),
            hold_ms=data.get("holdMs", 200),
            double_tap_ms=data.get("doubleTapMs", 250),
        )


@dataclass
class AppearanceConfig:
    scale: float = WheelAppearance.DEFAULT_SCALE
    show_labels: bool = True
    blur_background: bool = True  # 毛玻璃：呼出时抓取并模糊盘面背后的屏幕内容
    animate: bool = True  # 入场/退场动画

    def to_dict(self) -> dict:
        return {
            "scale": self.scale,
            "showLabels": self.show_labels,
            "blurBackground": self.blur_background,
            "animate": self.animate,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "AppearanceConfig":
        data = data or {}
        return cls(
            scale=WheelAppearance.sanitized_scale(data.get("scale", 1.0)),
            show_labels=bool(data.get("showLabels", True)),
            blur_background=bool(data.get("blurBackground", True)),
            animate=bool(data.get("animate", True)),
        )


@dataclass
class GeneralConfig:
    launch_at_login: bool = False
    show_in_taskbar: bool = False

    def to_dict(self) -> dict:
        return {"launchAtLogin": self.launch_at_login, "showInTaskbar": self.show_in_taskbar}

    @classmethod
    def from_dict(cls, data: dict | None) -> "GeneralConfig":
        data = data or {}
        return cls(
            launch_at_login=bool(data.get("launchAtLogin", False)),
            show_in_taskbar=bool(data.get("showInTaskbar", False)),
        )


@dataclass
class WheelSettings:
    version: int = SETTINGS_VERSION
    hotkey: HotKeyConfig = field(default_factory=HotKeyConfig)
    appearance: AppearanceConfig = field(default_factory=AppearanceConfig)
    general: GeneralConfig = field(default_factory=GeneralConfig)
    actions: list[WheelAction] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.actions:
            self.actions = default_actions()

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "hotkey": self.hotkey.to_dict(),
            "appearance": self.appearance.to_dict(),
            "general": self.general.to_dict(),
            "actions": [a.to_dict() for a in self.actions],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WheelSettings":
        actions: list[WheelAction] = []
        for item in data.get("actions", []):
            try:
                actions.append(WheelAction.from_dict(item))
            except ValueError:
                continue  # 未知 kind 直接丢弃，避免整个配置加载失败
        _migrate_actions(actions, int(data.get("version", SETTINGS_VERSION)))
        return cls(
            # 迁移后内存里已经是当前结构，落盘时按新版本号写，避免每次加载都重跑
            version=SETTINGS_VERSION,
            hotkey=HotKeyConfig.from_dict(data.get("hotkey")),
            appearance=AppearanceConfig.from_dict(data.get("appearance")),
            general=GeneralConfig.from_dict(data.get("general")),
            actions=actions,
        )


__all__ = [
    "AppearanceConfig",
    "GeneralConfig",
    "HotKeyConfig",
    "KEY_CODES",
    "MODE_COMBO",
    "MODE_DOUBLE_TAP",
    "MODE_HOLD",
    "MODIFIER_CODES",
    "REUSABLE_EXES",
    "SETTINGS_VERSION",
    "WheelSettings",
    "name_from_vk",
    "vk_from_name",
    "WheelActionKind",
]
