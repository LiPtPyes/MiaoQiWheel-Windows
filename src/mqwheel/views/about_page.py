"""关于页：版本、开源致谢与配置路径。"""

from __future__ import annotations

import os
import subprocess

from PySide6 import QtCore, QtWidgets

from mqwheel import __version__ as VERSION
from mqwheel.app_identity import APP_NAME, ORG_NAME, config_dir
from mqwheel.views.common import PageWidget, SectionCard, hint_label

CREDITS: tuple[tuple[str, str], ...] = (
    ("灵感来源", "macOS 版 MiaoQiWheel（妙启轮盘）"),
    ("界面框架", "Qt for Python（PySide6），LGPL v3"),
    ("图标", "FontAwesome 6（qtawesome），CC BY 4.0"),
    ("音量控制", "pycaw（MIT）"),
)


def config_dir_str() -> str:
    """「关于」页要显示/打开的配置目录。走 app_identity.config_dir() 这个唯一真源，
    保证显示的路径和实际写入的路径永远一致。"""
    return str(config_dir())


class AboutPage(PageWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.set_header("关于", "")
        self._add_title()
        self._add_credits()
        self._add_paths()
        self.finish()

    def _add_title(self) -> None:
        card = SectionCard("版本", self)
        name = QtWidgets.QLabel(APP_NAME)
        name.setStyleSheet("font-size: 16px; font-weight: 600;")
        card.add_full(name)
        card.add_full(hint_label(f"Windows 版 {VERSION}　·　{ORG_NAME}"))
        card.add_full(
            hint_label("该版本为早期版本，可能与部分以管理员权限运行的程序存在热键冲突，"
                       "遇到问题欢迎反馈。")
        )
        self.add_card(card)

    def _add_credits(self) -> None:
        card = SectionCard("致谢与许可", self)
        for title, detail in CREDITS:
            row = QtWidgets.QWidget()
            layout = QtWidgets.QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            label = QtWidgets.QLabel(title)
            label.setMinimumWidth(90)
            value = QtWidgets.QLabel(detail)
            value.setStyleSheet("color: #9AA3B0;")
            value.setWordWrap(True)
            layout.addWidget(label, 0)
            layout.addWidget(value, 1)
            card.add_full(row)
        self.add_card(card)

    def _add_paths(self) -> None:
        card = SectionCard("数据位置", self)
        path = config_dir_str()
        line = QtWidgets.QLineEdit(path)
        line.setReadOnly(True)
        card.add_row("配置目录", line)

        buttons = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(buttons)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        open_button = QtWidgets.QPushButton("打开配置目录")
        open_button.clicked.connect(self._open_config_dir)
        layout.addWidget(open_button)
        layout.addStretch(1)
        card.add_full(buttons)
        self.add_card(card)

    @staticmethod
    def _open_config_dir() -> None:
        path = config_dir_str()
        try:
            os.makedirs(path, exist_ok=True)
            os.startfile(path)  # noqa: S606 - 仅打开资源管理器
        except OSError:
            subprocess.Popen(["explorer.exe", path])


__all__ = ["AboutPage"]
