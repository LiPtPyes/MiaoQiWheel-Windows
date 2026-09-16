"""预设库测试：模板渲染、反解析、引号往返、预设与实现的一致性。"""

from __future__ import annotations

import os

import pytest

from mqwheel.models.action import WheelAction, WheelActionKind
from mqwheel.models.presets import (
    BUILTINS,
    BUILTIN_PREFIX,
    CATEGORIES,
    KIND_INTEGER,
    PresetParameter,
    ScriptPreset,
    all_presets,
    builtin_id_of,
    by_category,
    by_id,
    matching,
    selection_id,
    shell_quote,
    shell_unquote,
)


# region 引号与参数值
@pytest.mark.parametrize(
    "value",
    [
        r"C:\Program Files\Tool",
        r"C:\Users\a b\文档",
        'say "hi" there',
        "",
        "no-spaces",
    ],
)
def test_shell_quote_round_trip(value: str) -> None:
    assert shell_unquote(shell_quote(value)) == value


def test_shell_quote_always_wraps() -> None:
    assert shell_quote("plain") == '"plain"'
    assert shell_quote('a"b') == '"a""b"'


def test_integer_parameter_clamps() -> None:
    parameter = PresetParameter(
        id="volume", title="音量", default="50", kind=KIND_INTEGER, minimum=0, maximum=100
    )
    assert parameter.command_value("80") == "80"
    assert parameter.command_value("500") == "100"
    assert parameter.command_value("-5") == "0"
    assert parameter.command_value("abc") == "50"
    assert parameter.display_value("42") == "42"


def test_unknown_integer_falls_back_to_minimum() -> None:
    parameter = PresetParameter(id="n", title="n", default="", kind=KIND_INTEGER)
    assert parameter.command_value("xyz") == "0"


# endregion


# region 渲染与反解析
def test_command_renders_defaults() -> None:
    preset = by_id("set-volume")
    assert preset is not None
    action = preset.make_action()
    assert action.payload == BUILTIN_PREFIX + "set-volume"
    assert action.preset_params == {"volume": "50"}


def test_open_path_quotes_value() -> None:
    preset = by_id("open-path")
    assert preset is not None
    command = preset.command({"path": r"C:\Program Files\App"})
    assert command == r'explorer.exe "C:\Program Files\App"'


def test_shutdown_clamps_delay() -> None:
    preset = by_id("shutdown")
    assert preset is not None
    assert preset.command({"delay": "99999"}) == "shutdown.exe /s /t 3600"
    assert preset.command({"delay": "30"}) == "shutdown.exe /s /t 30"


def test_parameter_values_reverse_parse() -> None:
    preset = by_id("open-path")
    assert preset is not None
    command = preset.command({"path": r"C:\Users\a b"})
    assert preset.parameter_values(command) == {"path": r"C:\Users\a b"}


def test_parameter_values_round_trip_with_quotes() -> None:
    preset = by_id("copy-text")
    assert preset is not None  # builtin 无占位符，参数走 preset_params
    action = preset.make_action({"text": '含"引号"的文本'})
    assert action.preset_params == {"text": '含"引号"的文本'}
    assert matching(action.payload) is preset


def test_parameter_values_mismatch_returns_none() -> None:
    preset = by_id("open-path")
    assert preset is not None
    assert preset.parameter_values("explorer.exe") is None
    assert preset.parameter_values("notepad.exe x") is None


def test_matching_finds_preset_from_command() -> None:
    assert matching("rundll32.exe user32.dll,LockWorkStation") is by_id("lock-screen")
    assert matching("win+shift+s") is by_id("screenshot")
    assert matching("ms-settings:") is by_id("open-settings")
    assert matching("totally-unknown-command") is None


def test_matching_finds_rendered_parameterized_command() -> None:
    preset = by_id("terminal-at-folder")
    assert preset is not None
    command = preset.command({"folder": r"D:\工作"})
    assert matching(command) is preset


def test_selection_id_prefers_stored_id() -> None:
    action = WheelAction(title="x", kind=WheelActionKind.SHELL_COMMAND, payload="whoami")
    assert selection_id(action) == ScriptPreset.CUSTOM_ID
    action.preset_id = "sleep"
    assert selection_id(action) == "sleep"


def test_selection_id_recovers_from_payload() -> None:
    action = WheelAction(
        title="x",
        kind=WheelActionKind.SHELL_COMMAND,
        payload="shutdown.exe /h",
        preset_id=None,
    )
    assert selection_id(action) == "hibernate"


# endregion


# region 预设库整体约束
def test_ids_are_unique() -> None:
    ids = [p.id for p in BUILTINS]
    assert len(ids) == len(set(ids))


def test_every_preset_has_valid_category_and_symbol() -> None:
    for preset in all_presets():
        assert preset.category in CATEGORIES, preset.id
        assert preset.symbol.startswith("fa6s."), preset.id
        assert preset.title and preset.subtitle, preset.id


def test_categories_are_populated() -> None:
    grouped = by_category()
    assert len(grouped[CATEGORIES[0]]) >= 5  # 系统
    assert len(grouped[CATEGORIES[1]]) >= 2  # 文件与应用
    assert len(grouped[CATEGORIES[2]]) >= 1  # 文本
    assert sum(len(v) for v in grouped.values()) == len(BUILTINS)


def test_builtin_presets_have_implementations() -> None:
    from mqwheel.services import builtin_actions

    builtin_presets = [p for p in all_presets() if p.kind == WheelActionKind.BUILTIN.value]
    assert builtin_presets, "应当存在内置动作预设"
    for preset in builtin_presets:
        assert preset.command_template == BUILTIN_PREFIX + preset.id, preset.id
        assert preset.id in builtin_actions.REGISTRY, f"{preset.id} 缺少实现"


def test_keyboard_presets_parse() -> None:
    from mqwheel.services.action_executor import parse_shortcut

    for preset in all_presets():
        if preset.kind == WheelActionKind.KEYBOARD_SHORTCUT.value:
            assert parse_shortcut(preset.command_template), preset.id


def test_every_preset_produces_executable_action() -> None:
    for preset in all_presets():
        action = preset.make_action()
        assert action.kind == WheelActionKind(preset.kind)
        if preset.kind == WheelActionKind.BUILTIN.value:
            assert builtin_id_of(action) == preset.id
        else:
            assert action.payload, preset.id


def test_default_actions_reference_presets() -> None:
    from mqwheel.models.action import default_actions

    actions = default_actions()
    assert len(actions) == 6
    assert actions[0].preset_id == "lock-screen"
    assert actions[1].preset_id == "screenshot"


def test_default_action_paths_stay_absolute_without_env(monkeypatch) -> None:
    """环境变量缺失时，默认动作里的可执行文件路径也不能变成相对路径。

    `LOCALAPPDATA` / `ProgramFiles` 在从 Git Bash、部分启动器拉起时会**整批缺失**，
    而 ``os.path.join(os.environ.get(NAME, ""), ...)`` 会拼出一条**相对路径**。
    它会被写进默认设置并一直错下去，用户点「终端」看到的是「点了没反应」。
    """
    from mqwheel.models.action import default_actions

    for name in ("LOCALAPPDATA", "ProgramFiles", "ProgramFiles(x86)"):
        monkeypatch.delenv(name, raising=False)

    for action in default_actions():
        if action.kind is WheelActionKind.APPLICATION and os.sep in action.payload:
            assert os.path.isabs(action.payload), (
                f"「{action.title}」的路径不是绝对路径：{action.payload}"
            )


def test_wt_path_falls_back_to_bare_name(monkeypatch) -> None:
    """终端找不到时退回裸 `wt.exe` 交给 PATH，而不是相对路径。"""
    from mqwheel.models.action import _wt_path

    monkeypatch.setenv("LOCALAPPDATA", r"C:\definitely\not\here")
    assert _wt_path() == "wt.exe"

    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    assert _wt_path() == "wt.exe"
