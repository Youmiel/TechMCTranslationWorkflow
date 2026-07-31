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
from pathlib import Path

API_URL = "https://zh.minecraft.wiki/api.php"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / ".cache" / "wiki"
TIMEOUT = 15
BATCH_SIZE = 10  # MediaWiki API 建议 titles 参数不超过 50


def fetch_pages(titles: list[str]) -> dict[str, dict[str, str]]:
    """批量获取 Wiki 页面。返回 {title: {extract, url}}。"""
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

    # 处理重定向：记录 from → to 映射
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
        # 也以原始请求名建立索引
        for from_title, to_title in redirect_map.items():
            if to_title == title and from_title not in result:
                result[from_title] = result[title]
    return result


def save_page(title: str, extract: str, url: str) -> Path:
    """保存清洗后的页面为 Markdown。"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = title.replace("/", "_").replace("\\", "_").replace(" ", "_")
    filepath = CACHE_DIR / f"{safe_name}.md"
    filepath.write_text(
        f"# {title}\n\n> 来源：[Minecraft Wiki]({url})\n\n{extract}\n",
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
            for title, info in fetch_pages(batch).items():
                path = save_page(title, info["extract"], info["url"])
                summary["fetched"].append(
                    {"title": title, "file": str(path.relative_to(PROJECT_ROOT))}
                )
        except Exception as e:
            summary["errors"].append({"batch": batch, "error": str(e)})

    fetched_titles = {item["title"] for item in summary["fetched"]}
    for t in titles:
        if t not in fetched_titles:
            summary["missed"].append(t)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
