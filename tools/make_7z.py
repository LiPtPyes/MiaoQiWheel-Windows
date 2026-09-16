"""把 dist\\MiaoQiWheel 打成便携版 .7z，并附一份使用说明。

用法：python tools/make_7z.py

为什么需要它（除了已有的 .zip）：
    Cloudflare Pages 对**单个文件**有 25 MiB 硬上限，超出直接拒收。
    同样的载荷用 zip(deflate) 是 33.2 MiB，用 LZMA 只有 23.1 MiB ——
    差别来自 PySide6 那堆 DLL/.pyd 的可压缩性，deflate 吃不下。
    所以要走 Cloudflare 分发时用这个 .7z，而不是 .zip。

结构刻意与 make_zip.py 保持一致：MiaoQiWheel/ 目录 + 使用说明.txt，
这样两个包解压出来的东西完全一样，用户换格式不会困惑。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from make_zip import usage_text  # noqa: E402
from version_info import version_text  # noqa: E402


def main() -> int:
    try:
        import py7zr
    except ImportError:
        print("[错误] 缺少 py7zr，请先安装：")
        print("       .venv\\Scripts\\python.exe -m pip install py7zr")
        return 1

    src_dir = ROOT / "dist" / "MiaoQiWheel"
    if not src_dir.is_dir():
        print(f"[错误] 未找到 {src_dir}，请先运行 scripts\\build.bat。")
        return 1

    version = version_text()
    out_path = ROOT / "dist" / f"MiaoQiWheel-v{version}-portable.7z"
    if out_path.exists():
        out_path.unlink()

    files = sorted(p for p in src_dir.rglob("*") if p.is_file())
    raw = sum(p.stat().st_size for p in files)

    # preset 6 已经能到 23 MiB，再往上加只多花时间、收益很小。
    filters = [{"id": py7zr.FILTER_LZMA2, "preset": 6}]
    with py7zr.SevenZipFile(out_path, "w", filters=filters) as archive:
        archive.writeall(src_dir, "MiaoQiWheel")
        archive.writestr(usage_text(), "使用说明.txt")

    size_mb = out_path.stat().st_size / 1024 / 1024
    raw_mb = raw / 1024 / 1024
    print(f"已生成：{out_path}")
    print(f"文件数 {len(files)}，原始 {raw_mb:.1f} MB -> 压缩后 {size_mb:.1f} MB")

    limit = 25 * 1024 * 1024
    if out_path.stat().st_size > limit:
        print(f"[警告] 超过 Cloudflare Pages 的 25 MiB 单文件上限，仍会被拒收。")
        return 1
    print("在 Cloudflare Pages 的 25 MiB 上限之内，可直接部署。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
