"""
Mojang 官方翻译词汇表获取（便捷入口）

直接调用即可，路径由 mojang_glossary 内部自动推导。

用法：
    python scripts/glossary_fetch_mojang.py          # 下载/更新
    python scripts/glossary_fetch_mojang.py --check  # 仅检查新版本（退出码 1=有新版本）
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.mojang_glossary.main import fetch_glossary, check_version


def main():
    check_only = "--check" in sys.argv

    if check_only:
        new_version = check_version()
        if new_version:
            print(f"New version available: {new_version}")
            sys.exit(1)
        else:
            print("Already up to date.")
    else:
        updated = fetch_glossary()
        if updated:
            version_path = PROJECT_ROOT / ".cache" / "mojang" / "MC_version.txt"
            print(f"Mojang glossary updated to {version_path.read_text().strip()}")
        else:
            print("Already up to date.")


if __name__ == "__main__":
    main()
