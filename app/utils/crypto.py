"""Fernet 对称加密 — 用于加密敏感字段（Datasource 密码等）。

密钥来源：
1. `APP_SETTINGS.FERNET_KEY`（env `FERNET_KEY`）— 生产环境必须
2. 启动时若未提供，写入安全警告并使用一次性 instance-level 密钥
   （重启后旧密文不可解密，仅用于本地开发）
"""

from __future__ import annotations

from collections.abc import Iterable

from cryptography.fernet import Fernet, InvalidToken

_KEY_INSTANCE: Fernet | None = None
_KEY_PERSISTENT: bool = False


def _load_key() -> bytes:
    """从 `APP_SETTINGS.FERNET_KEY` 加载密钥；未提供时生成临时密钥。"""
    global _KEY_PERSISTENT
    try:
        from app.core.config import APP_SETTINGS

        raw = APP_SETTINGS.FERNET_KEY
    except Exception:  # noqa: BLE001
        raw = ""

    if raw:
        _KEY_PERSISTENT = True
        return raw.encode("utf-8") if isinstance(raw, str) else raw

    from app.core.log import log

    log.warning(
        "FERNET_KEY not configured; using an ephemeral in-memory key. Encrypted data will NOT survive restart. Set FERNET_KEY in .env for production.",
    )
    return Fernet.generate_key()


def _get_cipher() -> Fernet:
    global _KEY_INSTANCE
    if _KEY_INSTANCE is None:
        _KEY_INSTANCE = Fernet(_load_key())
    return _KEY_INSTANCE


def is_persistent_key() -> bool:
    """是否使用了持久化密钥（来自环境变量）。"""
    if _KEY_INSTANCE is None:
        _get_cipher()
    return _KEY_PERSISTENT


def generate_key() -> str:
    """生成一个新的 Fernet 密钥（URL-safe base64 编码的 32 字节）。"""
    return Fernet.generate_key().decode("utf-8")


def encrypt(plaintext: str) -> str:
    """加密字符串。"""
    if plaintext is None:
        return ""
    return _get_cipher().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    """解密字符串；解密失败时抛 `InvalidToken`。"""
    if not ciphertext:
        return ""
    try:
        return _get_cipher().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Fernet decrypt failed: invalid token or wrong key") from exc


def reset_for_testing() -> None:
    """重置单例（仅供测试）。"""
    global _KEY_INSTANCE, _KEY_PERSISTENT
    _KEY_INSTANCE = None
    _KEY_PERSISTENT = False


__all__: Iterable[str] = (
    "encrypt",
    "decrypt",
    "generate_key",
    "is_persistent_key",
    "reset_for_testing",
)
