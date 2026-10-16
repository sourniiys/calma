import sys
import pathlib
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from tahap5_stress_quest import (
    ActivitySource, ActivityType, EnergyLevel, QuestRecommendation, QuestStatus,
    QuestTier, ResponseStatus, RewardTracker, UserCondition, evaluate_recovery,
    get_option, recommend_quest,
)
from tahap4_interaksi import Energy, Mood, MoodSettings
from tahap5_stress_quest.quest import QuestTracker


def test_recommendations_offer_each_proposal_tier_and_adapt_to_energy():
    assert get_option(QuestTier.MICRO).target == "10 menit"
    assert get_option(QuestTier.STANDARD).target == "5.000 langkah"
    assert get_option(QuestTier.FULL, ActivityType.GYM).target == "minimal 60 menit"
    assert get_option(QuestTier.FULL, ActivityType.SWIM).target == "minimal 90 menit"
    assert recommend_quest(EnergyLevel.LOW).option.tier == QuestTier.MICRO
    assert recommend_quest(EnergyLevel.MEDIUM).option.tier == QuestTier.STANDARD
    assert recommend_quest(EnergyLevel.HIGH, preferred_activity=ActivityType.SWIM).option.activity == ActivityType.SWIM


def test_unwell_condition_and_soft_mode_avoid_strenuous_recommendation():
    assert recommend_quest(EnergyLevel.HIGH, condition=UserCondition.INJURED).option is None
    soft = recommend_quest(EnergyLevel.HIGH, preferred_activity=ActivityType.GYM, soft_mode=True)
    assert soft.option.tier == QuestTier.MICRO


def test_user_controlled_soft_mode_from_tahap4_reaches_quest_recommender():
    settings = MoodSettings()
    settings.check_in(Mood.LOW, Energy.LOW)
    assert not settings.soft_mode
    settings.set_soft_mode(True)

    recommendation = recommend_quest(EnergyLevel.HIGH, preferred_activity=ActivityType.GYM,
                                     soft_mode=settings.soft_mode)
    assert recommendation.option.tier == QuestTier.MICRO


def test_tracker_records_timestamps_source_and_penalty_free_skip():
    tracker = QuestTracker()
    recommendation = recommend_quest(EnergyLevel.MEDIUM)
    started = datetime(2026, 1, 1, 8, tzinfo=timezone.utc)
    session = tracker.start(recommendation, ActivitySource.DEVICE_DETECTED, started)
    completed = tracker.complete(started + timedelta(minutes=25))
    assert completed.status == QuestStatus.COMPLETED
    assert completed.source == ActivitySource.DEVICE_DETECTED
    assert completed.started_at == started
    assert completed.ended_at == started + timedelta(minutes=25)

    skipped = tracker.skip(recommendation, started + timedelta(days=1))
    assert skipped.status == QuestStatus.SKIPPED
    assert skipped.started_at is None
    assert len(tracker.history) == 2


def test_recovery_evaluation_uses_exact_pre_and_recovery_windows():
    start = pd.Timestamp("2026-01-01 10:00", tz="UTC")
    end = pd.Timestamp("2026-01-01 10:30", tz="UTC")
    index = pd.date_range(start - pd.Timedelta(minutes=10), periods=70, freq="min")
    values = pd.Series(80.0, index=index)
    values.loc[pd.date_range("2026-01-01 10:50", periods=10, freq="min", tz="UTC")] = 65

    result = evaluate_recovery(start.to_pydatetime(), end.to_pydatetime(), values, recovery_minutes=30)
    assert result.status == ResponseStatus.POSITIVE_RESPONSE
    assert result.before_mean == 80
    assert result.recovery_mean == 65
    assert result.decrease == 15
    assert "tidak membuktikan" in result.note


def test_missing_recovery_minute_is_insufficient_not_success():
    start = pd.Timestamp("2026-01-01 10:00", tz="UTC")
    end = pd.Timestamp("2026-01-01 10:30", tz="UTC")
    index = pd.date_range(start - pd.Timedelta(minutes=10), end + pd.Timedelta(minutes=29), freq="min")
    values = pd.Series(80.0, index=index).drop(pd.Timestamp("2026-01-01 10:55", tz="UTC"))
    result = evaluate_recovery(start.to_pydatetime(), end.to_pydatetime(), values)
    assert result.status == ResponseStatus.INSUFFICIENT_DATA
    assert result.decrease is None


def test_tracker_evaluation_informs_future_recommendations():
    tracker = QuestTracker()
    recommendation = recommend_quest(EnergyLevel.MEDIUM)
    start = pd.Timestamp("2026-01-01 10:00", tz="UTC")
    session = tracker.start(recommendation, at=start.to_pydatetime())
    tracker.complete((start + pd.Timedelta(minutes=30)).to_pydatetime())
    index = pd.date_range(start - pd.Timedelta(minutes=10), periods=70, freq="min")
    values = pd.Series(80.0, index=index)
    values.loc[pd.date_range("2026-01-01 10:50", periods=10, freq="min", tz="UTC")] = 65
    tracker.evaluate(session, values)

    next_choice = recommend_quest(EnergyLevel.MEDIUM, history=tracker.history)
    assert next_choice.option.activity == session.option.activity


def test_reward_is_optional_demo_and_capped_at_three_per_week():
    tracker = RewardTracker()
    now = datetime(2026, 1, 5, tzinfo=timezone.utc)
    assert tracker.offer(now, soft_mode=True).available
    assert not tracker.offer(now, soft_mode=True).emphasized
    assert "tidak ada transaksi" in tracker.offer(now).label
    for offset in range(3):
        tracker.claim(tracker.SUGGESTIONS[0], now + timedelta(days=offset))
    assert not tracker.offer(now).available
    with pytest.raises(ValueError, match="Batas reward"):
        tracker.claim(tracker.SUGGESTIONS[0], now + timedelta(days=4))