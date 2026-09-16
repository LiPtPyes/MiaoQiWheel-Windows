"""开机自启：注册表 Run 键读写（测试结束会还原原始状态）。"""

from __future__ import annotations

import sys

import pytest

from mqwheel.services import autostart


@pytest.mark.skipif(sys.platform != "win32", reason="仅 Windows 有注册表 Run 键")
def test_command_line_mentions_current_interpreter() -> None:
    line = autostart.command_line()
    assert line
    assert line.startswith('"'), "路径必须加引号，否则含空格时无法启动"
    assert ".py" in line or ".exe" in line


@pytest.mark.skipif(sys.platform != "win32", reason="仅 Windows 有注册表 Run 键")
def test_enable_disable_roundtrip() -> None:
    original = autostart.is_enabled()
    try:
        assert autostart.set_enabled(True)
        assert autostart.is_enabled()

        assert autostart.set_enabled(False)
        assert not autostart.is_enabled()
    finally:
        autostart.set_enabled(original)
