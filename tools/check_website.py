"""官网自洽性检查：所有「引用了某个东西」的地方，目标是否真的存在。

和 tools/check_release.py 是同一类思路 —— 这类错误不会报错、页面看着正常，
只是某个图标不显示、某张图 404、某个按钮点了没反应。

已踩过的坑（记忆里那条「图标是白名单」）：`<i class="fa-solid fa-xxx">` 如果
在 style.css 里没有对应的 `.fa-xxx::before`，**不是显示成方块，而是整个图标消失**，
只剩一个空占位框 —— 光看截图很难注意到。

用法：
    .venv\\Scripts\\python.exe tools\\check_website.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "website"

INDEX = SITE / "index.html"
CSS = SITE / "css" / "style.css"
MAIN_JS = SITE / "js" / "main.js"

# 站外 / 协议链接不算本地资源
EXTERNAL = ("http://", "https://", "//", "mailto:", "tel:", "#", "data:", "javascript:")


def is_local(ref: str) -> bool:
    ref = ref.strip()
    return bool(ref) and not ref.startswith(EXTERNAL)


def check_icons() -> tuple[list[str], str]:
    html = INDEX.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    used = set(re.findall(r"fa-solid fa-([a-z0-9-]+)", html))
    defined = set(re.findall(r"\.fa-([a-z0-9-]+)::before", css))
    missing = sorted(used - defined)
    detail = f"HTML 用到 {len(used)} 个，CSS 定义 {len(defined)} 个，缺失 {len(missing)} 个"
    return missing, detail


def check_html_assets() -> tuple[list[str], str]:
    html = INDEX.read_text(encoding="utf-8")
    refs = re.findall(r'(?:src|href)="([^"]+)"', html)
    missing = []
    checked = 0
    for ref in refs:
        if not is_local(ref) or ref.startswith("#"):
            continue
        # 去掉 query / hash
        clean = ref.split("?")[0].split("#")[0]
        if not clean:
            continue
        checked += 1
        if not (SITE / clean).exists():
            missing.append(clean)
    return missing, f"检查了 {checked} 个本地引用"


def check_css_urls() -> tuple[list[str], str]:
    css = CSS.read_text(encoding="utf-8")
    # 先剥掉 data URI：它内部可能嵌着 url(...)（内联 SVG 里 filter='url(%23n)'
    # 指向同一文档的 <filter id='n'>），那些不是文件引用，会误报。
    css = re.sub(r'url\(["\']?data:[^)]*\)', "", css)
    refs = re.findall(r"url\(['\"]?([^'\")]+)['\"]?\)", css)
    missing = []
    checked = 0
    for ref in refs:
        ref = ref.strip()
        # #foo 与 %23foo 都是同一文档内的片段引用
        if ref.startswith("#") or ref.lower().startswith("%23"):
            continue
        if not is_local(ref):
            continue
        clean = ref.split("?")[0].split("#")[0]
        if not clean:
            continue
        checked += 1
        # CSS 里的相对路径是相对 css/ 目录的
        if not (CSS.parent / clean).resolve().exists() and not (SITE / clean).exists():
            missing.append(clean)
    return missing, f"检查了 {checked} 个 url()"


def check_js_dom_ids() -> tuple[list[str], str]:
    """JS 里 getElementById 的 id，是否真在 HTML 里（漏了就是「点了没反应」）。"""
    js = MAIN_JS.read_text(encoding="utf-8")
    html = INDEX.read_text(encoding="utf-8")
    wanted = set(re.findall(r'getElementById\(\s*"([^"]+)"', js))
    wanted |= set(re.findall(r'getElementById\(\s*\'([^\']+)\'', js))
    # 页面里动态创建的 id 会误报，这里只提示不判失败
    absent = sorted(i for i in wanted if f'id="{i}"' not in html)
    return absent, f"JS 引用了 {len(wanted)} 个 id"


def main() -> int:
    results = [
        ("图标白名单", check_icons()),
        ("index.html 的本地资源", check_html_assets()),
        ("style.css 的 url()", check_css_urls()),
        ("JS 引用的 DOM id", check_js_dom_ids()),
    ]

    failed = 0
    for name, (missing, detail) in results:
        ok = not missing
        # DOM id 那项有动态生成的，缺了只提示
        hard = name != "JS 引用的 DOM id"
        if not ok and hard:
            failed += 1
        flag = "通过" if ok else ("提示" if not hard else "失败")
        print(f"  [{flag}] {name:26} — {detail}")
        if missing:
            print(f"           {missing}")

    print()
    if failed:
        print(f"CHECK-WEBSITE-FAIL（{failed} 项失败）")
        print("\n提示：图标缺码位时不是显示方块，而是整个图标消失，只剩空占位框。")
        return 1
    print("CHECK-WEBSITE-PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
