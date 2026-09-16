"""生成 exe 的 Windows 版本资源（供打包 spec 调用）。

注意：PyInstaller 从文件加载版本信息时是对整个文件内容 `eval()`，
所以不能提供「可执行的 Python 模块」；这里改为导出构造函数，由 spec 传对象。

版本号从 `mqwheel.__version__` 解析，保证与「关于」页显示的一致。

PyInstaller 在顶层**不做**导入：`read_version()` 只依赖标准库，因此
make_zip.py / make_installer.py 这类只需要版本号的工具无需安装 PyInstaller 也能调用。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # 仅用于类型标注，运行期不导入
    from PyInstaller.utils.win32.versioninfo import VSVersionInfo

SRC_INIT = Path(__file__).resolve().parents[1] / "src" / "mqwheel" / "__init__.py"


def read_version() -> tuple[int, int, int, int]:
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', SRC_INIT.read_text(encoding="utf-8"))
    raw = match.group(1) if match else "0.0.0"
    parts = (raw.split(".") + ["0", "0", "0", "0"])[:4]
    numbers: list[int] = []
    for part in parts:
        numbers.append(int(part) if part.isdigit() else 0)
    return tuple(numbers)  # type: ignore[return-value]


def version_text() -> str:
    """人类可读的版本号（major.minor.patch），不需要 PyInstaller。"""
    return ".".join(str(part) for part in read_version()[:3])


def version_quad() -> str:
    """四段形式（``1.1.0.0``）。

    安装程序的 ``VersionInfoVersion`` 只接受这种格式：给它三段的 ``1.1.0``
    会被拒绝或留空，结果就是 exe 属性里「文件版本」一片空白。
    单独拎出来是为了让 ``installer\\MiaoQiWheel.iss`` 不必另写一份版本号。
    """
    return ".".join(str(part) for part in read_version())


def build_version_info() -> "VSVersionInfo":
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo,
        StringFileInfo,
        StringStruct,
        StringTable,
        VarFileInfo,
        VarStruct,
        VSVersionInfo,
    )

    version = read_version()
    text = ".".join(str(part) for part in version[:3])
    return VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=version,
            prodvers=version,
            mask=0x3F,
            flags=0x0,
            OS=0x40004,  # VOS_NT_WINDOWS32
            fileType=0x1,  # VFT_APP
            subtype=0x0,
            date=(0, 0),
        ),
        kids=[
            StringFileInfo(
                [
                    StringTable(
                        "080404b0",  # 简体中文 / Unicode
                        [
                            # Comments 是 Windows 属性页的「备注」，放项目来源这类
                            # 说明性文字；LegalCopyright 则留给真正的版权声明，
                            # 与 LICENSE（MIT）和 installer\MiaoQiWheel.iss 保持一致。
                            StringStruct("Comments", "Port of MiaoQiWheel (macOS) to Windows"),
                            StringStruct("CompanyName", "MiaoQiWheel"),
                            StringStruct("FileDescription", "妙启轮盘"),
                            StringStruct("FileVersion", text),
                            StringStruct("InternalName", "MiaoQiWheel"),
                            StringStruct("LegalCopyright", "Copyright (c) 2026 晚棠 (MIT License)"),
                            StringStruct("OriginalFilename", "MiaoQiWheel.exe"),
                            StringStruct("ProductName", "妙启轮盘"),
                            StringStruct("ProductVersion", text),
                        ],
                    )
                ]
            ),
            VarFileInfo([VarStruct("Translation", [2052, 1200])]),
        ],
    )


__all__ = ["build_version_info", "read_version", "version_quad", "version_text"]
