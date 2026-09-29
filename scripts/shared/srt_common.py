# -*- coding: utf-8 -*-
"""srt_reflow 系列脚本的公共工具（2026-08-15 去重提取）：

- 折行：wrap_text（纯函数）/ auto_wrap_file（就地重排文件）
- 时间：parse_time / fmt
- 非语音标记：is_pure_marker（[Music]/[Applause] 等方括号标记动态识别）
- 块：collect_chunk_files（chunk_<k>.txt 收集）/ parse_owned_cue_range（OWNED cue 区间）

归属约定：多个独立工具 + srt_reflow_core 包共用的**通用函数**与**跨模块阈值常量**放本模块；
reflow 特有逻辑（锚定/分配/校验等）留在 srt_reflow_core/。

单一引用参数（仅本模块定义、无副本，已便于维护）不迁移；若需被他处复用，连同定义一并迁到本模块。

跨模块阈值常量按**语义分组**归并（非按数值）：同值不同义者各自独立定义。

导入方式：
- 独立工具（`python scripts/srt_xxx.py` 运行，sys.path[0]=scripts/）：`from shared.srt_common import ...`
- `srt_reflow_core` 包内：`from shared.srt_common import ...`（绝对导入——包存在顶层/包内两种导入路径，
  相对导入 `..shared` 在顶层路径下会越界）
"""
import re

MAX_LINE = 1000      # 单行字符上限（与折行宽度一致；超限 read_file 不可读，就地折行重排）

# ---- 时间与阅读速度阈值（单一事实源；改这里即全链生效）----
# 为什么在此：这些值被 reflow 主流程 / 回填 / 告警 / 分块 / 空隙探测多处消费，
# 分散定义时各副本易脱节——集中于此消除该风险。
# 归并原则：**按语义分组，不按数值**——同值不同义者各自独立定义（如 READING_MIN_GAP_MS 与 ULTRA_SHORT_MS 同为 300）。
# 微调须知：改值后跑 `python scripts/check_param_sync.py` 校验文档同步（零副本：期望值运行时读取本模块）。
LONG_GAP_MS = 5000            # 长停顿阈值：相邻语音 cue 间隔 > 此值 = 空隙点
#   权威说明：`.github/skills/redstone-conventions/SKILL.md`「空隙点」节（5s/10s 语义与用途）
JUMP_GAP_MS = 10000           # 剪辑跳转阈值：相邻单元边界间隔 > 此值 = 剪辑跳转
#   权威说明：同上
MIN_FRAG_MS = 1000            # 长句碎片阈值：单元时长 < 此值 = 碎片，须回报 Agent 裁决
#   权威说明：`.github/skills/segment-subtitles/SKILL.md`「阅读时长」节（单条时长通常 ≥1s）
SNAP_MS = 300                 # 切分点吸附真实 cue 边界的最大距离（无则 100ms 取整预测点）
#   权威说明：`.github/skills/reflow-redstone/semantic-reflow.md`（吸附与 100ms 预测点）
READING_MISMATCH_RATIO = 0.7  # 分配时长 < 阅读所需 × 此值 → 触发阅读感知插值
#   权威说明：`.github/skills/segment-subtitles/SKILL.md`「阅读时长」节（显著失配判据）
READING_MIN_GAP_MS = 300      # 显著阅读失配最小毫秒数（避免轻微差异过度触发插值）
CJK_SPEED = 5.0               # 中文阅读速度（字/秒）；0 = 禁用阅读校验
#   权威说明：`.github/skills/segment-subtitles/SKILL.md`「阅读时长（5 字/秒）」节
ULTRA_SHORT_MS = 300          # 极短单元告警阈值（回填告警分类用，与上者同值不同义）
LONG_UNIT_MS = 15000          # 超长单元基准阈值：实际阈值 = max(此值, 2 × 时长中位）

BRACKET_RE = re.compile(r"\[[^\]]*\]")   # 方括号非语音标记（[Music]/[Applause] 等）
TS_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})")

# r01 跨块句标记【承接句】/【延伸句】（片边界跨块句补全，见 reflow-redstone task-punctuate 规则 4）
# 剥离到句末标点 / 行尾 / 结尾。DOTALL 跨显示行（1000 字符折行会把补全拆到多行）。
# 分型：延伸句补的是句子后半（必含句号）→ 只匹配句号；承接句补句子前半（可无句号）→ 句号或行尾。
# 校验剥离用：标记内容不计入词序列与断句判定。
STITCH_RE = re.compile(r"【延伸句】.*?[.?!。]|【承接句】.*?(?:[.?!。]|(?=\n)|$)", re.DOTALL)
# 预分句用：只剔除标记前缀本身、保留补全内容（内容为本块真实句子，需参与 E/Z 锚定）——
# 与 STITCH_RE 连内容剥离（校验视角）不同；见 strip_stitch_prefix docstring（uVOFckoMdIU S94 事故修复）
STITCH_PREFIX_RE = re.compile(r"【(?:承接句|延伸句)】")


def parse_time(s):
    """SRT 时间码 → 毫秒（严格匹配 HH:MM:SS,mmm）。"""
    m = TS_RE.match(s.strip())
    if not m:
        raise ValueError(f"bad time: {s}")
    h, mm, ss, ms = (int(x) for x in m.groups())
    return h * 3600000 + mm * 60000 + ss * 1000 + ms


def fmt(ms):
    """毫秒 → SRT 时间码（HH:MM:SS,mmm）。"""
    ms = max(0, int(ms))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


def is_pure_marker(text):
    """纯非语音标记 cue：去掉全部 [xxx] 后无可见字符（[Music]/[Applause] 等）——
    动态识别、不硬编码枚举；此类 cue 两侧不参与空隙判定，仅保留时间骨架"""
    return BRACKET_RE.sub("", text).strip() == ""


def strip_stitch_marks(text):
    """剔除 r01 跨块句标记【承接句】/【延伸句】及其补全内容（校验剥离用）。

    跨块句 = OWNED 首/末句被片边界切断，补标点 subagent 用 CONTEXT 补全并标记（task-punctuate 规则 4）；
    标记内容 = 邻块补全部分，不属于本块 OWNED cue——措辞/断句校验前先剥离，避免邻块词污染词序列与定位。
    本块 OWNED 的跨块句部分若被包在标记内，剥离后缺失——由调用方（check_words）以「有标记 + 子集」放行。"""
    return STITCH_RE.sub("", text)


def strip_stitch_prefix(text):
    """只剔除 r01 跨块句标记前缀【承接句】/【延伸句】，保留补全内容（预分句用）。

    与 strip_stitch_marks（连内容剥离，校验用）不同：预分句的 EN/ZH 两侧都需保留标记内容参与 E/Z 锚定，
    只去掉前缀标记本身——否则 EN 侧整句被剥导致锚点缺失（r03_normalized_1 无 E 号）、ZH 侧带标记，
    两侧不对称（uVOFckoMdIU chunk_002 S94 事故：分句 agent 遇「延伸句无 E 锚点」只能写 CARRY）。
    标记彻底消除由 check-r03 格式标记残留校验兜底拦截。"""
    return STITCH_PREFIX_RE.sub("", text)


def wrap_text(text, width=1000):
    """整段文本就近折行（显示性换行，非语义分行——校验按整段解析不受影响）。

    每 ~width 字符折行：英文就近空格折（不拆词）；中文/无空格处按字符硬切。
    输入/输出均为「组间空行分隔」的整段文本；组内折行不改变语义，read_file 可按行读取超长产物。
    结构化产物（如 r03_plan.md 的 `- EN:/ZH:` 单行值）**禁用**折行（脚本按行解析）。"""
    out_blocks = []
    for block in text.split("\n\n"):
        # 组内归一为连续文本（英文空格连接 / 中文空连接），再按 width 折行
        if re.search(r"[A-Za-z]", block):
            seg = re.sub(r"\s+", " ", " ".join(block.split("\n"))).strip()
        else:
            seg = "".join(block.split("\n")).strip()
        lines, s = [], seg
        while len(s) > width:
            cut = s.rfind(" ", 0, width + 1)   # 英文就近空格折（不拆词）
            if cut <= 0:
                cut = width                      # 无空格 → 按字符硬切（中文等）
            lines.append(s[:cut].rstrip())
            s = s[cut:].lstrip()
        if s:
            lines.append(s)
        out_blocks.append("\n".join(lines))
    return "\n\n".join(out_blocks)


def auto_wrap_file(path, max_len=MAX_LINE):
    """就地折行重排：超长单行（>max_len 字符）按 ~max_len 就近折行（英文词边界不拆词、中文按字符）。
    折行是显示性换行（非语义分行），校验按整段解析不受影响；返回是否重排。"""
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    if not any(len(ln) > max_len for ln in raw.split("\n")):
        return False
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(wrap_text(raw, max_len) + "\n")
    return True


def collect_chunk_files(chunks_dir):
    r"""收集块文件（chunk_(\d{3}).txt）→ {序号: 绝对路径}（按序号排序）。"""
    import os
    out = {}
    for fn in sorted(os.listdir(chunks_dir)):
        m = re.fullmatch(r"chunk_(\d{3})\.txt", fn)
        if m:
            out[int(m.group(1))] = os.path.join(chunks_dir, fn)
    return out


def parse_owned_cue_range(chunk_path):
    """从 chunks 块文件解析 OWNED 的 cue 区间 → (min_c, max_c)；无 OWNED cue 返回 None。"""
    cids = []
    in_owned = False
    for ln in open(chunk_path, encoding="utf-8").read().split("\n"):
        if ln.startswith("## "):
            in_owned = ln.startswith("## OWNED")
            continue
        if in_owned:
            m = re.match(r"c(\d+)\t", ln)
            if m:
                cids.append(int(m.group(1)))
    return (min(cids), max(cids)) if cids else None


# ---- 告警定位（统一约定：问题项带「文件:行号 + 行上下文」；通过项只计数） ----
# 定位 = 块级产物 chunk_<k>.txt:行<l>（行号 = 该块文件内 1-based 物理行）/ 空隙点 c<ia>→c<ib>
#        / r03 整句（## S<n> 所在行）。上下文 = 该行截断片段（~55 字符），供 Agent 直接核对编辑。


def offset_to_line(text, offset):
    """文本内偏移 → (1-based 行号, 该行起始偏移, 该行文本)；offset 越界时夹取到有效范围。"""
    if not text:
        return 1, 0, ""
    offset = max(0, min(offset, len(text)))
    lines = text.split("\n")
    line_no = 1
    start = 0
    for i, ln in enumerate(lines):
        if start <= offset <= start + len(ln):
            line_no = i + 1
            return line_no, start, ln
        start += len(ln) + 1  # +1 换行符
    return len(lines), start, lines[-1]


def ctx_snippet(text, offset, radius=55):
    """偏移 → 行号 + 该行上下文片段（'…前置<命中>后置…'，命中处用 <> 标记）。
    供告警直接核对：Agent 按返回行号 read_file 定位编辑，无需全文件扫。"""
    line_no, start, ln = offset_to_line(text, offset)
    rel = offset - start
    a = max(0, rel - radius)
    b = min(len(ln), rel + radius)
    frag = ln[a:b]
    if a > 0:
        frag = "…" + frag
    if b < len(ln):
        frag = frag + "…"
    return line_no, frag


def loc_of(path):
    """告警位置前缀：短文件名（basename）。"""
    import os
    return os.path.basename(path)


# ---- 视觉宽度（通用工具；供独立脚本与 reflow 核心复用）----
# ---- 行宽阈值（单一事实源；改这里即全链生效）----
# 为什么在此：生成侧（presplit 机械化断句 / backfill 拆子段）与校验侧（check-r03 / check-width / alerts）
# 必须同一口径——否则生成侧与校验侧算法脱节会出**假 ERROR**（生成侧放行、校验侧报错）。
# 语义：目标区间 [SOFT_MIN, SOFT_MAX]，超 SOFT_MAX = 软告警、超 HARD_MAX = 硬违规（必切/打回）。
# 仅作**默认值**——各脚本仍可 CLI 覆盖（`--soft-max` / `--hard` / `--warn`），用于单视频调试。
SOFT_MIN = 15.0
SOFT_MAX = 22.0
HARD_MAX = 27.0
MIN_UNIT = 5.0        # 最小单元宽度（≈1s 阅读时长 @5字/秒，防碎片）

# 全角块（宽 1.0）：CJK 统一表意 + 扩展 A/B + 假名 + 谚文 + 兼容表意 + 全角标点
FULLWIDTH_RE = re.compile(r"[\u2e80-\u9fff\uac00-\ud7af\u3040-\u30ff\uf900-\ufaff\uff00-\uffef]")
LATIN_RE = re.compile(r"[A-Za-z]")
DIGIT_RE = re.compile(r"[0-9]")


def text_width(s):
    """视觉宽度：全角=1.0 / 拉丁=0.4 / 数字=0.5 / 空格=0.4（用户实测播放器口径）。

    系数含义：比例字体下拉丁与空格平均宽度约为全角的 0.4；数字取 0.5（多为等宽数字）。
    每次改动都会平移各脚本阈值语义——改系数须同步全部阈值消费方（跑 `check_param_sync.py`）。

    已按 Unicode 块通用化（含假名/谚文/扩展表意），不再只认 CJK——将来加书写系统
    只需扩展 FULLWIDTH_RE 等判定，权重不改。被 check-r03 / reflow 行宽告警 / presplit 机械化断句复用。
    """
    w = 0.0
    for ch in s:
        if FULLWIDTH_RE.match(ch):
            w += 1.0
        elif LATIN_RE.match(ch):
            w += 0.4
        elif DIGIT_RE.match(ch):
            w += 0.5
        elif ch == " ":
            w += 0.4
        else:
            w += 1.0
    return w
