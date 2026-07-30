"""
Mojang 官方翻译词汇表获取工具

从 Mojang 官方 API 下载最新版本的 en_us 和 zh_cn 语言文件，
按类别输出为 CSV。

扩展语言：编辑 config.py 中的 LANG_LIST / LANG_ORDER，
添加目标语言代码（如 "ja_jp"、"ko_kr"），重新运行即可。
CSV 列顺序与 LANG_ORDER 一致，第一列为 en_us，后续为各目标语言。

用法：
    # CLI
    python main.py [--check]

    # 编程调用
    from scripts.mojang_glossary.main import fetch_glossary, check_version
"""

import argparse
import logging
import sys
from pathlib import Path

from . import config
from .modules.procedures import (
    get_local_version,
    process_manifest,
    process_version_json,
    process_asset_index,
    process_game_jar,
    process_lang_resource,
    combine_glossary,
    write_glossary,
)


def parse_argv() -> argparse.Namespace:
    """命令行参数解析（预留扩展：--version 指定版本、--lang 指定语言等）"""
    parser = argparse.ArgumentParser(
        description="从 Mojang 官方 API 下载最新翻译词汇表"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="仅检查是否有新版本（退出码 1 = 有新版本）",
    )
    return parser.parse_args()


def fetch_glossary() -> bool:
    """下载并生成 Mojang 官方词汇表。返回 True 表示已更新，False 表示已是最新。"""
    version_info = process_manifest()
    local_version = get_local_version()
    logging.info(f"Latest version: {version_info['id']}, local: {local_version}")

    if local_version == version_info["id"]:
        logging.info("Already up to date.")
        return False

    asset_index_info, server_jar_info = process_version_json(version_info)
    resource_info_dict = process_asset_index(asset_index_info)
    _ = process_game_jar(version_info["id"], server_jar_info)
    process_lang_resource(resource_info_dict)
    glossary = combine_glossary()
    write_glossary(glossary, version_info["id"])
    logging.info(f"Glossary updated to {version_info['id']}")
    return True


def check_version() -> str | None:
    """检查是否有新版本。返回新版本号，若已是最新则返回 None。"""
    version_info = process_manifest()
    local_version = get_local_version()
    if local_version == version_info["id"]:
        return None
    return version_info["id"]


def main():
    args = parse_argv()

    if args.check:
        new_version = check_version()
        if new_version:
            print(f"New version available: {new_version}")
            sys.exit(1)
        else:
            print("Already up to date.")
            sys.exit(0)
    else:
        updated = fetch_glossary()
        if updated:
            version = Path(config.GLOSSARY_VERSION_PATH).read_text().strip()
            print(f"Glossary updated to {version}")
        else:
            print("Already up to date.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # add options later
    main()
