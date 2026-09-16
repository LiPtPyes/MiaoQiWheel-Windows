"""应用标识与路径常量。"""

import os
from pathlib import Path

APP_NAME = "妙启轮盘"
ORG_NAME = "MiaoQiWheel"
APP_ID = "MiaoQiWheel"  # 单实例互斥量 / 注册表键名使用 ASCII
SINGLE_INSTANCE_MUTEX = f"Local\\{APP_ID}.SingleInstance.v1"

PACKAGE_DIR = Path(__file__).resolve().parent
RESOURCES_DIR = PACKAGE_DIR / "resources"

APP_ICON_PATH = RESOURCES_DIR / "app.ico"
TRAY_ICON_PATH = RESOURCES_DIR / "tray.png"


def config_dir() -> Path:
    """配置目录：``%APPDATA%\\MiaoQiWheel``，取不到 APPDATA 时回退到 ``~\\.miaoqiwheel``。

    这是**唯一真源** —— 设置存储、崩溃日志、「关于」页显示的路径都必须走它，
    否则会出现「关于」页显示的目录和实际写入的目录不是同一个。

    两个反例（都踩过）：

    - ``os.environ["APPDATA"]``：本机实测这个变量在部分环境里会**整批缺失**
      （和 ``%ProgramFiles%`` 一样），直接取会 KeyError。
    - ``os.environ.get("APPDATA", 默认值)``：变量**存在但为空串**时 ``get`` 返回的是
      空串而不是默认值，``os.path.join("", APP_ID)`` 会得到一个**相对路径** ——
      配置会落到当前工作目录下，且随启动目录漂移。
    """
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / APP_ID
    return Path.home() / f".{APP_ID.lower()}"

