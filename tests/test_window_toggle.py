"""窗口呼出/最小化的决策逻辑测试。

不碰真实窗口：list_windows / foreground_window / ShowWindow 全部替换成假的，
只验证「什么情况走哪条分支」。真实行为由手工冒烟脚本覆盖。
"""

from __future__ import annotations

import pytest

from mqwheel.models.action import WheelAction, WheelActionKind
from mqwheel.services import action_executor, window_control as wc

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


@pytest.fixture(autouse=True)
def _clean_memory():
    wc.reset()
    yield
    wc.reset()


def _patch_windows(monkeypatch, windows: list[int], foreground: int, iconic: set[int] | None = None):
    """把窗口枚举与最小化状态换成假的。"""
    iconic = iconic or set()
    monkeypatch.setattr(wc, "list_windows", lambda _name: list(windows))
    monkeypatch.setattr(wc, "foreground_window", lambda: foreground)
    monkeypatch.setattr(wc.user32, "IsIconic", lambda hwnd: wc._hwnd(hwnd) in iconic)


def test_toggle_reports_not_running(monkeypatch) -> None:
    _patch_windows(monkeypatch, [], 0)
    assert wc.toggle(EDGE) == wc.RESULT_NOT_RUNNING


def test_toggle_rejects_empty_path() -> None:
    assert wc.toggle("") == wc.RESULT_FAILED
    assert wc.toggle("   ") == wc.RESULT_FAILED


def test_toggle_minimizes_when_already_foreground(monkeypatch) -> None:
    _patch_windows(monkeypatch, [100, 200], foreground=200)
    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(wc.user32, "ShowWindow", lambda hwnd, cmd: calls.append((wc._hwnd(hwnd), cmd)) or True)

    assert wc.toggle(EDGE) == wc.RESULT_MINIMIZED
    assert calls == [(200, wc.SW_MINIMIZE)]


def test_toggle_activates_when_foreground_is_minimized(monkeypatch) -> None:
    """窗口最小化后 GetForegroundWindow 仍可能返回它——此时必须走呼出分支。

    只看句柄相等会又走一次最小化，表现成「按了没反应」。
    """
    _patch_windows(monkeypatch, [100], foreground=100, iconic={100})
    activated: list[int] = []
    monkeypatch.setattr(wc, "activate", lambda hwnd: activated.append(hwnd) or True)

    assert wc.toggle(EDGE) == wc.RESULT_ACTIVATED
    assert activated == [100]


def test_toggle_activates_when_foreground_is_other_app(monkeypatch) -> None:
    _patch_windows(monkeypatch, [100], foreground=999)
    activated: list[int] = []
    monkeypatch.setattr(wc, "activate", lambda hwnd: activated.append(hwnd) or True)

    assert wc.toggle(EDGE) == wc.RESULT_ACTIVATED
    assert activated == [100]


def test_pick_skips_minimized_window_without_memory(monkeypatch) -> None:
    monkeypatch.setattr(wc.user32, "IsIconic", lambda hwnd: wc._hwnd(hwnd) == 100)
    assert wc._pick([100, 200]) == 200


def test_pick_restores_remembered_window(monkeypatch) -> None:
    """多窗口时「收起 → 再按一次」要原样还原刚才那个，而不是换一个。"""
    monkeypatch.setattr(wc.user32, "IsIconic", lambda hwnd: wc._hwnd(hwnd) == 100)
    wc._last_window = 100
    assert wc._pick([100, 200]) == 100


def test_pick_falls_back_to_first_when_all_minimized(monkeypatch) -> None:
    monkeypatch.setattr(wc.user32, "IsIconic", lambda _hwnd: True)
    assert wc._pick([100, 200]) == 100


def test_activate_restores_before_maximizing(monkeypatch) -> None:
    monkeypatch.setattr(wc.user32, "IsIconic", lambda _hwnd: True)
    commands: list[int] = []
    monkeypatch.setattr(wc.user32, "ShowWindow", lambda hwnd, cmd: commands.append(cmd) or True)
    monkeypatch.setattr(wc, "_try_foreground", lambda _hwnd: True)

    assert wc.activate(100)
    assert commands == [wc.SW_RESTORE, wc.SW_SHOWMAXIMIZED]


def test_activate_skips_restore_when_not_minimized(monkeypatch) -> None:
    monkeypatch.setattr(wc.user32, "IsIconic", lambda _hwnd: False)
    commands: list[int] = []
    monkeypatch.setattr(wc.user32, "ShowWindow", lambda hwnd, cmd: commands.append(cmd) or True)
    monkeypatch.setattr(wc, "_try_foreground", lambda _hwnd: True)

    assert wc.activate(100)
    assert commands == [wc.SW_SHOWMAXIMIZED]


# region 执行器接线


def _executor_with_stub(monkeypatch, result: str):
    executor = action_executor.ActionExecutor()
    launched: list[str] = []
    monkeypatch.setattr(action_executor.window_control, "toggle", lambda _p: result)
    monkeypatch.setattr(executor, "_open_application", lambda p: launched.append(p) or True)
    return executor, launched


def test_toggle_kind_launches_only_when_not_running(monkeypatch) -> None:
    executor, launched = _executor_with_stub(monkeypatch, wc.RESULT_NOT_RUNNING)
    action = WheelAction(title="浏览器", kind=WheelActionKind.WINDOW_TOGGLE, payload=EDGE)

    assert executor.execute(action)
    assert launched == [EDGE], "没在运行时才该启动"


@pytest.mark.parametrize("result", [wc.RESULT_ACTIVATED, wc.RESULT_MINIMIZED])
def test_toggle_kind_does_not_launch_when_window_exists(monkeypatch, result: str) -> None:
    executor, launched = _executor_with_stub(monkeypatch, result)
    action = WheelAction(title="浏览器", kind=WheelActionKind.WINDOW_TOGGLE, payload=EDGE)

    assert executor.execute(action)
    assert launched == [], "已有窗口时绝不能再启动一个"


def test_toggle_kind_without_payload_reports_error(monkeypatch) -> None:
    executor, _ = _executor_with_stub(monkeypatch, wc.RESULT_NOT_RUNNING)
    assert not executor.execute(
        WheelAction(title="空", kind=WheelActionKind.WINDOW_TOGGLE, payload="")
    )
    assert "未指定应用" in executor.last_error


def test_application_kind_still_always_launches(monkeypatch) -> None:
    """终端这类要保持每次新建，不能受窗口切换逻辑影响。"""
    executor = action_executor.ActionExecutor()
    launched: list[str] = []
    monkeypatch.setattr(executor, "_open_application", lambda p: launched.append(p) or True)

    assert executor.execute(WheelAction(title="终端", kind=WheelActionKind.APPLICATION, payload="wt.exe"))
    assert launched == ["wt.exe"]


# endregion
