"""缓存刷新脚本 —— 统一入口，检查并刷新本地缓存。

覆盖两类自动刷新：
  1. Mojang 官方词汇表（.cache/mojang/）
  2. TechMC 拆分术语表（.cache/glossary/）
Wiki 页面缓存（.cache/wiki/）只检查过期并告警，**不自动抓取**——
刷新由 Agent 在查找时按 wiki-tools 降级链按需做（MCP-2 lossless 优先），
避免脚本用 plain 覆盖已有高保真缓存（保真阶梯见 docs/WIKI_CACHE_FORMAT.md）。

用法:
    python scripts/refresh_cache.py
    python scripts/refresh_cache.py --force      # 强制检查全部（含 Wiki 全页）
    python scripts/refresh_cache.py --dry-run    # 仅检查，不实际刷新
    python scripts/refresh_cache.py --ttl 14     # 过期天数（默认7天）
    python scripts/refresh_cache.py --check-page "红石比较器" "活塞"   # 单页过期判定（读缓存前用）

单页判定（--check-page）是「按需刷新」的入口：查缓存前先判定该页是否过期，
过期即用 `fetch_wiki.py --refresh <页面>` 主动刷新后重读（见 wiki-tools Skill）。
过期判定 = front matter `fetched`（缺失回退文件 mtime）距今 > TTL。
"""

import argparse
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / ".cache"
WIKI_DIR = CACHE_DIR / "wiki"
MOJANG_DIR = CACHE_DIR / "mojang"
GLOSSARY_DIR = CACHE_DIR / "glossary"
FETCHED_RE = re.compile(r"^fetched:\s*(.+?)\s*$", re.M)
TITLE_RE = re.compile(r"^title:\s*(.+?)\s*$", re.M)


def read_rel_time(path: Path) -> datetime:
    """缓存页面的时间基准：front matter `fetched`（缺失/不可解析则回退文件 mtime）。

    规范见 docs/WIKI_CACHE_FORMAT.md——`fetched` 是声明的事实源，mtime 仅作兼容回退。
    """
    try:
        head = path.read_text(encoding="utf-8", errors="ignore")[:800]
    except OSError:
        head = ""
    m = FETCHED_RE.search(head)
    if m:
        raw = m.group(1).strip().strip('"').strip("'")
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(raw, fmt)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def read_title(path: Path) -> str:
    """front matter `title`（缺失则文件名 stem）。"""
    try:
        head = path.read_text(encoding="utf-8", errors="ignore")[:800]
    except OSError:
        return path.stem
    m = TITLE_RE.search(head)
    return m.group(1).strip() if m else path.stem


def resolve_page(name: str) -> Path | None:
    """按文件名 stem 或 front matter title 定位缓存页面。"""
    stem = name[:-3] if name.endswith(".md") else name
    direct = WIKI_DIR / f"{stem}.md"
    if direct.exists():
        return direct
    if not WIKI_DIR.exists():
        return None
    for f in WIKI_DIR.glob("*.md"):
        if read_title(f) == stem:
            return f
    return None


def age_desc(dt: datetime, now: datetime) -> str:
    days = (now - dt).total_seconds() / 86400
    return f"fetched={dt.strftime('%Y-%m-%dT%H:%M:%SZ')}（{days:.1f} 天前）"


def check_mojang() -> tuple[str, bool]:
    """检查 Mojang 词汇表是否需要更新。返回 (消息, 需要更新)。"""
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "glossary_fetch_mojang.py"), "--check"],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT)
    )
    needs_update = result.returncode == 1
    return result.stdout.strip(), needs_update


def check_glossary() -> tuple[str, bool]:
    """检查 TechMC 拆分术语表是否需要更新。返回 (消息, 需要更新)。"""
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "glossary_split.py"), "--check"],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT)
    )
    needs_update = result.returncode == 1
    return result.stdout.strip(), needs_update


def check_wiki(ttl_days: int) -> list[str]:
    """扫描 .cache/wiki/ 目录，返回过期的页面文件名列表。

    过期判断基于 front matter `fetched`（缺失回退 mtime），不需要 metadata.json。
    """
    if not WIKI_DIR.exists():
        return []

    expired = []
    ttl_seconds = ttl_days * 86400
    now = datetime.now(timezone.utc)

    for md_file in WIKI_DIR.glob("*.md"):
        age = (now - read_rel_time(md_file)).total_seconds()
        if age > ttl_seconds:
            # 文件名即规范 Wiki 页面名（中文规范名，见 docs/WIKI_CACHE_FORMAT.md）
            page_name = md_file.stem
            expired.append(page_name)

    return expired


def check_pages(names: list[str], ttl_days: int) -> list[tuple[str, str, str]]:
    """逐页判定过期状态。返回 [(查询名, 状态, 说明)]，状态 = ok / stale / missing。"""
    now = datetime.now(timezone.utc)
    ttl_seconds = ttl_days * 86400
    out: list[tuple[str, str, str]] = []
    for name in names:
        path = resolve_page(name)
        if path is None:
            out.append((name, "missing", "未缓存"))
            continue
        stamp = read_rel_time(path)
        detail = f"{path.name} {age_desc(stamp, now)}"
        if (now - stamp).total_seconds() > ttl_seconds:
            out.append((name, "stale", detail))
        else:
            out.append((name, "ok", detail))
    return out


def refresh_mojang() -> str:
    """运行 Mojang 词汇表更新。"""
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "glossary_fetch_mojang.py")],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT)
    )
    return result.stdout.strip()


def refresh_glossary() -> str:
    """运行 TechMC 术语表拆分。"""
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "glossary_split.py")],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT)
    )
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description="刷新过期的本地缓存")
    parser.add_argument("--force", action="store_true", help="强制刷新全部缓存")
    parser.add_argument("--dry-run", action="store_true", help="仅显示过期条目，不实际刷新")
    parser.add_argument("--ttl", type=int, default=7, help="过期天数，仅对 Wiki 缓存生效（默认7天）")
    parser.add_argument(
        "--check-page",
        nargs="+",
        metavar="页面名",
        help="单页过期判定（读缓存前用）：输出每页 fetched 时间与是否过期；退出码 1 = 有需处理项（过期/未缓存）",
    )
    args = parser.parse_args()

    if args.check_page:
        print(f"[refresh_cache] 单页过期判定（TTL={args.ttl} 天）\n")
        need_action = False
        for name, status, detail in check_pages(args.check_page, args.ttl):
            if status == "ok":
                print(f"  未过期  {name}\n          {detail}")
                continue
            need_action = True
            if status == "stale":
                print(f"  过期    {name}\n          {detail}")
                print(f"          → 主动刷新：python scripts/fetch_wiki.py --refresh \"{name}\"")
            else:
                print(f"  未缓存  {name}\n          {detail}")
                print("          → 走抓取降级链（wiki-tools「Wiki 页面获取」）")
        print()
        if need_action:
            print("[refresh_cache] 需处理：过期页先刷新再读取（不得静默使用旧内容）；未缓存页按降级链抓取。")
            sys.exit(1)
        print("[refresh_cache] 全部新鲜，可直接读缓存（无需网络请求）。")
        return

    print("[refresh_cache] 正在检查三类缓存...\n")

    # 1. 检查 Mojang 词汇表
    mojang_msg, mojang_stale = check_mojang()
    print(f"  Mojang 词汇表: {mojang_msg}")

    # 2. 检查 TechMC 拆分术语表
    glossary_msg, glossary_stale = check_glossary()
    print(f"  TechMC 术语表: {glossary_msg}")

    # 3. 检查 Wiki 页面缓存
    wiki_expired = check_wiki(args.ttl)
    if args.force:
        # 强制模式下所有 Wiki 页面都视为过期（文件名即规范名）；仍只告警不自动抓取
        all_pages = [f.stem for f in WIKI_DIR.glob("*.md")] if WIKI_DIR.exists() else []
        wiki_expired = all_pages

    if wiki_expired:
        print(f"  Wiki 缓存: {len(wiki_expired)} 页过期")
        for p in wiki_expired:
            print(f"    - {p}")
    else:
        print(f"  Wiki 缓存: 全部未过期（TTL={args.ttl}天）")

    needs_refresh = mojang_stale or glossary_stale
    if not needs_refresh and not wiki_expired:
        print("\n[refresh_cache] 所有缓存均为最新，无需刷新。")
        return

    if args.dry_run:
        print("\n[refresh_cache] --dry-run 模式，跳过实际刷新。")
        return

    # 执行刷新：Mojang/TechMC 自动；Wiki 仅告警（由 Agent 按 wiki-tools 降级链按需刷新）
    print("\n[refresh_cache] 开始刷新...\n")

    if mojang_stale:
        print(refresh_mojang())

    if glossary_stale:
        print(refresh_glossary())

    if wiki_expired:
        print("\n[refresh_cache] ⚠️ Wiki 过期页面不自动刷新（见上方清单）——由 Agent 在查找时按 wiki-tools 降级链按需刷新（MCP-2 lossless 优先），避免脚本 plain 降级覆盖高保真缓存。")

    print("\n[refresh_cache] 刷新完成（Wiki 仅检查告警，未自动抓取）。")


if __name__ == "__main__":
    main()
