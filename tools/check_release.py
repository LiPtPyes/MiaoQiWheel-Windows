"""发版前自检：版本号、官网配置、下载文件是否自洽。

改版本号时最容易漏的地方一次全查一遍。**最要紧的是第 3 项** ——
`site.config.js` 的 url 指向一个已经不存在的文件时，页面看起来完全正常
（按钮在、文字在），点下去却拿到 Cloudflare Pages 的回落页。
线上 sha256 校验发现不了这种问题：文件确实一致，只是内容错了。

用法：
    .venv\\Scripts\\python.exe tools\\check_release.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEBSITE = ROOT / "website"


def read_version() -> str:
    text = (ROOT / "src" / "mqwheel" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not match:
        raise SystemExit("找不到 __version__")
    return match.group(1)


def main() -> int:
    version = read_version()
    print(f"版本真源 src/mqwheel/__init__.py : {version}")
    print()

    checks: list[tuple[str, bool, str]] = []

    # ── 1. site.config.js 的 version / releaseDate ────────────────────
    config = (WEBSITE / "site.config.js").read_text(encoding="utf-8")
    cfg_version = re.search(r'version:\s*"([^"]+)"', config)
    cfg_date = re.search(r'releaseDate:\s*"([^"]+)"', config)
    checks.append(
        (
            "site.config.js 的 version",
            bool(cfg_version) and cfg_version.group(1) == version,
            cfg_version.group(1) if cfg_version else "（没读到）",
        )
    )
    checks.append(
        (
            "site.config.js 的 releaseDate 格式",
            bool(cfg_date) and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", cfg_date.group(1))),
            cfg_date.group(1) if cfg_date else "（没读到）",
        )
    )

    # ── 2. 两个下载 url 的文件名带上了新版本号 ────────────────────────
    urls = re.findall(r'url:\s*"([^"]+)"', config)
    checks.append(("下载 url 数量", len(urls) == 2, f"{len(urls)} 个"))

    for url in urls:
        name = Path(url).name
        checks.append((f"url 带新版本号  {name}", version in name, name))

    # ── 3. ★ url 指向的文件真的存在（最容易被忽略的一条） ──────────────
    for url in urls:
        target = WEBSITE / url
        size = f"{target.stat().st_size:,} 字节" if target.is_file() else "文件不存在！"
        checks.append((f"url 指向的文件存在  {Path(url).name}", target.is_file(), size))

    # ── 4. downloads/ 里不该留着旧版本 ────────────────────────────────
    downloads = WEBSITE / "downloads"
    if downloads.is_dir():
        stale = [
            p.name
            for p in sorted(downloads.iterdir())
            if p.is_file() and version not in p.name
        ]
        checks.append(
            ("downloads/ 无旧版本残留", not stale, ", ".join(stale) if stale else "干净")
        )

    # ── 5. index.html 的两处静态兜底 ──────────────────────────────────
    html = (WEBSITE / "index.html").read_text(encoding="utf-8")
    badge = re.search(r'id="verBadge"[^>]*>v?([\d.]+)<', html)
    foot = re.search(r'id="verFoot"[^>]*>([\d.]+)<', html)
    checks.append(
        (
            "index.html 的 verBadge",
            bool(badge) and badge.group(1) == version,
            badge.group(1) if badge else "（没读到）",
        )
    )
    checks.append(
        (
            "index.html 的 verFoot",
            bool(foot) and foot.group(1) == version,
            foot.group(1) if foot else "（没读到）",
        )
    )

    # ── 6. js/main.js 的兜底 ──────────────────────────────────────────
    main_js = (WEBSITE / "js" / "main.js").read_text(encoding="utf-8")
    fallback = re.search(r'CFG\.version\s*\|\|\s*"([\d.]+)"', main_js)
    checks.append(
        (
            "js/main.js 的 CFG.version 兜底",
            bool(fallback) and fallback.group(1) == version,
            fallback.group(1) if fallback else "（没读到）",
        )
    )

    # ── 输出 ──────────────────────────────────────────────────────────
    failed = 0
    for name, ok, detail in checks:
        print(f"  [{'通过' if ok else '失败'}] {name:38} — {detail}")
        failed += 0 if ok else 1

    print()
    if failed:
        print(f"CHECK-RELEASE-FAIL（{failed} 项失败）")
        print("\n提示：url 指向的文件不存在时，页面看起来正常、点下去是回落页，")
        print("      线上 sha256 校验查不出来 —— 必须在部署前拦住。")
        return 1
    print("CHECK-RELEASE-PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
