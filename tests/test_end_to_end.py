import sys
import pathlib
from datetime import datetime, timedelta, timezone

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from tahap3_deteksi.deteksi import detect_events
from tahap4_interaksi import (
    ConsentManager, ConsentPurpose, Energy, Mood, MoodSettings,
    UserConfirmation, UserState, UserStateMachine,
)
from tahap5_stress_quest import (
    ActivitySource, EnergyLevel, QuestTier, QuestTracker, ResponseStatus,
    recommend_quest,
)
from tahap6_keamanan import (
    DeliveryResult, EscalationStatus, PersonalSafetyPlan, SafetyContact,
    SafetyPlanStore, TrustedContactEscalation, open_crisis_access,
)
from tahap7_chatbot import CalmaChatbot


class NoNetworkProvider:
    def __init__(self):
        self.calls = []

    def send(self, phone, message):
        self.calls.append((phone, message))
        return DeliveryResult(True, "simulation", "local test only")


def test_user_path_from_potential_event_to_personalized_support(tmp_path):
    consent = ConsentManager()
    for purpose in (ConsentPurpose.DATA_STORAGE, ConsentPurpose.TRUSTED_CONTACT,
                    ConsentPurpose.MOOD_PERSONALIZATION):
        consent.grant(purpose)
    store = SafetyPlanStore(consent, tmp_path / "plan.json")
    store.update_plan(PersonalSafetyPlan(
        helpful_steps=("Duduk di tempat tenang",),
        trusted_contact=SafetyContact("Teman", "+628123456789"),
        emergency_contact=SafetyContact("Keluarga", "+628987654321"),
    ))

    # Nilai berikut sintetis khusus untuk tes, bukan data dari Garmin.
    timestamps = pd.date_range("2026-04-01 10:00", periods=17, freq="min", tz="UTC")
    synthetic_scores = pd.Series([50] * 5 + [75] * 12, index=timestamps)
    events = detect_events(synthetic_scores)
    assert len(events) == 1
    state = UserStateMachine()
    state.request_confirmation(events[0])
    state.answer_confirmation(UserConfirmation.YES)
    assert state.state == UserState.STRESS_CONFIRMED

    mood = MoodSettings()
    mood.check_in(Mood.LOW, Energy.LOW)
    mood.set_soft_mode(True)
    initial_recommendation = recommend_quest(EnergyLevel.LOW, soft_mode=mood.soft_mode)
    assert initial_recommendation.option.tier == QuestTier.MICRO

    tracker = QuestTracker()
    started = datetime(2026, 4, 1, 11, 0, tzinfo=timezone.utc)
    session = tracker.start(initial_recommendation, ActivitySource.USER_REPORTED, started)
    tracker.complete(started + timedelta(minutes=30))
    recovery_index = pd.date_range(started - timedelta(minutes=10), periods=70,
                                   freq="min")
    recovery_scores = pd.Series(80.0, index=recovery_index)
    recovery_scores.loc[pd.date_range("2026-04-01 11:50", periods=10,
                                      freq="min", tz="UTC")] = 65
    evaluation = tracker.evaluate(session, recovery_scores)
    assert evaluation.status == ResponseStatus.POSITIVE_RESPONSE

    next_recommendation = recommend_quest(EnergyLevel.LOW, history=tracker.history,
                                          soft_mode=mood.soft_mode)
    assert next_recommendation.option.activity == session.option.activity
    chatbot = CalmaChatbot(consent, store, mood)
    chat = chatbot.respond("Aku ingin ditemani", just_listen=True,
                           request_quest=True, energy=EnergyLevel.LOW)
    assert chat.just_listen
    assert chat.mood_context.mood == "low"
    assert chat.crisis_access is None
    crisis = open_crisis_access(store)
    assert crisis.emergency_number == "119"
    assert crisis.emergency_contact.name == "Keluarga"


def test_nonpositive_evaluation_can_start_cancellable_simulated_escalation(tmp_path):
    consent = ConsentManager()
    consent.grant(ConsentPurpose.DATA_STORAGE)
    consent.grant(ConsentPurpose.TRUSTED_CONTACT)
    store = SafetyPlanStore(consent, tmp_path / "plan.json")
    store.update_plan(PersonalSafetyPlan(
        trusted_contact=SafetyContact("Teman", "+628123456789"),
    ))
    provider = NoNetworkProvider()
    escalation = TrustedContactEscalation(consent, store, provider)

    start = datetime(2026, 4, 2, 11, 0, tzinfo=timezone.utc)
    recommendation = recommend_quest(EnergyLevel.MEDIUM)
    tracker = QuestTracker()
    session = tracker.start(recommendation, at=start)
    tracker.complete(start + timedelta(minutes=30))
    score_index = pd.date_range(start - timedelta(minutes=10), periods=70, freq="min")
    evaluation = tracker.evaluate(session, pd.Series(80.0, index=score_index))
    assert evaluation.status == ResponseStatus.NO_POSITIVE_RESPONSE

    countdown = escalation.start_after_evaluation(evaluation, start + timedelta(hours=1))
    assert countdown.status == EscalationStatus.COUNTDOWN_STARTED
    assert escalation.cancel().status == EscalationStatus.CANCELLED
    assert provider.calls == []