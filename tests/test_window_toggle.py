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


def _patch_windows(
    monkeypatch,
    windows: list[int],
    foreground: int,
    iconic: set[int] | None = None,
    foreground_process: str = "msedge.exe",
):
    """把窗口枚举、最小化状态与前台所属进程换成假的。

    `foreground_process` 是「当前前台窗口属于哪个进程」——判断应用在不在前台
    看的就是它，所以单独一个参数比让调用方去拼 `process_name_of_window` 清楚。
    """
    iconic = iconic or set()
    monkeypatch.setattr(wc, "list_windows", lambda _name: list(windows))
    monkeypatch.setattr(wc, "foreground_window", lambda: foreground)
    monkeypatch.setattr(wc.user32, "IsIconic", lambda hwnd: wc._hwnd(hwnd) in iconic)
    monkeypatch.setattr(
        wc,
        "process_name_of_window",
        lambda hwnd: foreground_process if foreground and wc._hwnd(hwnd) == foreground else "",
    )


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
    _patch_windows(monkeypatch, [100], foreground=999, foreground_process="explorer.exe")
    activated: list[int] = []
    monkeypatch.setattr(wc, "activate", lambda hwnd: activated.append(hwnd) or True)

    assert wc.toggle(EDGE) == wc.RESULT_ACTIVATED
    assert activated == [100]


def test_toggle_minimizes_when_foreground_is_helper_window(monkeypatch) -> None:
    """前台是该应用的辅助窗口时，也要认成「它在前台」。

    浏览器的会话恢复提示、拖拽预览这类窗口带 WS_EX_TOOLWINDOW，会被候选规则
    过滤掉。此时前台句柄不在候选列表里，但用户明明就在看这个应用 ——
    按句柄判断会误判成「不在前台」，于是该收起的时候反而又呼出一次。
    """
    # 100 是真正的浏览器窗口，888 是它的辅助窗口（不在候选里）且正在前台
    _patch_windows(monkeypatch, [100], foreground=888)
    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(
        wc.user32, "ShowWindow", lambda hwnd, cmd: calls.append((wc._hwnd(hwnd), cmd)) or True
    )

    assert wc.toggle(EDGE) == wc.RESULT_MINIMIZED
    assert calls == [(100, wc.SW_MINIMIZE)], "应收起候选里那个真正的窗口"


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
    # toggle() 现在带 reuse / minimize_when_active 两个关键字参数，stub 得收下
    monkeypatch.setattr(action_executor.window_control, "toggle", lambda _p, **_kw: result)
    monkeypatch.setattr(executor, "_open_application", lambda p, **_kw: launched.append(p) or True)
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
    monkeypatch.setattr(executor, "_open_application", lambda p, **_kw: launched.append(p) or True)

    assert executor.execute(WheelAction(title="终端", kind=WheelActionKind.APPLICATION, payload="wt.exe"))
    assert launched == ["wt.exe"]


def test_toggle_kind_launches_when_reuse_disabled(monkeypatch) -> None:
    """关掉「复用窗口」之后，即使已有窗口也该走启动流程。"""
    executor, launched = _executor_with_stub(monkeypatch, wc.RESULT_NEW_WINDOW)
    action = WheelAction(title="浏览器", kind=WheelActionKind.WINDOW_TOGGLE, payload=EDGE)

    assert executor.execute(action)
    assert launched == [EDGE]


def test_toggle_kind_forwards_action_switches(monkeypatch) -> None:
    """动作上的两个开关必须原样传到 window_control.toggle()。"""
    executor = action_executor.ActionExecutor()
    seen: list[dict] = []
    monkeypatch.setattr(
        action_executor.window_control,
        "toggle",
        lambda _p, **kw: seen.append(kw) or wc.RESULT_ACTIVATED,
    )
    action = WheelAction(
        title="浏览器",
        kind=WheelActionKind.WINDOW_TOGGLE,
        payload=EDGE,
        reuse_window=False,
        minimize_when_active=False,
    )

    assert executor.execute(action)
    assert seen == [{"reuse": False, "minimize_when_active": False}]


class _InlineThreading:
    """把 threading.Thread 换成立刻同步执行 —— 测试里要能断言后台任务的内容。"""

    class Thread:
        def __init__(self, target=None, args=(), **_kwargs):
            self._target, self._args = target, args

        def start(self) -> None:
            self._target(*self._args)


def _patch_launch(monkeypatch):
    """拦掉真实启动，返回 (显示方式列表, 等待最大化的路径列表)。"""
    shown: list[int] = []
    waited: list[str] = []
    monkeypatch.setattr(
        action_executor.shell32, "ShellExecuteW", lambda *_args: shown.append(_args[-1]) or 42
    )
    monkeypatch.setattr(
        action_executor.window_control,
        "activate_when_appears",
        lambda path, **_kw: waited.append(path) or True,
    )
    monkeypatch.setattr(action_executor, "threading", _InlineThreading)
    return shown, waited


def test_open_application_requests_maximize(monkeypatch) -> None:
    """「窗口切换」新开窗口时要以最大化方式启动，并等窗口出现后再补一刀。

    Edge / Chrome 会忽略 ShellExecute 传的 nShowCmd、按自己记住的尺寸开窗，
    所以除了请求最大化，还得挂一个「等窗口出现再最大化」的后台任务。
    """
    shown, waited = _patch_launch(monkeypatch)
    executor = action_executor.ActionExecutor()

    assert executor._open_application(EDGE, maximize=True)
    assert shown == [action_executor.SW_SHOWMAXIMIZED]
    assert waited == [EDGE], "启动后要等窗口出现再最大化"


def test_open_application_plain_launch_stays_normal(monkeypatch) -> None:
    """普通「应用」类型保持原样：正常大小打开，不挂后台任务。"""
    shown, waited = _patch_launch(monkeypatch)
    executor = action_executor.ActionExecutor()

    assert executor._open_application(EDGE)
    assert shown == [action_executor.SW_SHOWNORMAL]
    assert waited == [], "不该多挂一个等待任务"


# endregion


# region 两个行为开关


def test_toggle_new_window_mode_never_touches_existing(monkeypatch) -> None:
    """关掉「复用窗口」后，已经有窗口也不该去动它。"""
    _patch_windows(monkeypatch, [100], foreground=100)
    shown: list[tuple[int, int]] = []
    activated: list[int] = []
    monkeypatch.setattr(
        wc.user32, "ShowWindow", lambda hwnd, cmd: shown.append((wc._hwnd(hwnd), cmd)) or True
    )
    monkeypatch.setattr(wc, "activate", lambda hwnd: activated.append(hwnd) or True)

    assert wc.toggle(EDGE, reuse=False) == wc.RESULT_NEW_WINDOW
    assert shown == [], "不复用就不该收起任何窗口"
    assert activated == [], "不复用也不该呼出任何窗口"


def test_toggle_keeps_window_when_minimize_disabled(monkeypatch) -> None:
    """关掉「已经在前台时收起」后，再点一次只是重新顶到最前。"""
    _patch_windows(monkeypatch, [100], foreground=100)
    shown: list[tuple[int, int]] = []
    activated: list[int] = []
    monkeypatch.setattr(
        wc.user32, "ShowWindow", lambda hwnd, cmd: shown.append((wc._hwnd(hwnd), cmd)) or True
    )
    monkeypatch.setattr(wc, "activate", lambda hwnd: activated.append(hwnd) or True)

    assert wc.toggle(EDGE, minimize_when_active=False) == wc.RESULT_ACTIVATED
    assert shown == [], "开关关掉后不该收起"
    assert activated == [100]


# endregion


# region 新窗口出现后再最大化


def test_activate_when_appears_waits_for_window(monkeypatch) -> None:
    """刚启动的应用窗口不会立刻出现，要轮询等；等到了就最大化并记住它。"""
    windows = iter([[], [], [100]])
    monkeypatch.setattr(wc, "list_windows", lambda _name: next(windows))
    monkeypatch.setattr(wc.time, "sleep", lambda _seconds: None)
    activated: list[int] = []
    monkeypatch.setattr(wc, "activate", lambda hwnd: activated.append(hwnd) or True)

    assert wc.activate_when_appears(EDGE, timeout=5)
    assert activated == [100]
    assert wc._last_window == 100, "记住它，下次按才能正确收起"


def test_activate_when_appears_gives_up_on_timeout(monkeypatch) -> None:
    """窗口一直不出现就别死等，返回 False 让调用方自己决定。"""
    monkeypatch.setattr(wc, "list_windows", lambda _name: [])
    monkeypatch.setattr(wc.time, "sleep", lambda _seconds: None)
    activated: list[int] = []
    monkeypatch.setattr(wc, "activate", lambda hwnd: activated.append(hwnd) or True)

    assert not wc.activate_when_appears(EDGE, timeout=0)
    assert activated == []


def test_activate_when_appears_rejects_empty_path() -> None:
    assert not wc.activate_when_appears("")
    assert not wc.activate_when_appears("   ")


# endregion


# region 配置字段的读写


def test_new_switches_default_to_previous_behaviour() -> None:
    """两个新字段的默认值必须等于「这个功能一开始的样子」。"""
    action = WheelAction(title="浏览器", kind=WheelActionKind.WINDOW_TOGGLE, payload=EDGE)
    assert action.reuse_window is True
    assert action.minimize_when_active is True


def test_switches_survive_round_trip() -> None:
    action = WheelAction(
        title="浏览器",
        kind=WheelActionKind.WINDOW_TOGGLE,
        payload=EDGE,
        reuse_window=False,
        minimize_when_active=False,
    )
    restored = WheelAction.from_dict(action.to_dict())
    assert restored.reuse_window is False
    assert restored.minimize_when_active is False


def test_old_settings_without_switches_still_load() -> None:
    """升级前存下来的配置里没有这两个键，读进来要沿用旧行为而不是炸掉。"""
    legacy = {
        "id": "abc",
        "title": "浏览器",
        "kind": WheelActionKind.WINDOW_TOGGLE.value,
        "payload": EDGE,
    }
    restored = WheelAction.from_dict(legacy)
    assert restored.reuse_window is True
    assert restored.minimize_when_active is True


# endregion
