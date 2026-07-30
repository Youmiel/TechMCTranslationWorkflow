import os as _os
import typing as ty

from .types import LangResourceInfo, VersionInfo, AssetIndexInfo, GameJarInfo
from .errors import FileLoadError, FileParseError, VersionNotFoundError
from ..config import LANG_FORMAT, LANG_LIST


def read_json(path: str | _os.PathLike) -> ty.Any:
    import json

    try:
        with open(path, "r", encoding='utf-8') as f:
            json_obj = json.load(f)
            return json_obj
    except OSError as e:
        raise FileLoadError(f"Failed to load file: {e}") from e
    except UnicodeDecodeError as e:
        raise ValueError(f"Failed to decode text file: {e}") from e
    except json.JSONDecodeError as e:
        raise FileParseError(f"Failed to parse JSON: {e}") from e


# def resolve_version_manifest_v2(path: str | os.PathLike) -> VersionInfo:
# manifest = read_json(path)
def resolve_version_manifest_v2(manifest: dict[str, ty.Any]) -> VersionInfo:
    latest_release_name = manifest["latest"]["release"]
    version_details = manifest["versions"]
    for v in version_details:
        if v["id"] == latest_release_name:
            release_info: VersionInfo = v
            return release_info
    raise VersionNotFoundError(
        f"Latest release info is not in manifest: {latest_release_name}"
    )


def resolve_version(path: str | _os.PathLike) -> tuple[AssetIndexInfo, GameJarInfo]:
    version_detail = read_json(path)
    asset_index_json: AssetIndexInfo = version_detail["assetIndex"]
    game_jar_json: GameJarInfo = version_detail["downloads"]["client"]
    return asset_index_json, game_jar_json


def resolve_asset_index(path: str | _os.PathLike) -> ty.Dict[str, LangResourceInfo]:
    index = read_json(path)
    lang_info_dict = {}
    for lang_name in LANG_LIST:
        lang_info: LangResourceInfo = index["objects"][LANG_FORMAT.format(lang_name)]
        lang_info_dict[lang_name] = lang_info
    return lang_info_dict


def resolve_game_jar(
    jar_path: str | _os.PathLike, in_jar_loc: str, save_dir: str | _os.PathLike
) -> str:
    import zipfile

    with zipfile.ZipFile(jar_path, "r") as jar:
        with jar.open(in_jar_loc) as f:
            file_name = _os.path.basename(in_jar_loc)
            data = f.read()
            output_path = _os.path.join(save_dir, file_name)
            _os.makedirs(save_dir, exist_ok=True)
            with open(output_path, "wb") as out:
                out.write(data)
            return output_path
