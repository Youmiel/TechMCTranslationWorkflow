from typing import TypedDict


class VersionInfo(TypedDict):
    id: str
    type: str
    url: str
    time: str
    releaseTime: str
    sha1: str
    complianceLevel: int


class AssetIndexInfo(TypedDict):
    id: str
    sha1: str
    size: int
    totalSize: int
    url: str


class GameJarInfo(TypedDict):
    sha1: str
    size: int
    url: str


class LangResourceInfo(TypedDict):
    hash: str
    size: int
