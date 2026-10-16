"""Orkestrasi backend; perhitungan tetap memakai service tahap yang sudah ada."""
from datetime import datetime, timezone
from datetime import date as calendar_date
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tahap1_data.garmin_loader import load_minutely
from tahap2_baseline.baseline import BaselineModel
from tahap2_baseline.fitur import add_features
from tahap3_deteksi.deteksi import StressEvent, detect_events
from tahap3_deteksi.skor import hitung_skor
from tahap4_interaksi import ConsentPurpose, Energy, Mood, MoodCheckIn, MoodSettings
from tahap5_stress_quest import (
    ActivitySource, EnergyLevel, QuestEvaluation, QuestStatus, ResponseStatus,
    RewardTracker, UserCondition, evaluate_recovery, recommend_quest,
)
from tahap6_keamanan import (
    EscalationResult, EscalationStatus, PersonalSafetyPlan, SafetyContact,
    TrustedContactEscalation, repeated_stress_offer,
)
from tahap7_chatbot import CalmaChatbot, OpenAICompatibleProvider


class CalmaBackendService:
    def __init__(self, repository, *, data_dir: str | Path,
                 daily_csv: str | Path, model_metadata: str | Path,
                 legacy_safety_plan_path: str | Path | None = None):
        self.repository = repository
        self.data_dir = Path(data_dir)
        self.daily_csv = Path(daily_csv)
        self.model_metadata = Path(model_metadata)
        self.legacy_safety_plan_path = (Path(legacy_safety_plan_path)
                        if legacy_safety_plan_path is not None else None)
        self._raw_minutes: pd.DataFrame | None = None

    def require_consent(self, purpose: ConsentPurpose) -> None:
        if not self.repository.has_consent(purpose):
            raise PermissionError(f"Consent {purpose.value} belum diberikan atau sudah dicabut")

    def consent_status(self) -> list[dict[str, Any]]:
        latest: dict[ConsentPurpose, Any] = {}
        for change in self.repository.consent_history():
            latest[change.purpose] = change
        return [
            {"purpose": purpose, "granted": latest[purpose].granted,
             "changed_at": latest[purpose].changed_at if purpose in latest else None}
            for purpose in ConsentPurpose
        ]

    def update_consent(self, purpose: ConsentPurpose, granted: bool):
        return self.repository.update_consent(purpose, granted)

    def migrate_legacy_safety_plan(self, path: str | Path | None = None) -> dict[str, Any]:
        self.require_consent(ConsentPurpose.DATA_STORAGE)
        if path is None:
            path = self.legacy_safety_plan_path
        if path is None:
            return {"migrated": False, "reason": "user_specific_legacy_path_not_configured"}
        source = Path(path)
        if not source.is_file():
            return {"migrated": False, "reason": "legacy_file_not_found"}
        payload = json.loads(source.read_text(encoding="utf-8"))
        plan_data = payload.get("plan", payload)
        migrated = False
        if plan_data is not None and self.repository.get_plan() is None:
            plan = PersonalSafetyPlan(
                tuple(plan_data.get("warning_signs", ())),
                tuple(plan_data.get("helpful_steps", ())),
                SafetyContact(**plan_data["trusted_contact"])
                if plan_data.get("trusted_contact") else None,
                plan_data.get("professional_support", ""),
                SafetyContact(**plan_data["emergency_contact"])
                if plan_data.get("emergency_contact") else None,
            )
            self.repository.update_plan(plan)
            migrated = True
        attempt_at = payload.get("last_attempt_at") if isinstance(payload, dict) else None
        if attempt_at:
            self.repository.migrate_legacy_delivery_attempt(
                datetime.fromisoformat(attempt_at), payload.get("last_attempt_status", "failed"),
            )
        return {"migrated": migrated, "source_preserved": True}

    def baseline_status(self) -> dict[str, Any]:
        if not (self.repository.has_consent(ConsentPurpose.DATA_COLLECTION)
                and self.repository.has_consent(ConsentPurpose.PHYSIOLOGICAL_PROCESSING)):
            return {
                "status": "consent_required", "ready": False, "reason":
                "Consent pengumpulan dan pemrosesan fisiologis diperlukan sebelum membaca data.",
            }
        try:
            raw = self._load_minutes()
            features = add_features(raw)
            valid = features["valid"]
            days_covered = int((features.loc[valid].groupby(features.loc[valid].index.date).size() >= 60).sum())
            motion_checked = bool(features.loc[valid, "motion_checked"].any()) if "motion_checked" in features else False
            if int(valid.sum()) < 300:
                return self._baseline_result(
                    "not_ready", False, days_covered, int(valid.sum()), raw,
                    motion_checked, "Pengukuran HR valid belum mencapai minimum 300 sampel.",
                )
            model = BaselineModel().fit(raw)
            result = self._baseline_result(
                "ready" if model.ready else "provisional", model.ready,
                model.days_covered, model.n_valid, raw, motion_checked,
                "Baseline siap." if model.ready else "Data belum mencakup minimal tujuh hari; baseline masih sementara.",
            )
            if self.repository.has_consent(ConsentPurpose.DATA_STORAGE):
                self.repository.save_baseline(
                    model.mu_global, model.sigma, model.n_valid, model.days_covered,
                    model.ready, motion_checked,
                )
            return result
        except (OSError, ValueError, KeyError, TypeError):
            return {
                "status": "unavailable", "ready": False,
                "reason": "Data FIT tidak dapat dibaca atau belum cukup untuk membentuk baseline.",
            }

    @staticmethod
    def _baseline_result(status, ready, days, measurements, raw, motion_checked, reason):
        return {
            "status": status, "ready": ready, "days_covered": days,
            "required_days": 7, "valid_measurements": measurements,
            "data_start": raw.index.min().to_pydatetime() if len(raw) else None,
            "data_end": raw.index.max().to_pydatetime() if len(raw) else None,
            "motion_checked": motion_checked, "reason": reason,
        }

    def _load_minutes(self) -> pd.DataFrame:
        if self._raw_minutes is None:
            if not self.data_dir.is_dir() or not any(self.data_dir.glob("*WELLNESS.fit")):
                raise FileNotFoundError("File FIT wellness tidak tersedia")
            self._raw_minutes = load_minutely(str(self.data_dir))
        return self._raw_minutes.copy()

    def analyze_stress(self) -> dict[str, Any]:
        self.require_consent(ConsentPurpose.DATA_COLLECTION)
        self.require_consent(ConsentPurpose.PHYSIOLOGICAL_PROCESSING)
        self.require_consent(ConsentPurpose.DATA_STORAGE)
        status = self.baseline_status()
        if status["status"] not in {"ready", "provisional"}:
            return {"baseline": status, "created_event_ids": [], "event_count": 0}
        raw = self._load_minutes()
        model = BaselineModel().fit(raw)
        scores = hitung_skor(model, raw)["score"]
        has_steps = "steps" in raw.columns
        events = detect_events(scores, threshold=model.threshold, motion_checked=has_steps)
        event_ids = [self.repository.add_stress_event(event) for event in events]
        return {"baseline": status, "created_event_ids": event_ids,
                "event_count": len(event_ids)}

    def stress_events(self, limit: int) -> list[dict[str, Any]]:
        self.require_consent(ConsentPurpose.DATA_STORAGE)
        if not 1 <= limit <= 500:
            raise ValueError("Batas event harus antara 1 dan 500")
        events = self.repository.list_stress_events(limit)
        for event in events:
            for key in ("started_at", "alert_time", "ended_at", "confirmed_at"):
                if event.get(key):
                    event[key] = datetime.fromisoformat(event[key])
            event["motion_checked"] = bool(event["motion_checked"])
        return events

    def confirm_event(self, event_id: int, answer: str):
        self.require_consent(ConsentPurpose.DATA_STORAGE)
        event = self.repository.confirm_stress_event(event_id, answer)
        if event is None:
            if self.repository.get_stress_event(event_id) is None:
                return None
            raise ValueError("Event sudah memiliki konfirmasi")
        return event

    def mood_settings(self) -> MoodSettings:
        settings = MoodSettings()
        can_read_stored_mood = (
            self.repository.has_consent(ConsentPurpose.DATA_STORAGE)
            and self.repository.has_consent(ConsentPurpose.MOOD_PERSONALIZATION)
        )
        saved = self.repository.latest_mood_checkin() if can_read_stored_mood else None
        if saved:
            settings.latest_check_in = MoodCheckIn(
                Mood(saved["mood"]), Energy(saved["energy"]),
                datetime.fromisoformat(saved["recorded_at"]),
            )
        soft_mode = (self.repository.get_preference("soft_mode", "false") == "true"
                 if self.repository.has_consent(ConsentPurpose.DATA_STORAGE) else False)
        settings.set_soft_mode(soft_mode)
        return settings

    def add_mood(self, mood: Mood, energy: Energy) -> dict[str, Any]:
        self.require_consent(ConsentPurpose.DATA_STORAGE)
        self.require_consent(ConsentPurpose.MOOD_PERSONALIZATION)
        at = datetime.now(timezone.utc)
        record_id = self.repository.add_mood_checkin(mood.value, energy.value, at)
        return {"id": record_id, "mood": mood, "energy": energy,
                "recorded_at": at, "soft_mode_suggested": mood == Mood.LOW or energy == Energy.LOW}

    def mood_history(self, limit: int) -> list[dict[str, Any]]:
        self.require_consent(ConsentPurpose.DATA_STORAGE)
        self.require_consent(ConsentPurpose.MOOD_PERSONALIZATION)
        if not 1 <= limit <= 500:
            raise ValueError("Batas riwayat harus antara 1 dan 500")
        records = self.repository.list_mood_checkins(limit)
        for record in records:
            record["recorded_at"] = datetime.fromisoformat(record["recorded_at"])
            record["soft_mode_suggested"] = record["mood"] == Mood.LOW.value or record["energy"] == Energy.LOW.value
        return records

    def set_soft_mode(self, enabled: bool) -> dict[str, Any]:
        self.require_consent(ConsentPurpose.DATA_STORAGE)
        self.repository.set_preference("soft_mode", "true" if enabled else "false")
        return {"enabled": enabled, "prefer_light_activities": enabled,
                "deemphasize_scores_and_rewards": enabled}

    def recommend_quest(self, energy, condition, preferred_activity):
        history = []
        if self.repository.has_consent(ConsentPurpose.DATA_STORAGE):
            history = self.repository.quest_history()
        return recommend_quest(
            energy, condition, preferred_activity, history,
            soft_mode=self.mood_settings().soft_mode,
        )

    def start_quest(self, energy, condition, preferred_activity, source: ActivitySource):
        self.require_consent(ConsentPurpose.DATA_STORAGE)
        recommendation = self.recommend_quest(energy, condition, preferred_activity)
        if recommendation.option is None:
            return None
        return self.repository.create_quest(recommendation.option, QuestStatus.IN_PROGRESS,
                                            source=source)

    def quest_history(self, limit: int) -> list[dict[str, Any]]:
        self.require_consent(ConsentPurpose.DATA_STORAGE)
        return self.repository.list_quests(limit)

    def complete_quest(self, quest_id: int):
        self.require_consent(ConsentPurpose.DATA_STORAGE)
        return self.repository.complete_quest(quest_id)

    def cancel_quest(self, quest_id: int):
        self.require_consent(ConsentPurpose.DATA_STORAGE)
        return self.repository.cancel_quest(quest_id)

    def evaluate_quest(self, quest_id: int, recovery_minutes: int):
        self.require_consent(ConsentPurpose.DATA_STORAGE)
        self.require_consent(ConsentPurpose.DATA_COLLECTION)
        self.require_consent(ConsentPurpose.PHYSIOLOGICAL_PROCESSING)
        row = self.repository.get_quest(quest_id)
        if row is None:
            return None
        if row["status"] != QuestStatus.COMPLETED.value:
            raise ValueError("Quest harus diselesaikan sebelum evaluasi")
        started = datetime.fromisoformat(row["started_at"])
        ended = datetime.fromisoformat(row["ended_at"])
        try:
            model = BaselineModel().fit(self._load_minutes())
            scores = hitung_skor(model, self._load_minutes())["score"]
        except (OSError, ValueError, KeyError, TypeError):
            evaluation = QuestEvaluation(
                ResponseStatus.INSUFFICIENT_DATA, None, None, None,
                "Data bertimestamp belum cukup untuk mengevaluasi pemulihan.",
            )
            self.repository.save_quest_evaluation(quest_id, evaluation)
            return evaluation
        if (scores.index.tz is None) != (started.tzinfo is None):
            evaluation = QuestEvaluation(
                ResponseStatus.INSUFFICIENT_DATA, None, None, None,
                "Zona waktu data FIT dan aktivitas tidak kompatibel untuk evaluasi.",
            )
            self.repository.save_quest_evaluation(quest_id, evaluation)
            return evaluation
        evaluation = evaluate_recovery(started, ended, scores, recovery_minutes)
        self.repository.save_quest_evaluation(quest_id, evaluation)
        return evaluation

    def safety_plan(self) -> PersonalSafetyPlan | None:
        return self.repository.get_plan()

    def update_safety_plan(self, payload) -> PersonalSafetyPlan:
        plan = PersonalSafetyPlan(
            tuple(payload.warning_signs), tuple(payload.helpful_steps),
            SafetyContact(payload.trusted_contact.name, payload.trusted_contact.phone)
            if payload.trusted_contact else None,
            payload.professional_support,
            SafetyContact(payload.emergency_contact.name, payload.emergency_contact.phone)
            if payload.emergency_contact else None,
        )
        return self.repository.update_plan(plan)

    def chatbot(self, request):
        mood = self.mood_settings()
        provider = OpenAICompatibleProvider.from_environment()
        service = CalmaChatbot(self.repository, self.repository, mood, provider)
        return service.respond(request.message, just_listen=request.just_listen,
                               request_quest=request.request_quest, energy=request.energy,
                               history=[turn.model_dump() for turn in request.history])

    def crisis_information(self) -> dict[str, Any]:
        from tahap6_keamanan import open_crisis_access
        access = open_crisis_access(self.repository)
        plan = access.safety_plan
        return {
            "emergency_number": access.emergency_number,
            "message": access.message,
            "scope_note": access.scope_note,
            "safety_plan": {
                "warning_signs": list(plan.warning_signs),
                "helpful_steps": list(plan.helpful_steps),
                "trusted_contact": plan.trusted_contact,
                "professional_support": plan.professional_support,
                "emergency_contact": plan.emergency_contact,
            } if plan else None,
        }

    def support_status(self):
        self.require_consent(ConsentPurpose.DATA_STORAGE)
        days = [calendar_date.fromisoformat(value)
                for value in self.repository.confirmed_stress_days()]
        offer = repeated_stress_offer(days, self.repository)
        return offer

    def start_escalation(self, escalation: TrustedContactEscalation):
        if (not self.repository.has_consent(ConsentPurpose.TRUSTED_CONTACT)
                or not self.repository.has_consent(ConsentPurpose.DATA_STORAGE)):
            return EscalationResult(
                EscalationStatus.BLOCKED_CONSENT,
                "Consent penyimpanan dan kontak tepercaya harus aktif.",
            )
        row = self.repository.latest_quest_evaluation()
        if row is None:
            return EscalationResult(
                EscalationStatus.INSUFFICIENT_DATA,
                "Dukungan tambahan hanya ditawarkan setelah evaluasi quest yang memadai.",
            )
        evaluation = QuestEvaluation(
            ResponseStatus(row["evaluation_status"]), row["before_mean"],
            row["recovery_mean"], row["decrease"], row["evaluation_note"] or "",
        )
        return escalation.start_after_evaluation(evaluation)

    def model_evaluation(self):
        if not self.model_metadata.exists():
            return None
        import json
        return json.loads(self.model_metadata.read_text(encoding="utf-8"))

    def reward_offer(self, at: datetime | None = None):
        self.require_consent(ConsentPurpose.DATA_STORAGE)
        tracker = RewardTracker(self.repository.reward_history())
        return tracker.offer(at, soft_mode=self.mood_settings().soft_mode)

    def claim_reward(self, choice: str, at: datetime | None = None):
        self.require_consent(ConsentPurpose.DATA_STORAGE)
        return self.repository.claim_reward(choice, at)