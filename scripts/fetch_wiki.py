"""
Wiki 页面批量获取（兜底方案）

直接调用 MediaWiki API，不依赖 MCP 工具。
当 mc-wiki-fetch-mcp 和 Minecraft-Wiki-MCP 都不可用时使用。

用法：
    python scripts/fetch_wiki.py "Redstone Comparator" "Piston" "Observer"

输出：
    .cache/wiki/<页面名>.md   （每页一个 Markdown 文件）
    stdout: JSON 摘要         （Agent 解析用）
"""

import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API_URL = "https://zh.minecraft.wiki/api.php"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / ".cache" / "wiki"
TIMEOUT = 15
BATCH_SIZE = 10  # MediaWiki API 建议 titles 参数不超过 50


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

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "MinecraftRedstoneTranslator/0.1 (github.com/cly)"
        },
    )

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
            "url": f"https://zh.minecraft.wiki/w/{urllib.parse.quote(title.replace(' ', '_'))}",
        }
    return result, redirect_map


def save_page(title: str, extract: str, url: str) -> Path:
    """按统一模板保存清洗后的页面为 Markdown。

    规范见 docs/WIKI_CACHE_FORMAT.md：
    - 文件名 = 解析后的规范标题（中文）
    - 写入 front matter（title / url / fetched / via / fidelity）
    - fidelity 固定为 plain（explaintext 会剥离表格，属已知行为）
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = title.replace("/", "_").replace("\\", "_").replace(" ", "_")
    filepath = CACHE_DIR / f"{safe_name}.md"
    fetched = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    filepath.write_text(
        (
            f"---\n"
            f"title: {title}\n"
            f"url: {url}\n"
            f"fetched: {fetched}\n"
            f"via: fetch_wiki\n"
            f"fidelity: plain\n"
            f"---\n\n"
            f"# {title}\n\n"
            f"> 来源：[Minecraft Wiki]({url})\n\n"
            f"{extract}\n"
        ),
        encoding="utf-8",
    )
    return filepath


def main():
    if len(sys.argv) < 2:
        print("Usage: python fetch_wiki.py <page> [page ...]", file=sys.stderr)
        sys.exit(1)

    titles = sys.argv[1:]
    summary: dict = {"fetched": [], "missed": [], "errors": []}

    for i in range(0, len(titles), BATCH_SIZE):
        batch = titles[i : i + BATCH_SIZE]
        try:
            result, redirect_map = fetch_pages(batch)
            for title, info in result.items():
                path = save_page(title, info["extract"], info["url"])
                summary["fetched"].append(
                    {"title": title, "file": str(path.relative_to(PROJECT_ROOT))}
                )
            if redirect_map:
                summary.setdefault("redirects", {}).update(redirect_map)
        except Exception as e:
            summary["errors"].append({"batch": batch, "error": str(e)})

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


if __name__ == "__main__":
    main()
