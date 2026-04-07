"""设备凭证持久化存储。

init_device 成功后将 simei + token 写入本地文件，
localserver 重启时读取凭证自动恢复推理服务。
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# 凭证默认存储路径
_CREDENTIAL_DIR = Path("~/.deeppool").expanduser()
_CREDENTIAL_FILE = _CREDENTIAL_DIR / "device_credential.json"


@dataclass
class DeviceCredential:
    """设备凭证，包含向 platform 认证所需的最小信息。"""
    simei: str
    token: str


def save_credential(cred: DeviceCredential) -> None:
    """将设备凭证持久化到本地文件。"""
    _CREDENTIAL_DIR.mkdir(parents=True, exist_ok=True)
    _CREDENTIAL_FILE.write_text(
        json.dumps(asdict(cred), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("device credential saved simei=%s", cred.simei)


def load_credential() -> DeviceCredential | None:
    """从本地文件加载设备凭证，文件不存在或格式异常返回 None。"""
    if not _CREDENTIAL_FILE.is_file():
        logger.debug("no credential file found at %s", _CREDENTIAL_FILE)
        return None

    try:
        raw = json.loads(_CREDENTIAL_FILE.read_text(encoding="utf-8"))
        simei = str(raw.get("simei", "")).strip()
        token = str(raw.get("token", "")).strip()
        if not simei or not token:
            logger.warning("credential file incomplete, ignoring")
            return None
        return DeviceCredential(simei=simei, token=token)
    except Exception as exc:
        logger.warning("failed to load credential: %s", exc)
        return None
