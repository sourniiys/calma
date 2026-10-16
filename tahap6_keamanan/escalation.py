"""Countdown kontak tepercaya dengan consent dan rate limit yang dicek ulang."""
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Protocol

from tahap4_interaksi.consent import ConsentManager, ConsentPurpose
from .plan import DeliveryLimitReached, SafetyPlanStore


SUPPORT_MESSAGE = "Lagi butuh ditemani"
COUNTDOWN_DURATION = timedelta(minutes=10)


class EscalationStatus(str, Enum):
    COUNTDOWN_STARTED = "countdown_started"
    COUNTDOWN_ACTIVE = "countdown_active"
    CANCELLED = "cancelled"
    NO_COUNTDOWN = "no_countdown"
    BLOCKED_CONSENT = "blocked_consent"
    BLOCKED_CONTACT = "blocked_contact"
    RATE_LIMITED = "rate_limited"
    NOT_OFFERED = "not_offered"
    INSUFFICIENT_DATA = "insufficient_data"
    SIMULATED_ONLY = "simulated_only"
    SENT = "sent"
    DELIVERY_FAILED = "delivery_failed"
    DELIVERY_STATUS_UNKNOWN = "delivery_status_unknown"


@dataclass(frozen=True)
class DeliveryResult:
    success: bool
    mode: str
    detail: str


class MessageProvider(Protocol):
    def send(self, phone: str, message: str) -> DeliveryResult:
        """Provider tidak menerima skor atau data fisiologis."""


class SimulatedMessageProvider:
    def send(self, phone: str, message: str) -> DeliveryResult:
        return DeliveryResult(True, "simulation", "Simulasi selesai; tidak ada pesan nyata yang dikirim.")


@dataclass(frozen=True)
class Countdown:
    started_at: datetime
    due_at: datetime


@dataclass(frozen=True)
class EscalationResult:
    status: EscalationStatus
    message: str
    due_at: datetime | None = None
    mode: str | None = None


@dataclass(frozen=True)
class ProfessionalSupportOffer:
    eligible: bool
    distinct_stress_days: int
    professional_support_consent: bool
    booking_available: bool = False
    message: str = ""


def repeated_stress_offer(event_dates, consent: ConsentManager) -> ProfessionalSupportOffer:
    days = set()
    for event_time in event_dates:
        if isinstance(event_time, datetime):
            days.add(event_time.date())
        elif isinstance(event_time, date):
            days.add(event_time)
        else:
            raise TypeError("Waktu kejadian harus berupa date atau datetime")
    eligible = len(days) >= 3
    allowed = consent.has_consent(ConsentPurpose.PROFESSIONAL_SUPPORT)
    if not eligible:
        message = "Belum ada kejadian pada tiga hari berbeda."
    elif allowed:
        message = "Kamu dapat mempertimbangkan dukungan profesional; CALMA belum menyediakan pemesanan."
    else:
        message = "Opsi dukungan profesional tersedia untuk dipertimbangkan; consent layanan belum aktif."
    return ProfessionalSupportOffer(eligible, len(days), allowed, False, message)


class TrustedContactEscalation:
    def __init__(self, consent: ConsentManager, store: SafetyPlanStore,
                 provider: MessageProvider | None = None):
        self.consent = consent
        self.store = store
        self.provider = provider or SimulatedMessageProvider()
        load_countdown = getattr(store, "get_pending_countdown", None)
        self.pending: Countdown | None = load_countdown() if load_countdown else None

    def start_after_evaluation(self, evaluation, at: datetime | None = None) -> EscalationResult:
        from tahap5_stress_quest import ResponseStatus
        if evaluation.status == ResponseStatus.INSUFFICIENT_DATA:
            return EscalationResult(EscalationStatus.INSUFFICIENT_DATA,
                                    "Data belum cukup; jangan simpulkan aktivitas tidak membantu.")
        if evaluation.status != ResponseStatus.NO_POSITIVE_RESPONSE:
            return EscalationResult(EscalationStatus.NOT_OFFERED,
                                    "Dukungan tambahan tidak dipicu oleh evaluasi ini.")
        return self.start_countdown(at)

    def start_countdown(self, at: datetime | None = None) -> EscalationResult:
        now = self._aware(at or datetime.now(timezone.utc))
        if self.pending is not None:
            return EscalationResult(EscalationStatus.COUNTDOWN_ACTIVE,
                                    "Countdown sudah aktif.", self.pending.due_at)
        blocked = self._precheck(now)
        if blocked is not None:
            return blocked
        countdown = Countdown(now, now + COUNTDOWN_DURATION)
        save_countdown = getattr(self.store, "save_pending_countdown", None)
        if save_countdown:
            try:
                save_countdown(countdown)
            except OSError:
                return EscalationResult(EscalationStatus.DELIVERY_FAILED,
                                        "Countdown gagal disimpan; tidak ada pesan dijadwalkan.")
        self.pending = countdown
        return EscalationResult(EscalationStatus.COUNTDOWN_STARTED,
                                "Countdown 10 menit dimulai dan dapat dibatalkan.", self.pending.due_at)

    def cancel(self) -> EscalationResult:
        if self.pending is None:
            return EscalationResult(EscalationStatus.NO_COUNTDOWN, "Tidak ada countdown aktif.")
        clear_countdown = getattr(self.store, "clear_pending_countdown", None)
        if clear_countdown:
            clear_countdown()
        self.pending = None
        return EscalationResult(EscalationStatus.CANCELLED, "Countdown dibatalkan; pesan tidak dikirim.")

    def complete(self, at: datetime | None = None) -> EscalationResult:
        now = self._aware(at or datetime.now(timezone.utc))
        if self.pending is None:
            return EscalationResult(EscalationStatus.NO_COUNTDOWN, "Tidak ada countdown aktif.")
        if now < self.pending.due_at:
            return EscalationResult(EscalationStatus.COUNTDOWN_ACTIVE,
                                    "Countdown belum selesai.", self.pending.due_at)
        clear_countdown = getattr(self.store, "clear_pending_countdown", None)
        if clear_countdown:
            clear_countdown()
        self.pending = None

        blocked = self._precheck(now)
        if blocked is not None:
            return blocked
        contact = self.store.get_plan().trusted_contact
        try:
            self.store.reserve_delivery(now)
        except DeliveryLimitReached:
            return EscalationResult(EscalationStatus.RATE_LIMITED,
                                    "Batas satu pesan dalam 24 jam masih berlaku.")
        except OSError:
            return EscalationResult(EscalationStatus.DELIVERY_FAILED,
                                    "Status pengiriman tidak dapat disimpan; provider tidak dipanggil.")

        try:
            result = self.provider.send(contact.phone, SUPPORT_MESSAGE)
        except Exception:
            result = DeliveryResult(False, "unknown", "Provider mengalami kegagalan.")

        if not result.success:
            try:
                self.store.finish_delivery("failed")
            except OSError:
                pass
            return EscalationResult(EscalationStatus.DELIVERY_FAILED,
                                    "Pengiriman gagal; CALMA tidak menyatakan pesan terkirim.", mode=result.mode)
        try:
            self.store.finish_delivery("simulated" if result.mode == "simulation" else "sent")
        except OSError:
            return EscalationResult(EscalationStatus.DELIVERY_STATUS_UNKNOWN,
                                    "Provider menerima permintaan, tetapi status lokal gagal disimpan.", mode=result.mode)
        if result.mode == "simulation":
            return EscalationResult(EscalationStatus.SIMULATED_ONLY,
                                    "Simulasi selesai; tidak ada pesan nyata yang dikirim.", mode=result.mode)
        return EscalationResult(EscalationStatus.SENT, "Provider melaporkan pengiriman berhasil.", mode=result.mode)

    def _precheck(self, at: datetime) -> EscalationResult | None:
        if not self.consent.has_consent(ConsentPurpose.TRUSTED_CONTACT) or not self.consent.has_consent(ConsentPurpose.DATA_STORAGE):
            return EscalationResult(EscalationStatus.BLOCKED_CONSENT,
                                    "Consent kontak tepercaya dan penyimpanan harus aktif.")
        plan = self.store.get_plan()
        if plan is None or plan.trusted_contact is None:
            return EscalationResult(EscalationStatus.BLOCKED_CONTACT,
                                    "Kontak tepercaya belum dikonfigurasi.")
        if self.store.within_delivery_limit(at):
            return EscalationResult(EscalationStatus.RATE_LIMITED,
                                    "Batas satu pesan dalam 24 jam masih berlaku.")
        return None

    @staticmethod
    def _aware(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Waktu harus memiliki zona waktu")
        return value
