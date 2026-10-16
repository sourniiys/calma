import sys
import pathlib
from datetime import datetime, timezone

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from tahap3_deteksi.deteksi import StressEvent
from tahap4_interaksi import (
    ConsentManager, ConsentPurpose, Energy, Mood, MoodSettings,
    UserConfirmation, UserState, UserStateMachine,
)


def _event() -> StressEvent:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return StressEvent(start, start, start, 82.0)


def test_consent_defaults_closed_and_persists_revocation(tmp_path):
    path = tmp_path / "privacy" / "consent.json"
    manager = ConsentManager(path)
    purpose = ConsentPurpose.TRUSTED_CONTACT
    assert not manager.has_consent(purpose)

    manager.grant(purpose, datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert manager.has_consent(purpose)
    manager.revoke(purpose, datetime(2026, 1, 2, tzinfo=timezone.utc))

    reloaded = ConsentManager(path)
    assert not reloaded.has_consent(purpose)
    assert [item.granted for item in reloaded.history_for(purpose)] == [True, False]


def test_consent_rejects_naive_timestamp():
    manager = ConsentManager()
    with pytest.raises(ValueError, match="zona waktu"):
        manager.grant(ConsentPurpose.DATA_COLLECTION, datetime(2026, 1, 1))


def test_consent_write_failure_does_not_leave_grant_active(tmp_path):
    blocker = tmp_path / "not_a_directory"
    blocker.write_text("x", encoding="utf-8")
    manager = ConsentManager(blocker / "consent.json")

    with pytest.raises(OSError):
        manager.grant(ConsentPurpose.TRUSTED_CONTACT)

    assert not manager.has_consent(ConsentPurpose.TRUSTED_CONTACT)
    assert manager.history == ()


def test_low_mood_suggests_but_does_not_enable_soft_mode():
    settings = MoodSettings()
    entry = settings.check_in(Mood.LOW, Energy.LOW)
    assert entry.soft_mode_suggested
    assert not settings.soft_mode
    assert not settings.interface_preferences().fewer_notifications

    settings.set_soft_mode(True)
    preferences = settings.interface_preferences()
    assert preferences.soft_mode
    assert preferences.fewer_notifications
    assert preferences.minimal_animation
    assert preferences.one_primary_action
    assert preferences.deemphasize_scores_and_rewards
    assert preferences.prefer_light_activities


@pytest.mark.parametrize(
    ("answer", "expected_state"),
    [
        (UserConfirmation.YES, UserState.STRESS_CONFIRMED),
        (UserConfirmation.NO, UserState.STRESS_DENIED),
        (UserConfirmation.UNSURE, UserState.STRESS_UNSURE),
    ],
)
def test_user_confirmation_transitions(answer, expected_state):
    machine = UserStateMachine()
    event = _event()
    machine.request_confirmation(event)
    assert machine.state == UserState.AWAITING_STRESS_CONFIRMATION

    record = machine.answer_confirmation(answer)
    assert record.event is event
    assert machine.state == expected_state
    assert machine.pending_event is None
    assert len(machine.confirmation_history) == 1


def test_confirmation_requires_pending_event_and_prevents_overlapping_prompts():
    machine = UserStateMachine()
    with pytest.raises(RuntimeError, match="Tidak ada"):
        machine.answer_confirmation("yes")

    machine.request_confirmation(_event())
    with pytest.raises(RuntimeError, match="belum dijawab"):
        machine.request_confirmation(_event())
