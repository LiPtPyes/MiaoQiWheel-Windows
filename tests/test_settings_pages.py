"""设置窗口各页面的行为测试（offscreen 渲染，不需要真实窗口）。"""

from __future__ import annotations

from PySide6 import QtWidgets

from mqwheel.models.action import WheelAction, WheelActionKind
from mqwheel.models.presets import by_id
from mqwheel.models.settings import WheelSettings
from mqwheel.views.action_editor import ActionEditor
from mqwheel.views.actions_page import ActionsPage
from mqwheel.views.settings_window import SettingsWindow


def _combo(parent: QtWidgets.QWidget, index: int) -> QtWidgets.QComboBox:
    boxes = parent.findChildren(QtWidgets.QComboBox)
    assert len(boxes) > index
    return boxes[index]


def test_settings_window_has_four_pages(qapp) -> None:
    window = SettingsWindow(WheelSettings())
    assert window._stack.count() == 4, "四个页面：通用、轮盘选项、帮助、关于"
    sidebar = window._sidebar
    assert sidebar.count() == 4
    assert [sidebar.item(i).text() for i in range(4)] == ["通用", "轮盘选项", "帮助", "关于"]


def test_settings_window_emits_changed(qapp) -> None:
    window = SettingsWindow(WheelSettings())
    received: list[WheelSettings] = []
    window.settings_changed.connect(received.append)
    pages = window.findChildren(ActionsPage)
    assert pages
    # 页面内部触发一次改动（切换轮盘显示名称）
    pages[0]._add()
    assert received, "添加选项后应向上抛出 settings_changed"


def test_actions_page_add_and_remove(qapp) -> None:
    settings = WheelSettings()
    start = len(settings.actions)
    page = ActionsPage(settings)

    page._add()
    assert len(settings.actions) == start + 1

    page._remove()
    assert len(settings.actions) == start


def test_actions_page_respects_minimum(qapp) -> None:
    settings = WheelSettings()
    settings.actions = settings.actions[:2]
    page = ActionsPage(settings)
    page._list.setCurrentRow(0)
    page._remove()
    assert len(settings.actions) == 2, "少于最小数量时不应继续删除"


def test_general_change_refreshes_actions_page(qapp) -> None:
    """「恢复默认设置」会整体替换选项列表，轮盘选项页必须跟着刷新。"""
    window = SettingsWindow(WheelSettings())
    window._actions._add()
    assert window._actions._list.count() == 7

    fresh = WheelSettings()  # 默认 6 项
    window._settings.actions = fresh.actions
    window._general.settings_changed.emit()  # sender 为通用页

    assert window._actions._list.count() == 6, "通用页改动后轮盘选项页应重新加载"


def test_actions_page_reorder(qapp) -> None:
    settings = WheelSettings()
    page = ActionsPage(settings)
    first_id = settings.actions[0].id
    page._list.setCurrentRow(0)
    page._move(1)
    assert settings.actions[1].id == first_id


def test_editor_preset_builds_payload(qapp) -> None:
    editor = ActionEditor()
    action = WheelAction(title="", kind=WheelActionKind.SHELL_COMMAND, payload="")
    editor.set_action(action)

    preset_box = _combo(editor, 1)
    index = preset_box.findData("shutdown")
    assert index >= 0, "预设下拉里应能找到 shutdown"
    preset_box.setCurrentIndex(index)

    result = editor.collect()
    assert result.kind == WheelActionKind.SHELL_COMMAND
    assert result.payload == by_id("shutdown").command()
    assert result.title == "关机", "原名称为空时应套用预设标题"


def test_editor_param_change_updates_payload(qapp) -> None:
    editor = ActionEditor()
    editor.set_action(WheelAction(title="", kind=WheelActionKind.SHELL_COMMAND, payload=""))

    preset_box = _combo(editor, 1)
    preset_box.setCurrentIndex(preset_box.findData("shutdown"))

    spin = editor.findChild(QtWidgets.QSpinBox)
    assert spin is not None, "shutdown 预设应生成一个整数参数控件"
    spin.setValue(30)

    assert editor.collect().payload == "shutdown.exe /s /t 30"


def test_editor_builtin_preset_keeps_params(qapp) -> None:
    editor = ActionEditor()
    editor.set_action(WheelAction(title="", kind=WheelActionKind.BUILTIN, payload=""))

    preset_box = _combo(editor, 1)
    index = preset_box.findData("set-volume")
    assert index >= 0
    preset_box.setCurrentIndex(index)

    result = editor.collect()
    assert result.payload == "builtin:set-volume"
    assert result.preset_params == {"volume": "50"}


def test_editor_hides_preset_for_application(qapp) -> None:
    editor = ActionEditor()
    editor.set_action(WheelAction(title="记事本", kind=WheelActionKind.APPLICATION, payload="notepad.exe"))

    preset_box = _combo(editor, 1)
    assert not preset_box.isVisible(), "应用类型不需要预设下拉"


# region 窗口切换类型


def test_editor_window_toggle_round_trips_path(qapp) -> None:
    editor = ActionEditor()
    editor.set_action(
        WheelAction(title="浏览器", kind=WheelActionKind.WINDOW_TOGGLE, payload=r"C:\Edge\msedge.exe")
    )

    result = editor.collect()
    assert result.kind == WheelActionKind.WINDOW_TOGGLE
    assert result.payload == r"C:\Edge\msedge.exe"


def test_editor_window_toggle_hides_preset(qapp) -> None:
    editor = ActionEditor()
    editor.set_action(WheelAction(title="浏览器", kind=WheelActionKind.WINDOW_TOGGLE, payload="msedge.exe"))
    assert not _combo(editor, 1).isVisible(), "窗口切换类型不需要预设下拉"


def test_editor_switching_path_kinds_keeps_the_path(qapp) -> None:
    """「应用」↔「窗口切换」填的是同一个路径，来回切不该让用户重新浏览。"""
    editor = ActionEditor()
    editor.set_action(WheelAction(title="浏览器", kind=WheelActionKind.APPLICATION, payload=r"C:\Edge\msedge.exe"))

    kind_box = _combo(editor, 0)
    kind_box.setCurrentIndex(kind_box.findData(WheelActionKind.WINDOW_TOGGLE.value))
    assert editor.collect().payload == r"C:\Edge\msedge.exe"

    kind_box.setCurrentIndex(kind_box.findData(WheelActionKind.APPLICATION.value))
    assert editor.collect().payload == r"C:\Edge\msedge.exe"


def test_editor_switching_to_url_does_not_leak_path(qapp) -> None:
    editor = ActionEditor()
    editor.set_action(WheelAction(title="x", kind=WheelActionKind.APPLICATION, payload=r"C:\Edge\msedge.exe"))

    kind_box = _combo(editor, 0)
    kind_box.setCurrentIndex(kind_box.findData(WheelActionKind.URL.value))
    assert editor.collect().payload == "", "换到链接类型时不该把路径塞进去"


# endregion
