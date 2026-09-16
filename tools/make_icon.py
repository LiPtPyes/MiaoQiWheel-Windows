"""从 macOS 版 AppIcon 生成 Windows 图标（app.ico / tray.png）。

用法：
    .venv\\Scripts\\python.exe tools\\make_icon.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_ICON = (
    PROJECT_ROOT.parent
    / "MiaoQiWheel-main"
    / "Sources"
    / "MiaoQiWheel"
    / "Resources"
    / "Assets.xcassets"
    / "AppIcon.appiconset"
    / "icon_512x512.png"
)
OUTPUT_DIR = PROJECT_ROOT / "src" / "mqwheel" / "resources"

ICO_SIZES = [(16, 16), (20, 20), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> int:
    if not SOURCE_ICON.exists():
        print(f"找不到源图标: {SOURCE_ICON}")
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source = Image.open(SOURCE_ICON).convert("RGBA")

    ico_path = OUTPUT_DIR / "app.ico"
    source.save(ico_path, format="ICO", sizes=ICO_SIZES)
    print(f"已生成 {ico_path}")

    tray = source.resize((64, 64), Image.LANCZOS)
    tray_path = OUTPUT_DIR / "tray.png"
    tray.save(tray_path, format="PNG")
    print(f"已生成 {tray_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
