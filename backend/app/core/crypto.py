import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


def build_fernet(raw_key: str) -> Fernet:
    """
    构造 Fernet 加密器。

    - 支持直接传入 Fernet Key（base64 urlsafe，解码后 32 字节）。
    - 也支持传入口令字符串：会用 SHA256 派生为 Fernet Key。
    """

    value = (raw_key or "").strip()
    if not value:
        raise ValueError("未配置 FA_CREDENTIAL_ENCRYPTION_KEY，已禁用 API 凭据托管")

    # 优先尝试当作 Fernet Key 使用
    try:
        decoded = base64.urlsafe_b64decode(value.encode("utf-8"))
        if len(decoded) == 32:
            return Fernet(value.encode("utf-8"))
    except Exception:
        pass

    # 否则把口令派生为 Fernet Key（32 bytes）
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    derived = base64.urlsafe_b64encode(digest)
    return Fernet(derived)


def encrypt_text(fernet: Fernet, plaintext: str) -> str:
    """加密明文并返回可存储的字符串。"""

    value = plaintext or ""
    token = fernet.encrypt(value.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_text(fernet: Fernet, token: str) -> str:
    """解密 token，失败时抛出 ValueError（不泄漏敏感信息）。"""

    try:
        raw = fernet.decrypt((token or "").encode("utf-8"))
        return raw.decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("凭据解密失败：请确认 FA_CREDENTIAL_ENCRYPTION_KEY 未变更") from exc
