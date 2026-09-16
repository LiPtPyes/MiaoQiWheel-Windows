"""脚本预设：参数化命令模板，对齐 macOS 版 WheelScriptPreset。

两种实现方式：
- **命令模板**（`{{param}}` 占位符）：参数值经过 shell 引号处理后写进 payload，
  因此 payload 本身就是可直接执行的命令，反解析时按模板切出正则还原参数值。
- **内置动作**（payload 形如 `builtin:<id>`）：无法用命令行可靠表达的操作
  （关显示器、改深色模式、写剪贴板、调音量），参数值存在 `preset_params` 里，
  彻底绕开 cmd/PowerShell 的引号嵌套问题。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from mqwheel.models.action import WheelAction, WheelActionKind

CATEGORY_SYSTEM = "系统"
CATEGORY_FILES = "文件与应用"
CATEGORY_TEXT = "文本"
CATEGORIES = (CATEGORY_SYSTEM, CATEGORY_FILES, CATEGORY_TEXT)

KIND_TEXT = "text"
KIND_PATH = "path"
KIND_INTEGER = "integer"

BUILTIN_PREFIX = "builtin:"


def shell_quote(value: str) -> str:
    """按 cmd.exe 语义加引号：始终包裹双引号，内部双引号写成两个。"""
    return '"' + value.replace('"', '""') + '"'


def shell_unquote(raw: str) -> str:
    if len(raw) >= 2 and raw.startswith('"') and raw.endswith('"'):
        raw = raw[1:-1]
    return raw.replace('""', '"')


@dataclass(frozen=True)
class PresetParameter:
    id: str
    title: str
    placeholder: str = ""
    default: str = ""
    kind: str = KIND_TEXT
    minimum: int = 0
    maximum: int = 100

    def command_value(self, value: str) -> str:
        if self.kind == KIND_INTEGER:
            try:
                number = int(value)
            except ValueError:
                number = int(self.default) if self.default.isdigit() else self.minimum
            return str(min(max(number, self.minimum), self.maximum))
        return shell_quote(value)

    def display_value(self, raw: str) -> str:
        if self.kind == KIND_INTEGER:
            return raw
        return shell_unquote(raw)

    def sanitized(self, value: str) -> str:
        """给 UI 用：把任意输入规整成合法值。"""
        if self.kind == KIND_INTEGER:
            try:
                number = int(value)
            except ValueError:
                number = int(self.default) if self.default.isdigit() else self.minimum
            return str(min(max(number, self.minimum), self.maximum))
        return value


@dataclass(frozen=True)
class ScriptPreset:
    id: str
    title: str
    subtitle: str
    symbol: str
    category: str
    kind: str = WheelActionKind.SHELL_COMMAND.value
    command_template: str = ""
    parameters: tuple[PresetParameter, ...] = ()

    CUSTOM_ID = "custom"

    @property
    def default_parameters(self) -> dict[str, str]:
        return {p.id: p.default for p in self.parameters}

    def command(self, values: dict[str, str] | None = None) -> str:
        values = values or {}
        result = self.command_template
        for parameter in self.parameters:
            value = values.get(parameter.id, parameter.default)
            result = result.replace("{{%s}}" % parameter.id, parameter.command_value(value))
        return result

    def parameter_values(self, command: str) -> dict[str, str] | None:
        """从已渲染的命令反推参数值；不匹配返回 None（对齐 macOS 实现）。"""
        # 内置动作的参数存在 preset_params 里，模板不带占位符，走精确比较
        templated = [p for p in self.parameters if "{{%s}}" % p.id in self.command_template]
        if not templated:
            return {} if command == self.command_template else None

        pattern = "^"
        remaining = self.command_template
        for parameter in templated:
            token = "{{%s}}" % parameter.id
            position = remaining.find(token)
            if position < 0:
                return None
            pattern += re.escape(remaining[:position]) + "(.+?)"
            remaining = remaining[position + len(token) :]
        pattern += re.escape(remaining) + "$"

        match = re.match(pattern, command, re.DOTALL)
        if match is None:
            return None
        values = {
            parameter.id: parameter.display_value(match.group(index + 1))
            for index, parameter in enumerate(templated)
        }
        # 未出现在模板里的参数（内置动作）补默认值
        for parameter in self.parameters:
            values.setdefault(parameter.id, parameter.default)
        return values

    def make_action(self, values: dict[str, str] | None = None) -> WheelAction:
        resolved = dict(self.default_parameters)
        resolved.update(values or {})
        resolved = {p.id: p.sanitized(resolved[p.id]) for p in self.parameters}
        return WheelAction(
            title=self.title,
            subtitle=self.subtitle,
            symbol=self.symbol,
            kind=WheelActionKind(self.kind),
            payload=self.command(resolved),
            preset_id=self.id,
            preset_params=resolved,
        )


def _preset(
    preset_id: str,
    title: str,
    subtitle: str,
    symbol: str,
    category: str,
    template: str,
    kind: str = WheelActionKind.SHELL_COMMAND.value,
    parameters: tuple[PresetParameter, ...] = (),
) -> ScriptPreset:
    return ScriptPreset(
        id=preset_id,
        title=title,
        subtitle=subtitle,
        symbol=symbol,
        category=category,
        kind=kind,
        command_template=template,
        parameters=parameters,
    )


BUILTINS: tuple[ScriptPreset, ...] = (
    # region 系统
    _preset(
        "lock-screen",
        "锁定屏幕",
        "立即锁定工作站",
        "fa6s.lock",
        CATEGORY_SYSTEM,
        "rundll32.exe user32.dll,LockWorkStation",
    ),
    _preset(
        "turn-off-display",
        "关闭显示器",
        "屏幕立即变黑，动一下鼠标恢复",
        "fa6s.display",
        CATEGORY_SYSTEM,
        BUILTIN_PREFIX + "turn-off-display",
        kind=WheelActionKind.BUILTIN.value,
    ),
    _preset(
        "start-screen-saver",
        "启动屏幕保护",
        "立即进入已设置的屏保",
        "fa6s.images",
        CATEGORY_SYSTEM,
        BUILTIN_PREFIX + "start-screen-saver",
        kind=WheelActionKind.BUILTIN.value,
    ),
    _preset(
        "sleep",
        "睡眠",
        "立即进入睡眠，保留内存",
        "fa6s.moon",
        CATEGORY_SYSTEM,
        "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
    ),
    _preset(
        "hibernate",
        "休眠",
        "保存会话后断电",
        "fa6s.bed",
        CATEGORY_SYSTEM,
        "shutdown.exe /h",
    ),
    _preset(
        "shutdown",
        "关机",
        "延迟指定秒数后关机",
        "fa6s.power-off",
        CATEGORY_SYSTEM,
        "shutdown.exe /s /t {{delay}}",
        parameters=(
            PresetParameter(
                id="delay",
                title="延迟秒数",
                placeholder="0–3600",
                default="0",
                kind=KIND_INTEGER,
                minimum=0,
                maximum=3600,
            ),
        ),
    ),
    _preset(
        "restart",
        "重启",
        "延迟指定秒数后重启",
        "fa6s.arrows-rotate",
        CATEGORY_SYSTEM,
        "shutdown.exe /r /t {{delay}}",
        parameters=(
            PresetParameter(
                id="delay",
                title="延迟秒数",
                placeholder="0–3600",
                default="0",
                kind=KIND_INTEGER,
                minimum=0,
                maximum=3600,
            ),
        ),
    ),
    _preset(
        "sign-out",
        "注销",
        "退出当前用户",
        "fa6s.right-from-bracket",
        CATEGORY_SYSTEM,
        "shutdown.exe /l",
    ),
    _preset(
        "toggle-dark-mode",
        "切换深色模式",
        "在浅色与深色外观间切换",
        "fa6s.circle-half-stroke",
        CATEGORY_SYSTEM,
        BUILTIN_PREFIX + "toggle-dark-mode",
        kind=WheelActionKind.BUILTIN.value,
    ),
    _preset(
        "toggle-mute",
        "切换静音",
        "按下系统静音键",
        "fa6s.volume-xmark",
        CATEGORY_SYSTEM,
        "volume_mute",
        kind=WheelActionKind.KEYBOARD_SHORTCUT.value,
    ),
    _preset(
        "set-volume",
        "设置音量",
        "把系统音量设为指定百分比",
        "fa6s.volume-high",
        CATEGORY_SYSTEM,
        BUILTIN_PREFIX + "set-volume",
        kind=WheelActionKind.BUILTIN.value,
        parameters=(
            PresetParameter(
                id="volume",
                title="音量",
                placeholder="0–100",
                default="50",
                kind=KIND_INTEGER,
                minimum=0,
                maximum=100,
            ),
        ),
    ),
    _preset(
        "screenshot",
        "区域截图",
        "调用系统截图工具",
        "fa6s.camera",
        CATEGORY_SYSTEM,
        "win+shift+s",
        kind=WheelActionKind.KEYBOARD_SHORTCUT.value,
    ),
    _preset(
        "task-view",
        "任务视图",
        "显示所有窗口与虚拟桌面",
        "fa6s.border-all",
        CATEGORY_SYSTEM,
        "win+tab",
        kind=WheelActionKind.KEYBOARD_SHORTCUT.value,
    ),
    _preset(
        "new-virtual-desktop",
        "新建虚拟桌面",
        "切换到全新的桌面",
        "fa6s.desktop",
        CATEGORY_SYSTEM,
        "win+ctrl+d",
        kind=WheelActionKind.KEYBOARD_SHORTCUT.value,
    ),
    _preset(
        "run-dialog",
        "运行对话框",
        "打开「运行」",
        "fa6s.terminal",
        CATEGORY_SYSTEM,
        "win+r",
        kind=WheelActionKind.KEYBOARD_SHORTCUT.value,
    ),
    _preset(
        "clipboard-history",
        "剪贴板历史",
        "查看最近复制的内容",
        "fa6s.clipboard",
        CATEGORY_SYSTEM,
        "win+v",
        kind=WheelActionKind.KEYBOARD_SHORTCUT.value,
    ),
    _preset(
        "notification-center",
        "通知中心",
        "打开通知与日历面板",
        "fa6s.bell",
        CATEGORY_SYSTEM,
        "win+n",
        kind=WheelActionKind.KEYBOARD_SHORTCUT.value,
    ),
    _preset(
        "empty-recycle-bin",
        "清空回收站",
        "静默清空，不弹确认框",
        "fa6s.trash-can",
        CATEGORY_SYSTEM,
        'powershell.exe -NoProfile -Command "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"',
    ),
    _preset(
        "open-settings",
        "系统设置",
        "打开 Windows 设置",
        "fa6s.gear",
        CATEGORY_SYSTEM,
        "ms-settings:",
        kind=WheelActionKind.URL.value,
    ),
    # endregion
    # region 文件与应用
    _preset(
        "open-path",
        "打开文件或文件夹",
        "用默认方式打开指定位置",
        "fa6s.folder-open",
        CATEGORY_FILES,
        "explorer.exe {{path}}",
        parameters=(
            PresetParameter(
                id="path",
                title="位置",
                placeholder=r"C:\Users\…",
                default="%USERPROFILE%",
                kind=KIND_PATH,
            ),
        ),
    ),
    _preset(
        "terminal-at-folder",
        "在此处打开命令行",
        "在指定文件夹启动终端",
        "fa6s.terminal",
        CATEGORY_FILES,
        "cmd.exe /k cd /d {{folder}}",
        parameters=(
            PresetParameter(
                id="folder",
                title="文件夹",
                placeholder=r"C:\Users\…",
                default="%USERPROFILE%",
                kind=KIND_PATH,
            ),
        ),
    ),
    # endregion
    # region 文本
    _preset(
        "copy-text",
        "复制文本",
        "把指定内容写入剪贴板",
        "fa6s.copy",
        CATEGORY_TEXT,
        BUILTIN_PREFIX + "copy-text",
        kind=WheelActionKind.BUILTIN.value,
        parameters=(
            PresetParameter(
                id="text",
                title="文本",
                placeholder="要复制的内容",
                default="",
                kind=KIND_TEXT,
            ),
        ),
    ),
    _preset(
        "speak-text",
        "朗读文本",
        "用系统语音读出内容",
        "fa6s.comment-dots",
        CATEGORY_TEXT,
        BUILTIN_PREFIX + "speak-text",
        kind=WheelActionKind.BUILTIN.value,
        parameters=(
            PresetParameter(
                id="text",
                title="文本",
                placeholder="要朗读的内容",
                default="你好",
                kind=KIND_TEXT,
            ),
        ),
    ),
    # endregion
)

_BY_ID: dict[str, ScriptPreset] = {preset.id: preset for preset in BUILTINS}


def all_presets() -> list[ScriptPreset]:
    return list(BUILTINS)


def by_id(preset_id: str | None) -> ScriptPreset | None:
    return _BY_ID.get(preset_id or "")


def by_category() -> dict[str, list[ScriptPreset]]:
    grouped: dict[str, list[ScriptPreset]] = {name: [] for name in CATEGORIES}
    for preset in BUILTINS:
        grouped.setdefault(preset.category, []).append(preset)
    return grouped


def matching(command: str) -> ScriptPreset | None:
    """按 payload 反查预设：先精确匹配内置动作，再用模板正则匹配。"""
    for preset in BUILTINS:
        if preset.parameter_values(command) is not None:
            return preset
    return None


def selection_id(action: WheelAction) -> str:
    """设置界面里预设下拉框该选中哪一项。"""
    if action.preset_id == ScriptPreset.CUSTOM_ID:
        return ScriptPreset.CUSTOM_ID
    if action.preset_id in _BY_ID:
        return action.preset_id
    found = matching(action.payload)
    return found.id if found else ScriptPreset.CUSTOM_ID


def builtin_id_of(action: WheelAction) -> str | None:
    """内置动作的实际 id（来自 preset_id 或 payload 前缀）。"""
    if action.kind != WheelActionKind.BUILTIN:
        return None
    if action.preset_id and action.preset_id in _BY_ID:
        return action.preset_id
    if action.payload.startswith(BUILTIN_PREFIX):
        return action.payload[len(BUILTIN_PREFIX) :]
    return None


__all__ = [
    "BUILTIN_PREFIX",
    "BUILTINS",
    "CATEGORIES",
    "CATEGORY_FILES",
    "CATEGORY_SYSTEM",
    "CATEGORY_TEXT",
    "KIND_INTEGER",
    "KIND_PATH",
    "KIND_TEXT",
    "PresetParameter",
    "ScriptPreset",
    "all_presets",
    "builtin_id_of",
    "by_category",
    "by_id",
    "matching",
    "selection_id",
    "shell_quote",
    "shell_unquote",
]
