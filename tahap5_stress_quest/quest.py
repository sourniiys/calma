"""Logika Stress Quest CALMA; evaluasi respons tidak menyatakan sebab-akibat."""
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable

import pandas as pd


class QuestTier(str, Enum):
    MICRO = "micro"
    STANDARD = "standard"
    FULL = "full"


class ActivityType(str, Enum):
    WALK = "walk"
    STEP_TARGET = "step_target"
    GYM = "gym"
    SWIM = "swim"


class EnergyLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class UserCondition(str, Enum):
    OKAY = "okay"
    NOT_FEELING_WELL = "not_feeling_well"
    RECOVERING = "recovering"
    INJURED = "injured"


class ActivitySource(str, Enum):
    USER_REPORTED = "user_reported"
    DEVICE_DETECTED = "device_detected"


class QuestStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class ResponseStatus(str, Enum):
    POSITIVE_RESPONSE = "initial_positive_response"
    NO_POSITIVE_RESPONSE = "no_initial_positive_response"
    INSUFFICIENT_DATA = "insufficient_data"


QUEST_ORDER = {QuestTier.MICRO: 0, QuestTier.STANDARD: 1, QuestTier.FULL: 2}


@dataclass(frozen=True)
class QuestOption:
    tier: QuestTier
    activity: ActivityType
    title: str
    target: str
    instructions: str


@dataclass(frozen=True)
class QuestRecommendation:
    option: QuestOption | None
    reason: str


@dataclass(frozen=True)
class QuestEvaluation:
    status: ResponseStatus
    before_mean: float | None
    recovery_mean: float | None
    decrease: float | None
    note: str


@dataclass
class QuestSession:
    option: QuestOption
    status: QuestStatus
    recorded_at: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None
    source: ActivitySource | None = None
    evaluation: QuestEvaluation | None = None


@dataclass(frozen=True)
class RewardOffer:
    available: bool
    remaining_this_week: int
    suggestions: tuple[str, ...]
    emphasized: bool
    label: str


@dataclass(frozen=True)
class RewardClaim:
    choice: str
    claimed_at: datetime
    status: str = "DEMO_ONLY"


_OPTIONS = (
    QuestOption(QuestTier.MICRO, ActivityType.WALK, "Jalan santai", "10 menit",
                "Berjalan santai selama 10 menit sesuai kenyamananmu."),
    QuestOption(QuestTier.STANDARD, ActivityType.STEP_TARGET, "Target langkah", "5.000 langkah",
                "Capai target langkah secara bertahap; kamu boleh berhenti kapan saja."),
    QuestOption(QuestTier.FULL, ActivityType.GYM, "Gym", "minimal 60 menit",
                "Pilih sesi gym yang sesuai kemampuan dan kebiasaanmu."),
    QuestOption(QuestTier.FULL, ActivityType.SWIM, "Berenang", "minimal 90 menit",
                "Berenang sesuai kemampuan dan kondisi yang kamu rasakan."),
)
_OPTION_BY_ACTIVITY = {option.activity: option for option in _OPTIONS}
_UNAVAILABLE_CONDITIONS = {
    UserCondition.NOT_FEELING_WELL, UserCondition.RECOVERING, UserCondition.INJURED,
}


def get_option(tier: QuestTier | str, activity: ActivityType | str | None = None) -> QuestOption:
    tier = QuestTier(tier)
    if activity is not None:
        option = _OPTION_BY_ACTIVITY[ActivityType(activity)]
        if option.tier != tier:
            raise ValueError("Jenis aktivitas tidak sesuai dengan tingkat quest")
        return option
    return next(option for option in _OPTIONS if option.tier == tier)


def recommend_quest(energy: EnergyLevel | str,
                    condition: UserCondition | str = UserCondition.OKAY,
                    preferred_activity: ActivityType | str | None = None,
                    history: Iterable[QuestSession] = (),
                    soft_mode: bool = False) -> QuestRecommendation:
    """Pilih aktivitas dari kondisi yang dilaporkan; skor stres tidak menjadi input."""
    energy = EnergyLevel(energy)
    condition = UserCondition(condition)
    preferred = ActivityType(preferred_activity) if preferred_activity is not None else None

    if condition in _UNAVAILABLE_CONDITIONS:
        return QuestRecommendation(None, "Kondisimu terdengar perlu diprioritaskan; istirahat atau lewati quest tanpa penalti.")

    if soft_mode or energy == EnergyLevel.LOW:
        maximum_tier = QuestTier.MICRO
        reason = "Pilihan ringan diprioritaskan berdasarkan Soft Mode atau energi yang kamu laporkan rendah."
    elif energy == EnergyLevel.MEDIUM:
        maximum_tier = QuestTier.STANDARD
        reason = "Pilihan disesuaikan dengan energi yang kamu laporkan."
    else:
        maximum_tier = QuestTier.FULL if preferred in {ActivityType.GYM, ActivityType.SWIM} else QuestTier.STANDARD
        reason = "Pilihan mengikuti energi dan preferensi aktivitas yang kamu nyatakan."

    eligible = [option for option in _OPTIONS if QUEST_ORDER[option.tier] <= QUEST_ORDER[maximum_tier]]
    completed_positive = Counter(
        session.option.activity
        for session in history
        if session.status == QuestStatus.COMPLETED
        and session.evaluation is not None
        and session.evaluation.status == ResponseStatus.POSITIVE_RESPONSE
    )

    selected = None
    if completed_positive:
        known_good = [option for option in eligible if completed_positive[option.activity] > 0]
        if known_good:
            selected = max(known_good, key=lambda option: completed_positive[option.activity])
            reason = "Memprioritaskan aktivitas yang sebelumnya diikuti respons awal positif; ini bukan bukti sebab-akibat."
    if selected is None and preferred is not None:
        selected = next((option for option in eligible if option.activity == preferred), None)
    if selected is None:
        selected = next(option for option in eligible if option.tier == maximum_tier)
    return QuestRecommendation(selected, reason)


def _aware(value: datetime, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"Waktu {label} harus memiliki zona waktu")
    return value


class QuestTracker:
    def __init__(self) -> None:
        self._history: list[QuestSession] = []
        self._active: QuestSession | None = None

    @property
    def history(self) -> tuple[QuestSession, ...]:
        return tuple(self._history)

    @property
    def active_session(self) -> QuestSession | None:
        return self._active

    def start(self, recommendation: QuestRecommendation,
              source: ActivitySource | str = ActivitySource.USER_REPORTED,
              at: datetime | None = None) -> QuestSession:
        if recommendation.option is None:
            raise ValueError("Tidak ada aktivitas yang direkomendasikan untuk dimulai")
        if self._active is not None:
            raise RuntimeError("Selesaikan atau batalkan quest yang sedang berlangsung terlebih dahulu")
        started_at = _aware(at or datetime.now(timezone.utc), "mulai")
        session = QuestSession(
            option=recommendation.option,
            status=QuestStatus.IN_PROGRESS,
            recorded_at=started_at,
            started_at=started_at,
            source=ActivitySource(source),
        )
        self._history.append(session)
        self._active = session
        return session

    def complete(self, at: datetime | None = None) -> QuestSession:
        if self._active is None:
            raise RuntimeError("Tidak ada quest yang sedang berlangsung")
        ended_at = _aware(at or datetime.now(timezone.utc), "selesai")
        if ended_at <= self._active.started_at:
            raise ValueError("Waktu selesai harus setelah waktu mulai")
        self._active.ended_at = ended_at
        self._active.status = QuestStatus.COMPLETED
        completed = self._active
        self._active = None
        return completed

    def skip(self, recommendation: QuestRecommendation,
             at: datetime | None = None) -> QuestSession:
        if self._active is not None:
            raise RuntimeError("Quest sedang berlangsung; selesaikan sebelum mencatat skip")
        if recommendation.option is None:
            raise ValueError("Pilih quest yang ingin dilewati")
        skipped_at = _aware(at or datetime.now(timezone.utc), "skip")
        session = QuestSession(recommendation.option, QuestStatus.SKIPPED, skipped_at)
        self._history.append(session)
        return session

    def evaluate(self, session: QuestSession, scores: pd.Series,
                 recovery_minutes: int = 30) -> QuestEvaluation:
        if session not in self._history or session.status != QuestStatus.COMPLETED:
            raise ValueError("Evaluasi hanya tersedia untuk quest yang selesai dan tercatat")
        if session.started_at is None or session.ended_at is None:
            raise ValueError("Waktu mulai dan selesai aktivitas belum lengkap")
        result = evaluate_recovery(session.started_at, session.ended_at, scores, recovery_minutes)
        session.evaluation = result
        return result


def evaluate_recovery(started_at: datetime, ended_at: datetime, scores: pd.Series,
                      recovery_minutes: int = 30) -> QuestEvaluation:
    """Bandingkan 10 menit pra-aktivitas dengan 10 menit terakhir dari pemulihan 30-60 menit."""
    started_at = _aware(started_at, "mulai")
    ended_at = _aware(ended_at, "selesai")
    if ended_at <= started_at:
        raise ValueError("Waktu selesai harus setelah waktu mulai")
    if not 30 <= recovery_minutes <= 60:
        raise ValueError("Periode pemulihan harus 30 sampai 60 menit")
    if not isinstance(scores, pd.Series) or not isinstance(scores.index, pd.DatetimeIndex):
        raise TypeError("Skor harus berupa pandas Series dengan indeks timestamp")
    if scores.index.has_duplicates:
        raise ValueError("Timestamp skor tidak boleh duplikat")
    if (scores.index.tz is None) != (started_at.tzinfo is None):
        raise ValueError("Zona waktu skor harus konsisten dengan waktu aktivitas")

    valid_scores = pd.to_numeric(scores.sort_index(), errors="coerce")
    valid_scores = valid_scores.where(valid_scores.between(0, 100))
    start = pd.Timestamp(started_at)
    end = pd.Timestamp(ended_at)
    before_index = pd.date_range(end=start - pd.Timedelta(minutes=1), periods=10, freq="min")
    recovery_end = end + pd.Timedelta(minutes=recovery_minutes)
    recovery_index = pd.date_range(end=recovery_end - pd.Timedelta(minutes=1), periods=10, freq="min")
    before = valid_scores.reindex(before_index)
    recovery = valid_scores.reindex(recovery_index)

    if before.isna().any() or recovery.isna().any():
        return QuestEvaluation(
            ResponseStatus.INSUFFICIENT_DATA, None, None, None,
            "Data 10 menit sebelum aktivitas atau pada akhir pemulihan belum lengkap.",
        )

    before_mean = float(before.mean())
    recovery_mean = float(recovery.mean())
    decrease = before_mean - recovery_mean
    status = (ResponseStatus.POSITIVE_RESPONSE if decrease >= 10
              else ResponseStatus.NO_POSITIVE_RESPONSE)
    return QuestEvaluation(
        status, before_mean, recovery_mean, decrease,
        "Respons awal dari perubahan skor; hubungan waktu tidak membuktikan aktivitas sebagai penyebab.",
    )


class RewardTracker:
    WEEKLY_LIMIT = 3
    SUGGESTIONS = ("Buah segar", "Yogurt tanpa gula tambahan", "Teh herbal tanpa gula")

    def __init__(self, history: Iterable[RewardClaim] = ()) -> None:
        self._claims: list[RewardClaim] = list(history)

    @property
    def history(self) -> tuple[RewardClaim, ...]:
        return tuple(self._claims)

    def offer(self, at: datetime | None = None, soft_mode: bool = False) -> RewardOffer:
        at = _aware(at or datetime.now(timezone.utc), "reward")
        remaining = self.WEEKLY_LIMIT - self._count_this_week(at)
        return RewardOffer(
            available=remaining > 0,
            remaining_this_week=remaining,
            suggestions=self.SUGGESTIONS,
            emphasized=not soft_mode,
            label="Demo lokal saja; tidak ada transaksi atau integrasi layanan makanan.",
        )

    def claim(self, choice: str, at: datetime | None = None) -> RewardClaim:
        at = _aware(at or datetime.now(timezone.utc), "reward")
        if choice not in self.SUGGESTIONS:
            raise ValueError("Pilih salah satu reward demonstrasi yang tersedia")
        if self._count_this_week(at) >= self.WEEKLY_LIMIT:
            raise ValueError("Batas reward opsional minggu ini sudah tercapai")
        claim = RewardClaim(choice, at)
        self._claims.append(claim)
        return claim

    def _count_this_week(self, at: datetime) -> int:
        week = at.isocalendar()[:2]
        return sum(claim.claimed_at.isocalendar()[:2] == week for claim in self._claims)
