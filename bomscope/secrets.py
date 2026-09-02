"""At-rest encryption for stored credentials.

Tokens saved via the dashboard Settings are encrypted with Fernet before
being written to the settings table. The master key comes from
BOMSCOPE_SECRET_KEY (production) or is generated once and persisted to
<data_dir>/.secret with 0600 permissions (single-container default).

Encrypted values are stored with an "enc:" prefix; values without the
prefix are treated as plaintext for backward compatibility.
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_PREFIX = "enc:"
_fernet = None


def _data_dir() -> Path:
    env = os.getenv("BOMSCOPE_DATA_DIR")
    d = Path(env) if env else (Path("/data") if Path("/data").is_dir() else Path.cwd())
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        return Path.cwd()
    return d


def _load_fernet():
    global _fernet
    if _fernet is not None:
        return _fernet
    from cryptography.fernet import Fernet

    key = os.getenv("BOMSCOPE_SECRET_KEY")
    if not key:
        key_file = _data_dir() / ".secret"
        if key_file.exists():
            key = key_file.read_text().strip()
        else:
            key = Fernet.generate_key().decode()
            key_file.write_text(key)
            os.chmod(key_file, 0o600)
            logger.info("Generated new credential key at %s", key_file)
    try:
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as e:
        raise RuntimeError(
            "Invalid BOMSCOPE_SECRET_KEY — must be a urlsafe base64 Fernet key "
            "(generate with: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\")") from e
    return _fernet


def encrypt(value: str) -> str:
    """Encrypt a secret for storage. Returns "" for empty input."""
    if not value:
        return ""
    return _PREFIX + _load_fernet().encrypt(value.encode()).decode()


def decrypt(value: Optional[str]) -> str:
    """Decrypt a stored secret. Plaintext (no enc: prefix) passes through."""
    if not value:
        return ""
    if not value.startswith(_PREFIX):
        return value
    try:
        return _load_fernet().decrypt(value[len(_PREFIX):].encode()).decode()
    except Exception:
        logger.warning("Failed to decrypt stored credential (key changed?)")
        return ""
