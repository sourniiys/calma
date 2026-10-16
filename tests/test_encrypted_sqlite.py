import sys
import pathlib

import pytest
from cryptography.fernet import Fernet

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from calma_backend.encrypted_sqlite import EncryptedSQLiteConnection
from calma_backend.security import DataEncryptionError, LocalDataCipher


def test_sqlite_file_is_encrypted_at_rest_and_survives_reopen(tmp_path):
    path = tmp_path / "private.sqlite3.enc"
    cipher = LocalDataCipher(Fernet.generate_key())
    connection = EncryptedSQLiteConnection(path, cipher)
    with connection:
        connection.execute("CREATE TABLE private_data(value TEXT NOT NULL)")
        connection.execute("INSERT INTO private_data(value) VALUES (?)", ("private-health-marker",))
    connection.close()

    encrypted = path.read_bytes()
    assert not encrypted.startswith(b"SQLite format 3")
    assert b"private-health-marker" not in encrypted

    reopened = EncryptedSQLiteConnection(path, cipher)
    assert reopened.execute("SELECT value FROM private_data").fetchone()["value"] == "private-health-marker"
    reopened.close()


def test_encrypted_database_refuses_missing_or_wrong_key(tmp_path, monkeypatch):
    monkeypatch.delenv("CALMA_DATA_ENCRYPTION_KEY", raising=False)
    with pytest.raises(DataEncryptionError, match="wajib diatur"):
        LocalDataCipher.from_environment()

    path = tmp_path / "private.sqlite3.enc"
    first = LocalDataCipher(Fernet.generate_key())
    connection = EncryptedSQLiteConnection(path, first)
    with connection:
        connection.execute("CREATE TABLE values_table(value TEXT)")
        connection.execute("INSERT INTO values_table VALUES ('keep')")
    connection.close()

    wrong = LocalDataCipher(Fernet.generate_key())
    with pytest.raises(DataEncryptionError, match="tidak dapat dibuka"):
        EncryptedSQLiteConnection(path, wrong)
