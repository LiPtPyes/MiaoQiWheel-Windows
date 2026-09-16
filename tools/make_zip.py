"""把 dist\\MiaoQiWheel 打成便携版 zip，并附一份使用说明。

用法：python tools/make_zip.py
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from version_info import version_text  # noqa: E402


def usage_text() -> str:
    version = version_text()
    return f"""妙启轮盘 Windows 版 v{version}（便携版）
========================================

【运行】
  解压整个文件夹后，双击 MiaoQiWheel\\MiaoQiWheel.exe 即可。
  无需安装、不写注册表（只有开启「开机自启」时会写一个 Run 值）。
  程序会在系统托盘显示图标，右键可打开设置或退出。

【默认操作】
  长按 Tab 键约 0.2 秒呼出轮盘 -> 移动鼠标选择 -> 松开 Tab 执行。
  短按 Tab 仍是正常跳格；停在盘面正中或按 Esc 取消。

【设置】
  托盘右键 ->「打开设置…」
  - 通用：触发方式（长按/双击/组合键）、阈值、是否显示名称、轮盘大小、
          毛玻璃背景、动画、开机自启、恢复默认
  - 轮盘选项：增删改、拖拽排序、把 exe/快捷方式拖进列表即可加项、
          预设下拉（锁屏/关机/音量/深色模式等 23 个）
  - 帮助 / 关于：使用说明、版本与配置路径

【数据与卸载】
  配置与日志：%APPDATA%\\MiaoQiWheel\\settings.json
  卸载：先在设置里关掉开机自启，退出程序后删掉本文件夹即可。

【出问题怎么办】
  1. 热键无反应：确认没有以管理员权限运行的程序抢占；
     或在设置里换一个触发键（如 CapsLock、反引号）。
  2. 图标显示为空心圆：字体未加载，重新完整解压即可（不要只拷 exe）。
  3. 崩溃：把 %APPDATA%\\MiaoQiWheel\\crash.log 一并发给开发者。
  4. 环境变量 MQWHEEL_DISABLE_BACKDROP=1 可强制关闭毛玻璃抓屏。
"""


def main() -> int:
    src_dir = ROOT / "dist" / "MiaoQiWheel"
    if not src_dir.is_dir():
        print(f"[错误] 未找到 {src_dir}，请先打包。")
        return 1

    version = version_text()
    zip_path = ROOT / "dist" / f"MiaoQiWheel-v{version}-portable.zip"
    if zip_path.exists():
        zip_path.unlink()

    files = sorted(p for p in src_dir.rglob("*") if p.is_file())
    total = sum(p.stat().st_size for p in files)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, f"MiaoQiWheel/{path.relative_to(src_dir).as_posix()}")
        archive.writestr("使用说明.txt", usage_text())

    size_mb = zip_path.stat().st_size / 1024 / 1024
    raw_mb = total / 1024 / 1024
    print(f"已生成：{zip_path}")
    print(f"文件数 {len(files)}，原始 {raw_mb:.1f} MB -> 压缩后 {size_mb:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
