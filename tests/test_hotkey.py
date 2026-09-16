"""热键状态机测试：不安装真实钩子，只驱动纯逻辑。"""

from __future__ import annotations

import pytest

from mqwheel.models.settings import MODE_COMBO, MODE_DOUBLE_TAP, MODE_HOLD, HotKeyConfig
from mqwheel.services.hotkey import PASS_THROUGH, SWALLOW, HotKeyStateMachine

VK_TAB = 0x09
VK_SPACE = 0x20
VK_CONTROL = 0x11
VK_ALT = 0x12
VK_SHIFT = 0x10
VK_LWIN = 0x5B


class Recorder:
    def __init__(self) -> None:
        self.activated = 0
        self.released = 0
        self.reemitted: list[int] = []
        self.scheduled: list[int] = []
        self.cancelled = 0

    def build(self, config: HotKeyConfig, clock: list[int]) -> HotKeyStateMachine:
        def now() -> int:
            return clock[0]

        return HotKeyStateMachine(
            config,
            on_activate=lambda: setattr(self, "activated", self.activated + 1),
            on_release=lambda: setattr(self, "released", self.released + 1),
            on_reemit=self.reemitted.append,
            on_schedule=self.scheduled.append,
            on_cancel=lambda: setattr(self, "cancelled", self.cancelled + 1),
            now_fn=now,
        )


def _hold(label: str = "") -> Recorder:
    return Recorder()


def test_hold_short_tap_passes_through() -> None:
    rec = Recorder()
    clock = [1000]
    machine = rec.build(HotKeyConfig(mode=MODE_HOLD, key="tab", hold_ms=200), clock)

    assert machine.on_key_down(VK_TAB, set()) == SWALLOW
    clock[0] = 1120  # 120ms < 200ms 阈值
    assert machine.on_key_up(VK_TAB) == SWALLOW

    assert rec.activated == 0
    assert rec.released == 0
    assert rec.cancelled == 1
    assert rec.reemitted == [VK_TAB]  # 补发一次原生 Tab


def test_hold_long_press_activates_and_releases() -> None:
    rec = Recorder()
    clock = [1000]
    machine = rec.build(HotKeyConfig(mode=MODE_HOLD, key="tab", hold_ms=200), clock)

    assert machine.on_key_down(VK_TAB, set()) == SWALLOW
    assert rec.scheduled == [200]
    clock[0] = 1250
    machine.on_tick()
    assert rec.activated == 1
    assert machine.state == "active"

    # 长按期间的自动重复不应该漏给前台应用
    assert machine.on_key_down(VK_TAB, set()) == SWALLOW
    assert machine.on_key_up(VK_TAB) == SWALLOW
    assert rec.released == 1
    assert machine.state == "idle"


def test_hold_ignores_when_modifier_pressed() -> None:
    rec = Recorder()
    clock = [1000]
    machine = rec.build(HotKeyConfig(mode=MODE_HOLD, key="tab", hold_ms=200), clock)

    # Alt+Tab / Ctrl+Tab 必须保持系统原有行为
    assert machine.on_key_down(VK_TAB, {VK_ALT}) == PASS_THROUGH
    assert machine.on_key_up(VK_TAB) == PASS_THROUGH
    assert rec.activated == 0
    assert rec.reemitted == []


def test_hold_ignores_other_keys() -> None:
    rec = Recorder()
    clock = [1000]
    machine = rec.build(HotKeyConfig(mode=MODE_HOLD, key="tab", hold_ms=200), clock)
    assert machine.on_key_down(VK_SPACE, set()) == PASS_THROUGH
    assert machine.on_key_up(VK_SPACE) == PASS_THROUGH
    assert rec.released == 0


def test_double_tap_second_press_activates() -> None:
    rec = Recorder()
    clock = [1000]
    machine = rec.build(HotKeyConfig(mode=MODE_DOUBLE_TAP, key="tab", double_tap_ms=250), clock)

    assert machine.on_key_down(VK_TAB, set()) == PASS_THROUGH  # 第一次放行
    clock[0] = 1050
    assert machine.on_key_up(VK_TAB) == PASS_THROUGH
    assert machine.on_key_down(VK_TAB, set()) == SWALLOW  # 250ms 内第二次
    assert rec.activated == 1
    assert machine.on_key_up(VK_TAB) == SWALLOW
    assert rec.released == 1


def test_double_tap_ignores_slow_presses() -> None:
    rec = Recorder()
    clock = [1000]
    machine = rec.build(HotKeyConfig(mode=MODE_DOUBLE_TAP, key="tab", double_tap_ms=250), clock)
    machine.on_key_down(VK_TAB, set())
    machine.on_key_up(VK_TAB)
    clock[0] = 1400  # 超出窗口
    assert machine.on_key_down(VK_TAB, set()) == PASS_THROUGH
    assert rec.activated == 0


def test_combo_requires_modifiers() -> None:
    rec = Recorder()
    clock = [1000]
    machine = rec.build(
        HotKeyConfig(mode=MODE_COMBO, key="space", modifiers=["ctrl", "alt"]), clock
    )

    # 单独按空格不应触发
    assert machine.on_key_down(VK_SPACE, set()) == PASS_THROUGH
    assert rec.activated == 0

    # 只按了一个修饰键也不触发
    assert machine.on_key_down(VK_SPACE, {VK_CONTROL}) == PASS_THROUGH
    assert rec.activated == 0

    assert machine.on_key_down(VK_SPACE, {VK_CONTROL, VK_ALT}) == SWALLOW
    assert rec.activated == 1

    # 松开主键即执行
    assert machine.on_key_up(VK_SPACE) == SWALLOW
    assert rec.released == 1


def test_combo_release_on_modifier_up() -> None:
    rec = Recorder()
    clock = [1000]
    machine = rec.build(HotKeyConfig(mode=MODE_COMBO, key="space", modifiers=["alt"]), clock)
    machine.on_key_down(VK_SPACE, {VK_ALT})
    assert rec.activated == 1
    # 先松开 Alt 也算完成
    assert machine.on_key_up(VK_ALT) == SWALLOW
    assert rec.released == 1


def test_reset_clears_state() -> None:
    rec = Recorder()
    clock = [1000]
    machine = rec.build(HotKeyConfig(mode=MODE_HOLD, key="tab", hold_ms=200), clock)
    machine.on_key_down(VK_TAB, set())
    machine.reset()
    assert machine.state == "idle"
    assert machine.on_key_up(VK_TAB) == PASS_THROUGH
    assert rec.reemitted == []


@pytest.mark.parametrize(
    "mode,key,mods",
    [
        (MODE_HOLD, "tab", []),
        (MODE_DOUBLE_TAP, "tab", []),
        (MODE_COMBO, "space", ["win", "shift"]),
    ],
)
def test_modes_never_activate_on_unrelated_key(mode: str, key: str, mods: list[str]) -> None:
    rec = Recorder()
    machine = rec.build(HotKeyConfig(mode=mode, key=key, modifiers=mods), [0])
    assert machine.on_key_down(0x41, set()) == PASS_THROUGH  # A
    assert rec.activated == 0
