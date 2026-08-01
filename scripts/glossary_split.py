"""
词汇表拆分脚本

从上游 TechMC Glossary（合并 CSV）按 Category 列拆分为独立文件，
存放于 .cache/glossary/（Git 忽略）。拆分后丢弃 Category 列（文件名即类别）。

用法：
    python scripts/glossary_split.py          # 执行拆分
    python scripts/glossary_split.py --check  # 仅检查是否需要拆分（退出码 1=需要）
    python scripts/glossary_split.py --help   # 显示此帮助

工作流程：
    1. 读取 _repos/techmc-glossary/TechMC Glossary.csv
    2. 按 Category 列分组
    3. 每组输出到 .cache/glossary/<category>.csv
    4. 记录 submodule commit 到 .last-split-commit（用于变更检测）

检查机制：
    --check 对比 submodule 当前 commit 与上次拆分时记录的 commit，
    不同则退出码 1，相同且输出文件存在则退出码 0。
"""

import csv
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_CSV = PROJECT_ROOT / "_repos" / "techmc-glossary" / "TechMC Glossary.csv"
OUTPUT_DIR = PROJECT_ROOT / ".cache" / "glossary"
COMMIT_FILE = OUTPUT_DIR / ".last-split-commit"


def get_submodule_commit() -> str | None:
    """获取 techmc-glossary submodule 的当前 commit hash。"""
    try:
        result = subprocess.run(
            ["git", "submodule", "status", "_repos/techmc-glossary"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        # 输出格式: " 1f4da98548598cdd5d1c9c72818195cdab3bd6f5 _repos/techmc-glossary (heads/main)"
        parts = result.stdout.strip().split()
        if parts:
            # 去掉前缀 +/- 符号
            return parts[0].lstrip("+- ")
    except Exception:
        pass
    return None


def needs_split() -> bool:
    """检查上游是否已更新，需要重新拆分。"""
    if not SOURCE_CSV.exists():
        print("错误：源文件不存在", SOURCE_CSV)
        return False

    current_commit = get_submodule_commit()
    if not current_commit:
        print("警告：无法获取 submodule commit，将执行拆分")
        return True

    if not COMMIT_FILE.exists():
        return True

    last_commit = COMMIT_FILE.read_text().strip()
    if last_commit != current_commit:
        return True

    # 即使 commit 相同，也检查输出文件是否存在
    if not any(OUTPUT_DIR.glob("*.csv")):
        return True

    return False


def do_split() -> dict[str, list[dict]]:
    """读取源 CSV，按 Category 分组。返回 {category: [rows]}。"""
    categories: dict[str, list[dict]] = {}

    with open(SOURCE_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames

        if not fieldnames or "Category" not in fieldnames:
            raise ValueError("源 CSV 缺少 Category 列")

        for row in reader:
            cat_raw = row["Category"].strip()
            if not cat_raw:
                cat_raw = "uncategorized"
            # 处理分号分隔的多类别（如 "contraptions; slimestone"）
            for cat in (c.strip() for c in cat_raw.split(";") if c.strip()):
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(row)

    return categories


def write_category(category: str, rows: list[dict], fieldnames: list[str]):
    """将一个类别的行写入 .cache/glossary/<category>.csv。"""
    # 输出列：去掉 Category 列（文件名已表达）
    out_fields = [f for f in fieldnames if f != "Category"]

    safe_name = category.replace("/", "_").replace("\\", "_")
    out_path = OUTPUT_DIR / f"{safe_name}.csv"

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return out_path


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        sys.exit(0)

    if "--check" in sys.argv:
        if needs_split():
            print("需要拆分：上游术语表已更新或输出文件缺失")
            sys.exit(1)
        else:
            print("无需拆分：术语表未变化")
            sys.exit(0)

    if not needs_split():
        print("术语表未变化，跳过拆分（使用 --check 查看状态）")
        return

    print("正在拆分词汇表...")
    categories = do_split()

    if not categories:
        print("警告：源 CSV 中没有数据")
        return

    for cat, rows in categories.items():
        path = write_category(cat, rows, list(rows[0].keys()))
        print(f"  {path.name} — {len(rows)} 条")

    # 记录 commit
    commit = get_submodule_commit()
    if commit:
        COMMIT_FILE.write_text(commit)

    print(f"\n完成：{len(categories)} 个类别，共 {sum(len(r) for r in categories.values())} 条术语")


if __name__ == "__main__":
    main()
