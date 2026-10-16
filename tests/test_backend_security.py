import sys
import pathlib

import pytest
from cryptography.fernet import Fernet

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from calma_backend.security import DataEncryptionError, LocalDataCipher


def test_field_encryption_round_trip_hides_plaintext():
    cipher = LocalDataCipher(Fernet.generate_key())
    plaintext = "trusted contact +628123456789"
    encrypted = cipher.encrypt_text(plaintext)
    assert plaintext.encode() not in encrypted
    assert cipher.decrypt_text(encrypted) == plaintext
    payload = {"warning_signs": ["private detail"], "phone": "+628123456789"}
    encrypted_json = cipher.encrypt_json(payload)
    assert b"private detail" not in encrypted_json
    assert cipher.decrypt_json(encrypted_json) == payload


def test_missing_or_wrong_key_fails_closed(monkeypatch):
    monkeypatch.delenv("CALMA_DATA_ENCRYPTION_KEY", raising=False)
    with pytest.raises(DataEncryptionError, match="tidak dibuat otomatis"):
        LocalDataCipher.from_environment()

    first = LocalDataCipher(Fernet.generate_key())
    second = LocalDataCipher(Fernet.generate_key())
    with pytest.raises(DataEncryptionError, match="tidak dapat dibuka"):
        second.decrypt_text(first.encrypt_text("secret"))


def test_invalid_encryption_key_is_rejected():
    with pytest.raises(DataEncryptionError, match="tidak valid"):
        LocalDataCipher("not-a-fernet-key")