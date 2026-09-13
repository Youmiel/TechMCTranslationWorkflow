"""
Wiki 页面获取与缓存刷新（MediaWiki API 直连，不经 MCP）

两种内容源：
  - 默认 explaintext → `fidelity: plain`（正文可读，表格被剥离）
  - `--wikitext` → `fidelity: lossless`（ID 表/色值/历史/隐藏注释全保留）

两种工作模式：
  - **抓取**（默认）：页面名 = 待抓页面
  - **刷新缓存**（`--refresh`）：待抓列表 = `.cache/wiki/` 现有缓存，页面名退化为筛选项
    （省略 = 全部）——用于缓存过期时的主动刷新与批量维护，刷新后 `fetched` 自动更新

用法：
    python scripts/fetch_wiki.py "红石比较器" "活塞"            # 抓取（plain）
    python scripts/fetch_wiki.py --wikitext "红石比较器"          # 抓取（lossless）
    python scripts/fetch_wiki.py --refresh "红石比较器"          # 刷新单页（lossless，按需）
    python scripts/fetch_wiki.py --refresh                    # 刷新全部现缓存（维护全量）
    python scripts/fetch_wiki.py --refresh --dry-run          # 只探测，不写盘

输出：
    .cache/wiki/<规范标题>.md   （每页一个 Markdown 文件，规范见 docs/WIKI_CACHE_FORMAT.md）
    stdout: JSON 摘要           （Agent 解析用）
"""

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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from request_identity import user_agent  # noqa: E402

API_URL = "https://zh.minecraft.wiki/api.php"
WIKI_BASE = "https://zh.minecraft.wiki"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / ".cache" / "wiki"
TIMEOUT = 30
BATCH_SIZE = 10  # MediaWiki API 建议 titles 参数不超过 50
DEFAULT_INTERVAL = 2.0  # 请求间隔（秒）——抓取纪律：429/403 指数退避 2s → 4s → 8s
TITLE_RE = re.compile(r"^title:\s*(.+?)\s*$", re.M)
# 请求身份（含联系方式）：见 scripts/request_identity.py——联系方式由使用者配置，
# 不内置作者信息（避免 clone/fork 后以原作者名义发请求）
UA = user_agent()


def fetch_pages(titles: list[str]) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    """批量获取 Wiki 页面。返回 (result, redirect_map)。

    result: {规范标题: {extract, url}} —— **仅包含解析后的规范标题**。
            重定向别名（如"粘液块"→"黏液块"）只记入 redirect_map，不落盘，
            避免同一页面产生多份缓存文件（见 docs/WIKI_CACHE_FORMAT.md）。
    redirect_map: {查询名: 规范标题}
    """
    params = {
        "action": "query",
        "format": "json",
        "titles": "|".join(titles),
        "prop": "extracts",
        "explaintext": 1,
        "redirects": 1,
        "exlimit": "max",
    }
    url = API_URL + "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url, headers={"User-Agent": UA})

    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    # 处理重定向：记录 from → to 映射（仅用于摘要，不用于落盘）
    redirect_map: dict[str, str] = {}
    for rd in data.get("query", {}).get("redirects", []):
        redirect_map[rd["from"]] = rd["to"]

    result: dict[str, dict[str, str]] = {}
    for page_info in data.get("query", {}).get("pages", {}).values():
        if "missing" in page_info:
            continue
        title = page_info["title"]
        result[title] = {
            "extract": page_info.get("extract", ""),
            "url": page_url(title),
        }
    return result, redirect_map


def page_url(title: str) -> str:
    """页面 URL（规范标题）。"""
    return f"{WIKI_BASE}/w/{urllib.parse.quote(title.replace(' ', '_'))}"


def safe_name(title: str) -> str:
    """Windows 文件名安全化（与 docs/WIKI_CACHE_FORMAT.md「命名规则」一致）：
    `Tutorial:` 前缀（Windows 禁冒号）转 `（教程）` 后缀，其余非法字符转下划线。
    """
    if title.startswith("Tutorial:"):
        title = f"{title[len('Tutorial:'):]}（教程）"
    return title.replace("/", "_").replace("\\", "_").replace(" ", "_")


def render_page(title: str, content: str, url: str, fidelity: str) -> str:
    """按 docs/WIKI_CACHE_FORMAT.md 模板渲染缓存文件。"""
    fetched = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        f"---\n"
        f"title: {title}\n"
        f"url: {url}\n"
        f"fetched: {fetched}\n"
        f"via: fetch_wiki\n"
        f"fidelity: {fidelity}\n"
        f"---\n\n"
        f"# {title}\n\n"
        f"> 来源：[Minecraft Wiki]({url})\n\n"
        f"{content}\n"
    )


def _api_get(params: dict) -> dict:
    """调用官方 MediaWiki API，429/403 指数退避重试（2s → 4s → 8s，最多 3 次）。"""
    url = API_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    delay = 2
    last: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 403) and attempt < 2:
                time.sleep(delay)
                delay *= 2
                continue
            raise
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < 2:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise RuntimeError(f"请求失败：{last}")


def fetch_wikitext(page: str) -> dict[str, str]:
    """抓取单页 wikitext（**lossless 源**）。返回 {title, wikitext, url}。"""
    data = _api_get(
        {
            "action": "query",
            "format": "json",
            "titles": page,
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "redirects": 1,
        }
    )
    for info in data.get("query", {}).get("pages", {}).values():
        if "missing" in info:
            raise LookupError(f"页面不存在：{page}")
        revisions = info.get("revisions") or []
        rev = revisions[0] if revisions else {}
        content = (rev.get("slots", {}).get("main", {}) or {}).get("*")
        if content is None:
            content = rev.get("*", "")
        return {
            "title": info["title"],
            "wikitext": content,
            "url": page_url(info["title"]),
        }
    raise LookupError(f"未返回页面：{page}")


def read_cached_pages() -> list[tuple[Path, str]]:
    """现有缓存页列表 [(路径, front matter title)]（title 缺失回退文件名 stem）。"""
    if not CACHE_DIR.exists():
        return []
    out: list[tuple[Path, str]] = []
    for path in sorted(CACHE_DIR.glob("*.md")):
        head = path.read_text(encoding="utf-8", errors="ignore")[:800]
        m = TITLE_RE.search(head)
        out.append((path, m.group(1).strip() if m else path.stem))
    return out


FIDELITY_RANK = {"lossless": 3, "refined": 2, "plain": 1, "degraded": 0}


def read_front_matter(path: Path) -> str:
    """现有缓存的 fidelity 值（无缓存 / 无该字段 → 空字符串）。"""
    try:
        head = path.read_text(encoding="utf-8", errors="ignore")[:800]
    except OSError:
        return ""
    m = re.search(r"^fidelity:\s*(\S+)", head, re.M)
    return m.group(1) if m else ""


def would_downgrade(title: str, new_fidelity: str) -> bool:
    """新内容保真度是否低于已有缓存（保真度只升不降，见 wiki-tools「缓存写入保真阶梯」）。"""
    path = CACHE_DIR / f"{safe_name(title)}.md"
    if not path.exists():
        return False
    old = read_front_matter(path)
    return FIDELITY_RANK.get(new_fidelity, -1) < FIDELITY_RANK.get(old, -1)


def save_page(title: str, content: str, url: str, fidelity: str, force: bool = False) -> Path:
    """按统一模板保存页面（脚本写盘，覆盖已有缓存）。

    **默认拒绝保真度降级**（`plain` 覆盖已有 `lossless` 会丢表格/色值/历史），
    需显式 `force=True`（CLI `--force`）才允许覆盖。
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    filepath = CACHE_DIR / f"{safe_name(title)}.md"
    if not force and would_downgrade(title, fidelity):
        old = read_front_matter(filepath)
        raise PermissionError(
            f"拒绝保真度降级：{filepath.name} 已有 {old}，本次为 {fidelity}"
            f"（保真度只升不降；确需覆盖加 --force，或改用 --wikitext/--refresh）"
        )
    filepath.write_text(render_page(title, content, url, fidelity), encoding="utf-8")
    return filepath


def cmd_fetch(titles: list[str], wikitext: bool, interval: float, force: bool) -> int:
    """抓取模式：批量获取指定页面并落盘。"""
    summary: dict = {"fetched": [], "missed": [], "errors": []}

    if wikitext:
        # lossless 源：revisions 不支持批量（wikitext 体量大），逐页抓取 + 请求间隔
        last_call = 0.0
        for title in titles:
            gap = interval - (time.monotonic() - last_call)
            if gap > 0:
                time.sleep(gap)
            last_call = time.monotonic()
            try:
                info = fetch_wikitext(title)
                path = save_page(
                    info["title"], info["wikitext"], info["url"], "lossless", force
                )
                summary["fetched"].append(
                    {"title": info["title"], "file": str(path.relative_to(PROJECT_ROOT))}
                )
            except Exception as e:  # noqa: BLE001
                summary["errors"].append({"page": title, "error": str(e)})
    else:
        for i in range(0, len(titles), BATCH_SIZE):
            batch = titles[i : i + BATCH_SIZE]
            try:
                result, redirect_map = fetch_pages(batch)
            except Exception as e:  # noqa: BLE001
                summary["errors"].append({"batch": batch, "error": str(e)})
                continue
            # 逐页保存：单页被降级保护拒绝不影响同批其他页
            for title, info in result.items():
                try:
                    path = save_page(title, info["extract"], info["url"], "plain", force)
                    summary["fetched"].append(
                        {"title": title, "file": str(path.relative_to(PROJECT_ROOT))}
                    )
                except Exception as e:  # noqa: BLE001
                    summary["errors"].append({"page": title, "error": str(e)})
            if redirect_map:
                summary.setdefault("redirects", {}).update(redirect_map)

    fetched_titles = {item["title"] for item in summary["fetched"]}
    # 重定向别名（from）也算已覆盖：它解析到的规范标题已落盘
    covered = set(fetched_titles)
    for from_title, to_title in summary.get("redirects", {}).items():
        if to_title in fetched_titles:
            covered.add(from_title)
    for t in titles:
        if t not in covered:
            summary["missed"].append(t)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary["errors"] else 0


def cmd_refresh(only: list[str] | None, dry_run: bool, interval: float, force: bool) -> int:
    """刷新模式：把现有 `.cache/wiki/` 缓存按 wikitext（lossless）重抓。

    - `only` 省略 = 全量现缓存（维护场景）
    - `only` 指定 = 只刷这些页面（按需刷新，页面名可用文件名或 front matter title）
    """
    cached = read_cached_pages()
    if only:
        wanted = set(only)
        cached = [p for p in cached if p[0].stem in wanted or p[1] in wanted]
        matched = {p[0].stem for p in cached} | {p[1] for p in cached}
        missing = wanted - matched
        if missing:
            print(f"[warn] 未匹配到: {', '.join(sorted(missing))}", file=sys.stderr)

    if not cached:
        print("没有需要刷新的页面。")
        return 0

    print(f"待刷新 {len(cached)} 页（wikitext/lossless, dry_run={dry_run}）\n")
    ok = 0
    renames: list[tuple[str, str]] = []
    errors: list[tuple[str, str]] = []
    last_call = 0.0

    for path, title in cached:
        gap = interval - (time.monotonic() - last_call)
        if gap > 0:
            time.sleep(gap)
        last_call = time.monotonic()
        try:
            info = fetch_wikitext(title)
        except Exception as e:  # noqa: BLE001
            errors.append((title, str(e)))
            print(f"  [FAIL] {title}: {e}")
            continue

        canonical = info["title"]
        size = len(info["wikitext"])
        ok += 1
        rename = safe_name(canonical) != path.stem
        if rename:
            renames.append((path.stem, safe_name(canonical)))
        flag = "  <- 规范名不同" if rename else ""
        print(f"  [ok] {title} -> {canonical} ({size:,} 字符){flag}")
        if not dry_run:
            save_page(canonical, info["wikitext"], info["url"], "lossless", force)

    print(f"\n完成：{ok} 成功 / {len(errors)} 失败")
    if renames:
        print("\n规范名与缓存文件名不一致（需人工确认改名）：")
        for old, new in renames:
            print(f"  {old}.md -> {new}.md")
    if errors:
        print("\n失败清单：")
        for title, err in errors:
            print(f"  {title}: {err}")
    return 1 if errors else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Wiki 页面获取与缓存刷新（MediaWiki API 直连）")
    ap.add_argument("pages", nargs="*", help="页面名（抓取模式）；刷新模式下作筛选（省略 = 全部现缓存）")
    ap.add_argument("--wikitext", action="store_true", help="抓取 wikitext（lossless）而非 explaintext（plain）")
    ap.add_argument("--refresh", action="store_true", help="刷新模式：重抓现有 .cache/wiki/ 缓存（lossless）")
    ap.add_argument("--dry-run", action="store_true", help="仅探测，不写盘（仅 --refresh）")
    ap.add_argument(
        "--force",
        action="store_true",
        help="允许用低保真内容覆盖已有缓存的更高保真内容（默认拒绝，防 plain 覆盖 lossless）",
    )
    ap.add_argument("--interval", type=float, default=DEFAULT_INTERVAL, help="请求间隔秒数（默认 2.0）")
    args = ap.parse_args()

    if args.refresh:
        return cmd_refresh(args.pages or None, args.dry_run, args.interval, args.force)

    if not args.pages:
        ap.print_usage(sys.stderr)
        print("错误：抓取模式需至少一个页面名（或用 --refresh 刷新现缓存）", file=sys.stderr)
        return 1
    return cmd_fetch(args.pages, args.wikitext, args.interval, args.force)


if __name__ == "__main__":
    sys.exit(main())
