"""版本资源测试：锁住「打包产物与安装包都带完整版本信息」这个约定。

背景：``installer\\MiaoQiWheel.iss`` 的 ``[Setup]`` 段曾漏掉全部 ``VersionInfo*``
指令，编译出来的安装包在右键属性里「文件版本 / 版权 / 原始文件名」三项全是空白；
主程序的 ``LegalCopyright`` 则被填成了一句来源说明，真正的版权声明反而没地方放。

这类缺失不影响任何功能、也不会让别的测试变红 —— 只能靠断言字段内容来防住。
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]

# tools/ 不在 pytest 的 pythonpath 里（那里只有 src），按路径加载即可 ——
# 不必为了让一个测试能 import 就往 sys.path 里塞目录。
_SPEC = importlib.util.spec_from_file_location("_tool_version_info", ROOT / "tools" / "version_info.py")
assert _SPEC is not None and _SPEC.loader is not None
version_info: ModuleType = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(version_info)

ISS_PATH = ROOT / "installer" / "MiaoQiWheel.iss"

# 主程序 exe 版本资源里必须非空的字段。少一个，右键属性页就空一格。
REQUIRED_FIELDS = (
    "CompanyName",
    "FileDescription",
    "FileVersion",
    "InternalName",
    "LegalCopyright",
    "OriginalFilename",
    "ProductName",
    "ProductVersion",
)

# 安装包的版本资源全靠 .iss 声明；漏一条就是属性页里空一项。
REQUIRED_ISS_DIRECTIVES = (
    "VersionInfoVersion",
    "VersionInfoCompany",
    "VersionInfoDescription",
    "VersionInfoCopyright",
    "VersionInfoProductName",
    "VersionInfoProductVersion",
    "VersionInfoOriginalFileName",
)


@pytest.fixture(scope="module")
def string_fields() -> dict[str, str]:
    """把主程序版本资源里的字符串表摊平成 ``{字段名: 值}``。

    ``build_version_info()`` 需要 PyInstaller；它属于「打包（可选）」依赖，
    没装时跳过依赖本 fixture 的用例，而不是让整个测试文件失败。
    """
    pytest.importorskip("PyInstaller")
    info = version_info.build_version_info()
    # 层级固定为 VSVersionInfo -> StringFileInfo -> StringTable -> StringStruct
    table = info.kids[0].kids[0]
    return {item.name: item.val for item in table.kids}


def _iss_text() -> str:
    return ISS_PATH.read_text(encoding="utf-8")


# region 版本号来源
def test_read_version_matches_package_version() -> None:
    """版本号只有一个真源：``src/mqwheel/__init__.py`` 的 ``__version__``。"""
    from mqwheel import __version__

    parts = [int(part) for part in __version__.split(".")]
    expected = (parts + [0, 0, 0, 0])[:4]
    assert list(version_info.read_version()) == expected


def test_version_text_is_three_segments() -> None:
    assert version_info.version_text() == ".".join(
        str(part) for part in version_info.read_version()[:3]
    )


def test_version_quad_is_four_numeric_segments() -> None:
    """安装程序的 ``VersionInfoVersion`` 只认四段数字，三段会被拒绝或留空。"""
    segments = version_info.version_quad().split(".")
    assert len(segments) == 4
    assert all(segment.isdigit() for segment in segments)


# region 主程序版本资源
def test_version_resource_has_no_empty_field(string_fields: dict[str, str]) -> None:
    for name in REQUIRED_FIELDS:
        assert name in string_fields, f"主程序版本资源缺少字段 {name}"
        assert string_fields[name].strip(), f"主程序版本资源字段 {name} 为空"


def test_legal_copyright_is_a_notice_not_a_description(string_fields: dict[str, str]) -> None:
    """``LegalCopyright`` 要放版权声明。

    它原来写的是 "Port of MiaoQiWheel (macOS) to Windows" —— 属性页「版权」栏
    显示一句来源说明，而真正的版权声明反而没地方放。描述性文字应放 ``Comments``。
    """
    assert string_fields["LegalCopyright"].startswith("Copyright")


# region 安装包脚本
def test_iss_declares_every_version_info_directive() -> None:
    """安装包属性页里的那几栏，全靠 .iss 里的这些指令。"""
    text = _iss_text()
    for directive in REQUIRED_ISS_DIRECTIVES:
        # 前缀换行，避免匹配到注释里的同名文字
        assert f"\n{directive}=" in text, f"MiaoQiWheel.iss 缺少 {directive}"


def test_iss_does_not_hardcode_a_version() -> None:
    """版本号只应来自 ``/D`` 传参，.iss 里不该出现写死的数字。

    写死的兜底会和 ``__version__`` 漂移，编出一个版本号对不上的安装包 ——
    那比编译直接失败更难发现。所以脚本改成缺参数就 ``#error``。
    """
    text = _iss_text()
    assert '#define AppVersion "' not in text
    assert '#define VersionInfoVer "' not in text


def test_iss_requires_version_arguments() -> None:
    """缺版本号参数时必须编译期报错，而不是静默用某个默认值。"""
    text = _iss_text()
    assert "#ifndef AppVersion" in text
    assert "#error" in text


def test_copyright_matches_between_installer_and_app(string_fields: dict[str, str]) -> None:
    """同一个产品，安装包与主程序的版权文案必须一致。"""
    match = re.search(r'#define AppCopyright "([^"]+)"', _iss_text())
    assert match, "MiaoQiWheel.iss 未定义 AppCopyright"
    assert match.group(1) == string_fields["LegalCopyright"]
