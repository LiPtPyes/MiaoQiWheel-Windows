"""pytest 全局配置：让 Qt 相关测试在无显示环境下也能跑（offscreen）。

必须在导入 PySide6 之前设置，所以放在 conftest（pytest 最先加载的文件）。
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    """整个测试会话共用一个 QApplication。"""
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    from mqwheel.views import theme

    theme.apply(app)
    return app
