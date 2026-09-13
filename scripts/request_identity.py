"""请求身份（User-Agent 联系方式）统一解析。

Wikimedia 政策要求脚本 UA 必须含**联系方式**（邮箱 / 网站 / 仓库 URL），
否则可能被 403 拒绝或静默封禁（默认值 `python-urllib` / `python-requests`
明确在拒绝之列）。本项目自身不提供联系方式——**由使用者填写自己的**，
避免任何 clone / fork 后以原作者名义发请求（滥用会归因到原仓库）。

取值优先级（高 → 低）：

1. 环境变量 `TCTW_CONTACT`（临时覆盖，如 CI）
2. 配置文件 `configs/request_identity.yaml` 的 `contact` 字段
3. **从 git remote 探测**——clone / fork 后 remote 天然是使用者自己的仓库
4. 占位符 `<PROJECT_URL>` 作最后兜底，并大声提醒填写

用法：
    from request_identity import user_agent
    headers = {"User-Agent": user_agent()}          # "TechMCTranslationWorkflow/1.0 (…)"
    req = urllib.request.Request(url, headers={"User-Agent": user_agent()})
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CLIENT = "TechMCTranslationWorkflow/1.0"
ENV_VAR = "TCTW_CONTACT"
CONFIG_PATH = PROJECT_ROOT / "configs" / "request_identity.yaml"
PLACEHOLDER = "<PROJECT_URL>"
CONTACT_RE = re.compile(r"^contact:\s*(.+?)\s*$", re.M)
_URL_RE = re.compile(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$")

_warned = False


def _from_env() -> str | None:
    value = os.environ.get(ENV_VAR, "").strip()
    return value or None


def _from_config() -> str | None:
    """读 configs/request_identity.yaml 的 contact（无 yaml 依赖，逐行解析）。

    文件不存在 / 未配置 / 仍是占位符 → None（继续下一优先级）。
    """
    try:
        text = CONFIG_PATH.read_text(encoding="utf-8")
    except OSError:
        return None
    m = CONTACT_RE.search(text)
    if not m:
        return None
    value = m.group(1).split("#", 1)[0].strip().strip('"').strip("'")
    if not value or value.startswith("<"):
        return None
    return value


def _from_git_remote() -> str | None:
    """从 git remote 推导仓库 URL——使用者 clone / fork 后即为自己的地址。"""
    for remote in ("origin", "upstream"):
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", remote],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        url = result.stdout.strip()
        if not url:
            continue
        if url.startswith("git@"):  # git@github.com:owner/repo.git
            host_path = url.split("@", 1)[1]
            host, _, path = host_path.partition(":")
            return f"https://{host}/{path.removesuffix('.git')}"
        if url.startswith(("http://", "https://")):
            return url.removesuffix(".git")
    return None


def contact() -> str:
    """联系方式（邮箱 / 站点 / 仓库 URL）。"""
    global _warned
    for getter in (_from_env, _from_config, _from_git_remote):
        value = getter()
        if value:
            return value
    if not _warned:
        _warned = True
        print(
            f"[request_identity] ⚠️ 未取到请求联系方式（环境变量 {ENV_VAR} / "
            f"configs/request_identity.yaml / git remote 均无）——"
            f"请在 configs/request_identity.yaml 填写 contact 后重试；"
            f"当前使用占位符 {PLACEHOLDER}（Wikimedia 政策要求真实联系方式）",
            file=sys.stderr,
        )
    return PLACEHOLDER


def user_agent() -> str:
    """完整 User-Agent：`<client>/<version> (<contact>)`。"""
    return f"{CLIENT} ({contact()})"


if __name__ == "__main__":
    print(f"contact  = {contact()}")
    print(f"UA       = {user_agent()}")
