"""设置窗口通用控件：分组卡片、说明文字、页面容器。"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from mqwheel.views.theme import ACCENT


def page_heading(title: str, subtitle: str = "") -> QtWidgets.QWidget:
    """页面顶部的大标题 + 一行说明。"""
    box = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 8)
    layout.setSpacing(2)

    label = QtWidgets.QLabel(title)
    label.setStyleSheet("font-size: 18px; font-weight: 600;")
    layout.addWidget(label)

    if subtitle:
        hint = QtWidgets.QLabel(subtitle)
        hint.setStyleSheet("color: #9AA3B0;")
        hint.setWordWrap(True)
        layout.addWidget(hint)
    return box


def hint_label(text: str) -> QtWidgets.QLabel:
    label = QtWidgets.QLabel(text)
    label.setStyleSheet("color: #9AA3B0;")
    label.setWordWrap(True)
    return label


class SectionCard(QtWidgets.QGroupBox):
    """带标题的表单卡片。"""

    def __init__(self, title: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(title, parent)
        self._form = QtWidgets.QFormLayout(self)
        self._form.setContentsMargins(16, 22, 16, 14)
        self._form.setHorizontalSpacing(14)
        self._form.setVerticalSpacing(10)
        self._form.setLabelAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self._form.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

    @property
    def form(self) -> QtWidgets.QFormLayout:
        return self._form

    def add_row(self, label: str, widget: QtWidgets.QWidget) -> None:
        self._form.addRow(label, widget)

    def add_full(self, widget: QtWidgets.QWidget) -> None:
        self._form.addRow(widget)


class PageWidget(QtWidgets.QWidget):
    """所有设置页的基类：标题 + 卡片 + 底部撑开。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._root = QtWidgets.QVBoxLayout(self)
        self._root.setContentsMargins(24, 20, 24, 20)
        self._root.setSpacing(14)

    @property
    def root(self) -> QtWidgets.QVBoxLayout:
        return self._root

    def set_header(self, title: str, subtitle: str = "") -> None:
        self._root.addWidget(page_heading(title, subtitle))

    def add_card(self, card: QtWidgets.QWidget, stretch: int = 0) -> None:
        self._root.addWidget(card, stretch)

    def finish(self) -> None:
        self._root.addStretch(1)


def slider_row(
    minimum: int, maximum: int, value: int, suffix: str = "", single_step: int = 1
) -> tuple[QtWidgets.QWidget, QtWidgets.QSlider, QtWidgets.QLabel]:
    """带数值显示的横向滑块，返回 (容器, 滑块, 数值标签)。

    容器必须一并返回：只返回滑块的话，容器失去 Python 引用会被回收，
    连带把滑块一起删除。
    """
    container = QtWidgets.QWidget()
    layout = QtWidgets.QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)

    slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    slider.setRange(minimum, maximum)
    slider.setValue(value)
    slider.setSingleStep(single_step)
    slider.setPageStep(single_step * 5)
    slider.setMinimumWidth(180)

    label = QtWidgets.QLabel(f"{value}{suffix}")
    label.setMinimumWidth(52)
    label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)

    layout.addWidget(slider, 1)
    layout.addWidget(label, 0)
    return container, slider, label


def accented(text: str) -> str:
    return f'<span style="color: {ACCENT};">{text}</span>'


__all__ = ["PageWidget", "SectionCard", "accented", "hint_label", "page_heading", "slider_row"]
