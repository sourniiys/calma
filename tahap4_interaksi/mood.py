"""Check-in mood dan preferensi antarmuka yang tetap dikendalikan pengguna."""
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class Mood(str, Enum):
    GOOD = "good"
    OKAY = "okay"
    LOW = "low"


class Energy(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class MoodCheckIn:
    mood: Mood
    energy: Energy
    recorded_at: datetime

    def __post_init__(self) -> None:
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("Waktu check-in harus memiliki zona waktu")

    @property
    def soft_mode_suggested(self) -> bool:
        return self.mood == Mood.LOW or self.energy == Energy.LOW


@dataclass(frozen=True)
class InterfacePreferences:
    soft_mode: bool
    fewer_notifications: bool
    minimal_animation: bool
    one_primary_action: bool
    deemphasize_scores_and_rewards: bool
    prefer_light_activities: bool


class MoodSettings:
    def __init__(self) -> None:
        self.latest_check_in: MoodCheckIn | None = None
        self.soft_mode = False

    def check_in(self, mood: Mood | str, energy: Energy | str,
                 at: datetime | None = None) -> MoodCheckIn:
        self.latest_check_in = MoodCheckIn(
            mood=Mood(mood),
            energy=Energy(energy),
            recorded_at=at or datetime.now(timezone.utc),
        )
        return self.latest_check_in

    def set_soft_mode(self, enabled: bool) -> None:
        if not isinstance(enabled, bool):
            raise TypeError("Soft Mode harus diaktifkan atau dinonaktifkan secara eksplisit")
        self.soft_mode = enabled

    def interface_preferences(self) -> InterfacePreferences:
        enabled = self.soft_mode
        return InterfacePreferences(
            soft_mode=enabled,
            fewer_notifications=enabled,
            minimal_animation=enabled,
            one_primary_action=enabled,
            deemphasize_scores_and_rewards=enabled,
            prefer_light_activities=enabled,
        )
