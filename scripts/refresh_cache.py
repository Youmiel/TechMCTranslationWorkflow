"""缓存刷新脚本 —— 统一入口，检查并刷新所有本地缓存。

覆盖三类缓存：
  1. Mojang 官方词汇表（.cache/mojang/）
  2. TechMC 拆分术语表（.cache/glossary/）
  3. Wiki 页面缓存（.cache/wiki/）

用法:
    python scripts/refresh_cache.py
    python scripts/refresh_cache.py --force      # 强制刷新全部
    python scripts/refresh_cache.py --dry-run    # 仅检查，不实际抓取
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
        [sys.executable, str(PROJECT_ROOT / "scripts" / "fetch_mojang_glossary.py"), "--check"],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT)
    )
    needs_update = result.returncode == 1
    return result.stdout.strip(), needs_update


def check_glossary() -> tuple[str, bool]:
    """检查 TechMC 拆分术语表是否需要更新。返回 (消息, 需要更新)。"""
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "split_glossary.py"), "--check"],
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
            # 文件名即 Wiki 页面名（去掉 .md 后缀，恢复空格）
            page_name = md_file.stem.replace("_", " ")
            expired.append(page_name)

    return expired


def refresh_mojang() -> str:
    """运行 Mojang 词汇表更新。"""
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "fetch_mojang_glossary.py")],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT)
    )
    return result.stdout.strip()


def refresh_glossary() -> str:
    """运行 TechMC 术语表拆分。"""
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "split_glossary.py")],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT)
    )
    return result.stdout.strip()


def refresh_wiki(pages: list[str]) -> str:
    """调用 fetch_wiki.py 批量刷新过期 Wiki 页面。"""
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "fetch_wiki.py")] + pages,
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
        # 强制模式下所有 Wiki 页面都视为过期
        all_pages = [f.stem.replace("_", " ") for f in WIKI_DIR.glob("*.md")] if WIKI_DIR.exists() else []
        wiki_expired = all_pages

    if wiki_expired:
        print(f"  Wiki 缓存: {len(wiki_expired)} 页过期")
        for p in wiki_expired:
            print(f"    - {p}")
    else:
        print(f"  Wiki 缓存: 全部未过期（TTL={args.ttl}天）")

    any_stale = mojang_stale or glossary_stale or bool(wiki_expired)
    if not any_stale:
        print("\n[refresh_cache] 所有缓存均为最新，无需刷新。")
        return

    if args.dry_run:
        print("\n[refresh_cache] --dry-run 模式，跳过实际刷新。")
        return

    # 执行刷新
    print("\n[refresh_cache] 开始刷新...\n")

    if mojang_stale:
        print(refresh_mojang())

    if glossary_stale:
        print(refresh_glossary())

    if wiki_expired:
        print(refresh_wiki(wiki_expired))

    print("\n[refresh_cache] 刷新完成。")


if __name__ == "__main__":
    main()
