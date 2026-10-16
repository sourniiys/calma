import sys
import pathlib
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from tahap3_deteksi.deteksi import StressEvent
import pytest

from tahap4_interaksi import ConsentPurpose
from tahap5_stress_quest import ActivitySource, EnergyLevel, QuestStatus, recommend_quest
from tahap6_keamanan import PersonalSafetyPlan, SafetyContact, TrustedContactEscalation
from tahap6_keamanan.escalation import EscalationStatus
from calma_backend.security import LocalDataCipher
from calma_backend.database import SQLiteRepository


def test_consent_latest_value_and_history_survive_reopen(tmp_path):
    path = tmp_path / "calma.sqlite3"
    repo = SQLiteRepository(path)
    at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    repo.grant(ConsentPurpose.TRUSTED_CONTACT, at)
    repo.revoke(ConsentPurpose.TRUSTED_CONTACT, datetime(2026, 1, 2, tzinfo=timezone.utc))
    assert not repo.has_consent(ConsentPurpose.TRUSTED_CONTACT)
    repo.close()

    reopened = SQLiteRepository(path)
    history = reopened.consent_history(ConsentPurpose.TRUSTED_CONTACT)
    assert [record.granted for record in history] == [True, False]
    assert not reopened.has_consent(ConsentPurpose.TRUSTED_CONTACT)
    reopened.close()


def test_stress_event_confirmation_is_persisted_and_one_time(tmp_path):
    repo = SQLiteRepository(tmp_path / "events.sqlite3")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    event_id = repo.add_stress_event(StressEvent(start, start, start, 82, False))
    assert repo.get_stress_event(event_id)["status"] == "pending"
    confirmed = repo.confirm_stress_event(event_id, "yes", start)
    assert confirmed["status"] == "confirmed_by_user"
    assert repo.confirm_stress_event(event_id, "no", start) is None
    assert repo.confirmed_stress_days() == ["2026-01-01"]
    assert repo.add_stress_event(StressEvent(start, start, start, 82, False)) == event_id
    assert len(repo.list_stress_events()) == 1
    repo.close()


def test_quest_history_is_restored_as_domain_objects(tmp_path):
    repo = SQLiteRepository(tmp_path / "quests.sqlite3")
    option = recommend_quest(EnergyLevel.LOW).option
    at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    quest_id = repo.create_quest(option, QuestStatus.IN_PROGRESS, at, ActivitySource.USER_REPORTED)
    completed = repo.complete_quest(quest_id, datetime(2026, 1, 1, 0, 20, tzinfo=timezone.utc))
    assert completed["status"] == QuestStatus.COMPLETED.value
    history = repo.quest_history()
    assert len(history) == 1
    assert history[0].option.activity == option.activity
    assert history[0].source == ActivitySource.USER_REPORTED
    repo.close()


def test_safety_plan_is_persisted_and_requires_storage_consent(tmp_path):
    path = tmp_path / "safety.sqlite3"
    repo = SQLiteRepository(path)
    plan = PersonalSafetyPlan(
        warning_signs=("sulit tidur",),
        helpful_steps=("hubungi teman",),
        trusted_contact=SafetyContact("Dina", "+628123456789"),
    )
    with pytest.raises(PermissionError, match="Consent penyimpanan"):
        repo.update_plan(plan)

    repo.grant(ConsentPurpose.DATA_STORAGE)
    saved = repo.update_plan(plan)
    assert saved.warning_signs == ("sulit tidur",)
    repo.close()

    reopened = SQLiteRepository(path)
    restored = reopened.get_plan()
    assert restored.trusted_contact == plan.trusted_contact
    assert restored.helpful_steps == plan.helpful_steps
    reopened.revoke(ConsentPurpose.DATA_STORAGE)
    with pytest.raises(PermissionError):
        reopened.update_plan(plan)
    reopened.delete_plan()
    assert reopened.get_plan() is None
    reopened.close()


def test_sqlite_repository_implements_escalation_store_and_persists_cooldown(tmp_path):
    path = tmp_path / "escalation.sqlite3"
    repo = SQLiteRepository(path)
    repo.grant(ConsentPurpose.DATA_STORAGE)
    repo.grant(ConsentPurpose.TRUSTED_CONTACT)
    repo.update_plan(PersonalSafetyPlan(trusted_contact=SafetyContact("Dina", "+628123456789")))

    class NoDelivery:
        def send(self, phone, message):
            raise AssertionError("Waktu belum cukup; provider tidak boleh dipanggil")

    service = TrustedContactEscalation(repo, repo, NoDelivery())
    from datetime import datetime, timedelta, timezone
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert service.start_countdown(start).status == EscalationStatus.COUNTDOWN_STARTED
    service = TrustedContactEscalation(repo, repo, NoDelivery())
    assert service.pending.due_at == start + timedelta(minutes=10)
    assert service.complete(start + timedelta(minutes=10)).status == EscalationStatus.DELIVERY_FAILED
    assert repo.get_pending_countdown() is None
    assert repo.latest_delivery_attempt()["status"] == "failed"
    repo.close()

    reopened = SQLiteRepository(path)
    assert reopened.within_delivery_limit(start + timedelta(hours=23))
    assert not reopened.within_delivery_limit(start + timedelta(hours=24, minutes=10))
    reopened.close()


def test_reward_limit_is_transactional_and_persists_across_reopen(tmp_path):
    from datetime import timedelta

    path = tmp_path / "rewards.sqlite3"
    repo = SQLiteRepository(path)
    with pytest.raises(PermissionError, match="Consent penyimpanan"):
        repo.claim_reward("Buah segar", datetime(2026, 1, 5, tzinfo=timezone.utc))
    repo.grant(ConsentPurpose.DATA_STORAGE)
    start = datetime(2026, 1, 5, tzinfo=timezone.utc)
    for day in range(3):
        claim = repo.claim_reward("Buah segar", start + timedelta(days=day))
        assert claim.status == "DEMO_ONLY"
    repo.close()

    reopened = SQLiteRepository(path)
    assert len(reopened.reward_history()) == 3
    with pytest.raises(ValueError, match="Batas reward"):
        reopened.claim_reward("Buah segar", start + timedelta(days=4))
    reopened.close()


def test_legacy_safety_plan_migration_requires_consent_and_is_idempotent(tmp_path):
    import json
    from calma_backend.services import CalmaBackendService

    legacy = tmp_path / "legacy-plan.json"
    legacy_payload = {
        "plan": {
            "warning_signs": ["cemas"],
            "helpful_steps": ["hubungi teman"],
            "trusted_contact": {"name": "Dina", "phone": "+628123456789"},
            "professional_support": "Klinik",
            "emergency_contact": {"name": "Keluarga", "phone": "+628987654321"},
            "updated_at": "2026-01-01T00:00:00+00:00",
        },
        "last_attempt_at": "2026-01-01T01:00:00+00:00",
        "last_attempt_status": "failed",
    }
    legacy.write_text(json.dumps(legacy_payload), encoding="utf-8")
    repo = SQLiteRepository(tmp_path / "migration.sqlite3")
    service = CalmaBackendService(repo, data_dir=tmp_path / "fit",
                                  daily_csv=tmp_path / "daily.csv",
                                  model_metadata=tmp_path / "metadata.json")
    with pytest.raises(PermissionError, match="Consent"):
        service.migrate_legacy_safety_plan(legacy)
    repo.grant(ConsentPurpose.DATA_STORAGE)
    first = service.migrate_legacy_safety_plan(legacy)
    second = service.migrate_legacy_safety_plan(legacy)
    assert first == {"migrated": True, "source_preserved": True}
    assert second == {"migrated": False, "source_preserved": True}
    assert repo.get_plan().warning_signs == ("cemas",)
    assert repo.latest_delivery_attempt()["status"] == "failed"
    assert legacy.exists()
    repo.close()


def test_sensitive_calma_rows_are_encrypted_at_rest_and_restore_with_key(tmp_path):
    from cryptography.fernet import Fernet

    path = tmp_path / "health.enc"
    cipher = LocalDataCipher(Fernet.generate_key())
    repo = SQLiteRepository(path, cipher=cipher)
    repo.grant(ConsentPurpose.DATA_STORAGE)
    repo.add_mood_checkin("low", "low")
    marker = "private-safety-marker-90731"
    repo.update_plan(PersonalSafetyPlan(warning_signs=(marker,)))
    repo.close()

    encrypted = path.read_bytes()
    assert not encrypted.startswith(b"SQLite format 3")
    assert marker.encode("utf-8") not in encrypted

    reopened = SQLiteRepository(path, cipher=cipher)
    assert reopened.latest_mood_checkin()["mood"] == "low"
    assert reopened.get_plan().warning_signs == (marker,)
    reopened.close()


def test_only_one_active_quest_is_allowed(tmp_path):
    repo = SQLiteRepository(tmp_path / "one-active.sqlite3")
    option = recommend_quest(EnergyLevel.LOW).option
    at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    repo.create_quest(option, QuestStatus.IN_PROGRESS, at, ActivitySource.USER_REPORTED)
    with pytest.raises(ValueError, match="quest aktif"):
        repo.create_quest(option, QuestStatus.IN_PROGRESS, at, ActivitySource.USER_REPORTED)
    repo.close()


def test_legacy_safety_migration_without_user_specific_path_does_nothing(tmp_path):
    from calma_backend.services import CalmaBackendService

    repo = SQLiteRepository(tmp_path / "migration-no-path.sqlite3")
    repo.grant(ConsentPurpose.DATA_STORAGE)
    service = CalmaBackendService(repo, data_dir=tmp_path / "fit",
                                  daily_csv=tmp_path / "daily.csv",
                                  model_metadata=tmp_path / "metadata.json")
    result = service.migrate_legacy_safety_plan()
    assert result == {"migrated": False, "reason": "user_specific_legacy_path_not_configured"}
    repo.close()