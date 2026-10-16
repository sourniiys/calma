"""Kontrak request/response API CALMA."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from tahap4_interaksi import ConsentPurpose, Energy, Mood, UserConfirmation
from tahap5_stress_quest import ActivitySource, ActivityType, EnergyLevel, UserCondition


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AccountRegister(ApiModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)


class AccountLogin(ApiModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)


class AccountCreated(ApiModel):
    user_id: str


class TokenResponse(ApiModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime


class ConsentUpdate(ApiModel):
    granted: bool


class ConsentStatus(ApiModel):
    purpose: ConsentPurpose
    granted: bool
    changed_at: datetime | None = None


class BaselineStatus(ApiModel):
    status: Literal["consent_required", "not_ready", "provisional", "ready", "unavailable"]
    ready: bool
    days_covered: int = 0
    required_days: int = 7
    valid_measurements: int = 0
    data_start: datetime | None = None
    data_end: datetime | None = None
    motion_checked: bool = False
    reason: str
    score_is_clinical: Literal[False] = False


class StressEventOut(ApiModel):
    id: int
    started_at: datetime
    alert_time: datetime
    ended_at: datetime
    peak: float
    motion_checked: bool
    status: str
    confirmation: str | None = None
    confirmed_at: datetime | None = None


class StressConfirmation(ApiModel):
    answer: UserConfirmation


class StressAnalysisOut(ApiModel):
    baseline: BaselineStatus
    created_event_ids: list[int]
    event_count: int
    monitoring_mode: Literal["historical_file_analysis"] = "historical_file_analysis"


class MoodCheckInRequest(ApiModel):
    mood: Mood
    energy: Energy


class MoodCheckInOut(ApiModel):
    id: int
    mood: Mood
    energy: Energy
    recorded_at: datetime
    soft_mode_suggested: bool


class SoftModeUpdate(ApiModel):
    enabled: bool


class QuestRecommendationRequest(ApiModel):
    energy: EnergyLevel
    condition: UserCondition = UserCondition.OKAY
    preferred_activity: ActivityType | None = None


class QuestStartRequest(QuestRecommendationRequest):
    source: ActivitySource = ActivitySource.USER_REPORTED


class QuestEvaluationRequest(ApiModel):
    recovery_minutes: int = Field(default=30, ge=30, le=60)


class QuestRecordOut(ApiModel):
    id: int
    tier: str
    activity: str
    title: str
    target: str
    instructions: str
    status: str
    recorded_at: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None
    source: str | None = None
    evaluation_status: str | None = None
    before_mean: float | None = None
    recovery_mean: float | None = None
    decrease: float | None = None
    evaluation_note: str | None = None


class QuestRecommendationOut(ApiModel):
    tier: str | None
    activity: str | None
    title: str | None
    target: str | None
    instructions: str | None
    reason: str


class SafetyContactRequest(ApiModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=6, max_length=40)


class SafetyPlanRequest(ApiModel):
    warning_signs: list[str] = Field(default_factory=list, max_length=20)
    helpful_steps: list[str] = Field(default_factory=list, max_length=20)
    trusted_contact: SafetyContactRequest | None = None
    professional_support: str = Field(default="", max_length=500)
    emergency_contact: SafetyContactRequest | None = None


class ChatTurn(ApiModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=1000)


class ChatRequest(ApiModel):
    message: str = Field(max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)
    just_listen: bool = False
    request_quest: bool = False
    energy: EnergyLevel | None = None


class ChatResponse(ApiModel):
    text: str
    mode: str
    just_listen: bool
    crisis_access: bool
    quest: QuestRecommendationOut | None = None


class CrisisInformation(ApiModel):
    emergency_number: Literal["119"] = "119"
    message: str
    scope_note: str
    safety_plan: SafetyPlanRequest | None = None


class EscalationStart(ApiModel):
    status: str
    message: str
    due_at: datetime | None = None
    mode: str | None = None


class RewardOfferOut(ApiModel):
    available: bool
    remaining_this_week: int
    suggestions: tuple[str, ...]
    emphasized: bool
    label: str


class RewardClaimRequest(ApiModel):
    choice: Literal["Buah segar", "Yogurt tanpa gula tambahan", "Teh herbal tanpa gula"]


class RewardClaimOut(ApiModel):
    choice: str
    claimed_at: datetime
    status: Literal["DEMO_ONLY"]


class SafetyPlanMigrationOut(ApiModel):
    migrated: bool
    reason: str | None = None
    source_preserved: bool = True
