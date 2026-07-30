import os as _os
import io as _io
import typing as _ty
import logging as _log

from .download import download_file, match_file_SHA1, calc_SHA1_chunks
from . import asset_resolver as _resolver

from .. import config
from .types import VersionInfo, AssetIndexInfo, GameJarInfo, LangResourceInfo


def process_manifest() -> VersionInfo:
    import requests

    _log.debug(f"Checking manifest...")
    response = requests.get(config.URL_MANIFEST_V2, timeout=10)
    response.raise_for_status()
    return _resolver.resolve_version_manifest_v2(response.json())


def get_local_version() -> str:
    if _os.path.exists(config.GLOSSARY_VERSION_PATH) and _os.path.isfile(
        config.GLOSSARY_VERSION_PATH
    ): 
        with open(config.GLOSSARY_VERSION_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    else:
        _log.debug("No local version record found.")
        return "0.0.0"


def process_version_json(
    version_info: VersionInfo,
) -> tuple[AssetIndexInfo, GameJarInfo]:
    v_url, v_id, v_sha1 = version_info["url"], version_info["id"], version_info["sha1"]
    v_path = config.CACHE_VERSION_DIR / (v_id + ".json")
    if not v_path.exists() or (
        v_path.is_file() and not match_file_SHA1(v_path, v_sha1)
    ):
        _log.debug(f"Requesting {v_url}")
        download_file(v_url, v_path, v_sha1)
    return _resolver.resolve_version(v_path)


def process_asset_index(index_info: AssetIndexInfo) -> _ty.Dict[str, LangResourceInfo]:
    i_url, i_id, i_sha1 = index_info["url"], index_info["id"], index_info["sha1"]
    i_path = config.CACHE_ASSET_INDEX_DIR / (i_id + ".json")
    if not i_path.exists() or (
        i_path.is_file() and not match_file_SHA1(i_path, i_sha1)
    ):
        _log.debug(f"Requesting {i_url}")
        download_file(i_url, i_path, i_sha1)
    return _resolver.resolve_asset_index(i_path)


def process_game_jar(version_name: str, jar_info: GameJarInfo) -> str:
    jar_url, jar_sha1 = jar_info["url"], jar_info["sha1"]
    jar_path = config.CACHE_VERSION_DIR / (version_name + ".jar")

    if not jar_path.exists() or (
        jar_path.is_file() and not match_file_SHA1(jar_path, jar_sha1)
    ):
        _log.debug(f"Requesting {jar_url}")
        download_file(jar_url, jar_path, jar_sha1)

    return _resolver.resolve_game_jar(
        jar_path, config.JAR_LANG_LOCATION, config.CACHE_LANG_DIR
    )


def process_lang_resource(lang_res_map: _ty.Dict[str, LangResourceInfo]) -> None:
    for name, info in lang_res_map.items():
        lang_sha1 = info["hash"]
        lang_url = config.URL_RESOURCE_FORMAT.format(lang_sha1[0:2], lang_sha1)
        lang_save_path = config.CACHE_LANG_DIR / (name + ".json")
        if not lang_save_path.exists() or (
            lang_save_path.is_file() and not match_file_SHA1(lang_save_path, lang_sha1)
        ):
            _log.debug(f"Requesting {lang_url}")
            download_file(lang_url, lang_save_path, lang_sha1)


def combine_glossary() -> _ty.Dict[str, _ty.List[_ty.Dict[str, str]]]:
    import json
    import re

    patterns = {k: [] for k in config.TRANSLATION_KEY_REGEX.keys()}

    for category, r_list in config.TRANSLATION_KEY_REGEX.items():
        for r in r_list:
            patterns[category].append(re.compile(r))

    # glossary = []
    glossary = {k: [] for k in config.TRANSLATION_KEY_REGEX.keys()}
    for lang_name in config.LANG_ORDER:
        _log.debug(f"Processing {lang_name}")
        subset = {k: {} for k in config.TRANSLATION_KEY_REGEX.keys()}

        lang_path = config.CACHE_LANG_DIR / (lang_name + ".json")
        with open(lang_path, "r", encoding="utf-8") as f:
            lang_content = json.load(f)
            for category, pattern_list in patterns.items():
                for tr_k in lang_content.keys():
                    for p in pattern_list:
                        if p.fullmatch(tr_k):
                            subset[category][tr_k] = lang_content[tr_k]
                            break
        for k in glossary:
            glossary[k].append(subset[k])

    return glossary


def write_glossary(
    glossary: _ty.Dict[str, _ty.List[_ty.Dict[str, str]]], mc_version: str
) -> None:
    import csv 

    _os.makedirs(config.GLOSSARY_OUTPUT_DIR, exist_ok=True)
    if parent := _os.path.dirname(config.GLOSSARY_VERSION_PATH):
        _os.makedirs(parent, exist_ok=True)

    for category, content in glossary.items():
        key_set = set()
        for d in content:
            key_set.update(d.keys())
        key_list = sorted(key_set)

        _log.info(f"Writing glossary {category}...")

        glossary_path = _os.path.join(config.GLOSSARY_OUTPUT_DIR, f"{category}.csv")
        with open(glossary_path, "w", encoding="utf-8-sig", newline="") as f:
            form = csv.writer(f)
            form.writerow(config.LANG_ORDER)
            for k in key_list:
                row = []
                for lang in content:
                    row.append(lang.get(k, ""))
                form.writerow(row)

        # SHA1 暂未使用，保留以备后续校验需要
        # sha1_path = _os.path.join(config.GLOSSARY_OUTPUT_DIR, f"{category}.sha1")
        # def file_chunks():
        #     with open(glossary_path, "rb") as f:
        #         for chunk in iter(lambda: f.read(_io.DEFAULT_BUFFER_SIZE), b""):
        #             yield chunk
        # sha1 = calc_SHA1_chunks(file_chunks())
        # with open(sha1_path, "w", encoding="utf-8") as f:
        #     f.write(sha1)

    with open(config.GLOSSARY_VERSION_PATH, "w", encoding="utf-8") as f:
        f.write(mc_version)


__all__ = [
    "process_manifest",
    "get_local_version",
    "process_version_json",
    "process_asset_index",
    "process_game_jar",
    "process_lang_resource",
    "combine_glossary",
    "write_glossary",
]
