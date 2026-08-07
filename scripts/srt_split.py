# -*- coding: utf-8 -*-
"""
将"序号 / 时间轴 / 英文 / 中文"等结构的双语/多语 .srt 字幕
按字段拆分成多个单语文件。

行顺序由开头的 FIELDS 常量决定：字幕块第 i 行对应 FIELDS[i]。
'index' 与 'time' 是公共字段，会写入每一份输出；
其余字段名（如 'en'、'zh'）直接用作输出文件后缀，
生成「前缀.<字段名>.srt」。以后要加新语言，只需在 FIELDS 里
加名字即可，例如加上 'jp' 就会自动生成「前缀.jp.srt」。

用法：
    python srt_split.py 输入.srt [选项]

选项：
    -o, --output-prefix 前缀   输出文件前缀（默认取输入文件名主体）
    -d, --output-dir 目录      输出目录（默认与输入文件同目录）
    --out 字段=路径             显式指定任意字段的输出文件（可多次使用）

示例：
    python srt_split.py video.srt
        # -> video.en.srt , video.zh.srt（与输入同目录）

    python srt_split.py video.srt -o sub -d out
        # -> out/sub.en.srt , out/sub.zh.srt

    python srt_split.py video.srt --out en=my_en.srt --out zh=my_zh.srt
        # -> 使用显式指定的输出文件
"""
import argparse
import sys
from pathlib import Path

# ============================================================
# 字段顺序配置：字幕块中第 i 行对应 FIELDS[i] 的内容。
#   'index'、'time' 为公共字段，会写入每一份输出；
#   其余字段名直接用作输出文件后缀（前缀.<字段名>.srt）。
# 以后要加新语言，只需在这里加名字，例如加上 'jp'。
# ============================================================
FIELDS = ["index", "time", "en", "zh"]
COMMON_FIELDS = ("index", "time")


def split_srt(
    src: Path, out_dir: Path, prefix: str, overrides: dict[str, str]
) -> dict[str, Path]:
    """按 FIELDS 配置把多语 srt 拆成多个单语文件，返回 {字段: 输出路径}。"""
    # 需要生成的语言字段（不含公共字段）
    lang_fields = [f for f in FIELDS if f not in COMMON_FIELDS]

    raw = src.read_text(encoding="utf-8")
    # 以空行分隔成字幕块
    blocks = [b for b in raw.split("\n\n") if b.strip()]

    parts = {field: [] for field in lang_fields}
    parsed = 0
    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln.strip()]
        # 行数需与 FIELDS 配置一致
        if len(lines) != len(FIELDS):
            print(f"  跳过异常块（{len(lines)} 行，期望 {len(FIELDS)} 行）: {lines[0][:50]!r}")
            continue
        data = dict(zip(FIELDS, lines))  # 字段名 -> 该行内容
        parsed += 1
        for field in lang_fields:
            parts[field].append(f"{data['index']}\n{data['time']}\n{data[field]}\n")

    out_paths: dict[str, Path] = {}
    for field, field_blocks in parts.items():
        override = overrides.get(field)
        out = Path(override) if override else out_dir / f"{prefix}.{field}.srt"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(field_blocks), encoding="utf-8")
        out_paths[field] = out
        print(f"  {src.name}: 字段 '{field}' 解析 {parsed} 条 -> {out}")
    return out_paths


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="将多语 .srt 字幕按字段拆分为多个单语文件。")
    parser.add_argument("input", help="输入的双语/多语 .srt 文件路径")
    parser.add_argument(
        "-o", "--output-prefix",
        help="输出文件前缀（默认取输入文件名主体）",
    )
    parser.add_argument(
        "-d", "--output-dir",
        help="输出目录（默认与输入文件同目录）",
    )
    parser.add_argument(
        "--out", action="append", default=[], metavar="FIELD=PATH",
        help="显式指定某字段的输出路径（可多次使用），如 --out jp=sub_jp.srt",
    )
    args = parser.parse_args(argv)

    src = Path(args.input)
    if not src.exists():
        print(f"  未找到输入文件: {src}", file=sys.stderr)
        return 1

    # 收集显式输出路径覆盖：字段名 -> 路径
    overrides: dict[str, str] = {}
    for item in args.out:
        if "=" not in item:
            print(f"  --out 格式错误（应为 FIELD=PATH）: {item!r}", file=sys.stderr)
            return 1
        field, path = item.split("=", 1)
        overrides[field] = path

    prefix = args.output_prefix or src.stem
    out_dir = Path(args.output_dir) if args.output_dir else src.parent

    split_srt(src, out_dir, prefix, overrides)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
