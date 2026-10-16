"""Primitive enkripsi field lokal; bukan enkripsi seluruh file SQLite."""
from cryptography.fernet import Fernet, InvalidToken
import json
import os


class DataEncryptionError(RuntimeError):
    pass


class LocalDataCipher:
    ENVIRONMENT_VARIABLE = "CALMA_DATA_ENCRYPTION_KEY"

    def __init__(self, key: str | bytes):
        if isinstance(key, str):
            key = key.encode("ascii")
        try:
            self._fernet = Fernet(key)
        except (TypeError, ValueError) as exc:
            raise DataEncryptionError("Kunci enkripsi CALMA tidak valid") from exc

    @classmethod
    def from_environment(cls) -> "LocalDataCipher":
        key = os.getenv(cls.ENVIRONMENT_VARIABLE)
        if not key:
            raise DataEncryptionError(
                f"{cls.ENVIRONMENT_VARIABLE} wajib diatur; kunci tidak dibuat otomatis"
            )
        return cls(key)

    @classmethod
    def generate_key_for_operator(cls) -> str:
        """Generate a key only when explicitly requested by an operator command."""
        return Fernet.generate_key().decode("ascii")

    def encrypt_text(self, value: str) -> bytes:
        if not isinstance(value, str):
            raise TypeError("Nilai yang dienkripsi harus berupa teks")
        return self._fernet.encrypt(value.encode("utf-8"))

    def encrypt_bytes(self, value: bytes) -> bytes:
        if not isinstance(value, bytes):
            raise TypeError("Nilai yang dienkripsi harus berupa bytes")
        return self._fernet.encrypt(value)

    def decrypt_text(self, value: bytes | str) -> str:
        if isinstance(value, str):
            value = value.encode("ascii")
        try:
            return self._fernet.decrypt(value).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError, TypeError) as exc:
            raise DataEncryptionError("Data terenkripsi tidak dapat dibuka dengan kunci ini") from exc

    def decrypt_bytes(self, value: bytes | str) -> bytes:
        if isinstance(value, str):
            value = value.encode("ascii")
        try:
            return self._fernet.decrypt(value)
        except (InvalidToken, TypeError) as exc:
            raise DataEncryptionError("Data terenkripsi tidak dapat dibuka dengan kunci ini") from exc

    def encrypt_json(self, value) -> bytes:
        return self.encrypt_text(json.dumps(value, separators=(",", ":"), ensure_ascii=True))

    def decrypt_json(self, value: bytes | str):
        try:
            return json.loads(self.decrypt_text(value))
        except json.JSONDecodeError as exc:
            raise DataEncryptionError("Payload terenkripsi bukan JSON yang valid") from exc
