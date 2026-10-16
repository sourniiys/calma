"""State machine interaksi pengguna dan konfirmasi event dari Tahap 3."""
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from tahap3_deteksi.deteksi import StressEvent


class UserState(str, Enum):
    READY = "ready"
    AWAITING_STRESS_CONFIRMATION = "awaiting_stress_confirmation"
    STRESS_CONFIRMED = "stress_confirmed_by_user"
    STRESS_DENIED = "stress_denied_by_user"
    STRESS_UNSURE = "user_unsure"


class UserConfirmation(str, Enum):
    YES = "yes"
    NO = "no"
    UNSURE = "unsure"


@dataclass(frozen=True)
class ConfirmationRecord:
    event: StressEvent
    answer: UserConfirmation
    answered_at: datetime


class UserStateMachine:
    def __init__(self) -> None:
        self.state = UserState.READY
        self.pending_event: StressEvent | None = None
        self._history: list[ConfirmationRecord] = []

    @property
    def confirmation_history(self) -> tuple[ConfirmationRecord, ...]:
        return tuple(self._history)

    def request_confirmation(self, event: StressEvent) -> None:
        if self.state == UserState.AWAITING_STRESS_CONFIRMATION:
            raise RuntimeError("Konfirmasi event sebelumnya belum dijawab")
        if not isinstance(event, StressEvent):
            raise TypeError("Event harus berasal dari deteksi Tahap 3")
        self.pending_event = event
        self.state = UserState.AWAITING_STRESS_CONFIRMATION

    def answer_confirmation(self, answer: UserConfirmation | str,
                            at: datetime | None = None) -> ConfirmationRecord:
        if self.state != UserState.AWAITING_STRESS_CONFIRMATION or self.pending_event is None:
            raise RuntimeError("Tidak ada konfirmasi stres yang sedang menunggu jawaban")
        answer = UserConfirmation(answer)
        answered_at = at or datetime.now(timezone.utc)
        if answered_at.tzinfo is None or answered_at.utcoffset() is None:
            raise ValueError("Waktu konfirmasi harus memiliki zona waktu")

        record = ConfirmationRecord(self.pending_event, answer, answered_at)
        self._history.append(record)
        self.pending_event = None
        self.state = {
            UserConfirmation.YES: UserState.STRESS_CONFIRMED,
            UserConfirmation.NO: UserState.STRESS_DENIED,
            UserConfirmation.UNSURE: UserState.STRESS_UNSURE,
        }[answer]
        return record

    def reset(self) -> None:
        if self.state == UserState.AWAITING_STRESS_CONFIRMATION:
            raise RuntimeError("Jawab atau batalkan konfirmasi sebelum reset")
        self.pending_event = None
        self.state = UserState.READY
