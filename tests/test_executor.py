"""动作执行器测试：只覆盖解析与分发，不真的启动进程。"""

from __future__ import annotations

import pytest

from mqwheel.models.action import WheelAction, WheelActionKind
from mqwheel.services import action_executor


@pytest.mark.parametrize(
    "text,expected",
    [
        ("win+shift+s", [0x5B, 0x10, ord("S")]),
        ("ctrl+alt+delete", [0x11, 0x12, 0x2E]),
        ("ctrl+c", [0x11, ord("C")]),
        ("tab", [0x09]),
        ("", []),
        ("ctrl+nosuchkey", []),  # 主键无法识别 → 不发残缺组合
    ],
)
def test_parse_shortcut(text: str, expected: list[int]) -> None:
    assert action_executor.parse_shortcut(text) == expected


def test_execute_dispatches_by_kind(monkeypatch) -> None:
    calls: list[str] = []
    executor = action_executor.ActionExecutor()
    monkeypatch.setattr(executor, "_open_application", lambda p: calls.append("app") or True)
    monkeypatch.setattr(executor, "_open_url", lambda p: calls.append("url") or True)
    monkeypatch.setattr(executor, "_run_command", lambda p: calls.append("cmd") or True)
    monkeypatch.setattr(
        action_executor.input_sender, "send_combo", lambda vks: calls.append("keys") or True
    )

    for kind in (
        WheelActionKind.APPLICATION,
        WheelActionKind.URL,
        WheelActionKind.KEYBOARD_SHORTCUT,
        WheelActionKind.SHELL_COMMAND,
    ):
        assert executor.execute(WheelAction(title="t", kind=kind, payload="x"))

    assert calls == ["app", "url", "keys", "cmd"]


def test_open_missing_path_reports_error(tmp_path) -> None:
    executor = action_executor.ActionExecutor()
    assert not executor.execute(
        WheelAction(
            title="不存在",
            kind=WheelActionKind.APPLICATION,
            payload=str(tmp_path / "nope.exe"),
        )
    )
    assert "不存在" in executor.last_error
