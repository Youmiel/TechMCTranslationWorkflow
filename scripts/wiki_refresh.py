"""按 lossless 源刷新 .cache/wiki/ 缓存（wiki-tools 降级链第 1 优先级）。

数据源 = `mc-wiki-fetch-mcp` 所代理的 API（wikitext 无损），但**不经 MCP 工具本身**
调用——避免大量 wikitext 涌入 Agent 上下文（22 页 ≈ 400KB）。

用法：
    python .cache/tmp/wiki_refresh_lossless.py --dry-run          # 只探测规范标题与体积
    python .cache/tmp/wiki_refresh_lossless.py                    # 实际抓取并落盘
    python .cache/tmp/wiki_refresh_lossless.py --only 活塞 潜影贝 # 只刷指定页

纪律：请求间隔 >= 2s；429/403 指数退避（2s → 4s → 8s，最多 3 次）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIKI_DIR = ROOT / ".cache" / "wiki"
API_BASE = "https://mcwiki.rice-awa.top"
TIMEOUT = 90
MIN_INTERVAL = 2.0


def read_title(path: Path) -> str:
    head = path.read_text(encoding="utf-8")[:400]
    m = re.search(r"^title:\s*(.+)$", head, re.M)
    return m.group(1).strip() if m else path.stem


def fetch_page(page: str) -> dict:
    """抓取单页 wikitext。返回 API 的 data.page 字典。"""
    url = (
        f"{API_BASE}/api/page/{urllib.parse.quote(page, safe='')}?"
        + urllib.parse.urlencode({"format": "wikitext", "useCache": "false"})
    )
    req = urllib.request.Request(
        url, headers={"User-Agent": "MinecraftRedstoneTranslator/0.1"}
    )
    delay = 2
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if not data.get("success"):
                raise RuntimeError(f"API 返回失败: {data.get('error')}")
            return data["data"]["page"]
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 403) and attempt < 2:
                time.sleep(delay)
                delay *= 2
                continue
            raise
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < 2:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise RuntimeError(f"抓取失败: {last_err}")


def render(page: dict) -> str:
    """按 docs/WIKI_CACHE_FORMAT.md 模板渲染（lossless）。"""
    title = page["pageName"]
    url = page["url"]
    content = page["content"]["wikitext"]
    fetched = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        f"---\n"
        f"title: {title}\n"
        f"url: {url}\n"
        f"fetched: {fetched}\n"
        f"via: mc-wiki-fetch-mcp\n"
        f"fidelity: lossless\n"
        f"---\n\n"
        f"# {title}\n\n"
        f"> 来源：[Minecraft Wiki]({url})\n\n"
        f"{content}\n"
    )


def safe_name(title: str) -> str:
    """Windows 文件名安全化（与 docs/WIKI_CACHE_FORMAT.md「命名规则」一致）：
    `Tutorial:` 前缀（Windows 禁冒号）转 `（教程）` 后缀，其余非法字符转下划线。
    """
    if title.startswith("Tutorial:"):
        title = f"{title[len('Tutorial:'):]}（教程）"
    return title.replace("/", "_").replace("\\", "_").replace(" ", "_")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只探测，不写盘")
    ap.add_argument("--only", nargs="*", default=None, help="只刷指定页面（文件名或标题）")
    args = ap.parse_args()

    files = sorted(WIKI_DIR.glob("*.md"))
    if args.only:
        wanted = set(args.only)
        files = [f for f in files if f.stem in wanted or read_title(f) in wanted]
        missing = wanted - {f.stem for f in files} - {read_title(f) for f in files}
        if missing:
            print(f"[warn] 未匹配到: {', '.join(sorted(missing))}", file=sys.stderr)

    if not files:
        print("没有需要刷新的页面。")
        return 0

    print(f"待刷新 {len(files)} 页（dry_run={args.dry_run}）\n")
    stats: list[tuple[str, str, int, str]] = []
    renamed: list[tuple[str, str]] = []
    errors: list[tuple[str, str]] = []
    last_call = 0.0

    for path in files:
        title = read_title(path)
        gap = MIN_INTERVAL - (time.monotonic() - last_call)
        if gap > 0:
            time.sleep(gap)
        last_call = time.monotonic()
        try:
            page = fetch_page(title)
        except Exception as e:  # noqa: BLE001
            errors.append((title, str(e)))
            print(f"  [FAIL] {title}: {e}")
            continue

        canonical = page["pageName"]
        size = len(page["content"]["wikitext"])
        stats.append((title, canonical, size, page["url"]))
        flag = ""
        if safe_name(canonical) != path.stem:
            renamed.append((path.stem, safe_name(canonical)))
            flag = "  <- 规范名不同"
        print(f"  [ok] {title} -> {canonical} ({size:,} 字符){flag}")

        if not args.dry_run:
            target = WIKI_DIR / f"{safe_name(canonical)}.md"
            target.write_text(render(page), encoding="utf-8")

    total = sum(s[2] for s in stats)
    print(f"\n完成：{len(stats)} 成功 / {len(errors)} 失败，共 {total:,} 字符")
    if renamed:
        print("\n规范名与缓存文件名不一致（需人工确认改名）：")
        for old, new in renamed:
            print(f"  {old}.md -> {new}.md")
    if errors:
        print("\n失败清单：")
        for title, err in errors:
            print(f"  {title}: {err}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
