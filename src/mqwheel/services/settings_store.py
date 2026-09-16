"""设置持久化：单个 JSON 文件，写在 %APPDATA% 下，失败时回退到用户目录。

只依赖标准库，便于在无 Qt 环境下单测。
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from mqwheel.app_identity import config_dir
from mqwheel.models.settings import WheelSettings

FILE_NAME = "settings.json"


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else config_dir() / FILE_NAME

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> WheelSettings:
        if not self.path.exists():
            settings = WheelSettings()
            self.save(settings)
            return settings
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return WheelSettings.from_dict(raw)
        except (OSError, json.JSONDecodeError):
            pass
        return WheelSettings()

    def save(self, settings: WheelSettings) -> bool:
        """原子写入：先写临时文件再替换，避免中途崩溃损坏配置。"""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(settings.to_dict(), ensure_ascii=False, indent=2)
            tmp_fd, tmp_name = tempfile.mkstemp(
                dir=str(self.path.parent), prefix=".settings-", suffix=".tmp"
            )
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as handle:
                    handle.write(payload)
                os.replace(tmp_name, self.path)
            finally:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
            return True
        except OSError:
            return False
