"""帮助页：使用说明与常见问题。"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from mqwheel.app_identity import APP_NAME
from mqwheel.views.common import PageWidget, SectionCard, hint_label

STEPS: tuple[tuple[str, str], ...] = (
    ("1", "按住设定的快捷键（默认长按 Tab 约 0.2 秒），轮盘会在光标处出现。"),
    ("2", "保持按住，把鼠标移向想要的选项，中心区会显示当前选中的名称。"),
    ("3", "松开快捷键即可执行。指针停在轮盘正中、或按 Esc，则取消执行。"),
)

TIPS: tuple[str, ...] = (
    "按住模式下短按（未到阈值）会补发一次原按键，Tab 仍然是原来的跳格键。",
    "Alt+Tab、Ctrl+Tab 等系统组合键始终放行，不会被轮盘吞掉。",
    "轮盘最多 12 个选项，最少 2 个；拖入 exe 或快捷方式即可快速添加应用。",
    "命令行里带空格的路径或文本请交给预设参数填写，程序会按规则自动加引号。",
)

FAQ: tuple[tuple[str, str], ...] = (
    (
        "按了快捷键没反应？",
        "确认设置里的触发方式与主键；若使用组合键，检查是否与其他软件冲突。"
        "部分以管理员权限运行的窗口会拦截普通权限程序的键盘钩子，"
        "此时把本程序也以管理员身份启动即可。",
    ),
    (
        "轮盘出现了但点不动？",
        "轮盘是穿透窗口，靠移动指针选择，不需要点击；松开快捷键才执行。",
    ),
    (
        "某个动作没执行成功？",
        "脚本类动作可先在「运行」对话框里试同样的命令；"
        "应用类动作检查路径是否仍然存在。",
    ),
    (
        "配置保存在哪里？",
        "保存在 %APPDATA%\\MiaoQiWheel\\settings.json，删除它即可恢复默认设置。",
    ),
)


class HelpPage(PageWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.set_header("使用说明", f"{APP_NAME} 是一个全局呼出的圆形快捷菜单。")
        self._add_steps()
        self._add_tips()
        self._add_faq()
        self.finish()

    def _add_steps(self) -> None:
        card = SectionCard("怎么用", self)
        for index, text in STEPS:
            row = QtWidgets.QWidget()
            layout = QtWidgets.QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(10)
            badge = QtWidgets.QLabel(index)
            badge.setFixedSize(22, 22)
            badge.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                "background: #3FA9FF; color: #0E1620; border-radius: 11px; font-weight: 600;"
            )
            layout.addWidget(badge, 0)
            label = QtWidgets.QLabel(text)
            label.setWordWrap(True)
            layout.addWidget(label, 1)
            card.add_full(row)
        self.add_card(card)

    def _add_tips(self) -> None:
        card = SectionCard("小提示", self)
        for text in TIPS:
            label = hint_label("· " + text)
            card.add_full(label)
        self.add_card(card)

    def _add_faq(self) -> None:
        card = SectionCard("常见问题", self)
        for question, answer in FAQ:
            title = QtWidgets.QLabel(question)
            title.setStyleSheet("font-weight: 600;")
            title.setWordWrap(True)
            card.add_full(title)
            body = hint_label(answer)
            card.add_full(body)
        self.add_card(card)


__all__ = ["HelpPage"]
