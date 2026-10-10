# -*- coding: utf-8 -*-
"""参数同步校验：文档中的参数值 vs 代码常量。

**为什么需要**：多个 Skill 运行时不加载 `segment-subtitles`（行宽等规则**内联**在各自文件里，
见 `reflow-redstone/SKILL.md` 权威表“规则已内联语义回填文件，不加载”），故文档侧必须保留
**自包含值**——这是“省上下文”与“单一事实源”的取舍。代价是“改代码常量后文档滞后”成为
结构性风险（2026-09-27 行宽 26→27 即实例，残留 5 处）。

**为什么不是新副本**：本脚本**不重复任何数值**——`VALUE_CHECKS` 只登记“文件 + 正则 + 期望
常量引用”，期望值运行时从 `shared/srt_common` 读取。改常量后直接重跑即可发现全部滞后处，
不存在“脚本自己过期”的问题。

同时检查两类结构性隐患：
- **旧模块名残留**：改名/移动后残留的旧引用会**静默生效**（拿到陈旧副本而不报错）——
  2026-09-29 `srt_reflow_common` → `shared.srt_common` 迁移时曾出现工作区残留副本。
- **未使用的值占位符**：`render_subagent_prompt.py` 注册了但无模板使用的占位符（死代码）。

用法（命令根 = Project_Main/）：
    python scripts/check_param_sync.py              # 全部检查
    python scripts/check_param_sync.py --list       # 只列清单（不检查）
    python scripts/check_param_sync.py --file <子串>  # 只看路径含该子串的条目
    python scripts/check_param_sync.py --expand     # 展开每个通过项（默认只报问题）
退出码：0 = 全部一致；1 = 存在不同步 / 残留 / 死占位符
"""
import argparse
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from shared.srt_common import (  # noqa: E402
    CJK_SPEED, GAP_FILL_MS, HARD_MAX, JUMP_GAP_MS, LONG_GAP_MS, MAX_LINE, MIN_FRAG_MS, SNAP_MS,
    SOFT_MAX, SOFT_MIN, ULTRA_SHORT_MS,
    PUNCT_ROLE_CHARS, TERMINATOR_ROLE,
)
# 工作流脚本内常量（非 shared）；import 无副作用、无重活
from vocalign_backfill import LOWCONF_SCORE, LOWCONF_WINDOW, OVER_WIDE_RATIO  # noqa: E402
from vocalign_collect import PATCH_PAD_S  # noqa: E402

# 扫描范围（旧模块名 / 死占位符检查用）；_work 为一次性产物、不参与
SCAN_DIRS = (".github", "docs", "scripts", ".vscode")


class ExpectPlaceholder(str):
    """期望该处**保持占位符形式**（而非硬编码数值）。

    用途：已改用占位符注入的位置（如 `_discipline.md` 的 `<折行宽度>`），若有人把它退回写死数值，
    脚本即报错——防止“占位符机制被绕过”这一回归。
    """


def fmt(v):
    """期望值 → 文档中的字面形式。

    - 数值（代码常量）：27.0 → '27'；5000 → '5000'；5.0 → '5'
    - `ExpectPlaceholder`（str 子类）：**原样**比较（如 '<折行宽度>'）
    """
    if isinstance(v, str):
        return str(v)
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return f"{v:g}"


# ---- 文档值检查清单 ----
# 格式：(相对路径, 正则含 1+ 捕获组, 期望常量元组, 描述)
# 维护：新增参数值时追加一行即可；**不要在正则或描述里写具体数值**（那是副本）。
VALUE_CHECKS = (
    # 行宽（权威段 = 「segment-subtitles#行宽规则」；下列为不加载该 Skill 的内联消费方）
    (".github/skills/segment-subtitles/SKILL.md",
     r"中文行超宽（>(\d+) 视觉宽度，硬限制）", (HARD_MAX,), "行宽硬限"),
    (".github/skills/segment-subtitles/SKILL.md",
     r"时间码（>(\d+) 软告警）", (SOFT_MAX,), "行宽软限"),
    (".github/skills/segment-subtitles/SKILL.md",
     r"目标 (\d+)-(\d+)、软告警 >(\d+)", (SOFT_MIN, SOFT_MAX, SOFT_MAX), "行宽目标区间+软限"),
    (".github/skills/segment-subtitles/SKILL.md",
     r"\*\*硬限制 >(\d+)（必切）\*\*", (HARD_MAX,), "行宽硬限"),
    (".github/skills/reflow-redstone/semantic-reflow.md",
     r"代价最小化拼合 \[(\d+),(\d+)\]（硬 ≤(\d+)）", (SOFT_MIN, SOFT_MAX, HARD_MAX), "行宽目标区间+硬限"),
    (".github/skills/reflow-redstone/semantic-reflow.md",
     r"译文单元行宽 ≤(\d+)\*\*（软 (\d+) / 硬 (\d+)）", (HARD_MAX, SOFT_MAX, HARD_MAX), "check-r03 行宽"),
    (".github/skills/reflow-redstone/semantic-reflow.md",
     r"预测点清单、行宽 > (\d+)", (SOFT_MAX,), "告警清单软限"),
    (".github/skills/reflow-redstone/semantic-reflow.md",
     r"行宽 > (\d+) 必切（软 (\d+) 预警", (HARD_MAX, SOFT_MAX), "动作规则"),
    (".github/skills/reflow2/phase2.md",
     r"超宽（>硬 (\d+)，视觉宽度）", (HARD_MAX,), "拆子段硬限"),
    (".github/skills/reflow2/phase2.md",
     r"行宽 >(\d+) → 必切", (HARD_MAX,), "动作规则"),
    (".github/skills/translate-redstone/SKILL.md",
     r"行宽（`srt_check_width\.py` >(\d+) 打回）", (HARD_MAX,), "阶段二硬闸门"),
    (".github/skills/translate-redstone/SKILL.md",
     r">(\d+) 硬打回退出码 1、>(\d+) 软告警", (HARD_MAX, SOFT_MAX), "校验命令说明"),
    (".github/skills/subagent-dispatch/SKILL.md",
     r"行宽 >(\d+) 切分", (HARD_MAX,), "修复档位举例"),
    (".github/experience/source_experience.md",
     r"行宽 (\d+) 硬限", (HARD_MAX,), "碎片接受理由"),
    (".github/experience/source_experience.md",
     r"直接超硬限 (\d+)", (HARD_MAX,), "括注断点理由"),
    (".github/experience/source_experience.md",
     r"宽度 > (\d+) 时", (HARD_MAX,), "回 r02 补标点判据"),
    (".github/experience/source_experience.md",
     r"行宽 (\d+)-(\d+) 软预警", (SOFT_MAX, HARD_MAX), "软预警区间"),
    (".github/experience/source_experience.md",
     r"\*\*硬限 (\d+)\*\*（软 (\d+)）", (HARD_MAX, SOFT_MAX), "当前口径"),
    ("docs/PRODUCT_FORMATS_REFLOW.md",
     r"代价最小化拼合 \[(\d+),(\d+)\]（硬 ≤(\d+)）", (SOFT_MIN, SOFT_MAX, HARD_MAX), "预分句宽度"),
    ("docs/PRODUCT_FORMATS_REFLOW.md",
     r"行宽 (\d+)-(\d+) / ZH 忠实", (SOFT_MAX, HARD_MAX), "check-r03 契约"),
    ("docs/PRODUCT_FORMATS_REFLOW.md",
     r"📏 行宽 >(\d+)", (SOFT_MAX,), "告警清单软限"),
    ("docs/PRODUCT_FORMATS_TRANSLATE.md",
     r"行宽软 (\d+) / 硬 (\d+)", (SOFT_MAX, HARD_MAX), "产物约束"),    (".vscode/tasks.json",
     r"行宽≤(\d+)/ZH忠实", (HARD_MAX,), "任务描述"),
    # 折行（MAX_LINE；由脚本统一执行、subagent 不折行）
    (".github/skills/reflow-redstone/semantic-reflow.md",
     r"折行 ≤(\d+) 字符/行", (MAX_LINE,), "r01 折行"),
    (".github/skills/reflow-redstone/semantic-reflow.md",
     r"MAX_LINE=(\d+)", (MAX_LINE,), "归一化说明"),
    (".github/skills/reflow2/phase2.md",
     r"折行 ≤(\d+) 字符/行", (MAX_LINE,), "r01 折行"),
    (".github/skills/redstone-conventions/SKILL.md",
     r"产物单行 ≤(\d+) 字符", (MAX_LINE,), "折行约定"),
    (".github/skills/subagent-dispatch/_discipline.md",
     r"每 ~`(.*?)` 字符", (ExpectPlaceholder("<折行宽度>"),), "折行须知（须保持占位符）"),
    ("docs/PRODUCT_FORMATS.md",
     r"产物单行 ≤(\d+) 字符", (MAX_LINE,), "折行约定"),
    ("docs/PRODUCT_FORMATS_REFLOW.md",
     r"折行 ≤(\d+) 字符/行", (MAX_LINE,), "r01 折行"),
    (".github/agents/reflow-worker.agent.md",
     r"每 ~(\d+) 字符折行", (MAX_LINE,), "折行提示"),
    # 空隙 / 剪辑跳转（LONG_GAP_MS / JUMP_GAP_MS）
    (".github/skills/redstone-conventions/SKILL.md",
     r"长停顿 >(\d+)s / 剪辑跳转 >(\d+)s", (LONG_GAP_MS // 1000, JUMP_GAP_MS // 1000), "空隙阈值"),
    # 段间小空隙填充（GAP_FILL_MS；观感例外，vocalign 独有）
    (".github/skills/vocalign/SKILL.md",
     r"相邻段间隙 < (\d+)s 时把前段", (GAP_FILL_MS // 1000,), "空隙填充阈值"),
    # 超宽英文片比例判据（OVER_WIDE_RATIO）
    (".github/skills/vocalign/phase3.md",
     r"英/中宽比 ≥ (\d+)", (OVER_WIDE_RATIO,), "超宽片判据"),
    # 可疑点重识别半径（PATCH_PAD_S）
    (".github/skills/vocalign/phase0.md",
     r"默认即 ±(\d+)s", (PATCH_PAD_S,), "重识别半径"),
    ("docs/PRODUCT_FORMATS_VOCALIGN.md",
     r"英/中宽比 ≥ (\d+)（正常片约", (OVER_WIDE_RATIO,), "超宽片判据"),
    # 假空隙判据（LOWCONF_WINDOW / LOWCONF_SCORE；回填降级阈值）
    ("docs/PRODUCT_FORMATS_VOCALIGN.md",
     r"边界前后各 (\d+) 词内有 `score` < (\d+\.\d+)",
     (LOWCONF_WINDOW, LOWCONF_SCORE), "假空隙判据"),
    (".github/skills/reflow-redstone/semantic-reflow.md",
     r"长停顿 >(\d+)s / 剪辑跳转 >(\d+)s", (LONG_GAP_MS // 1000, JUMP_GAP_MS // 1000), "空隙阈值"),
    (".github/skills/reflow-redstone/semantic-reflow.md",
     r"单元内 gap > (\d+)s、剪辑跳转 > (\d+)s", (LONG_GAP_MS // 1000, JUMP_GAP_MS // 1000), "告警清单"),
    (".github/skills/reflow2/phase2.md",
     r"长停顿 >(\d+)s / 剪辑跳转 >(\d+)s", (LONG_GAP_MS // 1000, JUMP_GAP_MS // 1000), "空隙阈值"),
    # 阅读速度 / 碎片 / 吸附（CJK_SPEED / MIN_FRAG_MS / SNAP_MS）
    (".github/skills/segment-subtitles/SKILL.md",
     r"中文按 (\d+) 字/秒", (CJK_SPEED,), "阅读速度"),
    (".github/skills/segment-subtitles/SKILL.md",
     r"单条字幕时长通常 ≥(\d+)s", (MIN_FRAG_MS // 1000,), "碎片阈值"),
    (".github/skills/segment-subtitles/SKILL.md",
     r"阅读所需×(\d+\.\d+) 且失配 ≥(\d+)ms", (0.7, SNAP_MS), "显著失配判据"),
    (".github/skills/segment-subtitles/SKILL.md",
     r"长句碎片（<(\d+)s）", (1,), "碎片定义"),
    (".github/skills/reflow2/phase2.md",
     r"吸附真实 cue 边界 ≤(\d+)ms", (SNAP_MS,), "吸附窗口"),
    (".github/skills/reflow-redstone/semantic-reflow.md",
     r"\[--snap-ms (\d+)\] \[--cjk-speed (\d+)\]", (SNAP_MS, CJK_SPEED), "CLI 示例"),    (".github/skills/reflow-redstone/semantic-reflow.md",
     r"按中文阅读速度（`--cjk-speed (\d+)`）", (CJK_SPEED,), "阅读速度"),
    (".github/skills/reflow-redstone/semantic-reflow.md",
     r"允许预测点（(\d+)ms 取整", (100,), "预测点取整"),    # 标点角色表（权威 = shared.srt_common.PUNCT_ROLE_CHARS；此处仅校 terminator ——
    # 它是 Z/E 句界判据，改动会直接改句数、使 align/ 失效，故必须与文档同步）
    (".github/skills/segment-subtitles/SKILL.md",
     r"\|\s*`terminator`\s*\|[^|]*\|\s*`([^`]+)`",
     (PUNCT_ROLE_CHARS[TERMINATOR_ROLE],), "标点角色表 terminator 字符集"),)

# ---- 旧模块名残留检查（改名/移动后残留会静默生效）----
LEGACY_PATTERNS = (
    (r"\bsrt_reflow_common\b", "旧模块名 `srt_reflow_common`（现为 `shared.srt_common`）"),
    (r"\bsrt_reflow_punct\b", "旧模块名 `srt_reflow_punct`（现为 `srt_reflow_core.punct`）"),
    (r"from\s+request_identity\s+import", "旧导入路径 `request_identity`（现为 `shared.request_identity`）"),
    (r"\bDEFAULT_ROLE_CHARS\b",
     "旧标点表名 `DEFAULT_ROLE_CHARS`（已改为跨语言通用表 `shared.srt_common.PUNCT_ROLE_CHARS`）"),
    (r"\bDEFAULT_BRACKETS\b",
     "旧括号表名 `DEFAULT_BRACKETS`（已改为跨语言通用表 `shared.srt_common.PUNCT_BRACKETS`）"),
    (r"\b_en_extra_guard\b",
     "旧 guard 名 `_en_extra_guard`（已改为按标点种类判定的 `punct._extra_guard`）"),
)
# 已知的历史遗留引用所在目录前缀（一次性产物，不参与生产；改名前产生）
LEGACY_SKIP_PREFIXES = ("_work/", "_Archive/", "_Archive_Prompt/", "_Sandbox/", "_Release/")
# 自身排除：本脚本 docstring 必然提及旧模块名（用于说明迁移背景），不算残留
LEGACY_SKIP_FILES = ("scripts/check_param_sync.py",)


def check_values(target=None):
    """文档值 vs 代码常量。返回 (problems, checked_count)。"""
    problems, n = [], 0
    for rel, pattern, consts, desc in VALUE_CHECKS:
        if target and target not in rel:
            continue
        n += 1
        path = PROJECT_ROOT / rel
        if not path.is_file():
            problems.append(f"❌ {rel}：文件不存在")
            continue
        text = path.read_text(encoding="utf-8")
        exp = tuple(fmt(c) for c in consts)
        hits = list(re.finditer(pattern, text))
        if not hits:
            problems.append(f"❌ {rel}：未匹配到“{desc}”（正则 {pattern!r}）——文档措辞可能已改，请更新清单")
            continue
        for m in hits:
            if m.groups() != exp:
                line_no = text.count("\n", 0, m.start()) + 1
                problems.append(
                    f"❌ {rel}:{line_no} {desc}：文档 {'/'.join(m.groups())} ≠ 代码 {'/'.join(exp)}"
                )
    return problems, n


def check_legacy(target=None):
    """旧模块名 / 旧导入路径残留。"""
    problems, n = [], 0
    exts = (".py", ".md", ".json", ".yaml", ".yml")
    for d in SCAN_DIRS:
        base = PROJECT_ROOT / d
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix not in exts:
                continue
            if any(str(path.relative_to(PROJECT_ROOT)).startswith(p) for p in LEGACY_SKIP_PREFIXES):
                continue
            rel = str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
            if rel in LEGACY_SKIP_FILES:
                continue
            if target and target not in rel:
                continue
            n += 1
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for pat, desc in LEGACY_PATTERNS:
                for m in re.finditer(pat, text):
                    line_no = text.count("\n", 0, m.start()) + 1
                    problems.append(f"❌ {rel}:{line_no} {desc}")
    return problems, n


def check_placeholders():
    """值占位符是否都已注册且有模板使用（防死代码）。"""
    problems, n = [], 0
    render = PROJECT_ROOT / "scripts" / "render_subagent_prompt.py"
    m = re.search(r"VALUE_PLACEHOLDERS\s*=\s*\{(.*?)\n\}", render.read_text(encoding="utf-8"), re.S)
    if not m:
        return ["❌ scripts/render_subagent_prompt.py：未找到 VALUE_PLACEHOLDERS 定义"], 0
    keys = re.findall(r'"([^"]+)"\s*:', m.group(1))
    templates = sorted((PROJECT_ROOT / ".github" / "skills").rglob("*.md"))
    for k in keys:
        n += 1
        users = [str(t.relative_to(PROJECT_ROOT)).replace("\\", "/")
                 for t in templates if k in t.read_text(encoding="utf-8")]
        if not users:
            problems.append(f"❌ 占位符 {k}：已注册但无模板使用（死代码）")
        else:
            print(f"  占位符 {k} ← {', '.join(users)}")
    return problems, n


def main():
    ap = argparse.ArgumentParser(description="参数同步校验：文档值 vs 代码常量（零副本：期望值运行时读取）")
    ap.add_argument("--list", action="store_true", help="只列检查清单，不实际检查")
    ap.add_argument("--file", default=None, help="只检查相对路径含该子串的条目")
    ap.add_argument("--expand", action="store_true", help="展开通过项统计")
    args = ap.parse_args()

    if args.list:
        print(f"文档值检查（{len(VALUE_CHECKS)} 条）：")
        for rel, pattern, consts, desc in VALUE_CHECKS:
            exp = "/".join(fmt(c) for c in consts)
            print(f"  {rel:58s} {desc:20s} ← {exp}")
        print(f"\n旧模块名检查（{len(LEGACY_PATTERNS)} 条）：{', '.join(d for _, d in LEGACY_PATTERNS)}")
        print(f"扫描范围：{', '.join(SCAN_DIRS)}（跳过 {', '.join(LEGACY_SKIP_PREFIXES)}）")
        return 0

    all_problems = []
    for name, fn in (("文档值", check_values), ("旧模块名", check_legacy)):
        problems, n = fn(args.file)
        all_problems += problems
        if args.expand:
            print(f"  {name}：检查 {n} 项，问题 {len(problems)} 处")

    problems, n = check_placeholders()
    all_problems += problems
    if args.expand:
        print(f"  值占位符：检查 {n} 项，问题 {len(problems)} 处")

    if all_problems:
        print(f"\n发现 {len(all_problems)} 处不同步：")
        for p in all_problems:
            print("  " + p)
        print("\n提示：文档值须与 `shared/srt_common.py` 常量一致；"
              "内联原因见 segment-subtitles「行宽规则」段的消费方清单表。")
        return 1
    print("✅ 参数同步校验通过（文档值 = 代码常量；无旧模块名残留；无死占位符）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
