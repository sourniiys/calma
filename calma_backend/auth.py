"""Akun lokal dan token bearer opak untuk prototipe backend CALMA."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import re
import secrets
import sqlite3
from pathlib import Path
from threading import RLock

from .encrypted_sqlite import EncryptedSQLiteConnection
from .security import LocalDataCipher


PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128
SCRYPT_N = 1 << 14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 64
DEFAULT_TOKEN_TTL = timedelta(minutes=60)
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class AuthenticationError(ValueError):
    pass


class DuplicateAccountError(ValueError):
    pass


@dataclass(frozen=True)
class TokenGrant:
    user_id: str
    access_token: str
    expires_at: datetime
    token_type: str = "bearer"


class AccountStore:
    """Stores password hashes and token hashes; plaintext secrets are returned only once."""

    def __init__(self, database_path: str | Path,
                 token_ttl: timedelta = DEFAULT_TOKEN_TTL,
                 cipher: LocalDataCipher | None = None):
        value = str(database_path)
        if value != ":memory:":
            Path(value).parent.mkdir(parents=True, exist_ok=True)
        self.cipher = cipher or LocalDataCipher.from_environment()
        self.connection = EncryptedSQLiteConnection(value, self.cipher,
                                                    check_same_thread=False)
        self._lock = RLock()
        self.token_ttl = token_ttl
        self._create_schema()

    def _create_schema(self) -> None:
        with self._lock, self.connection:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    user_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash BLOB NOT NULL,
                    password_salt BLOB NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS bearer_tokens (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES accounts(user_id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT
                );
                CREATE INDEX IF NOT EXISTS bearer_tokens_user_idx ON bearer_tokens(user_id);
                """
            )

    @staticmethod
    def _normalize_email(email: str) -> str:
        if not isinstance(email, str):
            raise ValueError("Email harus berupa teks")
        normalized = email.strip().casefold()
        if len(normalized) > 254 or not _EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("Format email tidak valid")
        return normalized

    @staticmethod
    def _validate_password(password: str) -> None:
        if not isinstance(password, str):
            raise ValueError("Password harus berupa teks")
        if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
            raise ValueError(
                f"Password harus memiliki {PASSWORD_MIN_LENGTH}-{PASSWORD_MAX_LENGTH} karakter"
            )

    @staticmethod
    def _hash_password(password: str, salt: bytes) -> bytes:
        return hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=SCRYPT_N,
            r=SCRYPT_R, p=SCRYPT_P, dklen=SCRYPT_DKLEN,
        )

    def health_check(self) -> bool:
        with self._lock:
            return self.connection.execute("SELECT 1").fetchone()[0] == 1

    @staticmethod
    def _token_digest(token: str) -> str:
        return hashlib.sha256(token.encode("ascii")).hexdigest()

    @staticmethod
    def _now(value: datetime | None = None) -> datetime:
        value = value or datetime.now(timezone.utc)
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Waktu harus memiliki zona waktu")
        return value

    def register(self, email: str, password: str,
                 at: datetime | None = None) -> str:
        email = self._normalize_email(email)
        self._validate_password(password)
        now = self._now(at)
        user_id = secrets.token_hex(16)
        salt = secrets.token_bytes(16)
        password_hash = self._hash_password(password, salt)
        with self._lock, self.connection:
            try:
                self.connection.execute(
                    "INSERT INTO accounts(user_id,email,password_hash,password_salt,created_at) VALUES (?,?,?,?,?)",
                    (user_id, email, password_hash, salt, now.isoformat()),
                )
            except sqlite3.IntegrityError as exc:
                raise DuplicateAccountError("Akun dengan email tersebut sudah terdaftar") from exc
        return user_id

    def login(self, email: str, password: str,
              at: datetime | None = None) -> TokenGrant:
        email = self._normalize_email(email)
        self._validate_password(password)
        now = self._now(at)
        with self._lock:
            account = self.connection.execute(
                "SELECT user_id,password_hash,password_salt FROM accounts WHERE email = ?",
                (email,),
            ).fetchone()
        if account is None:
            self._hash_password(password, b"calma-dummy-salt")
            raise AuthenticationError("Email atau password salah")
        candidate = self._hash_password(password, account["password_salt"])
        if not hmac.compare_digest(candidate, account["password_hash"]):
            raise AuthenticationError("Email atau password salah")
        token = secrets.token_urlsafe(32)
        expires_at = now + self.token_ttl
        with self._lock, self.connection:
            self.connection.execute(
                "INSERT INTO bearer_tokens(token_hash,user_id,created_at,expires_at) VALUES (?,?,?,?)",
                (self._token_digest(token), account["user_id"], now.isoformat(), expires_at.isoformat()),
            )
        return TokenGrant(account["user_id"], token, expires_at)

    def user_for_token(self, token: str, at: datetime | None = None) -> str | None:
        if not isinstance(token, str) or not token or len(token) > 200:
            return None
        now = self._now(at)
        with self._lock:
            row = self.connection.execute(
                """SELECT user_id FROM bearer_tokens
                   WHERE token_hash = ? AND revoked_at IS NULL AND expires_at > ?""",
                (self._token_digest(token), now.isoformat()),
            ).fetchone()
        return row["user_id"] if row else None

    def revoke_token(self, token: str, at: datetime | None = None) -> bool:
        now = self._now(at)
        with self._lock, self.connection:
            result = self.connection.execute(
                "UPDATE bearer_tokens SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
                (now.isoformat(), self._token_digest(token)),
            )
        return result.rowcount == 1

    def account_security_record(self, email: str) -> dict[str, bytes] | None:
        """Internal/test inspection helper; never includes cleartext password/token."""
        normalized = self._normalize_email(email)
        with self._lock:
            row = self.connection.execute(
                "SELECT password_hash,password_salt FROM accounts WHERE email = ?", (normalized,),
            ).fetchone()
        return dict(row) if row else None

    def close(self) -> None:
        with self._lock:
            self.connection.close()