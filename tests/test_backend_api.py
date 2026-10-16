import sys
import pathlib
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from calma_backend.api import create_app
from tahap3_deteksi.deteksi import StressEvent
from tahap5_stress_quest import (
    EnergyLevel, QuestEvaluation, QuestStatus, ResponseStatus, recommend_quest,
)


@pytest.fixture
def api_client(tmp_path):
    app = create_app(
        database_path=tmp_path / "api.sqlite3",
        data_dir=tmp_path / "missing-fit",
        daily_csv=tmp_path / "missing-daily.csv",
        model_metadata=tmp_path / "missing-model.json",
    )
    with TestClient(app) as client:
        user_id = _register_and_login(client, "test@example.com", "correct horse battery staple")
        client.app.state.test_user_id = user_id
        yield client


def _register_and_login(client, email, password):
    registered = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert registered.status_code == 201
    logged_in = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert logged_in.status_code == 200
    token = logged_in.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return registered.json()["user_id"]


def _repo(client):
    return client.app.state.context_for_user(client.app.state.test_user_id).repository


def _grant(client, purpose):
    response = client.put(f"/api/v1/consents/{purpose}", json={"granted": True})
    assert response.status_code == 200
    return response.json()


def test_health_openapi_and_model_evaluation_contract(api_client):
    health = api_client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    spec = api_client.get("/openapi.json").json()
    assert "/api/v1/chatbot/messages" in spec["paths"]
    assert "/api/v1/crisis-information" in spec["paths"]
    assert spec["components"]["securitySchemes"]["BearerAuth"]["scheme"] == "bearer"
    assert spec["paths"]["/api/v1/stress/events"]["get"]["security"] == [{"BearerAuth": []}]
    assert api_client.get("/api/v1/models/historical/evaluation").status_code == 404


def test_private_routes_reject_anonymous_and_auth_routes_are_public(tmp_path):
    app = create_app(database_path=tmp_path / "auth.sqlite3", data_dir=tmp_path / "fit",
                     daily_csv=tmp_path / "daily.csv", model_metadata=tmp_path / "model.json")
    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/openapi.json").status_code == 200
        for path in ("/api/v1/baseline/status", "/api/v1/consents", "/api/v1/stress/events",
                     "/api/v1/mood-checkins", "/api/v1/quests", "/api/v1/safety-plan",
                     "/api/v1/crisis-information", "/api/v1/support/status"):
            response = client.get(path)
            assert response.status_code == 401, (path, response.status_code)

        registered = client.post("/api/v1/auth/register", json={
            "email": "auth@example.com", "password": "correct horse battery staple",
        })
        assert registered.status_code == 201
        assert "password" not in registered.json()
        wrong = client.post("/api/v1/auth/login", json={
            "email": "auth@example.com", "password": "wrong horse battery staple",
        })
        assert wrong.status_code == 401
        assert "wrong horse" not in wrong.text
        login = client.post("/api/v1/auth/login", json={
            "email": "auth@example.com", "password": "correct horse battery staple",
        })
        assert login.status_code == 200
        assert login.json()["token_type"] == "bearer"
        logout = client.post("/api/v1/auth/logout", headers={
            "Authorization": f"Bearer {login.json()['access_token']}"})
        assert logout.status_code == 204


def test_startup_migrates_populated_plaintext_legacy_database(tmp_path, monkeypatch):
    import sqlite3

    legacy_path = tmp_path / "calma.sqlite3"
    connection = sqlite3.connect(legacy_path)
    connection.execute("CREATE TABLE old_health(value TEXT)")
    connection.execute("INSERT INTO old_health VALUES ('do not print this value')")
    connection.commit()
    connection.close()

    encrypted_path = tmp_path / "calma.enc"
    monkeypatch.setenv("CALMA_DATA_ENCRYPTION_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")

    app = create_app(database_path=encrypted_path)
    assert app.state.account_store.health_check()
    app.state.account_store.connection.execute("SELECT value FROM old_health").fetchone()[0] == "do not print this value"


def test_user_database_migrates_populated_plaintext_legacy_file(tmp_path, monkeypatch):
    import sqlite3

    monkeypatch.setenv("CALMA_DATA_ENCRYPTION_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
    app = create_app(database_path=tmp_path / "calma.enc")
    user_id = app.state.account_store.register("legacy@example.com", "correct horse battery staple")
    user_directory = tmp_path / "calma_users"
    user_directory.mkdir()
    legacy = user_directory / f"{user_id}.sqlite3"
    connection = sqlite3.connect(legacy)
    connection.execute("CREATE TABLE old_health(value TEXT)")
    connection.execute("INSERT INTO old_health VALUES ('private')")
    connection.commit()
    connection.close()

    context = app.state.context_for_user(user_id)
    assert context.repository.connection.execute("SELECT value FROM old_health").fetchone()[0] == "private"


def test_users_cannot_read_each_others_mood_or_quest_history(api_client):
    _grant(api_client, "data_storage")
    _grant(api_client, "mood_personalization")
    assert api_client.post("/api/v1/mood-checkins", json={
        "mood": "low", "energy": "low",
    }).status_code == 201
    assert api_client.post("/api/v1/quests", json={"energy": "low"}).status_code == 201

    api_client.post("/api/v1/auth/logout")
    second_user_id = _register_and_login(
        api_client, "second@example.com", "another secure password phrase",
    )
    assert second_user_id != api_client.app.state.test_user_id
    assert api_client.get("/api/v1/mood-checkins").status_code == 403
    assert api_client.get("/api/v1/quests").status_code == 403

    _grant(api_client, "data_storage")
    _grant(api_client, "mood_personalization")
    assert api_client.get("/api/v1/mood-checkins").json() == []
    assert api_client.get("/api/v1/quests").json() == []


def test_baseline_requires_consent_and_does_not_claim_ready_when_data_missing(api_client):
    initial = api_client.get("/api/v1/baseline/status").json()
    assert initial["status"] == "consent_required"
    _grant(api_client, "data_collection")
    _grant(api_client, "physiological_processing")
    unavailable = api_client.get("/api/v1/baseline/status")
    assert unavailable.status_code == 200
    assert unavailable.json()["status"] == "unavailable"
    assert not unavailable.json()["ready"]


def test_real_fit_api_reports_provisional_historical_data_without_motion(api_client, tmp_path):
    from pathlib import Path
    import shutil
    from calma_backend.api import create_app

    project = Path(__file__).resolve().parents[1]
    # Use the real repository FIT files but a separate temporary database.
    from fastapi.testclient import TestClient
    user_data_root = tmp_path / "user-data"
    app = create_app(
        database_path=tmp_path / "real-fit-api.enc",
        data_dir=user_data_root,
        daily_csv=project / "data" / "calma_harian_bersih.csv",
        model_metadata=project / "hasil" / "model_historis" / "garmin_daily_stress.metadata.json",
    )
    with TestClient(app) as client:
        user_id = _register_and_login(client, "fit@example.com", "another secure password phrase")
        user_fit_dir = user_data_root / user_id
        user_fit_dir.mkdir(parents=True)
        for source in (project / "data" / "garmin_user1").glob("*WELLNESS.fit"):
            shutil.copy2(source, user_fit_dir / source.name)
        _grant(client, "data_collection")
        _grant(client, "physiological_processing")
        _grant(client, "data_storage")
        baseline = client.get("/api/v1/baseline/status").json()
        assert baseline["status"] == "provisional"
        assert baseline["ready"] is False
        assert baseline["motion_checked"] is False
        result = client.post("/api/v1/stress/analyze")
        assert result.status_code == 200
        assert result.json()["monitoring_mode"] == "historical_file_analysis"
        assert result.json()["baseline"]["ready"] is False
        events = client.get("/api/v1/stress/events").json()
        assert all(event["motion_checked"] is False for event in events)


def test_mood_write_requires_storage_and_mood_consent(api_client):
    body = {"mood": "low", "energy": "low"}
    assert api_client.post("/api/v1/mood-checkins", json=body).status_code == 403
    _grant(api_client, "data_storage")
    assert api_client.post("/api/v1/mood-checkins", json=body).status_code == 403
    _grant(api_client, "mood_personalization")
    created = api_client.post("/api/v1/mood-checkins", json=body)
    assert created.status_code == 201
    assert created.json()["soft_mode_suggested"] is True
    assert api_client.get("/api/v1/mood-checkins").json()[0]["mood"] == "low"


def test_stress_confirmation_is_persisted_and_one_time(api_client):
    repository = _repo(api_client)
    moment = datetime(2026, 1, 1, tzinfo=timezone.utc)
    event_id = repository.add_stress_event(StressEvent(moment, moment, moment, 82, False))
    assert api_client.get("/api/v1/stress/events").status_code == 403
    _grant(api_client, "data_storage")
    assert api_client.get("/api/v1/stress/events").json()[0]["status"] == "pending"
    confirmed = api_client.post(
        f"/api/v1/stress/events/{event_id}/confirmation", json={"answer": "yes"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed_by_user"
    duplicate = api_client.post(
        f"/api/v1/stress/events/{event_id}/confirmation", json={"answer": "no"},
    )
    assert duplicate.status_code == 422


def test_quest_recommendation_storage_gate_and_history(api_client):
    request = {"energy": "low", "condition": "okay"}
    recommendation = api_client.post("/api/v1/quests/recommendations", json=request)
    assert recommendation.status_code == 200
    assert recommendation.json()["tier"] == "micro"
    assert api_client.post("/api/v1/quests", json=request).status_code == 403
    _grant(api_client, "data_storage")
    started = api_client.post("/api/v1/quests", json=request)
    assert started.status_code == 201
    assert started.json()["status"] == "in_progress"
    completed = api_client.post(f"/api/v1/quests/{started.json()['id']}/complete")
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert len(api_client.get("/api/v1/quests").json()) == 1


def test_quest_can_be_cancelled_without_claiming_completion(api_client):
    _grant(api_client, "data_storage")
    started = api_client.post("/api/v1/quests", json={"energy": "low"}).json()
    cancelled = api_client.post(f"/api/v1/quests/{started['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "skipped"
    assert cancelled.json()["ended_at"] is not None


def test_escalation_requires_nonpositive_evaluation_and_support_counts_distinct_days(api_client):
    _grant(api_client, "data_storage")
    _grant(api_client, "trusted_contact")
    blocked = api_client.post("/api/v1/support/escalation/countdown")
    assert blocked.status_code == 409

    repository = _repo(api_client)
    for day in (1, 2, 3):
        moment = datetime(2026, 2, day, tzinfo=timezone.utc)
        event_id = repository.add_stress_event(StressEvent(moment, moment, moment, 82, True))
        repository.confirm_stress_event(event_id, "yes", moment)
    _grant(api_client, "professional_support")
    offer = api_client.get("/api/v1/support/status")
    assert offer.status_code == 200
    assert offer.json()["eligible"] is True
    assert offer.json()["distinct_stress_days"] == 3
    assert offer.json()["booking_available"] is False


def test_safety_plan_requires_storage_consent_and_crisis_route_is_public(api_client):
    plan = {
        "warning_signs": ["sulit tidur"],
        "helpful_steps": ["hubungi teman"],
        "trusted_contact": {"name": "Dina", "phone": "+628123456789"},
        "professional_support": "Klinik pilihan pengguna",
        "emergency_contact": {"name": "Keluarga", "phone": "+628987654321"},
    }
    assert api_client.put("/api/v1/safety-plan", json=plan).status_code == 403
    _grant(api_client, "data_storage")
    assert api_client.put("/api/v1/safety-plan", json=plan).status_code == 200
    restored = api_client.get("/api/v1/safety-plan")
    assert restored.status_code == 200
    assert restored.json()["warning_signs"] == ["sulit tidur"]
    crisis = api_client.get("/api/v1/crisis-information")
    assert crisis.status_code == 200
    assert crisis.json()["emergency_number"] == "119"


def test_api_safety_plan_is_stored_in_encrypted_per_user_database(api_client, tmp_path):
    _grant(api_client, "data_storage")
    marker = "private-safety-marker-account-40957"
    payload = {"warning_signs": [marker], "helpful_steps": ["hubungi teman"]}
    saved = api_client.put("/api/v1/safety-plan", json=payload)
    assert saved.status_code == 200

    user_id = api_client.app.state.test_user_id
    path = tmp_path / "api_users" / f"{user_id}.sqlite3.enc"
    ciphertext = path.read_bytes()
    assert not ciphertext.startswith(b"SQLite format 3")
    assert marker.encode("utf-8") not in ciphertext
    assert api_client.get("/api/v1/safety-plan").json()["warning_signs"] == [marker]


def test_chatbot_fallback_and_invalid_payload(api_client):
    response = api_client.post("/api/v1/chatbot/messages", json={"message": "Saya sedih", "just_listen": True})
    assert response.status_code == 200
    assert response.json()["mode"] == "rule_based_fallback"
    assert response.json()["just_listen"] is True
    contextual = api_client.post("/api/v1/chatbot/messages", json={
        "message": "Apa yang harus kulakukan?",
        "history": [{"role": "user", "content": "Aku kewalahan dengan deadline kerja."}],
    })
    assert contextual.status_code == 200
    assert "pekerjaan" in contextual.json()["text"]
    invalid = api_client.post("/api/v1/chatbot/messages", json={"message": 42})
    assert invalid.status_code == 422


def test_soft_mode_and_revoke_effect_are_stored(api_client):
    _grant(api_client, "data_storage")
    changed = api_client.put("/api/v1/preferences/soft-mode", json={"enabled": True})
    assert changed.status_code == 200
    assert changed.json()["prefer_light_activities"] is True
    revoked = api_client.put("/api/v1/consents/data_storage", json={"granted": False})
    assert revoked.status_code == 200
    assert api_client.put("/api/v1/preferences/soft-mode", json={"enabled": False}).status_code == 403


def test_support_history_read_requires_storage_consent(api_client):
    assert api_client.get("/api/v1/support/status").status_code == 403


def test_reward_api_persists_demo_claims_and_enforces_weekly_limit(api_client):
    assert api_client.get("/api/v1/rewards/status").status_code == 403
    _grant(api_client, "data_storage")
    status_before = api_client.get("/api/v1/rewards/status")
    assert status_before.status_code == 200
    assert status_before.json()["available"] is True
    for _ in range(3):
        response = api_client.post("/api/v1/rewards/claims", json={"choice": "Buah segar"})
        assert response.status_code == 201
        assert response.json()["status"] == "DEMO_ONLY"
    assert api_client.post("/api/v1/rewards/claims", json={"choice": "Buah segar"}).status_code == 422
    assert api_client.get("/api/v1/rewards/status").json()["available"] is False


def test_recovery_evaluation_returns_insufficient_data_and_escalation_is_consent_gated(api_client):
    _grant(api_client, "data_storage")
    _grant(api_client, "data_collection")
    _grant(api_client, "physiological_processing")
    repository = _repo(api_client)
    started_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
    quest_id = repository.create_quest(
        recommend_quest(EnergyLevel.LOW).option, QuestStatus.IN_PROGRESS, started_at,
    )
    repository.complete_quest(quest_id, datetime(2026, 3, 1, 0, 20, tzinfo=timezone.utc))
    evaluated = api_client.post(f"/api/v1/quests/{quest_id}/evaluation", json={"recovery_minutes": 30})
    assert evaluated.status_code == 200
    assert evaluated.json()["evaluation_status"] == "insufficient_data"
    assert evaluated.json()["decrease"] is None
    assert api_client.post("/api/v1/support/escalation/countdown").status_code == 403

    _grant(api_client, "trusted_contact")
    assert api_client.post("/api/v1/support/escalation/countdown").status_code == 409
    plan = {"trusted_contact": {"name": "Dina", "phone": "+628123456789"}}
    assert api_client.put("/api/v1/safety-plan", json=plan).status_code == 200
    repository.save_quest_evaluation(quest_id, QuestEvaluation(
        ResponseStatus.NO_POSITIVE_RESPONSE, 80, 75, 5, "test fixture",
    ))
    started = api_client.post("/api/v1/support/escalation/countdown")
    assert started.status_code == 200
    assert started.json()["status"] == "countdown_started"
    assert api_client.post("/api/v1/support/escalation/cancel").json()["status"] == "cancelled"
