"""SQLite repository untuk state backend CALMA pada satu pengguna lokal."""
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from threading import RLock
from typing import Any

from tahap3_deteksi.deteksi import StressEvent
from tahap4_interaksi.consent import ConsentChange, ConsentPurpose
from tahap6_keamanan.plan import (
    DeliveryLimitReached, PersonalSafetyPlan, SafetyContact,
)
from tahap5_stress_quest.quest import (
    ActivitySource, QuestOption, QuestSession, QuestStatus, QuestTier,
    ActivityType, ResponseStatus, QuestEvaluation, RewardClaim, RewardTracker,
)
from .encrypted_sqlite import EncryptedSQLiteConnection
from .security import LocalDataCipher


class SQLiteRepository:
    def __init__(self, database_path: str | Path,
                 cipher: LocalDataCipher | None = None):
        value = str(database_path)
        if value != ":memory:":
            Path(value).parent.mkdir(parents=True, exist_ok=True)
        self.cipher = cipher or LocalDataCipher.from_environment()
        self.connection = EncryptedSQLiteConnection(value, self.cipher,
                                                    check_same_thread=False)
        self._lock = RLock()
        self._create_schema()

    def close(self) -> None:
        with self._lock:
            self.connection.close()

    def _create_schema(self) -> None:
        with self._lock, self.connection:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS consent_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    purpose TEXT NOT NULL,
                    granted INTEGER NOT NULL CHECK (granted IN (0, 1)),
                    changed_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS consent_purpose_idx
                    ON consent_changes(purpose, id DESC);
                CREATE TABLE IF NOT EXISTS baseline (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    mu REAL NOT NULL,
                    sigma REAL NOT NULL CHECK (sigma >= 3),
                    n_valid INTEGER NOT NULL,
                    days_covered INTEGER NOT NULL,
                    ready INTEGER NOT NULL CHECK (ready IN (0, 1)),
                    motion_checked INTEGER NOT NULL CHECK (motion_checked IN (0, 1)),
                    fitted_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS stress_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    alert_time TEXT NOT NULL,
                    ended_at TEXT NOT NULL,
                    peak REAL NOT NULL,
                    motion_checked INTEGER NOT NULL CHECK (motion_checked IN (0, 1)),
                    status TEXT NOT NULL DEFAULT 'pending',
                    confirmation TEXT,
                    confirmed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS mood_checkins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mood TEXT NOT NULL,
                    energy TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    changed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS quest_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tier TEXT NOT NULL,
                    activity TEXT NOT NULL,
                    title TEXT NOT NULL,
                    target TEXT NOT NULL,
                    instructions TEXT NOT NULL,
                    status TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    started_at TEXT,
                    ended_at TEXT,
                    source TEXT,
                    evaluation_status TEXT,
                    before_mean REAL,
                    recovery_mean REAL,
                    decrease REAL,
                    evaluation_note TEXT
                );
                CREATE INDEX IF NOT EXISTS quest_status_idx
                    ON quest_sessions(status, id DESC);
                CREATE TABLE IF NOT EXISTS safety_plan (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    warning_signs TEXT NOT NULL,
                    helpful_steps TEXT NOT NULL,
                    trusted_contact_name TEXT,
                    trusted_contact_phone TEXT,
                    professional_support TEXT NOT NULL,
                    emergency_contact_name TEXT,
                    emergency_contact_phone TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS escalation_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    attempted_at TEXT NOT NULL,
                    status TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS escalation_attempts_time_idx
                    ON escalation_attempts(attempted_at DESC);
                CREATE TABLE IF NOT EXISTS reward_claims (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    choice TEXT NOT NULL,
                    claimed_at TEXT NOT NULL,
                    status TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS reward_claims_time_idx
                    ON reward_claims(claimed_at DESC);
                CREATE TABLE IF NOT EXISTS support_countdown (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    started_at TEXT NOT NULL,
                    due_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _now(at: datetime | None = None) -> datetime:
        value = at or datetime.now(timezone.utc)
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Waktu harus memiliki zona waktu")
        return value

    def update_consent(self, purpose: ConsentPurpose | str, granted: bool,
                       at: datetime | None = None) -> ConsentChange:
        purpose = ConsentPurpose(purpose)
        if not isinstance(granted, bool):
            raise TypeError("Status consent harus berupa boolean")
        changed = ConsentChange(purpose, granted, self._now(at))
        with self._lock, self.connection:
            self.connection.execute(
                "INSERT INTO consent_changes(purpose, granted, changed_at) VALUES (?, ?, ?)",
                (purpose.value, int(granted), changed.changed_at.isoformat()),
            )
        return changed

    def grant(self, purpose: ConsentPurpose | str,
              at: datetime | None = None) -> ConsentChange:
        return self.update_consent(purpose, True, at)

    def revoke(self, purpose: ConsentPurpose | str,
               at: datetime | None = None) -> ConsentChange:
        return self.update_consent(purpose, False, at)

    def has_consent(self, purpose: ConsentPurpose | str) -> bool:
        purpose = ConsentPurpose(purpose)
        with self._lock:
            row = self.connection.execute(
                "SELECT granted FROM consent_changes WHERE purpose = ? ORDER BY id DESC LIMIT 1",
                (purpose.value,),
            ).fetchone()
        return bool(row["granted"]) if row else False

    def consent_history(self, purpose: ConsentPurpose | str | None = None) -> list[ConsentChange]:
        query = "SELECT purpose, granted, changed_at FROM consent_changes"
        args: tuple[Any, ...] = ()
        if purpose is not None:
            query += " WHERE purpose = ?"
            args = (ConsentPurpose(purpose).value,)
        query += " ORDER BY id"
        with self._lock:
            rows = self.connection.execute(query, args).fetchall()
        return [ConsentChange(ConsentPurpose(row["purpose"]), bool(row["granted"]),
                              datetime.fromisoformat(row["changed_at"])) for row in rows]

    def save_baseline(self, mu: float, sigma: float, n_valid: int,
                      days_covered: int, ready: bool, motion_checked: bool,
                      fitted_at: datetime | None = None) -> dict[str, Any]:
        fitted = self._now(fitted_at).isoformat()
        with self._lock, self.connection:
            self.connection.execute(
                """INSERT INTO baseline(id, mu, sigma, n_valid, days_covered, ready,
                   motion_checked, fitted_at) VALUES (1, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET mu=excluded.mu, sigma=excluded.sigma,
                   n_valid=excluded.n_valid, days_covered=excluded.days_covered,
                   ready=excluded.ready, motion_checked=excluded.motion_checked,
                   fitted_at=excluded.fitted_at""",
                (mu, sigma, n_valid, days_covered, int(ready), int(motion_checked), fitted),
            )
        return self.get_baseline()

    def get_baseline(self) -> dict[str, Any] | None:
        with self._lock:
            row = self.connection.execute("SELECT * FROM baseline WHERE id = 1").fetchone()
        if row is None:
            return None
        result = dict(row)
        result["ready"] = bool(result["ready"])
        result["motion_checked"] = bool(result["motion_checked"])
        return result

    def add_stress_event(self, event: StressEvent) -> int:
        values = (event.start.isoformat(), event.alert_time.isoformat())
        with self._lock:
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                existing = self.connection.execute(
                    "SELECT id FROM stress_events WHERE started_at = ? AND alert_time = ?",
                    values,
                ).fetchone()
                if existing is not None:
                    self.connection.commit()
                    return int(existing["id"])
                cursor = self.connection.execute(
                    """INSERT INTO stress_events(started_at, alert_time, ended_at, peak,
                       motion_checked) VALUES (?, ?, ?, ?, ?)""",
                    (event.start.isoformat(), event.alert_time.isoformat(), event.end.isoformat(),
                     event.peak, int(event.motion_checked)),
                )
                self.connection.commit()
                return int(cursor.lastrowid)
            except Exception:
                self.connection.rollback()
                raise

    def get_stress_event(self, event_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self.connection.execute("SELECT * FROM stress_events WHERE id = ?", (event_id,)).fetchone()
        return dict(row) if row else None

    def list_stress_events(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT * FROM stress_events ORDER BY id DESC LIMIT ?", (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def confirm_stress_event(self, event_id: int, answer: str,
                             at: datetime | None = None) -> dict[str, Any] | None:
        if answer not in {"yes", "no", "unsure"}:
            raise ValueError("Jawaban konfirmasi tidak dikenal")
        status = {"yes": "confirmed_by_user", "no": "denied_by_user",
                  "unsure": "user_unsure"}[answer]
        timestamp = self._now(at).isoformat()
        with self._lock, self.connection:
            cursor = self.connection.execute(
                """UPDATE stress_events SET status = ?, confirmation = ?, confirmed_at = ?
                   WHERE id = ? AND status = 'pending'""",
                (status, answer, timestamp, event_id),
            )
        return self.get_stress_event(event_id) if cursor.rowcount else None

    def add_mood_checkin(self, mood: str, energy: str,
                         at: datetime | None = None) -> int:
        timestamp = self._now(at).isoformat()
        with self._lock, self.connection:
            cursor = self.connection.execute(
                "INSERT INTO mood_checkins(mood, energy, recorded_at) VALUES (?, ?, ?)",
                (mood, energy, timestamp),
            )
            return int(cursor.lastrowid)

    def latest_mood_checkin(self) -> dict[str, Any] | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM mood_checkins ORDER BY id DESC LIMIT 1",
            ).fetchone()
        return dict(row) if row else None

    def list_mood_checkins(self, limit: int = 200) -> list[dict[str, Any]]:
        if not 1 <= limit <= 500:
            raise ValueError("Batas riwayat mood harus antara 1 dan 500")
        with self._lock:
            rows = self.connection.execute(
                "SELECT * FROM mood_checkins ORDER BY id DESC LIMIT ?", (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def set_preference(self, key: str, value: str,
                       at: datetime | None = None) -> None:
        timestamp = self._now(at).isoformat()
        with self._lock, self.connection:
            self.connection.execute(
                """INSERT INTO preferences(key, value, changed_at) VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value, changed_at=excluded.changed_at""",
                (key, value, timestamp),
            )

    def get_preference(self, key: str, default: str | None = None) -> str | None:
        with self._lock:
            row = self.connection.execute("SELECT value FROM preferences WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def create_quest(self, option: QuestOption, status: QuestStatus,
                     at: datetime | None = None,
                     source: ActivitySource | None = None) -> int:
        timestamp = self._now(at).isoformat()
        started_at = timestamp if status == QuestStatus.IN_PROGRESS else None
        with self._lock:
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                if status == QuestStatus.IN_PROGRESS:
                    active = self.connection.execute(
                        "SELECT 1 FROM quest_sessions WHERE status = ? LIMIT 1",
                        (QuestStatus.IN_PROGRESS.value,),
                    ).fetchone()
                    if active:
                        raise ValueError("Selesaikan atau lewati quest aktif sebelum memulai yang baru")
                cursor = self.connection.execute(
                    """INSERT INTO quest_sessions(tier, activity, title, target, instructions,
                       status, recorded_at, started_at, source)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (option.tier.value, option.activity.value, option.title, option.target,
                     option.instructions, status.value, timestamp, started_at,
                     source.value if source else None),
                )
                self.connection.commit()
                return int(cursor.lastrowid)
            except Exception:
                self.connection.rollback()
                raise

    def get_quest(self, quest_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self.connection.execute("SELECT * FROM quest_sessions WHERE id = ?", (quest_id,)).fetchone()
        return dict(row) if row else None

    def list_quests(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT * FROM quest_sessions ORDER BY id DESC LIMIT ?", (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def quest_history(self, limit: int = 200) -> list[QuestSession]:
        sessions = []
        for row in reversed(self.list_quests(limit)):
            option = QuestOption(QuestTier(row["tier"]), ActivityType(row["activity"]),
                                 row["title"], row["target"], row["instructions"])
            evaluation = None
            if row["evaluation_status"]:
                evaluation = QuestEvaluation(
                    ResponseStatus(row["evaluation_status"]), row["before_mean"],
                    row["recovery_mean"], row["decrease"], row["evaluation_note"] or "",
                )
            sessions.append(QuestSession(
                option, QuestStatus(row["status"]), datetime.fromisoformat(row["recorded_at"]),
                datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
                datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
                ActivitySource(row["source"]) if row["source"] else None,
                evaluation,
            ))
        return sessions

    def complete_quest(self, quest_id: int, at: datetime | None = None) -> dict[str, Any] | None:
        timestamp = self._now(at).isoformat()
        with self._lock, self.connection:
            cursor = self.connection.execute(
                "UPDATE quest_sessions SET status = ?, ended_at = ? WHERE id = ? AND status = ?",
                (QuestStatus.COMPLETED.value, timestamp, quest_id, QuestStatus.IN_PROGRESS.value),
            )
        return self.get_quest(quest_id) if cursor.rowcount else None

    def cancel_quest(self, quest_id: int, at: datetime | None = None) -> dict[str, Any] | None:
        timestamp = self._now(at).isoformat()
        with self._lock, self.connection:
            cursor = self.connection.execute(
                "UPDATE quest_sessions SET status = ?, ended_at = ? WHERE id = ? AND status = ?",
                (QuestStatus.SKIPPED.value, timestamp, quest_id, QuestStatus.IN_PROGRESS.value),
            )
        return self.get_quest(quest_id) if cursor.rowcount else None

    def save_quest_evaluation(self, quest_id: int, evaluation: QuestEvaluation) -> bool:
        with self._lock, self.connection:
            cursor = self.connection.execute(
                """UPDATE quest_sessions SET evaluation_status=?, before_mean=?, recovery_mean=?,
                   decrease=?, evaluation_note=? WHERE id=? AND status=?""",
                (evaluation.status.value, evaluation.before_mean, evaluation.recovery_mean,
                 evaluation.decrease, evaluation.note, quest_id, QuestStatus.COMPLETED.value),
            )
        return cursor.rowcount > 0

    def latest_quest_evaluation(self) -> dict[str, Any] | None:
        with self._lock:
            row = self.connection.execute(
                """SELECT * FROM quest_sessions WHERE status = ? AND evaluation_status IS NOT NULL
                         AND id = (SELECT MAX(id) FROM quest_sessions)
                         ORDER BY id DESC LIMIT 1""",
                     (QuestStatus.COMPLETED.value,),
            ).fetchone()
        return dict(row) if row else None

    def confirmed_stress_days(self) -> list[str]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT DISTINCT substr(started_at, 1, 10) AS day FROM stress_events "
                "WHERE confirmation = 'yes' ORDER BY day",
            ).fetchall()
        return [row["day"] for row in rows]

    def update_plan(self, plan: PersonalSafetyPlan) -> PersonalSafetyPlan:
        if not self.has_consent(ConsentPurpose.DATA_STORAGE):
            raise PermissionError("Consent penyimpanan belum diberikan atau sudah dicabut")
        updated_at = self._now().isoformat()
        values = (
            json.dumps(list(plan.warning_signs)), json.dumps(list(plan.helpful_steps)),
            plan.trusted_contact.name if plan.trusted_contact else None,
            plan.trusted_contact.phone if plan.trusted_contact else None,
            plan.professional_support,
            plan.emergency_contact.name if plan.emergency_contact else None,
            plan.emergency_contact.phone if plan.emergency_contact else None,
            updated_at,
        )
        with self._lock, self.connection:
            self.connection.execute(
                """INSERT INTO safety_plan(id, warning_signs, helpful_steps,
                   trusted_contact_name, trusted_contact_phone, professional_support,
                   emergency_contact_name, emergency_contact_phone, updated_at)
                   VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET warning_signs=excluded.warning_signs,
                   helpful_steps=excluded.helpful_steps,
                   trusted_contact_name=excluded.trusted_contact_name,
                   trusted_contact_phone=excluded.trusted_contact_phone,
                   professional_support=excluded.professional_support,
                   emergency_contact_name=excluded.emergency_contact_name,
                   emergency_contact_phone=excluded.emergency_contact_phone,
                   updated_at=excluded.updated_at""",
                values,
            )
        return self.get_plan()

    def get_plan(self) -> PersonalSafetyPlan | None:
        with self._lock:
            row = self.connection.execute("SELECT * FROM safety_plan WHERE id = 1").fetchone()
        if row is None:
            return None
        trusted = (SafetyContact(row["trusted_contact_name"], row["trusted_contact_phone"])
                   if row["trusted_contact_name"] and row["trusted_contact_phone"] else None)
        emergency = (SafetyContact(row["emergency_contact_name"], row["emergency_contact_phone"])
                     if row["emergency_contact_name"] and row["emergency_contact_phone"] else None)
        return PersonalSafetyPlan(
            warning_signs=tuple(json.loads(row["warning_signs"])),
            helpful_steps=tuple(json.loads(row["helpful_steps"])),
            trusted_contact=trusted,
            professional_support=row["professional_support"],
            emergency_contact=emergency,
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def delete_plan(self) -> None:
        with self._lock, self.connection:
            self.connection.execute("DELETE FROM safety_plan WHERE id = 1")

    def within_delivery_limit(self, at: datetime) -> bool:
        now = self._now(at)
        with self._lock:
            row = self.connection.execute(
                "SELECT attempted_at FROM escalation_attempts ORDER BY id DESC LIMIT 1",
            ).fetchone()
        if row is None:
            return False
        previous = datetime.fromisoformat(row["attempted_at"])
        from datetime import timedelta
        return now < previous + timedelta(hours=24)

    def reserve_delivery(self, at: datetime) -> None:
        if not self.has_consent(ConsentPurpose.DATA_STORAGE):
            raise PermissionError("Consent penyimpanan belum diberikan atau sudah dicabut")
        now = self._now(at)
        from datetime import timedelta
        with self._lock:
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                row = self.connection.execute(
                    "SELECT attempted_at FROM escalation_attempts ORDER BY id DESC LIMIT 1",
                ).fetchone()
                if row is not None:
                    previous = datetime.fromisoformat(row["attempted_at"])
                    if now < previous + timedelta(hours=24):
                        raise DeliveryLimitReached("Batas satu pesan dalam 24 jam masih berlaku")
                self.connection.execute(
                    "INSERT INTO escalation_attempts(attempted_at, status) VALUES (?, 'pending')",
                    (now.isoformat(),),
                )
                self.connection.commit()
            except Exception:
                self.connection.rollback()
                raise

    def finish_delivery(self, status: str) -> None:
        if status not in {"simulated", "sent", "failed"}:
            raise ValueError("Status pengiriman tidak dikenal")
        with self._lock, self.connection:
            self.connection.execute(
                """UPDATE escalation_attempts SET status = ? WHERE id =
                   (SELECT id FROM escalation_attempts WHERE status = 'pending'
                    ORDER BY id DESC LIMIT 1)""",
                (status,),
            )

    def latest_delivery_attempt(self) -> dict[str, Any] | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM escalation_attempts ORDER BY id DESC LIMIT 1",
            ).fetchone()
        return dict(row) if row else None

    def get_pending_countdown(self):
        from tahap6_keamanan.escalation import Countdown
        with self._lock:
            row = self.connection.execute(
                "SELECT started_at, due_at FROM support_countdown WHERE id = 1",
            ).fetchone()
        if row is None:
            return None
        return Countdown(datetime.fromisoformat(row["started_at"]),
                         datetime.fromisoformat(row["due_at"]))

    def save_pending_countdown(self, countdown) -> None:
        with self._lock, self.connection:
            self.connection.execute(
                """INSERT INTO support_countdown(id, started_at, due_at) VALUES (1, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET started_at=excluded.started_at,
                   due_at=excluded.due_at""",
                (countdown.started_at.isoformat(), countdown.due_at.isoformat()),
            )

    def clear_pending_countdown(self) -> None:
        with self._lock, self.connection:
            self.connection.execute("DELETE FROM support_countdown WHERE id = 1")

    def migrate_legacy_delivery_attempt(self, at: datetime, status: str) -> None:
        if not self.has_consent(ConsentPurpose.DATA_STORAGE):
            raise PermissionError("Consent penyimpanan belum diberikan atau sudah dicabut")
        at = self._now(at)
        if status not in {"pending", "simulated", "sent", "failed"}:
            status = "failed"
        with self._lock, self.connection:
            exists = self.connection.execute(
                "SELECT 1 FROM escalation_attempts WHERE attempted_at = ? LIMIT 1",
                (at.isoformat(),),
            ).fetchone()
            if exists is None:
                self.connection.execute(
                    "INSERT INTO escalation_attempts(attempted_at, status) VALUES (?, ?)",
                    (at.isoformat(), status),
                )

    def claim_reward(self, choice: str, at: datetime | None = None) -> RewardClaim:
        if not self.has_consent(ConsentPurpose.DATA_STORAGE):
            raise PermissionError("Consent penyimpanan belum diberikan atau sudah dicabut")
        timestamp = self._now(at)
        with self._lock:
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                rows = self.connection.execute(
                    "SELECT choice, claimed_at, status FROM reward_claims ORDER BY id",
                ).fetchall()
                history = [RewardClaim(row["choice"], datetime.fromisoformat(row["claimed_at"]), row["status"])
                           for row in rows]
                claim = RewardTracker(history).claim(choice, timestamp)
                self.connection.execute(
                    "INSERT INTO reward_claims(choice, claimed_at, status) VALUES (?, ?, ?)",
                    (claim.choice, claim.claimed_at.isoformat(), claim.status),
                )
                self.connection.commit()
                return claim
            except Exception:
                self.connection.rollback()
                raise

    def reward_history(self, limit: int = 100) -> list[RewardClaim]:
        if not 1 <= limit <= 500:
            raise ValueError("Batas riwayat reward harus antara 1 dan 500")
        with self._lock:
            rows = self.connection.execute(
                "SELECT choice, claimed_at, status FROM reward_claims ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [RewardClaim(row["choice"], datetime.fromisoformat(row["claimed_at"]), row["status"])
                for row in rows]
