import sys
import pathlib
from datetime import date, datetime, timedelta, timezone

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from tahap4_interaksi import ConsentManager, ConsentPurpose
from tahap5_stress_quest import QuestEvaluation, ResponseStatus
from tahap6_keamanan import (
    DeliveryResult, EscalationStatus, PersonalSafetyPlan, SafetyContact,
    SafetyPlanStore, TrustedContactEscalation, open_crisis_access,
)


class RecordingProvider:
    def __init__(self, success=True, mode="simulation"):
        self.success = success
        self.mode = mode
        self.calls = []

    def send(self, phone, message):
        self.calls.append((phone, message))
        return DeliveryResult(self.success, self.mode, "test provider")


def _setup(tmp_path, provider=None, grant_contact=True, grant_storage=True):
    consent = ConsentManager()
    if grant_contact:
        consent.grant(ConsentPurpose.TRUSTED_CONTACT)
    if grant_storage:
        consent.grant(ConsentPurpose.DATA_STORAGE)
    store = SafetyPlanStore(consent, tmp_path / "safety.json")
    if grant_storage:
        store.update_plan(PersonalSafetyPlan(
            warning_signs=("sulit tidur",), helpful_steps=("hubungi teman",),
            trusted_contact=SafetyContact("Dina", "+628123456789"),
            emergency_contact=SafetyContact("Keluarga", "+628987654321"),
        ))
    provider = provider or RecordingProvider()
    return consent, store, provider, TrustedContactEscalation(consent, store, provider)


def test_safety_plan_requires_storage_consent_and_can_be_reviewed_and_deleted(tmp_path):
    consent = ConsentManager()
    store = SafetyPlanStore(consent, tmp_path / "private.json")
    plan = PersonalSafetyPlan(warning_signs=("cemas",))
    with pytest.raises(PermissionError, match="Consent penyimpanan"):
        store.update_plan(plan)

    consent.grant(ConsentPurpose.DATA_STORAGE)
    store.update_plan(plan)
    reloaded = SafetyPlanStore(consent, tmp_path / "private.json")
    assert reloaded.get_plan().warning_signs == ("cemas",)
    consent.revoke(ConsentPurpose.DATA_STORAGE)
    assert reloaded.get_plan().warning_signs == ("cemas",)
    with pytest.raises(PermissionError):
        reloaded.update_plan(plan)
    reloaded.delete_plan()
    assert reloaded.get_plan() is None


def test_countdown_requires_contact_and_both_consents(tmp_path):
    _, _, _, no_consent = _setup(tmp_path / "no-consent", grant_contact=False)
    assert no_consent.start_countdown().status == EscalationStatus.BLOCKED_CONSENT

    consent = ConsentManager()
    consent.grant(ConsentPurpose.TRUSTED_CONTACT)
    consent.grant(ConsentPurpose.DATA_STORAGE)
    store = SafetyPlanStore(consent, tmp_path / "no-contact.json")
    store.update_plan(PersonalSafetyPlan())
    service = TrustedContactEscalation(consent, store, RecordingProvider())
    assert service.start_countdown().status == EscalationStatus.BLOCKED_CONTACT


def test_countdown_waits_ten_minutes_and_sends_only_simulated_support_message(tmp_path):
    _, _, provider, service = _setup(tmp_path)
    start = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    result = service.start_countdown(start)
    assert result.status == EscalationStatus.COUNTDOWN_STARTED
    assert result.due_at == start + timedelta(minutes=10)
    assert service.complete(start + timedelta(minutes=9)).status == EscalationStatus.COUNTDOWN_ACTIVE
    assert provider.calls == []

    completed = service.complete(start + timedelta(minutes=10))
    assert completed.status == EscalationStatus.SIMULATED_ONLY
    assert "tidak ada pesan nyata" in completed.message
    assert provider.calls == [("+628123456789", "Lagi butuh ditemani")]
    assert "stress" not in provider.calls[0][1].lower()
    assert "hr" not in provider.calls[0][1].lower()


def test_countdown_can_be_cancelled_without_calling_provider(tmp_path):
    _, _, provider, service = _setup(tmp_path)
    assert service.start_countdown().status == EscalationStatus.COUNTDOWN_STARTED
    assert service.cancel().status == EscalationStatus.CANCELLED
    assert service.complete().status == EscalationStatus.NO_COUNTDOWN
    assert provider.calls == []


def test_consent_revoked_during_countdown_blocks_provider(tmp_path):
    consent, _, provider, service = _setup(tmp_path)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    service.start_countdown(now)
    consent.revoke(ConsentPurpose.TRUSTED_CONTACT, now + timedelta(minutes=3))

    result = service.complete(now + timedelta(minutes=10))
    assert result.status == EscalationStatus.BLOCKED_CONSENT
    assert provider.calls == []


def test_one_message_per_24_hours_is_persisted(tmp_path):
    consent, store, provider, service = _setup(tmp_path)
    start = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    service.start_countdown(start)
    assert service.complete(start + timedelta(minutes=10)).status == EscalationStatus.SIMULATED_ONLY

    reloaded = SafetyPlanStore(consent, store.path)
    next_service = TrustedContactEscalation(consent, reloaded, provider)
    assert next_service.start_countdown(start + timedelta(hours=23)).status == EscalationStatus.RATE_LIMITED
    assert next_service.start_countdown(start + timedelta(hours=24, minutes=10)).status == EscalationStatus.COUNTDOWN_STARTED


def test_provider_failure_never_reports_delivery_success(tmp_path):
    provider = RecordingProvider(success=False, mode="fake")
    _, store, _, service = _setup(tmp_path, provider=provider)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    service.start_countdown(now)
    result = service.complete(now + timedelta(minutes=10))

    assert result.status == EscalationStatus.DELIVERY_FAILED
    assert "tidak menyatakan" in result.message
    assert store.last_attempt_status == "failed"
    assert len(provider.calls) == 1


def test_countdown_is_offered_only_after_sufficient_nonpositive_evaluation(tmp_path):
    _, _, _, service = _setup(tmp_path)
    insufficient = QuestEvaluation(ResponseStatus.INSUFFICIENT_DATA, None, None, None, "not enough")
    positive = QuestEvaluation(ResponseStatus.POSITIVE_RESPONSE, 80, 60, 20, "response")
    no_positive = QuestEvaluation(ResponseStatus.NO_POSITIVE_RESPONSE, 80, 75, 5, "response")

    assert service.start_after_evaluation(insufficient).status == EscalationStatus.INSUFFICIENT_DATA
    assert service.start_after_evaluation(positive).status == EscalationStatus.NOT_OFFERED
    assert service.start_after_evaluation(no_positive).status == EscalationStatus.COUNTDOWN_STARTED


def test_repeated_stress_uses_three_distinct_calendar_days_and_requires_consent():
    from tahap6_keamanan import repeated_stress_offer

    consent = ConsentManager()
    same_day = [date(2026, 1, 1), date(2026, 1, 1), date(2026, 1, 1)]
    assert not repeated_stress_offer(same_day, consent).eligible

    three_days = [datetime(2026, 1, day, 12, tzinfo=timezone.utc) for day in (1, 2, 3)]
    offer = repeated_stress_offer(three_days, consent)
    assert offer.eligible
    assert not offer.professional_support_consent
    assert not offer.booking_available
    consent.grant(ConsentPurpose.PROFESSIONAL_SUPPORT)
    assert repeated_stress_offer(three_days, consent).professional_support_consent


def test_crisis_access_is_direct_and_includes_safety_plan_and_119(tmp_path):
    _, store, _, _ = _setup(tmp_path)
    access = open_crisis_access(store)
    assert access.emergency_number == "119"
    assert access.safety_plan.warning_signs == ("sulit tidur",)
    assert access.emergency_contact.name == "Keluarga"
    assert "bukan layanan darurat" in access.scope_note
