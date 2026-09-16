@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0.."

echo ==== 妙启轮盘 环境准备 ====
echo.

if exist ".venv\Scripts\python.exe" (
    echo [1/4] 虚拟环境已存在，跳过创建。
    goto :deps
)

echo [1/4] 查找可用的 Python 解释器...
:: 本项目依赖 PySide6-Essentials 6.9.3，要求 Python >= 3.13。
:: 候选顺序：py 启动器 3.13 -> 托管 3.13 -> PATH 中且版本达标的 python。
:: 不用裸 python：若解析到 3.11，pip 会因找不到匹配的 wheel 而失败，报错还很难懂。
set "PY="
py -3.13 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    set "PY=py -3.13"
    echo     找到 Python 3.13（py 启动器）
)

if not defined PY (
    if exist "%USERPROFILE%\.workbuddy-ai\binaries\python\versions\3.13.12\python.exe" (
        set "PY=%USERPROFILE%\.workbuddy-ai\binaries\python\versions\3.13.12\python.exe"
        echo     找到托管 Python 3.13
    )
)

if not defined PY (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "PY=python"
        echo     使用 PATH 中的 Python
    )
)

if not defined PY (
    echo.
    echo [错误] 未找到 Python 3.13 或更高版本。
    echo        本项目依赖 PySide6-Essentials 6.9.3，需要 Python 3.13。
    echo        请从 https://www.python.org/downloads/ 安装后重试。
    exit /b 1
)

echo.
echo [2/4] 创建虚拟环境...
%PY% -m venv .venv
if errorlevel 1 (
    echo [错误] 创建虚拟环境失败。
    exit /b 1
)

:deps
echo [3/4] 升级 pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip -q -i https://mirrors.tencent.com/pypi/simple/ --trusted-host mirrors.tencent.com

echo [4/4] 安装依赖（约 3~5 分钟）...
".venv\Scripts\python.exe" -m pip install -r requirements.txt -i https://mirrors.tencent.com/pypi/simple/ --trusted-host mirrors.tencent.com
if errorlevel 1 (
    echo.
    echo [错误] 依赖安装失败。若为网络问题，可改用官方源重试：
    echo        .venv\Scripts\python.exe -m pip install -r requirements.txt
    exit /b 1
)

echo.
echo ==== 完成 ====
".venv\Scripts\python.exe" -c "import sys; print('Python', '.'.join(map(str, sys.version_info[:3])))"
echo 运行：scripts\run.bat
echo 打包：scripts\build.bat
echo 安装包：scripts\build_installer.bat
endlocal
