# -*- coding: utf-8 -*-
"""srt_reflow 基础 I/O 与语言无关工具：时间解析/格式化/归一化/01 解析/全文拼接/视觉宽度。

多语言扩展（短期已落地）：norm 按拉丁语系归一化（NFKD 去重音 é→e + 小写 + 去非字母数字撇号，
覆盖 en/fr/de/es 等）；text_width 按 Unicode 块通用（全角=1.0 / 拉丁=1.5 / 数字=1.0 / 空格=0.5，
含假名/谚文/扩展表意）。中期/长期扩展见 srt_reflow.py 顶部 docstring「多语言扩展」。
"""
import re
import unicodedata
from pathlib import Path

TS_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})")
BRACKET_RE = re.compile(r"\[[^\]]*\]")
LATIN_KEEP_RE = re.compile(r"[^a-z0-9']")
# 全角块（宽 1.0）：CJK 统一表意 + 扩展 A/B + 假名 + 谚文 + 兼容表意 + 全角标点
FULLWIDTH_RE = re.compile(r"[\u2e80-\u9fff\uac00-\ud7af\u3040-\u30ff\uf900-\ufaff\uff00-\uffef]")
LATIN_RE = re.compile(r"[A-Za-z]")
DIGIT_RE = re.compile(r"[0-9]")


def parse_time(s):
    m = TS_RE.match(s.strip())
    if not m:
        raise ValueError(f"bad time: {s}")
    h, mm, ss, ms = (int(x) for x in m.groups())
    return h * 3600000 + mm * 60000 + ss * 1000 + ms


def fmt(ms):
    ms = max(0, int(ms))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


def norm(s):
    """归一化（拉丁语系源语言）：NFKD 分解去重音（é→e）→ 小写 → 去非字母数字撇号。

    多语言扩展：本函数按「拉丁语系」归一化，覆盖 en/fr/de/es/pt 等拉丁源语言；将来支持
    CJK/西里尔/阿拉伯等非拉丁源语言时，需按 Unicode 脚本分类分流（如 CJK 保留对应码块）。
    """
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return LATIN_KEEP_RE.sub("", s.lower()) 


def parse_srt(path):
    """01 解析：返回 [{'idx','start','end','text'}]，剔除 [Music] 等方括号标记 cue"""
    text = Path(path).read_text(encoding="utf-8-sig")
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) < 2 or not re.fullmatch(r"\d+", lines[0]):
            continue
        m = re.match(
            r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})", lines[1]
        )
        if not m:
            continue
        body = " ".join(lines[2:])
        body = BRACKET_RE.sub("", body).strip()
        if not body:
            continue  # [Music] 等非语音 cue 剔除
        cues.append(
            {"idx": int(lines[0]), "start": parse_time(m.group(1)), "end": parse_time(m.group(2)), "text": body}
        )
    return cues


def build_full(cues):
    """拼接全文（归一化）+ char→cue_index 映射 + 每 cue 在 full 中的起始偏移"""
    full_chars = []
    mapping = []
    cue_offsets = []  # cue 索引 -> full 中字符偏移
    off = 0
    for ci, c in enumerate(cues):
        n = norm(c["text"])
        cue_offsets.append(off)
        full_chars.append(n)
        mapping.extend([ci] * len(n))
        off += len(n)
    return "".join(full_chars), mapping, cue_offsets


def text_width(s):
    """视觉宽度（保留原权重语义）：全角=1.0 / 拉丁=1.5 / 数字=1.0 / 空格=0.5。

    已按 Unicode 块通用化（含假名/谚文/扩展表意），不再只认 CJK——将来加书写系统
    只需扩展 FULLWIDTH_RE 等判定，权重不改。被 check-r03 / reflow 行宽告警复用：
    改权重会改变现有 en-zh 的 20 阈值语义，需谨慎并同步各引用处。
    """
    w = 0.0
    for ch in s:
        if FULLWIDTH_RE.match(ch):
            w += 1.0
        elif LATIN_RE.match(ch):
            w += 1.5
        elif DIGIT_RE.match(ch):
            w += 1.0
        elif ch == " ":
            w += 0.5
        else:
            w += 1.0
    return w
