"""Safety plan lokal; data tidak dikirim ke layanan eksternal."""
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Iterable

from tahap4_interaksi.consent import ConsentManager, ConsentPurpose


def _default_storage_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "CALMA" / "safety_plan.json"
    return Path.home() / ".calma" / "safety_plan.json"


def _clean_text(value: str, label: str, maximum: int = 500) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} harus berupa teks")
    value = value.strip()
    if len(value) > maximum:
        raise ValueError(f"{label} terlalu panjang (maksimal {maximum} karakter)")
    return value


def _clean_items(values: Iterable[str], label: str) -> tuple[str, ...]:
    items = tuple(_clean_text(item, label) for item in values)
    items = tuple(item for item in items if item)
    if len(items) > 20:
        raise ValueError(f"{label} maksimal 20 item")
    return items


@dataclass(frozen=True)
class SafetyContact:
    name: str
    phone: str

    def __post_init__(self) -> None:
        name = _clean_text(self.name, "Nama kontak", 100)
        phone = _clean_text(self.phone, "Nomor kontak", 40)
        digits = sum(character.isdigit() for character in phone)
        if not name or digits < 6 or any(c not in "+-() 0123456789" for c in phone):
            raise ValueError("Nama dan nomor kontak yang valid harus diisi")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "phone", phone)


@dataclass(frozen=True)
class PersonalSafetyPlan:
    warning_signs: tuple[str, ...] = ()
    helpful_steps: tuple[str, ...] = ()
    trusted_contact: SafetyContact | None = None
    professional_support: str = ""
    emergency_contact: SafetyContact | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        object.__setattr__(self, "warning_signs", _clean_items(self.warning_signs, "Tanda bantuan"))
        object.__setattr__(self, "helpful_steps", _clean_items(self.helpful_steps, "Langkah bantuan"))
        object.__setattr__(self, "professional_support",
                           _clean_text(self.professional_support, "Dukungan profesional"))
        if self.updated_at.tzinfo is None or self.updated_at.utcoffset() is None:
            raise ValueError("Waktu safety plan harus memiliki zona waktu")


class SafetyPlanStore:
    """Penyimpanan JSON lokal. Baca dan hapus tetap tersedia setelah consent dicabut."""

    def __init__(self, consent: ConsentManager, path: str | Path | None = None):
        self.consent = consent
        self.path = Path(path) if path is not None else _default_storage_path()
        self._plan: PersonalSafetyPlan | None = None
        self._last_attempt_at: datetime | None = None
        self._last_attempt_status: str | None = None
        if self.path.exists():
            self._load()

    @property
    def last_attempt_at(self) -> datetime | None:
        return self._last_attempt_at

    @property
    def last_attempt_status(self) -> str | None:
        return self._last_attempt_status

    def get_plan(self) -> PersonalSafetyPlan | None:
        return self._plan

    def update_plan(self, plan: PersonalSafetyPlan) -> PersonalSafetyPlan:
        self._require_storage_consent()
        previous = self._plan
        self._plan = replace(plan, updated_at=datetime.now(timezone.utc))
        try:
            self._persist()
        except OSError:
            self._plan = previous
            raise
        return self._plan

    def delete_plan(self) -> None:
        self._plan = None
        self._persist()

    def within_delivery_limit(self, at: datetime) -> bool:
        at = self._aware(at)
        if self._last_attempt_at is None:
            return False
        return at < self._last_attempt_at + self._day()

    def reserve_delivery(self, at: datetime) -> None:
        self._require_storage_consent()
        at = self._aware(at)
        if self.within_delivery_limit(at):
            raise DeliveryLimitReached("Batas satu pesan dalam 24 jam masih berlaku")
        previous_at, previous_status = self._last_attempt_at, self._last_attempt_status
        self._last_attempt_at, self._last_attempt_status = at, "pending"
        try:
            self._persist()
        except OSError:
            self._last_attempt_at, self._last_attempt_status = previous_at, previous_status
            raise

    def finish_delivery(self, status: str) -> None:
        previous = self._last_attempt_status
        self._last_attempt_status = status
        try:
            self._persist()
        except OSError:
            self._last_attempt_status = previous
            raise

    def _require_storage_consent(self) -> None:
        if not self.consent.has_consent(ConsentPurpose.DATA_STORAGE):
            raise PermissionError("Consent penyimpanan belum diberikan atau sudah dicabut")

    @staticmethod
    def _aware(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Waktu harus memiliki zona waktu")
        return value

    @staticmethod
    def _day():
        from datetime import timedelta
        return timedelta(hours=24)

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        plan = None
        if self._plan is not None:
            plan = {
                "warning_signs": list(self._plan.warning_signs),
                "helpful_steps": list(self._plan.helpful_steps),
                "trusted_contact": asdict(self._plan.trusted_contact) if self._plan.trusted_contact else None,
                "professional_support": self._plan.professional_support,
                "emergency_contact": asdict(self._plan.emergency_contact) if self._plan.emergency_contact else None,
                "updated_at": self._plan.updated_at.isoformat(),
            }
        payload = {
            "plan": plan,
            "last_attempt_at": self._last_attempt_at.isoformat() if self._last_attempt_at else None,
            "last_attempt_status": self._last_attempt_status,
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def _load(self) -> None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            plan = payload.get("plan")
            if plan is not None:
                trusted = plan.get("trusted_contact")
                emergency = plan.get("emergency_contact")
                self._plan = PersonalSafetyPlan(
                    warning_signs=tuple(plan.get("warning_signs", ())),
                    helpful_steps=tuple(plan.get("helpful_steps", ())),
                    trusted_contact=SafetyContact(**trusted) if trusted else None,
                    professional_support=plan.get("professional_support", ""),
                    emergency_contact=SafetyContact(**emergency) if emergency else None,
                    updated_at=datetime.fromisoformat(plan["updated_at"]),
                )
            attempt_at = payload.get("last_attempt_at")
            self._last_attempt_at = datetime.fromisoformat(attempt_at) if attempt_at else None
            self._last_attempt_status = payload.get("last_attempt_status")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("Berkas safety plan lokal tidak valid") from exc


class DeliveryLimitReached(ValueError):
    pass
