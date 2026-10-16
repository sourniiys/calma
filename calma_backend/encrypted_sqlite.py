"""SQLite in-memory dengan file persisten yang dienkripsi utuh memakai Fernet."""
from pathlib import Path
import sqlite3
from threading import RLock

from .security import LocalDataCipher


class EncryptedSQLiteConnection:
    """Small sqlite3 connection adapter; no plaintext DB file is created on disk."""

    def __init__(self, database_path: str | Path, cipher: LocalDataCipher,
                 check_same_thread: bool = False):
        self.path = None if str(database_path) == ":memory:" else Path(database_path)
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cipher = cipher
        self._lock = RLock()
        self._closed = False
        self._connection = sqlite3.connect(":memory:", check_same_thread=check_same_thread)
        self._connection.row_factory = sqlite3.Row
        if self.path is not None and self.path.exists():
            encrypted = self.path.read_bytes()
            plaintext = self.cipher.decrypt_bytes(encrypted)
            try:
                self._connection.deserialize(plaintext)
            except sqlite3.DatabaseError as exc:
                self._connection.close()
                self._closed = True
                raise ValueError("Payload DB terenkripsi bukan database SQLite yang valid") from exc
            self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA busy_timeout = 5000")

    @property
    def row_factory(self):
        return self._connection.row_factory

    @row_factory.setter
    def row_factory(self, value):
        self._connection.row_factory = value

    def execute(self, *args, **kwargs):
        return self._connection.execute(*args, **kwargs)

    def executescript(self, *args, **kwargs):
        return self._connection.executescript(*args, **kwargs)

    def cursor(self, *args, **kwargs):
        return self._connection.cursor(*args, **kwargs)

    def __enter__(self):
        self._connection.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        result = self._connection.__exit__(exc_type, exc_value, traceback)
        if exc_type is None:
            self.persist()
        return result

    def commit(self):
        self._connection.commit()
        self.persist()

    def rollback(self):
        self._connection.rollback()

    def persist(self):
        if self.path is None:
            return
        with self._lock:
            serialized = self._connection.serialize()
            encrypted = self.cipher.encrypt_bytes(serialized)
            temporary_path = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary_path.write_bytes(encrypted)
            temporary_path.replace(self.path)

    def close(self):
        if self._closed:
            return
        self._connection.commit()
        self.persist()
        self._connection.close()
        self._closed = True
