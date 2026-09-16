"""应用标识与路径常量。"""

from pathlib import Path

APP_NAME = "妙启轮盘"
ORG_NAME = "MiaoQiWheel"
APP_ID = "MiaoQiWheel"  # 单实例互斥量 / 注册表键名使用 ASCII
SINGLE_INSTANCE_MUTEX = f"Local\\{APP_ID}.SingleInstance.v1"

PACKAGE_DIR = Path(__file__).resolve().parent
RESOURCES_DIR = PACKAGE_DIR / "resources"

APP_ICON_PATH = RESOURCES_DIR / "app.ico"
TRAY_ICON_PATH = RESOURCES_DIR / "tray.png"
