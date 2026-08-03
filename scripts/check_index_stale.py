# -*- coding: utf-8 -*-
"""检查 _repos/ 各 submodule 的当前 commit 是否与索引记录一致，决定哪些索引需更新。

依据 `index-repos` Skill「更新判断」：比较 submodule 当前 HEAD commit 与
`indexes/repos/<repo>.md` 头部记录的「上游 commit」；不一致即该仓库索引过期，需重新生成。

注意：本脚本检测的是"已检出 commit 与索引记录是否漂移"——submodule 更新
（`git submodule update --remote`）后 HEAD 变化即会标记需更新。若要检测"上游是否有
更新"，先 `git submodule update --remote --init` 再跑本脚本。

用法:
    python scripts/check_index_stale.py               # 全部仓库
    python scripts/check_index_stale.py --only <repo> # 只看单个仓库
退出码: 0 = 全部最新; 1 = 存在需更新/异常
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPOS_DIR = PROJECT_ROOT / "_repos"
INDEX_DIR = PROJECT_ROOT / "indexes" / "repos"
COMMIT_RE = re.compile(r"上游 commit[:：]\s*([0-9a-fA-F]{7,40})")

ap = argparse.ArgumentParser(description='检查 submodule commit 与索引记录是否一致')
ap.add_argument('--only', help='只检查指定仓库名')
args = ap.parse_args()


def current_commit(repo_dir: Path):
    """读取 submodule 当前 HEAD commit；非 git 仓库返回 None。"""
    r = subprocess.run(["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def recorded_commit(index_path: Path):
    """从索引 md 头部提取「上游 commit」；无索引或未记录返回 None。"""
    if not index_path.exists():
        return None
    text = index_path.read_text(encoding="utf-8", errors="replace")
    m = COMMIT_RE.search(text)
    return m.group(1) if m else None


repos = sorted(
    d for d in REPOS_DIR.iterdir()
    if d.is_dir() and not d.name.startswith(".")
)
if args.only:
    repos = [r for r in repos if r.name == args.only]

if not repos:
    print("未找到任何 submodule 目录（_repos/）")
    sys.exit(0)

print(f"{'仓库':<30} {'当前 commit':<14} {'索引记录':<14} 状态")
print("-" * 82)
problems = []
for repo in repos:
    idx = INDEX_DIR / f"{repo.name}.md"
    cur = current_commit(repo)
    rec = recorded_commit(idx)
    if cur is None:
        status = "无法读取当前 commit"
        problems.append(repo.name)
    elif rec is None:
        status = "无索引或无 commit 记录"
        problems.append(repo.name)
    elif cur != rec:
        status = "需更新"
        problems.append(repo.name)
    else:
        status = "最新"
    print(f"{repo.name:<30} {(cur or '-'):<14} {(rec or '-'):<14} {status}")

print("-" * 82)
if problems:
    print(f"需处理 {len(problems)} 个仓库: {', '.join(problems)}")
    sys.exit(1)
print("全部最新，无需更新索引。")
