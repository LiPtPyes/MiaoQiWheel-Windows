"""用 Inno Setup 把 dist\\MiaoQiWheel 编译成单文件安装程序。

用法：
    .venv\\Scripts\\python.exe tools\\make_installer.py
    .venv\\Scripts\\python.exe tools\\make_installer.py --iscc "D:\\Inno Setup 6\\ISCC.exe"

前置条件：
    1. 已运行 scripts\\build.bat 生成 dist\\MiaoQiWheel\\；
    2. 已安装 Inno Setup 6（https://jrsoftware.org/isdl.php），本脚本会自行搜索 ISCC.exe。

版本号取自 tools/version_info.read_version()，与打包脚本、关于页保持同一来源。
本脚本本身不依赖 PyInstaller。
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from version_info import version_quad, version_text  # noqa: E402

ISS_PATH = ROOT / "installer" / "MiaoQiWheel.iss"
SOURCE_DIR = ROOT / "dist" / "MiaoQiWheel"
OUTPUT_DIR = ROOT / "dist"
ICON_PATH = ROOT / "src" / "mqwheel" / "resources" / "app.ico"

# 脚本使用 ArchitecturesAllowed=x64compatible，该值自 Inno Setup 6.3 起提供。
# 仅用于出错时给出建议文案，**不做编译前拦截**：编译器的真实版本在编译开始前
# 拿不到（见 parse_engine_version 的说明），强行拦截只会误伤。
MIN_COMPILER = (6, 3, 0)

# ISCC.exe 的常见安装位置。
# winget / 用户级安装会落在 %LOCALAPPDATA%\Programs，需在运行时动态拼出；
# 下面这些是全局与自定义盘的固定路径。
_ISCC_CANDIDATES = (
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
    r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
    r"D:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"D:\Program Files\Inno Setup 6\ISCC.exe",
    r"E:\Program Files (x86)\Inno Setup 6\ISCC.exe",
)


def find_iscc(explicit: str | None = None) -> Path | None:
    """按显式路径 → 环境变量 → PATH → 常见安装位置 的顺序查找 ISCC.exe。

    显式路径既可以是 ISCC.exe 本身，也可以是它的安装目录 —— 用户很自然地
    会把「Inno Setup 的地址」理解成目录并原样粘进来，此时自动补上文件名。
    路径确实无效时返回 None（由调用方给出提示），不做静默回退，避免用户
    以为自己指定的编译器被用上了、实际却用了另一个。
    """
    if explicit:
        candidate = Path(explicit)
        if candidate.is_dir():
            candidate = candidate / "ISCC.exe"
        return candidate if candidate.is_file() else None

    # 允许用户在环境变量里直接指定，便于装在非标准位置
    from_env = os.environ.get("ISCC_PATH")
    if from_env and Path(from_env).is_file():
        return Path(from_env)

    from shutil import which

    for name in ("ISCC", "iscc", "ISCC.exe"):
        found = which(name)
        if found:
            return Path(found)

    candidates = list(_ISCC_CANDIDATES)
    # 用户级安装（winget --scope user / 安装时选「仅为我安装」）
    for env_key in ("LOCALAPPDATA", "ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env_key)
        if not base:
            continue
        candidates.insert(
            0, str(Path(base) / "Programs" / "Inno Setup 6" / "ISCC.exe")
            if env_key == "LOCALAPPDATA"
            else str(Path(base) / "Inno Setup 6" / "ISCC.exe"),
        )
    for item in candidates:
        if Path(item).is_file():
            return Path(item)
    return None


def parse_engine_version(text: str) -> tuple[int, int, int] | None:
    """从 ISCC 的编译输出里解析真实版本号，返回 (major, minor, patch)。

    **不要试图从 ISCC.exe 的文件属性里读版本** —— Inno Setup 有意把版本信息
    抹掉了，两条路都是死的（实测 6.7.3）：
      - `VS_FIXEDFILEINFO.dwFileVersionMS` 恒为 0x00010000，读出来是 (1, 0)；
      - `StringFileInfo\\...\\FileVersion` 恒为字符串 "0.0.0.0"。
    只有真正开始编译时，它才会在输出里打印一行
        Compiler engine version: Inno Setup 6.7.3
    这是唯一可靠的来源，所以版本判断只能在编译之后做。

    `ISCC /?` 的横幅只有主版本号（"Inno Setup 6"），不足以判断 6.2 与 6.7，
    因此这里不采用它。
    """
    match = re.search(
        r"Compiler\s+engine\s+version:\s*Inno\s+Setup\s+(\d+)\.(\d+)(?:\.(\d+))?",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3) or 0))


def main(argv: list[str]) -> int:
    explicit = None
    if "--iscc" in argv:
        index = argv.index("--iscc")
        if index + 1 < len(argv):
            explicit = argv[index + 1]

    if not ISS_PATH.is_file():
        print(f"[错误] 未找到脚本 {ISS_PATH}")
        return 1

    if not SOURCE_DIR.is_dir():
        print(f"[错误] 未找到 {SOURCE_DIR}，请先运行 scripts\\build.bat。")
        return 1

    iscc = find_iscc(explicit)
    if iscc is None:
        print("[错误] 未找到 ISCC.exe，请先安装 Inno Setup 6：")
        print("       https://jrsoftware.org/isdl.php")
        if explicit:
            print(f"       你指定的路径无效：{explicit}")
        print('       或用 --iscc 显式指定，填 ISCC.exe 或它的安装目录都行，例如：')
        print('         --iscc "D:\\Program Files (x86)\\Inno Setup 6"')
        return 1

    version = version_text()
    # 安装程序的 VersionInfoVersion 必须是四段数字（1.1.0.0），三段会被
    # Inno 拒绝或留空；这里从同一真源补齐，避免在 .iss 里另写一份。
    version_4 = version_quad()
    print(f"使用编译器：{iscc}")
    print(f"版本号：{version}")
    print(f"源目录：{SOURCE_DIR}")
    print()
    print("开始编译（约 1~2 分钟）...")

    # 显式传入绝对路径，消除 ISCC 相对路径解析基准的歧义：
    # 不同版本/调用方式下，它在「脚本目录」与「当前工作目录」之间有过差异。
    command = [
        str(iscc),
        f"/DAppVersion={version}",
        f"/DVersionInfoVer={version_4}",
        f"/DSourceDir={SOURCE_DIR}",
        f"/DOutputDir={ROOT / 'dist'}",
        f"/DIconFile={ROOT / 'src' / 'mqwheel' / 'resources' / 'app.ico'}",
        str(ISS_PATH),
    ]
    # 不合并 stderr：ISCC 把编译日志写到 stdout、错误写到 stderr，
    # 分开收集才能在出错时准确定位原因。
    result = subprocess.run(command, capture_output=True, text=True, cwd=str(ROOT))
    output = f"{result.stdout}\n{result.stderr}"

    if result.returncode != 0:
        print(output.rstrip())
        print()

        # 版本检查放在这里做，而不是编译前 —— 编译器只有真正开始编译时才会
        # 打印 "Compiler engine version"。同时 ISCC 对无效取值会给出退出码 2
        # 与明确报错，所以旧版本必然走不到这里以下的分支。
        engine = parse_engine_version(output)
        if engine:
            have = ".".join(str(p) for p in engine)
            print(f"[错误] 编译失败（Inno Setup {have}，退出码 {result.returncode}）。")

        # 把 "Invalid value" 那类难懂的报错翻译成可操作的建议。
        if "x64compatible" in output or "ArchitecturesAllowed" in output:
            need = ".".join(str(p) for p in MIN_COMPILER)
            print(f"       脚本使用 ArchitecturesAllowed=x64compatible，自 {need} 起才支持。")
            print("       请升级 Inno Setup：https://jrsoftware.org/isdl.php")
        else:
            print("       请查看上方 ISCC 输出定位问题。")
        return result.returncode

    engine = parse_engine_version(output)
    if engine:
        print(f"编译器版本：Inno Setup {'.'.join(str(p) for p in engine)}")

    output_path = ROOT / "dist" / f"MiaoQiWheel-Setup-{version}.exe"
    if output_path.is_file():
        size_mb = output_path.stat().st_size / 1024 / 1024
        print()
        print(f"已生成：{output_path}")
        print(f"大小：{size_mb:.1f} MB")
        print("这是可直接分发的单文件安装程序，用户双击即可安装。")
        return 0

    print(output.rstrip())
    print("[警告] 编译已结束，但未找到预期产物，请检查上方 ISCC 输出。")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
