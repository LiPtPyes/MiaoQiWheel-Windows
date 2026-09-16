@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."

echo ==== 妙启轮盘 安装包制作 ====
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到虚拟环境，请先运行 scripts\setup.bat 创建。
    exit /b 1
)

:: 与 build.bat 一致：拦截版本不符的 venv，避免产物运行时与预期不一致。
".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [错误] 当前 .venv 的 Python 版本低于 3.13，本项目需要 3.13。
    echo        请删除 .venv 目录后重新运行 scripts\setup.bat。
    exit /b 1
)

if not exist "dist\MiaoQiWheel\MiaoQiWheel.exe" (
    echo [错误] 未找到 dist\MiaoQiWheel\MiaoQiWheel.exe。
    echo        请先运行 scripts\build.bat 完成打包。
    exit /b 1
)

echo [1/2] 检查 Inno Setup 编译器...
".venv\Scripts\python.exe" -c "import sys; sys.path.insert(0,'tools'); import make_installer as m; sys.exit(0 if m.find_iscc() else 1)"
if errorlevel 1 (
    echo.
    echo [错误] 未检测到 Inno Setup 6（ISCC.exe）。
    echo        请从 https://jrsoftware.org/isdl.php 下载安装后重试。
    echo        安装时保持默认路径即可，本脚本会自动查找。
    exit /b 1
)

echo [2/2] 编译安装包（约 1~2 分钟）...
".venv\Scripts\python.exe" tools\make_installer.py %*
if errorlevel 1 (
    echo [错误] 安装包编译失败，请查看上方输出。
    exit /b 1
)

echo.
echo ==== 完成 ====
endlocal
