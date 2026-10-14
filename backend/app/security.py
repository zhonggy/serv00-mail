"""密码哈希、JWT、邮箱凭据加密、API Key。

可移植性设计：bcrypt / cryptography 在某些平台（如 FreeBSD）上 pip 安装
需要 Rust 编译，可能失败。本模块对两者都做了纯 Python/std 安全降级，
保证缺包时应用仍可运行（密码哈希降级为 PBKDF2，凭据加密降级为
HMAC-SHA256 CTR 流 + 完整性校验）。
"""
import base64
import datetime
import hashlib
import hmac
import os
import secrets

import jwt

from .config import get_settings

settings = get_settings()

# ---------- 可选依赖 ----------
try:
    import bcrypt as _bcrypt

    _HAS_BCRYPT = True
except ImportError:
    _HAS_BCRYPT = False

try:
    from cryptography.fernet import Fernet as _Fernet, InvalidToken as _InvalidToken

    _HAS_FERNET = True
except ImportError:
    _HAS_FERNET = False


# ---------- 登录密码 ----------
def hash_password(password: str) -> str:
    if _HAS_BCRYPT:
        return "bcrypt$" + _bcrypt.hashpw(
            password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")
    # 降级：PBKDF2-HMAC-SHA256（stdlib，无需编译）
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000)
    return "pbkdf2$" + salt.hex() + "$" + dk.hex()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        if password_hash.startswith("bcrypt$"):
            if not _HAS_BCRYPT:
                return False
            return _bcrypt.checkpw(password.encode("utf-8"),
                                   password_hash[len("bcrypt$"):].encode("utf-8"))
        if password_hash.startswith("pbkdf2$"):
            _, salt_hex, dk_hex = password_hash.split("$")
            salt = bytes.fromhex(salt_hex)
            dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000)
            return hmac.compare_digest(dk.hex(), dk_hex)
        # 兼容历史数据：无前缀视为原生 bcrypt
        if _HAS_BCRYPT:
            return _bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        return False
    except (ValueError, TypeError):
        return False


# ---------- JWT ----------
def create_access_token(user_id: int, login_mailbox_id: int | None = None) -> str:
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": str(user_id), "exp": expire}
    if login_mailbox_id:
        # 邮箱登录：token 绑定登录用的邮箱；这类 token 永远是普通用户身份
        payload["mb"] = int(login_mailbox_id)
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        int(payload["sub"])
        return payload
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


# ---------- 邮箱密码加密 ----------
class _FallbackCipher:
    """Fernet 兼容接口的纯 Python 实现。

    构造：nonce(16B) || AES-CTR 风格的 HMAC-SHA256 密钥流异或 || HMAC-SHA256 标签。
    密钥复用 FERNET_KEY（32 字节 urlsafe base64），与真实 Fernet 的 token
    不互通——切换实现后已存的邮箱密码需重建（删除重建邮箱即可）。
    """

    def __init__(self, key: bytes):
        raw = base64.urlsafe_b64decode(key + b"=" * (-len(key) % 4))
        if len(raw) != 32:
            raise ValueError("FERNET_KEY 必须是 32 字节的 base64")
        self.key = raw

    def _stream(self, nonce: bytes, n: int) -> bytes:
        out = b""
        counter = 0
        while len(out) < n:
            out += hmac.new(self.key, nonce + counter.to_bytes(4, "big"),
                            hashlib.sha256).digest()
            counter += 1
        return out[:n]

    def encrypt(self, data: bytes) -> bytes:
        nonce = os.urandom(16)
        ct = bytes(a ^ b for a, b in zip(data, self._stream(nonce, len(data))))
        tag = hmac.new(self.key, nonce + ct, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(nonce + ct + tag)

    def decrypt(self, token: bytes) -> bytes:
        raw = base64.urlsafe_b64decode(token)
        if len(raw) < 48:
            raise ValueError("bad token")
        nonce, ct, tag = raw[:16], raw[16:-32], raw[-32:]
        expect = hmac.new(self.key, nonce + ct, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expect):
            raise ValueError("bad token")
        return bytes(a ^ b for a, b in zip(ct, self._stream(nonce, len(ct))))


def _get_cipher():
    if not settings.fernet_key:
        raise RuntimeError("FERNET_KEY 未配置，请按 .env.example 生成")
    key = settings.fernet_key.encode()
    if _HAS_FERNET:
        return _Fernet(key)
    return _FallbackCipher(key)


def encrypt_credential(plain: str) -> str:
    return _get_cipher().encrypt(plain.encode()).decode()


def decrypt_credential(token: str) -> str:
    try:
        return _get_cipher().decrypt(token.encode()).decode()
    except Exception as e:
        raise RuntimeError("邮箱凭据解密失败，FERNET_KEY 可能已变更或加密实现已切换") from e


# ---------- API Key ----------
def generate_api_key() -> tuple[str, str, str]:
    """返回 (明文key, sha256哈希, 展示前缀)。明文只在创建时返回一次。"""
    raw = "sk-" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, key_hash, raw[:10]


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_mailbox_password(length: int = 16) -> str:
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()
