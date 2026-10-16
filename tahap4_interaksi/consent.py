"""Pengelolaan persetujuan pengguna yang spesifik dan dapat diaudit lokal."""
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path


class ConsentPurpose(str, Enum):
    DATA_COLLECTION = "data_collection"
    PHYSIOLOGICAL_PROCESSING = "physiological_processing"
    DATA_STORAGE = "data_storage"
    MOOD_PERSONALIZATION = "mood_personalization"
    EXTERNAL_CHAT_PROCESSING = "external_chat_processing"
    TRUSTED_CONTACT = "trusted_contact"
    PROFESSIONAL_SUPPORT = "professional_support"


@dataclass(frozen=True)
class ConsentChange:
    purpose: ConsentPurpose
    granted: bool
    changed_at: datetime

    def __post_init__(self) -> None:
        if self.changed_at.tzinfo is None or self.changed_at.utcoffset() is None:
            raise ValueError("Waktu perubahan consent harus memiliki zona waktu")


class ConsentManager:
    """Consent selalu tertutup secara default; perubahan dapat disimpan sebagai JSON lokal."""

    def __init__(self, storage_path: str | Path | None = None):
        self.storage_path = Path(storage_path) if storage_path is not None else None
        self._history: list[ConsentChange] = []
        if self.storage_path is not None and self.storage_path.exists():
            self._load()

    @property
    def history(self) -> tuple[ConsentChange, ...]:
        return tuple(self._history)

    def history_for(self, purpose: ConsentPurpose) -> tuple[ConsentChange, ...]:
        purpose = ConsentPurpose(purpose)
        return tuple(change for change in self._history if change.purpose == purpose)

    def has_consent(self, purpose: ConsentPurpose) -> bool:
        purpose = ConsentPurpose(purpose)
        for change in reversed(self._history):
            if change.purpose == purpose:
                return change.granted
        return False

    def grant(self, purpose: ConsentPurpose, at: datetime | None = None) -> ConsentChange:
        return self._record(purpose, True, at)

    def revoke(self, purpose: ConsentPurpose, at: datetime | None = None) -> ConsentChange:
        return self._record(purpose, False, at)

    def _record(self, purpose: ConsentPurpose, granted: bool,
                at: datetime | None) -> ConsentChange:
        purpose = ConsentPurpose(purpose)
        changed = ConsentChange(purpose, granted, at or datetime.now(timezone.utc))
        self._history.append(changed)
        try:
            self._persist()
        except OSError:
            self._history.pop()
            raise
        return changed

    def _persist(self) -> None:
        if self.storage_path is None:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {"purpose": c.purpose.value, "granted": c.granted,
             "changed_at": c.changed_at.isoformat()}
            for c in self._history
        ]
        temporary_path = self.storage_path.with_suffix(self.storage_path.suffix + ".tmp")
        temporary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary_path.replace(self.storage_path)

    def _load(self) -> None:
        try:
            records = json.loads(self.storage_path.read_text(encoding="utf-8"))
            self._history = [
                ConsentChange(
                    purpose=ConsentPurpose(record["purpose"]),
                    granted=record["granted"],
                    changed_at=datetime.fromisoformat(record["changed_at"]),
                )
                for record in records
            ]
            if any(not isinstance(record.granted, bool) for record in self._history):
                raise ValueError("Status consent pada berkas lokal harus berupa boolean")
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("Berkas riwayat consent lokal tidak valid") from exc
