@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0.."

echo ==== 妙启轮盘 打包 ====

if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到虚拟环境，请先运行 scripts\setup.bat 创建。
    exit /b 1
)

:: 拦截 Python 版本不符的旧 venv：产物会换掉运行时，且 PySide6 可能装错 ABI。
".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [错误] 当前 .venv 的 Python 版本低于 3.13，本项目需要 3.13。
    echo        请删除 .venv 目录后重新运行 scripts\setup.bat。
    exit /b 1
)

if not exist ".venv\Scripts\pyinstaller.exe" (
    echo [1/4] 安装 PyInstaller...
    ".venv\Scripts\python.exe" -m pip install -q pyinstaller -i https://mirrors.tencent.com/pypi/simple/ --trusted-host mirrors.tencent.com
    if errorlevel 1 (
        echo [错误] PyInstaller 安装失败（检查网络或改用其他 PyPI 镜像）。
        exit /b 1
    )
) else (
    echo [1/4] PyInstaller 已就绪，跳过安装。
)

echo [2/4] 清理上次产物...
if exist build rmdir /s /q build
if exist dist\MiaoQiWheel rmdir /s /q dist\MiaoQiWheel

echo [3/4] 打包中（约 1~3 分钟）...
".venv\Scripts\pyinstaller.exe" MiaoQiWheel.spec --noconfirm --distpath dist --workpath build
if errorlevel 1 (
    echo [错误] 打包失败，请查看上方输出。
    exit /b 1
)

echo [4/4] 压缩为便携版 zip...
".venv\Scripts\python.exe" tools\make_zip.py
if errorlevel 1 (
    echo [错误] 压缩失败。
    exit /b 1
)

echo.
echo ==== 完成 ====
echo 程序目录：dist\MiaoQiWheel\MiaoQiWheel.exe
echo 便携压缩包见上方输出路径。
echo.
echo 如需单文件安装程序，继续运行：scripts\build_installer.bat
endlocal
