import os as _os
import io as _io
import typing as _typing

import requests

from .. import config
from .errors import IntegrityError


def calc_SHA1_chunks(chunks: _typing.Iterable[bytes]) -> str:
    import hashlib
    sha1 = hashlib.sha1()
    for chunk in chunks:
        if chunk:
            sha1.update(chunk)
    return sha1.hexdigest()


def match_file_SHA1(path: str | _os.PathLike, hash: str) -> bool:
    def file_chunks():
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(_io.DEFAULT_BUFFER_SIZE), b""):
                yield chunk

    return calc_SHA1_chunks(file_chunks()) == hash


def download_file(
    url: str, save_path: str | _os.PathLike, expected_sha1: str, max_retries=config.MAX_RETRIES
) -> None:
    import hashlib

    for i in range(max_retries):
        try:
            _os.makedirs(_os.path.dirname(save_path), exist_ok=True)
            sha1 = hashlib.sha1()
            with requests.get(url, stream=True, timeout=10) as r:
                r.raise_for_status()
                with open(save_path, "wb") as f:
                    for chunk in r.iter_content(_io.DEFAULT_BUFFER_SIZE):
                        if chunk:
                            f.write(chunk)
                            sha1.update(chunk)
            actual = sha1.hexdigest()

            if actual != expected_sha1:
                _os.remove(save_path)
                raise IntegrityError(
                    f"{url}\nSHA1 mismatch: expected {expected_sha1}, got {actual}"
                )

            return  # success

        except (requests.exceptions.RequestException, OSError, IntegrityError) as e:
            if _os.path.exists(save_path):
                _os.remove(save_path)
            if i == max_retries - 1:
                raise e  # last attempt, raise errors if fails
