import sys
import pathlib
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from calma_backend.auth import (
    AccountStore, AuthenticationError, DuplicateAccountError,
)
from calma_backend.security import DataEncryptionError, LocalDataCipher


def test_password_is_hashed_and_signup_returns_unique_account(tmp_path):
    store = AccountStore(tmp_path / "accounts.sqlite3")
    user_a = store.register("  a@example.com ", "correct horse battery staple")
    user_b = store.register("b@example.com", "another secure password")
    record = store.account_security_record("a@example.com")

    assert user_a != user_b
    assert b"correct horse battery staple" not in record["password_hash"]
    assert len(record["password_salt"]) >= 16
    with pytest.raises(DuplicateAccountError):
        store.register("A@example.com", "different secure password")
    store.close()


def test_login_uses_generic_failure_and_issues_hashed_revocable_token(tmp_path):
    store = AccountStore(tmp_path / "accounts.sqlite3")
    user_id = store.register("person@example.com", "correct horse battery staple")
    with pytest.raises(AuthenticationError, match="Email atau password salah"):
        store.login("person@example.com", "incorrect horse battery staple")

    grant = store.login("person@example.com", "correct horse battery staple")
    assert grant.user_id == user_id
    assert store.user_for_token(grant.access_token) == user_id
    digest = store._token_digest(grant.access_token)
    row = store.connection.execute("SELECT token_hash FROM bearer_tokens").fetchone()
    assert row["token_hash"] == digest
    assert grant.access_token not in row["token_hash"]

    assert store.revoke_token(grant.access_token)
    assert store.user_for_token(grant.access_token) is None
    store.close()


def test_token_expiry_and_password_validation(tmp_path):
    store = AccountStore(tmp_path / "accounts.sqlite3", token_ttl=timedelta(minutes=5))
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    store.register("person@example.com", "correct horse battery staple", created)
    grant = store.login("person@example.com", "correct horse battery staple", created)
    assert store.user_for_token(grant.access_token, created + timedelta(minutes=4)) is not None
    assert store.user_for_token(grant.access_token, created + timedelta(minutes=5)) is None
    with pytest.raises(ValueError, match="12-128"):
        store.register("short@example.com", "tiny")
    store.close()


def test_account_database_is_encrypted_and_refuses_a_different_key(tmp_path):
    path = tmp_path / "accounts.sqlite3.enc"
    key = Fernet.generate_key()
    store = AccountStore(path, cipher=LocalDataCipher(key))
    store.register("private@example.com", "super secret password phrase")
    store.close()

    encrypted_file = path.read_bytes()
    assert not encrypted_file.startswith(b"SQLite format 3")
    assert b"private@example.com" not in encrypted_file
    assert b"super secret password phrase" not in encrypted_file

    with pytest.raises(DataEncryptionError, match="tidak dapat dibuka"):
        AccountStore(path, cipher=LocalDataCipher(Fernet.generate_key()))


def test_api_startup_requires_a_provisioned_encryption_key(tmp_path, monkeypatch):
    from calma_backend.api import create_app

    monkeypatch.delenv("CALMA_DATA_ENCRYPTION_KEY", raising=False)
    with pytest.raises(DataEncryptionError, match="wajib diatur"):
        create_app(database_path=tmp_path / "no-key.enc")