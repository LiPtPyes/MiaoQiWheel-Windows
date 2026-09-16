# -*- mode: python ; coding: utf-8 -*-
"""妙启轮盘 PyInstaller 打包配置（onedir 便携版）。

用法：
    .venv\\Scripts\\pyinstaller.exe MiaoQiWheel.spec --noconfirm --distpath dist

产物：dist\\MiaoQiWheel\\MiaoQiWheel.exe（整个目录可拷贝到任意位置，绿色免安装）
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH)
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT / "tools"))

import version_info  # noqa: E402

VERSION_INFO = version_info.build_version_info()  # 版本号取自 mqwheel.__version__

# region 资源与隐式导入
datas = [
    (str(SRC / "mqwheel" / "resources" / "app.ico"), "mqwheel/resources"),
    (str(SRC / "mqwheel" / "resources" / "tray.png"), "mqwheel/resources"),
]
# qtawesome 没有官方钩子：必须带上 fonts/*.ttf，否则所有图标退化成占位圆环
datas += collect_data_files("qtawesome")

hiddenimports = collect_submodules("mqwheel")
hiddenimports += [
    "comtypes.client",  # pycaw 延迟导入，静态分析扫不到
    "pycaw.pycaw",
    "pycaw.constants",
    "pycaw.utils",
    "qtawesome",  # 首次绘制图标时才导入
]
# endregion

# region 裁剪：只为体积，不影响功能
excludes = [
    # 标准库与开发工具
    "tkinter",
    "unittest",
    "doctest",
    "pydoc",
    "pdb",
    "lib2to3",
    "distutils",
    "setuptools",
    "pip",
    "pytest",
    "_pytest",
    "PIL",  # 仅 tools/make_icon.py 用到
    "IPython",
    # pywin32 全家（运行期只用 winreg + ctypes）
    "win32com",
    "pythoncom",
    "pywintypes",
    # PySide6 未使用模块（Essentials 已不含 WebEngine/Quick/Multimedia）
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtQuickControls2",
    "PySide6.QtQuick3D",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
    "PySide6.QtWebChannel",
    "PySide6.Qt3DCore",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtPositioning",
    "PySide6.QtSerialPort",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtTextToSpeech",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtStateMachine",
    "PySide6.QtSpatialAudio",
    "PySide6.QtUiTools",
    "PySide6.QtShaderTools",
    "PySide6.QtNetworkAuth",
    "PySide6.QtDBus",
]
# endregion

a = Analysis(  # noqa: F821
    [str(SRC / "mqwheel" / "main.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# region 瘦身：剔除确认用不到的 Qt 组件
# 纯 Widgets 应用：不需要软件 OpenGL（19.7MB 的大头）、SVG 图标引擎与无关插件。
DROP_FILES = {
    "opengl32sw.dll",
    "qt6opengl.dll",
    "qt6openglwidgets.dll",
    "qt6svg.dll",
    # 图像格式：程序只加载 ico / png，其余解码器一律剔除
    "qicns.dll",
    "qtiff.dll",
    "qtga.dll",
    "qsvg.dll",
    "qwbmp.dll",
    "qwebp.dll",
}
DROP_DIRS = (
    "plugins/generic/",
    "plugins/iconengines/",
    # Qt 自带 96 个 .qm 界面翻译（6.5 MB）。程序从未安装 QTranslator，
    # 这些文件一个都不会被加载 —— 删掉纯赚体积，行为零变化。
    "pyside6/translations/",
)

# ⚠ 不要裁 qtawesome 的字体。
#
# 看着很划算（11 套没用的图标字体约 5 MB），实际不可行：qtawesome 的
# `_instance()` 会执行 `IconicFont(*_BUNDLED_FONTS)`，**一次性加载全部 12 套字体**，
# 并且逐个做 MD5 校验。少任何一个 .ttf 都会在第一次画图标时抛
# `FileNotFoundError`，表现是所有图标一起消失 —— 不是"少了某个图标"。
# 想让 qtawesome 只加载 fa6s 得去改它的私有 `_BUNDLED_FONTS`，太脆，不值这 1.5 MB。


def _norm(dest_name: str) -> str:
    """统一成小写、正斜杠的路径。

    PyInstaller 的 TOC 里 dest 用的是**反斜杠且不带前导斜杠**
    （实测形如 `qtawesome\\fonts\\codicon-0.0.36.ttf`），直接拿原串匹配会全部落空。
    """
    return dest_name.replace("\\", "/").lower()


def _keep(dest_name: str) -> bool:
    path = _norm(dest_name)
    if any(marker in path for marker in DROP_DIRS):
        return False
    return path.rsplit("/", 1)[-1] not in DROP_FILES


a.binaries = [entry for entry in a.binaries if _keep(entry[0])]  # noqa: F821
a.datas = [entry for entry in a.datas if _keep(entry[0])]  # noqa: F821
# endregion

pyz = PYZ(a.pure, a.zipped_data, cipher=None)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MiaoQiWheel",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # 不用 UPX：省不了多少体积，反而容易被杀软误报
    console=False,  # 无控制台窗口
    disable_windowed_traceback=False,  # 崩溃写 crash.log（main.py 内的钩子负责）
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(SRC / "mqwheel" / "resources" / "app.ico"),
    version=VERSION_INFO,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MiaoQiWheel",
)
