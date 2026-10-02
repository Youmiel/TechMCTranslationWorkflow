# -*- coding: utf-8 -*-
"""阶段编号与引用一致性校验（阶段令牌 / 跨文件锚点 / 结构形态）。

**为什么需要**：三个主 skill（translate-redstone / reflow-redstone / reflow2）的阶段编号长期
并存多套空间——汉字数字与阿拉伯数字混用、`阶段零`(U+96F6) 与 `阶段〇`(U+3007) 两个不同字符
并存、分数编号 `阶段二½` 与加号编号 `阶段二+` 无定义顺序、reflow 与 reflow2 的阶段三内部
“步骤 1-7”同号异义（步骤 4 一边是翻译、一边是源头固化）。这些缺陷**无任何脚本兜底**，
只能靠人眼；且跨文件 `#锚点` 引用一旦标题改名即**静默失效**（Markdown 不报错，点击才 404）。

**零副本**：本脚本不重复任何标题文本——注册表只登记**锚点**（链接目标的天然标识）与
**阶段号**，期望值运行时从文档解析（同 `check_param_sync.py` 惯例：改文档即重跑，不存在
“脚本自己过期”）。标题文本改了但锚点未登记 → 报“被引用锚点不存在”，逼出一次自觉更新。

检查分组：
- A 阶段令牌合法（唯一空间 `〇一二三四五六`；禁 零/壹/阿拉伯数字/½/+/A）、无残留 `§1.x`
- B 跨文件 `](#锚点)` 可解析；被引用锚点在冻结清单内
- C 有序列表序号连续、阶段标题集合与注册表一致、自称阶段数吻合、禁合并标题、表格阶段行升序
- D 无残留数字步骤号（阶段三内部已改角色名引用）
- E 标题不得含全角括注（括注使锚点变长、引用方写短形式即静默断链）
- F `「」` 弱引用可解析（**警告级**：外部引用须 `「<前缀>#<标题>」`，无 `#` = 同文件引用）
- P 引用块短语（`>` 句尾无句末标点）与标题写死数量词（见 `docs/SYMBOLS.md`）
用法（命令根 = Project_Main/）：
    python scripts/check_phase_sync.py                 # 全部检查
    python scripts/check_phase_sync.py --list          # 只列注册表
    python scripts/check_phase_sync.py --group A       # 只跑某组（可重复）
    python scripts/check_phase_sync.py --file <子串>    # 只看路径含该子串的文件
    python scripts/check_phase_sync.py --expand        # 展开每处问题的文件:行号 + 片段
退出码：0 = 全部通过；1 = 存在违规
"""
import argparse
import collections
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---- 扫描范围 ----
SCAN_TARGETS = (".github", "docs", "scripts", "AGENTS.md")
# 扫描的文本类型：.md 为主，.py 的 docstring/描述文本同样承载阶段引用
SCAN_GLOBS = ("*.md", "*.py")
# 排除：submodule（自有 阶段 A/B/C 体系）、字节码目录
SCAN_EXCLUDE_PREFIXES = (".github/skills/humanizer-zh", "scripts/__pycache__")
# 自身排除：docstring 与注册表必然出现旧令牌（用于说明迁移背景），非残留
SCAN_EXCLUDE_FILES = ("scripts/check_phase_sync.py", "scripts/srt_snap_audio.py")

# ---- 阶段空间注册表（唯一权威；新号在此、旧号不出现在此 = 旧号自动成违规）----
# 号 → (角色名, 适用工作流集合)。阶段四 仅 translate 适用（reflow/reflow2 无去翻译腔）。
PHASES = {
    "〇": ("字幕机械修复", ("translate-redstone", "reflow-redstone", "reflow2")),
    "一": ("领域预判与准备", ("translate-redstone", "reflow-redstone", "reflow2")),
    "二": ("术语扫描与知识补齐", ("translate-redstone", "reflow-redstone", "reflow2")),
    "三": ("工作流核心", ("translate-redstone", "reflow-redstone", "reflow2")),
    "四": ("去翻译腔", ("translate-redstone",)),
    "五": ("人工审核与输出门禁", ("translate-redstone", "reflow-redstone", "reflow2")),
    "六": ("数据源效果总结", ("translate-redstone", "reflow-redstone", "reflow2")),
}

# 各主/阶段文件的阶段标题集合（`### 阶段X` 级别）——与 PHASES 归属交叉约束
PHASE_HEADING_SETS = {
    ".github/skills/translate-redstone/SKILL.md": frozenset("〇一二三四五六"),
    ".github/skills/reflow-redstone/SKILL.md": frozenset("〇一二三五六"),
    ".github/skills/reflow2/SKILL.md": frozenset("〇一二三五六"),
    ".github/skills/redstone-preprocess/SKILL.md": frozenset("〇一二"),
    ".github/skills/redstone-review/SKILL.md": frozenset(),   # 不设编号阶段标题（审核循环机制）
    ".github/skills/redstone-finalize/SKILL.md": frozenset("六"),
    ".github/skills/reflow-redstone/semantic-reflow.md": frozenset("三"),
    ".github/skills/reflow2/phase2.md": frozenset("三"),
}

# ---- 被外部引用的锚点冻结清单（file → 必须存在的锚点集）----
# 语义：标题改名 → 锚点消失 → 本检查报警，逼出“同步更新链接 + 此处登记”的自觉动作。
FROZEN_ANCHORS = {
    ".github/skills/redstone-preprocess/SKILL.md": (
        "阶段〇字幕机械修复",
        "阶段一领域预判与准备",
        "阶段二术语扫描与知识补齐",
        "21-术语扫描",
        "22-集中补齐",
        "23-术语确认",
        "24-术语入库",
        "输入--输出",
    ),
    ".github/skills/redstone-conventions/SKILL.md": (
        "工作区隔离",
        "环境",
        "语言顺序与输出变体",
        "长视频分块",
        "时间纪律",
    ),
    ".github/skills/subagent-dispatch/SKILL.md": (
        "派发配方",
        "派发边界",
        "主会话读写最小化",
        "收信号即验",
        "定点修正校验打回先小规模修不整块重派",
        "合并",
        "纪律母版",
        "派发引用-prompt",
        "任务导航表",
    ),
    ".github/skills/segment-subtitles/SKILL.md": (
        "输出与校验",
        "共享-cue-与整条归属",
    ),
    ".github/skills/term-registration/SKILL.md": ("同步步骤",),
    ".github/skills/use-glossary/SKILL.md": ("术语源优先级", "类别预判"),
    ".github/skills/maintain-knowledge/SKILL.md": ("经验提炼规则",),
    ".github/skills/wiki-tools/SKILL.md": ("缓存过期与主动刷新",),
}

# ---- 违规类型（check 组 → 描述），供 --list 与分组过滤 ----
CHECK_GROUPS = {
    "A": "阶段令牌 / 残留编号",
    "B": "跨文件锚点",
    "C": "结构形态",
    "D": "数字步骤号残留",
    "E": "标题括注",
    "F": "弱引用 `「」` 断链",
    "P": "引用块短语 / 标题数量词",
}

# 警告级组：只报不拦（不影响退出码）——判据只能验「存在性/归属」，
# 未命中 ≠ 违规（可能是指称概念、仓库外对象、或有意的短形式），需借上下文裁定。
WARN_GROUPS = {"F"}

# 豁免：自有“阶段 X”体系、与工作流编号空间无关的文件（不进 A 组检查）
PHASE_TOKEN_EXEMPT_FILES = (".github/skills/video-abstract/SKILL.md",)

# 豁免：P 组引用块检查（**待办**：小节含义/分类名规范未定，定了就删本行）
# trap_words.md 的小节下 `>` 中文名来自 glossary_categories.yaml 的 label（零消费方的双源），
# 其去留取决于分类名权威的裁定（见 docs/SYMBOLS.md 维护节）。
BQ_EXEMPT_FILES = (".github/experience/trap_words.md",)

# ---- 正则 ----
# 阶段令牌：捕获 `阶段` 后紧跟的“编号性”字符（数字 / 汉字数字 / 分数 / 加号 / 单个 ABC）
PHASE_TOKEN_RE = re.compile(r"阶段\s*([0-9零〇一二三四五六七八九十百½¼¾+]+|[ABC])(?![0-9零〇一二三四五六七八九十])")
# 阶段缩写引用（`阶段〇/一` 形式——应改为 Markdown 链接）
PHASE_ABBR_RE = re.compile(r"阶段[〇一二三四五六](?:\s*/\s*[〇一二三四五六])+")
# 残留子节编号（原 §1.1–§1.4 = 阶段一子节；阶段改号后应为 §2.x 且引用改用链接）
LEGACY_SUBSEC_RE = re.compile(r"§\s*1\.[1-4]")
# 数字步骤号（阶段三内部已改角色名引用）；限同行——`\s*` 会跨行误报（如「term-registration#同步步骤」换行后接“1.”）
LEGACY_STEP_RE = re.compile(r"步骤[ \t]*[0-9]")
# 有序列表项（含缩进；用于序号连续性）
ORDERED_ITEM_RE = re.compile(r"^(\s*)(\d+)\.\s")
# 无序列表项（用于区分“新列表开始”与“列表内续行”）
UNORDERED_ITEM_RE = re.compile(r"^(\s*)[-*+]\s")
# 小数序号列表项（`9.5.` 形式——Markdown 列表序号不允许）
DECIMAL_ITEM_RE = re.compile(r"^\s*\d+\.\d+\.\s", re.MULTILINE)
# 阶段标题（`### 阶段X：…`）
PHASE_HEADING_RE = re.compile(r"^(#{2,4})\s*阶段\s*([0-9零〇一二三四五六七八九十½¼¾+]*)", re.MULTILINE)
# 合并标题（`### 阶段〇 / 阶段一：…`）
MERGED_HEADING_RE = re.compile(r"^#{2,6}\s*阶段[〇一二三四五六](?:\s*/\s*阶段?[〇一二三四五六])+", re.MULTILINE)
# 自称阶段数（`本工作流包含五个阶段`）
DECLARED_COUNT_RE = re.compile(r"本工作流[^。\n]{0,20}?([一二三四五六七八九十\d]+)\s*个阶段")
CN_DIGITS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
# 块内标题（取锚点用；MULTILINE 必需——缺则标题集恒空、全体锚点误报）
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
# 标题内的全角括注（**任意位置**，含"括注 + 冒号 + 说明"形态）
# 为什么不用"末尾锚定"：`## 定点修正（surgical-fix）：校验打回…` 括注在中间，
# 末尾锚定会漏；且括注在标题任何位置都会污染锚点与引号引用
TITLE_ANY_PAREN_RE = re.compile(r"（[^（）]{1,40}）")
# Markdown 链接（含锚点）
LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")

# ---- P 组判据（见 docs/SYMBOLS.md「SYMBOLS.md#`>` 引用块」与「SYMBOLS.md#标题不写死数量词」）----
# 标题含写死的数量词（`四级查找` / `三档决策` / `三种词汇表…`）——数量是可变量，
# 写进标题即要求内容永不变，否则标题与内容失同步、连带大量引用更改。
TITLE_COUNT_RE = re.compile(r"[一二三四五六七八九十0-9]+\s*(?:级|档|种|条|步|层|类)")
# `>` 行（捕获正文）与代码围栏
BLOCKQ_RE = re.compile(r"^>\s?(.*)$")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
# 完整句 = blockquote 块内有句末标点（含 URL/参见类出处标记）；块级判定、非单行
BLOCKQ_SENT_RE = re.compile(r"[。；！？]|参见|摘自|https?://")
# 含中文（无中文 = 英文示例/原文引用，豁免）
CJK_RE = re.compile(r"[\u4e00-\u9fff]")

# ---- F 组判据（见 docs/SYMBOLS.md「`「」` 弱引用」）----
# 约定：外部引用写 `「<文件名|skill 名|目录名>#<标题>」`；无 `#` = 同文件引用。
# 无法解析到外部文件名 → 按同文件引用处理，找不到即报。
WEAKREF_RE = re.compile(r"「([^」\n]{1,80})」")
# 分节名（`四、内容边界`）——同文件引用，天然成立
SECTION_NAME_RE = re.compile(r"^[一二三四五六七八九十]+、")
# 译文对话（引号内以句末标点收尾）——豁免
DIALOG_RE = re.compile(r"[。！？]$")
# 仓库外对象（记忆文件等，不在本仓库内）—— 形态判据：引用方已给出 `xxx-xxx` 式源名
OUTSIDE_HINT_RE = re.compile(r"skill-writing-principles|prompt-conventions|orchestrator-discipline")
# 标题「归一化」：去空白/标点/强调符（与 `_sym_fix.py` 同口径，供标题比对）
TITLE_NORM_RE = re.compile(r"[\s`*_（）()【】\[\]，,。.、：:/\\\-—–~·]+")
# 引号外紧邻的 owner 表达（`X.md`「」、skill名`「」、X 的「」）
# 词边界：前缀不得是单词中间（否则 `csv-rules` Skill「」会误匹配 `kill`）
OUTER_OWNER_RE = re.compile(
    r"(?<![\w\-])(?:`([\w\-./]+\.(?:md|py|csv|tsv|json|yaml))`|([a-z][a-z0-9]*(?:-[a-z0-9]+)*)`?)"
    r"(?:的|中|里)?\s*$")
# 警示块（需视觉阻断，豁免）
WARN_BQ_RE = re.compile(r"^⚠️")
# 代码围栏内的样式化引用块（如 `> 合句为 S<n+m>` 是格式骨架示例，非文档引用块）
# —— 由 fence 状态机隐式跳过，见 check_p


def _build_repo_index():
    """全仓索引：标题（归一化）→ 文件集；rel → 本文件标题集；名字 → 文件集。

    名字索引含三类：文件名（`task-fix.md`）、文件 stem、路径段（skill 名 / 目录名）。
    解析时优先 `SKILL.md`，避免 skill 名同时命中该目录下全部文件造成假歧义。
    """
    titles = collections.defaultdict(set)
    rel_titles = {}
    names = collections.defaultdict(set)
    for rel in iter_files():
        p = PROJECT_ROOT / rel
        names[p.name].add(rel)
        names[p.stem].add(rel)
        for seg in rel.split("/")[:-1]:
            names[seg].add(rel)
        text = read_text(rel)
        own = set()
        if text is not None and p.suffix == ".md":
            for _m, head in iter_headings(text, ".md") or ():
                n = TITLE_NORM_RE.sub("", head)
                if n:
                    titles[n].add(rel)
                    own.add(n)
        rel_titles[rel] = own
    return titles, rel_titles, names


def _resolve_prefix(prefix, names):
    """`「X#标题」` 的 X → 候选文件集。skill 名优先解为该 skill 的 SKILL.md。"""
    p = prefix.strip().strip("/")
    if not p:
        return set()
    if "." in p or "/" in p:                     # 文件名 / 相对路径
        hit = set(names.get(p, set()))
        if not hit:
            hit = {r for r in names.get(p.split("/")[-1], set())
                   if r.endswith("/" + p) or r == p}
        return hit
    hits = set(names.get(p, set()))              # skill 名 / 目录名
    skills = {r for r in hits if r.endswith("/SKILL.md")}
    return skills or hits


def check_f(problems):
    """F 组：`「」` 弱引用可解析（warn 级，见 `docs/SYMBOLS.md`「`「」` 弱引用」）。

    约定：外部引用写 `「<文件名|skill 名|目录名>#<标题>」`；**无 `#` = 同文件引用**。
    无法解析到外部文件名 → 按同文件引用处理，找不到即报。

    豁免（形态判据，非白名单）：
    - 代码围栏内 / 反引号内——格式骨架与符号说明示例（是在示范，不是在引用）
    - 分节名（`四、内容边界`）——同文件引用，天然成立
    - 译文对话（引号内以句末标点收尾）
    - `.py` 文件**不产出标题**，故其中无 `#` 的引用一律按外部引用报（自身无从可引）

    **只能验存在性与归属，不能验「指向正确」**——未命中可能是指称概念、仓库外对象或有意的
    短形式，故本组为警告级（`WARN_GROUPS`），不拦退出码。
    """
    _titles, rel_titles, names = _build_repo_index()
    for rel in iter_files():
        text = read_text(rel)
        if text is None:
            continue
        own = rel_titles.get(rel, set())
        fence = False
        for i, line in enumerate(text.split("\n"), 1):
            if FENCE_RE.match(line):
                fence = not fence
                continue
            if fence:
                continue
            for m in WEAKREF_RE.finditer(line):
                val = m.group(1)
                if line[:m.start()].count("`") % 2:      # 反引号内 = 示例
                    continue
                # Python 字符串字面量内 = 代码（如正则 `r"「([^」]…)」"`），非引用
                if Path(rel).suffix == ".py" and (line[:m.start()].count('"') % 2
                                                   or line[:m.start()].count("'") % 2):
                    continue
                if SECTION_NAME_RE.match(val) or DIALOG_RE.search(val):
                    continue
                if "#" in val:
                    prefix, _, head = val.partition("#")
                    cand = _resolve_prefix(prefix, names)
                    if not cand:
                        problems.append(("F", rel, i,
                                         f"外部引用前缀无法解析 → `{prefix}`"
                                         f"（应为文件名 / skill 名 / 目录名）", line.strip()[:120]))
                    elif len(cand) > 1:
                        problems.append(("F", rel, i,
                                         f"外部引用前缀歧义 → `{prefix}` 命中 {len(cand)} 个文件"
                                         f"（改带目录路径）", line.strip()[:120]))
                    elif TITLE_NORM_RE.sub("", head) not in rel_titles.get(next(iter(cand)), set()):
                        problems.append(("F", rel, i,
                                         f"外部引用标题未命中 → `{next(iter(cand))}` 无「{head}」",
                                         line.strip()[:120]))
                    continue
                n = TITLE_NORM_RE.sub("", val)
                if n in own:
                    continue                                  # 同文件引用，合规
                # 引号外已给出 owner（如 `conventions「长视频分块」`）→ 报 owner 问题，
                # 比报「标题歧义」准确（歧义往往是因为 owner 是简称、未被识别）
                if Path(rel).suffix == ".py":
                    problems.append(("F", rel, i,
                                     f"`「{val}」` 未带文件名（`.py` 自身无标题，须写"
                                     f"`「<文件名>#<标题>」`）", line.strip()[:120]))
                    continue
                outer = OUTER_OWNER_RE.search(line[:m.start()])
                if outer:
                    owner = outer.group(1) or outer.group(2)
                    if not _resolve_prefix(owner, names):
                        problems.append(("F", rel, i,
                                         f"引号外 owner `{owner}` 无法解析"
                                         f"（应为文件名 / skill 名 / 目录名）；"
                                         f"或并入引号：`「{owner}#{val}」`",
                                         line.strip()[:120]))
                        continue
                hit = _titles.get(n, set())
                tip = (f"（全仓 {len(hit)} 个文件有同名标题：{sorted(hit)[0]}）" if hit
                       else "（全仓无此标题：应改 `“”` 指称概念，或补正确的标题名）")
                problems.append(("F", rel, i,
                                 f"`「{val}」` 本文件无此标题且未带文件名{tip}",
                                 line.strip()[:120]))


def iter_files(target=None):
    """遍历扫描范围内的文本文件，返回相对项目根的 posix 路径列表。"""
    out = []
    for t in SCAN_TARGETS:
        base = PROJECT_ROOT / t
        if base.is_file():
            paths = [base]
        else:
            paths = sorted(p for g in SCAN_GLOBS for p in base.rglob(g))
        for p in paths:
            rel = str(p.relative_to(PROJECT_ROOT)).replace("\\", "/")
            if any(rel.startswith(x) for x in SCAN_EXCLUDE_PREFIXES):
                continue
            if rel in SCAN_EXCLUDE_FILES:
                continue
            if target and target not in rel:
                continue
            out.append(rel)
    return out


def read_text(rel):
    """读文档；不可解码返回 None（跳过，不误报）。"""
    try:
        return (PROJECT_ROOT / rel).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def line_of(text, pos):
    """字符偏移 → 1-based 行号。"""
    return text.count("\n", 0, pos) + 1


def line_text(text, pos):
    """字符偏移所在行原文（截断到 120 字符，供 --expand 片段）。"""
    s = text.rfind("\n", 0, pos) + 1
    e = text.find("\n", pos)
    raw = text[s:e if e != -1 else len(text)].strip()
    return raw[:120]


def slugify(heading):
    """按 GitHub 规则把标题转为锚点。

    - 先剥离内联格式（Markdown 链接取标签、去反引号与强调符）
    - 转小写；删除“非字母/数字/下划线/空白/连字符”的标点（CJK 属 \\w 故保留）
    - **逐个空白字符**替换为连字符（多空格 → 多连字符；此处**不得**折叠连续空白，
      否则 `A / B` 会得 `a-b` 而 GitHub 实为 `a--b`，造成批量误报）
    """
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    s = re.sub(r"[`*]", "", s)
    s = s.lower()
    s = re.sub(r"[^\w\s\-]", "", s, flags=re.UNICODE)
    return re.sub(r"\s", "-", s).rstrip("-")


def heading_anchor_map(text):
    """文档全部标题 → 锚点集合（重复标题按 GitHub 规则追加 -1/-2）。"""
    seen, out = {}, set()
    for m in HEADING_RE.finditer(text):
        base = slugify(m.group(2))
        if not base:
            continue
        n = seen.get(base, 0)
        seen[base] = n + 1
        out.add(base if n == 0 else f"{base}-{n}")
    return out


def check_ordered_lists(rel, text, problems):
    """有序列表序号连续性：同一列表内应严格 +1。

    列表边界靠**分节行**判定——Markdown 中两块列表面间只要有标题、引用块或段落
    就属不同列表，各自重编号；否则两个小节各自的 `1./2.` 会被误判为断序。
    嵌套序列按缩进分层独立跟跟（更深缩进不受更浅层影响）。
    """
    lines = text.split("\n")
    seq = {}    # 缩进 → (下一期望序号, 列表块号)
    block = 0   # 递增：遇到分节行即换块（同块内才要求连续）
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        m = ORDERED_ITEM_RE.match(line)
        deeper = max(seq, default=-1)
        is_break = (
            stripped.startswith(("#", ">"))
            or (not m and indent <= deeper)          # 顶格段落/无序项/表格行 → 新列表
        )
        if is_break:
            for k in [k for k in seq if k >= indent]:
                del seq[k]
            block += 1
        if not m:
            continue
        num = int(m.group(2))
        exp, b = seq.get(indent, (None, None))
        if exp is not None and b == block and num != exp:
            problems.append(("C", rel, i,
                             f"有序列表序号不连续（同层级上项应为 `{exp}.`，实为 `{num}.`）",
                             _line_raw(text, i)))
        seq[indent] = (num + 1, block)


def check_a(rel, text, problems):
    """A 组：阶段令牌合法性 + 残留子节编号 + 阶段缩写引用。"""
    if rel not in PHASE_TOKEN_EXEMPT_FILES:
        for m in PHASE_TOKEN_RE.finditer(text):
            token = m.group(1)
            if token not in PHASES:
                problems.append(("A", rel, line_of(text, m.start()), f"非法阶段令牌 `阶段{token}`",
                                 line_text(text, m.start())))
    for m in LEGACY_SUBSEC_RE.finditer(text):
        problems.append(("A", rel, line_of(text, m.start()), "残留子节编号 §1.x（应为 §2.x 或改链接）",
                         line_text(text, m.start())))
    for m in PHASE_ABBR_RE.finditer(text):
        problems.append(("A", rel, line_of(text, m.start()), "阶段缩写引用（应改为 Markdown 链接）",
                         line_text(text, m.start())))


def check_b(rel, text, problems, anchor_cache):
    """B 组：跨文件锚点可解析 + 冻结锚点存在。"""
    for m in LINK_RE.finditer(text):
        target = m.group(2)
        if target.startswith(("http://", "https://", "mailto:")) or "#" not in target:
            continue
        path_part, _, anchor = target.partition("#")
        if not anchor:
            continue
        if not path_part:
            tgt_rel = rel
        else:
            tgt = (PROJECT_ROOT / rel).parent / path_part
            try:
                tgt_rel = str(tgt.resolve().relative_to(PROJECT_ROOT)).replace("\\", "/")
            except ValueError:
                continue
        if not (PROJECT_ROOT / tgt_rel).is_file():
            problems.append(("B", rel, line_of(text, m.start()), f"链接目标不存在 `{path_part}`",
                             line_text(text, m.start())))
            continue
        if tgt_rel not in anchor_cache:
            t = read_text(tgt_rel)
            anchor_cache[tgt_rel] = heading_anchor_map(t) if t else set()
        # 链接侧也须同一套规范化：作者常写含空格/括号的原文（`#共享 cue 与…（…）`），
        # 浏览器与 GitHub 均按 slug 规则解析，故比较前统一规范化
        if slugify(anchor) not in anchor_cache[tgt_rel]:
            problems.append(("B", rel, line_of(text, m.start()),
                             f"锚点失效 → `{tgt_rel}#{anchor}` 无对应标题", line_text(text, m.start())))

    if rel in FROZEN_ANCHORS:
        if rel not in anchor_cache:
            anchor_cache[rel] = heading_anchor_map(text)
        for a in FROZEN_ANCHORS[rel]:
            if a not in anchor_cache[rel]:
                problems.append(("B", rel, 1, f"冻结锚点不存在 `#{a}`（标题已改名？同步注册表与链接）", ""))


def check_c(rel, text, problems):
    """C 组：列表序号 / 阶段标题集合 / 自称阶段数 / 合并标题 / 表格阶段行序。"""
    check_ordered_lists(rel, text, problems)
    for m in DECIMAL_ITEM_RE.finditer(text):
        problems.append(("C", rel, line_of(text, m.start()), "小数序号列表项（Markdown 列表序号不允许）",
                         line_text(text, m.start())))

    headings = [m for m in PHASE_HEADING_RE.finditer(text)]
    got = {m.group(2) for m in headings if m.group(2)}
    if rel in PHASE_HEADING_SETS:
        want = PHASE_HEADING_SETS[rel]
        missing, extra = want - got, got - want
        if missing:
            problems.append(("C", rel, 1, f"阶段标题缺失 {sorted(missing)}（注册表期望 {sorted(want)}）", ""))
        if extra:
            problems.append(("C", rel, 1, f"阶段标题多余 {sorted(extra)}（注册表期望 {sorted(want)}）", ""))

    dm = DECLARED_COUNT_RE.search(text)
    if dm:
        raw = dm.group(1)
        num = int(raw) if raw.isdigit() else CN_DIGITS.get(raw, 0)
        if len(got) != num:
            problems.append(("C", rel, line_of(text, dm.start()),
                             f"自称阶段数 `{raw}` ≠ 实际阶段标题数 {len(got)}", line_text(text, dm.start())))

    for m in MERGED_HEADING_RE.finditer(text):
        problems.append(("C", rel, line_of(text, m.start()), "合并阶段标题（拆为独立阶段标题）",
                         line_text(text, m.start())))

    _check_table_phase_order(rel, text, problems)


def _check_table_phase_order(rel, text, problems):
    """表格内阶段号须升序（同一表格块内）。"""
    order = {p: i for i, p in enumerate(PHASES)}
    rows = []
    for ln, line in enumerate(text.split("\n"), 1):
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            m = re.match(r"\|\s*阶段\s*([〇一二三四五六])", s)
            rows.append((ln, order.get(m.group(1)) if m else None))
        else:
            _report_monotonic(rel, text, rows, problems)
            rows = []
    _report_monotonic(rel, text, rows, problems)


def _report_monotonic(rel, text, rows, problems):
    """报告一段表格内非升序的阶段行。"""
    seq = [(ln, o) for ln, o in rows if o is not None]
    for (pln, po), (ln, o) in zip(seq, seq[1:]):
        if o < po:
            problems.append(("C", rel, ln, f"表格阶段行非升序（第 {pln} 行在前，第 {ln} 行在后）",
                             _line_raw(text, ln)))


def _line_raw(text, ln):
    """按行号取原文片段（截断 120 字符）。"""
    lines = text.split("\n")
    return lines[ln - 1].strip()[:120] if 0 < ln <= len(lines) else ""


def check_d(rel, text, problems):
    """D 组：残留数字步骤号。"""
    for m in LEGACY_STEP_RE.finditer(text):
        problems.append(("D", rel, line_of(text, m.start()), "残留数字步骤号（应改角色名引用）",
                         line_text(text, m.start())))


def iter_headings(text, suffix=".md"):
    """产出 (match, 标题文本)，只取**真正的 Markdown 标题**且层级为 H2–H6。

    - `.py` 文件里 `# 注释` 不是标题（Python 注释语法）→ 直接跳过
    - `.md` 文件跳过代码围栏内（``` / ~~~）的行：代码里的 `# 注释` 不是标题
      （如 SETUP.md 的 `# TechMCTranslationWorkflow/1.0 (https://…)`）
    - **排除 H1**：H1 = 文件题，不参与跨文件锚点引用（带括注无害）
    """
    if suffix != ".md":
        return
    for m in HEADING_RE.finditer(text):
        if len(m.group(1)) < 2:
            continue
        before = text[:m.start()]
        # 数围栏开启符：奇数 = 当前在围栏内
        if len(re.findall(r"^\s*(`{3,}|~{3,})", before, re.MULTILINE)) % 2:
            continue
        yield m, m.group(2)


def check_e(rel, text, problems):
    """E 组：标题不得含括注（`skill-writing-principles`「标题不携带内容组成/参数清单」）。

    括注使锚点变长：引用方写短形式（`#术语源优先级` vs 实际 `#四级查找位置与执行`）即
    **静默断链**；且引号引用标题时短形式匹配失败，会被误判为指称概念。
    """
    for m, head in iter_headings(text, Path(rel).suffix):
        if TITLE_ANY_PAREN_RE.search(head):
            problems.append(("E", rel, line_of(text, m.start()),
                             f"标题含括注（改用冒号/连接符或移入正文）：'{head}'", head))


def check_p(rel, text, problems):
    """P 组：① 引用块短语（`docs/SYMBOLS.md`「`>` 引用块」）；② 标题写死数量词。

    `>` 的正当用途仅 3 种：⚠️ 警示块、外部内容引用、文档导语（H1 后一次、须完整句）。
    禁止标题后紧跟短语型 `>`（= 标题逃生舱）与正文中用 `>` 承载强调段。

    判据（客观、零硬编码）：**完整句必有句末标点，短语必无**。
    - P1：`##`–`######` 标题后首个非空行是 `>`，且整个 blockquote 块无句末标点、非 ⚠️
    - P2：正文中 `>` 块首行无句末标点、非 ⚠️、无出处
    豁免：H1 后导语、`> ⚠️`、代码围栏内（格式骨架示例）。
    """
    if Path(rel).suffix != ".md" or rel in BQ_EXEMPT_FILES:
        return
    lines = text.split("\n")
    head_lv, head_txt = 0, ""
    gap = False          # 标题与本块之间是否已有内容
    prev_bq = False      # 上一行也是 `>`（= 本块续行）
    fence = False
    for i, line in enumerate(lines):
        if FENCE_RE.match(line):
            fence = not fence
            prev_bq = False
            continue
        if fence:
            continue
        hm = HEADING_RE.match(line)
        if hm:
            head_lv, head_txt, gap, prev_bq = len(hm.group(1)), hm.group(2), False, False
            continue
        bm = BLOCKQ_RE.match(line)
        if not bm:
            if line.strip():
                gap = True
            prev_bq = False
            continue
        if prev_bq:                 # 续行归上一块，不独立判定
            prev_bq = True
            continue
        prev_bq = True
        body = bm.group(1).strip()
        # 收集整块（含续行）：块级判定——块内有句末标点 = 完整说明句
        blk = [body]
        for k in range(i + 1, len(lines)):
            nxt = BLOCKQ_RE.match(lines[k])
            if not nxt:
                break
            blk.append(nxt.group(1).strip())
        whole = " ".join(x for x in blk if x)
        # 豁免：空、⚠️ 警示块、多行说明块（≥2 非空行 = 说明而非短语）、
        # 块内有句末标点（完整句）、纯英文（英文原句示例/原文引用）
        if (not body or WARN_BQ_RE.match(body)
                or len([x for x in blk if x]) >= 2
                or BLOCKQ_SENT_RE.search(whole)
                or not CJK_RE.search(whole)):
            continue
        if head_lv >= 2 and not gap:
            problems.append(("P", rel, i + 1,
                             f"标题下短语型 `>`（删／并回标题／扩成正文首句）：'{body[:40]}'", line))
        else:
            problems.append(("P", rel, i + 1,
                             f"正文中短语型 `>`（改写成正文）：'{body[:40]}'", line))

    # ② 标题写死数量词
    for m, head in iter_headings(text, Path(rel).suffix):
        cm = TITLE_COUNT_RE.search(head)
        if cm:
            problems.append(("P", rel, line_of(text, m.start()),
                             f"标题含数量词 `{cm.group(0)}`（数量是可变量，改用稳定名词）", head))


def run_checks(groups, target=None):
    """跑指定检查组，返回 (problems, stat)。

    F 组需要全仓索引（标题 → 文件集），故在建 index 后单独跑（不进逐文件循环）。
    """
    problems, anchor_cache, stat = [], {}, {}
    for rel in iter_files(target):
        text = read_text(rel)
        if text is None:
            continue
        for g, fn in (("A", check_a), ("C", check_c), ("D", check_d), ("E", check_e), ("P", check_p)):
            if g in groups:
                fn(rel, text, problems)
        if "B" in groups:
            check_b(rel, text, problems, anchor_cache)
    if "F" in groups:
        check_f(problems)
    for p in problems:
        stat[p[0]] = stat.get(p[0], 0) + 1
    problems.sort(key=lambda p: (p[0], p[1], p[2]))
    return problems, stat


def print_list():
    """列注册表（供人工核对编号空间与冻结锚点）。"""
    print("阶段空间（唯一权威，禁其它编号形态）：")
    for p, (role, flows) in PHASES.items():
        print(f"  阶段{p}  {role:12s} ← {', '.join(flows)}")
    print("\n阶段标题集合（各文件应出现的阶段号）：")
    for rel, s in sorted(PHASE_HEADING_SETS.items()):
        print(f"  {rel:58s} {''.join(sorted(s))}")
    print(f"\n冻结锚点（{len(FROZEN_ANCHORS)} 文件）：")
    for rel, anchors in sorted(FROZEN_ANCHORS.items()):
        print(f"  {rel}  ({len(anchors)} 个)")
    print(f"\n检查分组：{', '.join(f'{k}={v}' for k, v in CHECK_GROUPS.items())}")
    print(f"扫描范围：{', '.join(SCAN_TARGETS)}（{', '.join(SCAN_GLOBS)}；"
          f"排除 {', '.join(SCAN_EXCLUDE_PREFIXES)}）")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="阶段编号与引用一致性校验（零副本注册表）")
    ap.add_argument("--list", action="store_true", help="只列注册表，不实际检查")
    ap.add_argument("--group", action="append", choices=sorted(CHECK_GROUPS),
                    help="只跑指定检查组（可重复；默认全部）")
    ap.add_argument("--file", default=None, help="只检查相对路径含该子串的文件")
    ap.add_argument("--expand", action="store_true", help="展开每处问题的行号与片段")
    ap.add_argument("--out", default=None, help="把完整报告写入该文件（UTF-8，适合问题多时）")
    args = ap.parse_args()

    if args.list:
        print_list()
        return 0

    groups = set(args.group) if args.group else set(CHECK_GROUPS)
    problems, stat = run_checks(groups, args.file)

    lines = []
    hard = [p for p in problems if p[0] not in WARN_GROUPS]
    warn = [p for p in problems if p[0] in WARN_GROUPS]
    if not problems:
        lines.append(f"✅ 阶段编号校验通过（检查组 {'/'.join(sorted(groups))}；"
                     f"令牌空间 = {'/'.join(PHASES)}；锚点与结构均一致）")
    else:
        head = (f"发现 {len(hard)} 处违规" if hard else "✅ 硬性检查通过") \
            + (f" + {len(warn)} 处警告（仅报不拦）" if warn else "")
        lines.append(head + "：")
        for g in sorted(groups):
            n = stat.get(g, 0)
            if n:
                tag = "⚠️" if g in WARN_GROUPS else "❌"
                lines.append(f"  {tag} [{g}] {CHECK_GROUPS[g]}：{n} 处")
        if args.expand:
            lines.append("")
            for g, rel, ln, desc, snippet in problems:
                lines.append(f"  [{g}] {rel}:{ln} {desc}")
                if snippet:
                    lines.append(f"        {snippet}")
        else:
            lines.append("\n提示：加 --expand 看每处的文件:行号 + 片段；加 --list 看注册表。")

    report = "\n".join(lines)
    if args.out:
        (PROJECT_ROOT / args.out).write_text(report + "\n", encoding="utf-8")
        print(f"报告已写入 {args.out}（{len(problems)} 处违规）")
    else:
        print(report)
    # 警告级组（`WARN_GROUPS`）只报不拦：未命中 ≠ 违规（需借上下文裁定）
    hard = [p for p in problems if p[0] not in WARN_GROUPS]
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
