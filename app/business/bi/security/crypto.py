"""BI 模块 Fernet 加解密工具。

用于加密数据源密码与 LLM API Key，密钥来自 ``.env`` 的 ``BI_CRYPTO_KEY``。

使用方式：

    from app.business.bi.security.crypto import encrypt, decrypt, mask

    ciphertext = encrypt("my-secret-password")
    plaintext = decrypt(ciphertext)
    masked = mask("my-secret-password")  # "***"
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.business.bi.config import BIZ_SETTINGS
from app.utils import BizError

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """获取 Fernet 实例（单例），密钥来自 ``BI_CRYPTO_KEY`` 配置项。"""
    global _fernet
    if _fernet is None:
        key = BIZ_SETTINGS.BI_CRYPTO_KEY
        if not key:
            raise BizError(4000, "BI_CRYPTO_KEY 未配置，无法加解密")
        try:
            _fernet = Fernet(key.encode())
        except (ValueError, TypeError) as e:
            raise BizError(4000, f"BI_CRYPTO_KEY 无效: {e}") from e
    return _fernet


def encrypt(plaintext: str) -> str:
    """加密明文，返回密文字符串。"""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """解密密文，返回明文字符串。"""
    f = _get_fernet()
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken as e:
        raise BizError(4000, f"解密失败: {e}") from e


def mask(plaintext: str) -> str:
    """脱敏显示（如密码字段返回前端时用 ``***`` 替代）。"""
    if not plaintext:
        return ""
    return "***"
