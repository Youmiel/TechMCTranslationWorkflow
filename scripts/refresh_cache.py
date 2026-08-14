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
"""

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / ".cache"
WIKI_DIR = CACHE_DIR / "wiki"
MOJANG_DIR = CACHE_DIR / "mojang"
GLOSSARY_DIR = CACHE_DIR / "glossary"


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

    过期判断基于文件修改时间，不需要 metadata.json。
    """
    if not WIKI_DIR.exists():
        return []

    expired = []
    ttl_seconds = ttl_days * 86400
    now = datetime.now(timezone.utc)

    for md_file in WIKI_DIR.glob("*.md"):
        mtime = datetime.fromtimestamp(md_file.stat().st_mtime, tz=timezone.utc)
        age = (now - mtime).total_seconds()
        if age > ttl_seconds:
            # 文件名即规范 Wiki 页面名（中文规范名，见 docs/WIKI_CACHE_FORMAT.md）
            page_name = md_file.stem
            expired.append(page_name)

    return expired


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
    args = parser.parse_args()

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
