# -*- coding: utf-8 -*-
"""srt_reflow 系列脚本的公共工具（2026-08-15 去重提取）：

- 折行：wrap_text（纯函数）/ auto_wrap_file（就地重排文件）
- 时间：parse_time / fmt
- 非语音标记：is_pure_marker（[Music]/[Applause] 等方括号标记动态识别）
- 块：collect_chunk_files（chunk_<k>.txt 收集）/ parse_owned_cue_range（OWNED cue 区间）

归属约定：多个独立脚本 + srt_reflow_core 包共用的**通用函数**放本模块；
reflow 特有逻辑（锚定/分配/校验等）留在 srt_reflow_core/。

导入方式：
- 独立脚本（`python scripts/srt_xxx.py` 运行，sys.path[0]=scripts/）：`from srt_reflow_common import ...`
- srt_reflow_core 包内：`from ..srt_reflow_common import ...`
"""
import re

MAX_LINE = 1000      # 单行字符上限（与折行宽度一致；超限 read_file 不可读，就地折行重排）

BRACKET_RE = re.compile(r"\[[^\]]*\]")   # 方括号非语音标记（[Music]/[Applause] 等）
TS_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})")

# r01 跨块句标记【承接句】/【延伸句】（片边界跨块句补全，见 reflow-redstone task-punctuate 规则 4）
# 标记内容 = 邻块补全的完整句；剥离到句末标点 / 下一个【 / 结尾。校验剥离用：标记内容不计入词序列与断句判定
STITCH_RE = re.compile(r"【(?:承接句|延伸句)】.*?(?:[.?!。]|(?=【)|$)")
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


# ---- 视觉宽度（通用工具；2026-08-20 自 srt_reflow_core/io.py 上移，供独立脚本与 reflow 核心复用）----
# 全角块（宽 1.0）：CJK 统一表意 + 扩展 A/B + 假名 + 谚文 + 兼容表意 + 全角标点
FULLWIDTH_RE = re.compile(r"[\u2e80-\u9fff\uac00-\ud7af\u3040-\u30ff\uf900-\ufaff\uff00-\uffef]")
LATIN_RE = re.compile(r"[A-Za-z]")
DIGIT_RE = re.compile(r"[0-9]")


def text_width(s):
    """视觉宽度（半角/全角标准，2026-08-11 修正：拉丁/数字由 1.5/1.0 改为 0.5，此前虚高把带英文行推成长句）：
    全角=1.0 / 拉丁=0.5 / 数字=0.5 / 空格=0.5。

    已按 Unicode 块通用化（含假名/谚文/扩展表意），不再只认 CJK——将来加书写系统
    只需扩展 FULLWIDTH_RE 等判定，权重不改。被 check-r03 / reflow 行宽告警 / presplit 机械化断句复用：
    权重按真实显示（拉丁/数字为半角，≈0.5 汉字），改权重会改变阈值语义，需同步各引用处。
    """
    w = 0.0
    for ch in s:
        if FULLWIDTH_RE.match(ch):
            w += 1.0
        elif LATIN_RE.match(ch):
            w += 0.5
        elif DIGIT_RE.match(ch):
            w += 0.5
        elif ch == " ":
            w += 0.5
        else:
            w += 1.0
    return w
