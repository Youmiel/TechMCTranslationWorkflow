"""
编辑器适配初始化脚本（跨平台）

为 Claude Code、Cursor 等编辑器创建必要的符号链接，
使其复用 .github/ 下的统一 Skill 和指令文件。

用法：
    python scripts/setup_editors.py          # 首次初始化
    python scripts/setup_editors.py --force  # 覆盖已有链接
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GITHUB_SKILLS = PROJECT_ROOT / ".github" / "skills"
AGENTS_MD = PROJECT_ROOT / "AGENTS.md"

CLAUDE_DIR = PROJECT_ROOT / ".claude"
CLAUDE_SKILLS = CLAUDE_DIR / "skills"
CLAUDE_MD = PROJECT_ROOT / "CLAUDE.md"

CLAUDE_HEADER = (
    "<!--\n"
    "  CLAUDE.md → AGENTS.md\n"
    "  此文件由 scripts/setup_editors.py 生成，请勿手动编辑。\n"
    "  Claude Code 会自动加载此文件作为项目指令。\n"
    "  所有修改请在 AGENTS.md 中进行。\n"
    "-->\n\n"
)


def is_admin() -> bool:
    """检查是否有管理员权限（Windows）或 root（Unix）。"""
    try:
        if sys.platform == "win32":
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        return os.geteuid() == 0  # type: ignore[attr-defined]
    except Exception:
        return False


def create_symlink_or_copy(src: Path, dst: Path, is_dir: bool) -> str:
    """创建符号链接，权限不足时降级为复制。返回操作描述。"""
    if dst.exists() or dst.is_symlink():
        return "exists"

    try:
        if sys.platform == "win32":
            # Windows: 目录用 junction（无需管理员），文件用 symlink（需开发者模式）
            if is_dir:
                import subprocess
                subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(dst), str(src)],
                    check=True, capture_output=True, text=True
                )
                return "junction"
            elif is_admin():
                os.symlink(src, dst)
                return "symlink"
            else:
                raise OSError("No permission for file symlink")
        else:
            # macOS / Linux: 直接用 os.symlink
            dst.symlink_to(src)
            return "symlink"
    except (OSError, subprocess.CalledProcessError):
        # 降级：复制
        if is_dir:
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        return "copy"


def setup_claude(force: bool) -> None:
    """为 Claude Code 创建适配。"""
    print("[Claude Code]")

    if force and CLAUDE_SKILLS.exists():
        if CLAUDE_SKILLS.is_symlink() or CLAUDE_SKILLS.is_junction():
            CLAUDE_SKILLS.unlink()
        else:
            shutil.rmtree(CLAUDE_SKILLS)

    if not CLAUDE_SKILLS.exists():
        CLAUDE_DIR.mkdir(exist_ok=True)
        method = create_symlink_or_copy(GITHUB_SKILLS, CLAUDE_SKILLS, is_dir=True)
        if method == "exists":
            print("  .claude/skills/ 已存在，跳过（使用 --force 覆盖）")
        else:
            print(f"  .claude/skills/ → .github/skills/  ({method})")
    else:
        print("  .claude/skills/ 已存在，跳过（使用 --force 覆盖）")

    # CLAUDE.md
    if force and CLAUDE_MD.exists():
        CLAUDE_MD.unlink()

    if not CLAUDE_MD.exists():
        agents_content = AGENTS_MD.read_text(encoding="utf-8")
        CLAUDE_MD.write_text(CLAUDE_HEADER + agents_content, encoding="utf-8")
        print("  CLAUDE.md (同步自 AGENTS.md)")


def main():
    parser = argparse.ArgumentParser(description="编辑器适配初始化")
    parser.add_argument("--force", action="store_true", help="覆盖已有链接和文件")
    args = parser.parse_args()

    print("=== 编辑器适配初始化 ===")
    print(f"项目根：{PROJECT_ROOT}")
    print()

    setup_claude(args.force)

    print()
    print("[Cursor]")
    print("  Cursor 可直接读取 AGENTS.md，无需额外配置。")
    print("  如需自定义规则，可在 .cursor/rules/ 下创建 .mdc 文件。")
    print()

    print("=== 适配完成 ===")
    print()
    print("验证方法：")
    print("  VS Code Copilot: 聊天框输入 / 应看到 Skill 名称")
    print("  Claude Code:     claude 启动后自动加载 CLAUDE.md 和 .claude/skills/")
    print("  Cursor:          自动读取 AGENTS.md")
    print()
    print("重新运行以更新 CLAUDE.md：")
    print("  python scripts/setup_editors.py --force")


if __name__ == "__main__":
    main()
