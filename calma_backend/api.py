"""FastAPI adapter untuk AI Core dan service CALMA; tidak menyediakan UI."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import sqlite3
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from tahap4_interaksi import ConsentPurpose
from tahap6_keamanan import TrustedContactEscalation
from .auth import AccountStore, AuthenticationError, DuplicateAccountError
from .database import SQLiteRepository
from .security import LocalDataCipher
from .schemas import (
    AccountCreated, AccountLogin, AccountRegister, BaselineStatus, ChatRequest,
    ChatResponse, ConsentStatus, ConsentUpdate,
    CrisisInformation, EscalationStart, MoodCheckInOut, MoodCheckInRequest,
    QuestEvaluationRequest, QuestRecordOut, QuestRecommendationOut,
    QuestRecommendationRequest, QuestStartRequest, RewardClaimOut,
    RewardClaimRequest, RewardOfferOut, SafetyPlanMigrationOut, SafetyPlanRequest,
    SoftModeUpdate, StressAnalysisOut, StressConfirmation, StressEventOut,
    TokenResponse,
)
from .services import CalmaBackendService


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class UserContext:
    repository: SQLiteRepository
    services: CalmaBackendService
    escalation: TrustedContactEscalation


def _legacy_plaintext_path_for(encrypted_path: Path) -> Path:
    if encrypted_path.name.endswith(".sqlite3.enc"):
        return encrypted_path.with_suffix("")
    return encrypted_path.with_suffix(".sqlite3")


def _migrate_legacy_database_if_needed(encrypted_path: Path, cipher: LocalDataCipher) -> None:
    """Migrate a plaintext SQLite legacy DB into the encrypted on-disk format."""
    if str(encrypted_path) == ":memory:" or encrypted_path.exists():
        return
    legacy_path = _legacy_plaintext_path_for(encrypted_path)
    if legacy_path == encrypted_path or not legacy_path.is_file():
        return
    try:
        with sqlite3.connect(f"file:{legacy_path.as_posix()}?mode=ro", uri=True) as connection:
            tables = [row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'",
            )]
            populated = []
            for table in tables:
                quoted = '"' + table.replace('"', '""') + '"'
                if connection.execute(f"SELECT 1 FROM {quoted} LIMIT 1").fetchone():
                    populated.append(table)
    except sqlite3.Error as exc:
        raise RuntimeError(
            "Legacy SQLite tidak dapat diperiksa; startup dihentikan dan file sumber dipertahankan."
        ) from exc
    try:
        encrypted_path.parent.mkdir(parents=True, exist_ok=True)
        source = sqlite3.connect(f"file:{legacy_path.as_posix()}?mode=ro", uri=True)
        try:
            serialized = source.serialize()
        finally:
            source.close()
        encrypted_path.write_bytes(cipher.encrypt_bytes(serialized))
        backup_path = legacy_path.with_name(legacy_path.name + ".migrated")
        if backup_path.exists():
            backup_path.unlink()
        shutil.copy2(legacy_path, backup_path)
    except (sqlite3.Error, OSError, ValueError) as exc:
        raise RuntimeError(
            "Legacy SQLite plaintext tidak dapat dimigrasi ke format terenkripsi yang aman."
        ) from exc


def create_app(*, database_path: str | Path | None = None,
               data_dir: str | Path | None = None,
               daily_csv: str | Path | None = None,
               model_metadata: str | Path | None = None) -> FastAPI:
    database_path = Path(database_path or os.getenv("CALMA_DB_PATH", ROOT / "data" / "calma_backend.enc"))
    data_dir = Path(data_dir or os.getenv("CALMA_GARMIN_DIR", ROOT / "data" / "garmin_user1"))
    daily_csv = Path(daily_csv or os.getenv("CALMA_DAILY_CSV", ROOT / "data" / "calma_harian_bersih.csv"))
    model_metadata = Path(model_metadata or os.getenv(
        "CALMA_MODEL_METADATA", ROOT / "hasil" / "model_historis" / "validation_20261016"
        / "garmin_daily_stress.metadata.json"))
    cipher = LocalDataCipher.from_environment()
    _migrate_legacy_database_if_needed(Path(database_path), cipher)
    account_store = AccountStore(database_path, cipher=cipher)
    user_database_dir = database_path.parent / f"{database_path.stem}_users"
    legacy_safety_root = Path(os.getenv(
        "CALMA_LEGACY_SAFETY_ROOT", user_database_dir / "legacy_safety_plans"))
    user_contexts: dict[str, UserContext] = {}

    def context_for_user(user_id: str) -> UserContext:
        context = user_contexts.get(user_id)
        if context is None:
            user_database_path = user_database_dir / f"{user_id}.sqlite3.enc"
            _migrate_legacy_database_if_needed(user_database_path, cipher)
            repository = SQLiteRepository(user_database_path, cipher=cipher)
            context = UserContext(
                repository,
                CalmaBackendService(repository, data_dir=data_dir / user_id,
                                    daily_csv=daily_csv, model_metadata=model_metadata,
                                    legacy_safety_plan_path=legacy_safety_root / user_id / "safety_plan.json"),
                TrustedContactEscalation(repository, repository),
            )
            user_contexts[user_id] = context
        return context

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        for context in user_contexts.values():
            context.repository.close()
        account_store.close()

    app = FastAPI(
        title="CALMA Backend API",
        description="API lokal CALMA. Skor stres adalah heuristik prototipe, bukan diagnosis klinis.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.account_store = account_store
    app.state.user_contexts = user_contexts
    app.state.context_for_user = context_for_user

    public_paths = {
        "/api/v1/health", "/api/v1/auth/register", "/api/v1/auth/login",
        "/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc",
    }

    @app.middleware("http")
    async def require_bearer_auth(request: Request, call_next):
        if request.url.path.startswith("/api/v1/") and request.url.path not in public_paths:
            authorization = request.headers.get("Authorization", "")
            scheme, _, token = authorization.partition(" ")
            if scheme.casefold() != "bearer" or not token:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Autentikasi bearer diperlukan.", "code": "authentication_required"},
                    headers={"WWW-Authenticate": "Bearer"},
                )
            user_id = account_store.user_for_token(token)
            if user_id is None:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Token tidak valid atau kedaluwarsa.", "code": "invalid_token"},
                    headers={"WWW-Authenticate": "Bearer"},
                )
            request.state.user_id = user_id
            request.state.bearer_token = token
            request.state.user_context = context_for_user(user_id)
        return await call_next(request)

    @app.exception_handler(PermissionError)
    async def permission_error_handler(request: Request, exc: PermissionError):
        return JSONResponse(status_code=403, content={"detail": str(exc), "code": "consent_required"})

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "invalid_request"})

    @app.exception_handler(sqlite3.Error)
    async def database_error_handler(request: Request, exc: sqlite3.Error):
        return JSONResponse(status_code=503, content={"detail": "Penyimpanan lokal sementara tidak tersedia.", "code": "storage_unavailable"})

    def service(request: Request) -> CalmaBackendService:
        return request.state.user_context.services

    def user_context(request: Request) -> UserContext:
        return request.state.user_context

    @app.post("/api/v1/auth/register", response_model=AccountCreated, status_code=201)
    def register_account(body: AccountRegister, request: Request):
        try:
            user_id = account_store.register(body.email, body.password)
        except DuplicateAccountError as exc:
            raise HTTPException(status_code=409, detail="Akun dengan email tersebut sudah terdaftar") from exc
        return {"user_id": user_id}

    @app.post("/api/v1/auth/login", response_model=TokenResponse)
    def login_account(body: AccountLogin):
        try:
            grant = account_store.login(body.email, body.password)
        except AuthenticationError as exc:
            raise HTTPException(
                status_code=401, detail="Email atau password salah",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        return {"access_token": grant.access_token, "token_type": grant.token_type,
                "expires_at": grant.expires_at}

    @app.post("/api/v1/auth/logout", status_code=204)
    def logout_account(request: Request):
        if not account_store.revoke_token(request.state.bearer_token):
            raise HTTPException(status_code=401, detail="Token tidak valid atau sudah dicabut")
        return None

    @app.get("/api/v1/health")
    def health(request: Request):
        if not account_store.health_check():
            raise HTTPException(status_code=503, detail="Penyimpanan tidak tersedia")
        return {"status": "ok", "service": "calma-backend", "api_version": "v1"}

    @app.get("/api/v1/baseline/status", response_model=BaselineStatus)
    def baseline_status(request: Request):
        return service(request).baseline_status()

    @app.post("/api/v1/stress/analyze", response_model=StressAnalysisOut)
    def analyze_stress(request: Request):
        return service(request).analyze_stress()

    @app.get("/api/v1/stress/events", response_model=list[StressEventOut])
    def stress_events(request: Request, limit: int = Query(default=100, ge=1, le=500)):
        return service(request).stress_events(limit)

    @app.post("/api/v1/stress/events/{event_id}/confirmation", response_model=StressEventOut)
    def confirm_stress_event(event_id: int, body: StressConfirmation, request: Request):
        event = service(request).confirm_event(event_id, body.answer.value)
        if event is None:
            raise HTTPException(status_code=404, detail="Event tidak ditemukan")
        return event

    @app.post("/api/v1/mood-checkins", response_model=MoodCheckInOut, status_code=201)
    def add_mood_checkin(body: MoodCheckInRequest, request: Request):
        return service(request).add_mood(body.mood, body.energy)

    @app.get("/api/v1/mood-checkins", response_model=list[MoodCheckInOut])
    def mood_history(request: Request, limit: int = Query(default=100, ge=1, le=500)):
        return service(request).mood_history(limit)

    @app.put("/api/v1/preferences/soft-mode")
    def set_soft_mode(body: SoftModeUpdate, request: Request):
        return service(request).set_soft_mode(body.enabled)

    @app.get("/api/v1/consents", response_model=list[ConsentStatus])
    def consent_status(request: Request):
        return service(request).consent_status()

    @app.put("/api/v1/consents/{purpose}", response_model=ConsentStatus)
    def update_consent(purpose: ConsentPurpose, body: ConsentUpdate, request: Request):
        change = service(request).update_consent(purpose, body.granted)
        return {"purpose": change.purpose, "granted": change.granted,
                "changed_at": change.changed_at}

    @app.post("/api/v1/quests/recommendations", response_model=QuestRecommendationOut)
    def recommend(body: QuestRecommendationRequest, request: Request):
        recommendation = service(request).recommend_quest(
            body.energy, body.condition, body.preferred_activity,
        )
        option = recommendation.option
        return {
            "tier": option.tier.value if option else None,
            "activity": option.activity.value if option else None,
            "title": option.title if option else None,
            "target": option.target if option else None,
            "instructions": option.instructions if option else None,
            "reason": recommendation.reason,
        }

    @app.post("/api/v1/quests", response_model=QuestRecordOut, status_code=201)
    def start_quest(body: QuestStartRequest, request: Request):
        quest_id = service(request).start_quest(
            body.energy, body.condition, body.preferred_activity, body.source,
        )
        if quest_id is None:
            raise HTTPException(status_code=409, detail="Tidak ada quest yang sesuai dengan kondisi yang dilaporkan")
        return user_context(request).repository.get_quest(quest_id)

    @app.get("/api/v1/quests", response_model=list[QuestRecordOut])
    def quest_history(request: Request, limit: int = Query(default=100, ge=1, le=500)):
        return service(request).quest_history(limit)

    @app.post("/api/v1/quests/{quest_id}/complete", response_model=QuestRecordOut)
    def complete_quest(quest_id: int, request: Request):
        result = service(request).complete_quest(quest_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Quest aktif tidak ditemukan")
        return result

    @app.post("/api/v1/quests/{quest_id}/cancel", response_model=QuestRecordOut)
    def cancel_quest(quest_id: int, request: Request):
        result = service(request).cancel_quest(quest_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Quest aktif tidak ditemukan")
        return result

    @app.post("/api/v1/quests/{quest_id}/evaluation", response_model=QuestRecordOut)
    def evaluate_quest(quest_id: int, body: QuestEvaluationRequest, request: Request):
        evaluation = service(request).evaluate_quest(quest_id, body.recovery_minutes)
        if evaluation is None:
            raise HTTPException(status_code=404, detail="Quest tidak ditemukan")
        return user_context(request).repository.get_quest(quest_id)

    @app.get("/api/v1/safety-plan", response_model=SafetyPlanRequest | None)
    def get_safety_plan(request: Request):
        plan = service(request).safety_plan()
        if plan is None:
            return None
        return _plan_payload(plan)

    @app.put("/api/v1/safety-plan", response_model=SafetyPlanRequest)
    def update_safety_plan(body: SafetyPlanRequest, request: Request):
        return _plan_payload(service(request).update_safety_plan(body))

    @app.delete("/api/v1/safety-plan", status_code=204)
    def delete_safety_plan(request: Request):
        user_context(request).repository.delete_plan()
        return None

    @app.post("/api/v1/safety-plan/migrate-legacy", response_model=SafetyPlanMigrationOut)
    def migrate_safety_plan(request: Request):
        return service(request).migrate_legacy_safety_plan()

    @app.get("/api/v1/rewards/status", response_model=RewardOfferOut)
    def reward_status(request: Request):
        return service(request).reward_offer()

    @app.post("/api/v1/rewards/claims", response_model=RewardClaimOut, status_code=201)
    def claim_reward(body: RewardClaimRequest, request: Request):
        return service(request).claim_reward(body.choice)

    @app.post("/api/v1/chatbot/messages", response_model=ChatResponse)
    def chatbot(body: ChatRequest, request: Request):
        response = service(request).chatbot(body)
        quest = response.quest_recommendation
        quest_payload = None
        if quest is not None:
            option = quest.option
            quest_payload = {
                "tier": option.tier.value if option else None,
                "activity": option.activity.value if option else None,
                "title": option.title if option else None,
                "target": option.target if option else None,
                "instructions": option.instructions if option else None,
                "reason": quest.reason,
            }
        return {"text": response.text, "mode": response.mode,
                "just_listen": response.just_listen,
                "crisis_access": response.crisis_access is not None,
                "quest": quest_payload}

    @app.get("/api/v1/crisis-information", response_model=CrisisInformation)
    def crisis_information(request: Request):
        return service(request).crisis_information()

    @app.get("/api/v1/support/status")
    def support_status(request: Request):
        return service(request).support_status()

    @app.post("/api/v1/support/escalation/countdown", response_model=EscalationStart)
    def start_escalation(request: Request):
        escalation = user_context(request).escalation
        result = service(request).start_escalation(escalation)
        return _escalation_payload(result)

    @app.post("/api/v1/support/escalation/cancel", response_model=EscalationStart)
    def cancel_escalation(request: Request):
        result = user_context(request).escalation.cancel()
        return _escalation_payload(result)

    @app.post("/api/v1/support/escalation/complete", response_model=EscalationStart)
    def complete_escalation(request: Request):
        result = user_context(request).escalation.complete(datetime.now(timezone.utc))
        return _escalation_payload(result)

    @app.get("/api/v1/models/historical/evaluation")
    def model_evaluation(request: Request):
        report = service(request).model_evaluation()
        if report is None:
            raise HTTPException(status_code=404, detail="Laporan evaluasi belum tersedia")
        return report

    @app.get("/openapi.json", include_in_schema=False)
    def openapi_schema():
        return app.openapi()

    def authenticated_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title, version=app.version, description=app.description,
            routes=app.routes,
        )
        schema.setdefault("components", {}).setdefault("securitySchemes", {})[
            "BearerAuth"
        ] = {"type": "http", "scheme": "bearer", "bearerFormat": "opaque token"}
        for path, operations in schema.get("paths", {}).items():
            if not path.startswith("/api/v1/") or path in public_paths:
                continue
            for operation in operations.values():
                if isinstance(operation, dict) and "operationId" in operation:
                    operation["security"] = [{"BearerAuth": []}]
        app.openapi_schema = schema
        return schema

    app.openapi = authenticated_openapi

    static_root = ROOT / "calma"
    if static_root.exists():
        app.mount("/calma", StaticFiles(directory=str(static_root), html=True), name="calma")

    @app.get("/", include_in_schema=False)
    def index_redirect():
        return RedirectResponse(url="/calma/index.html")

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"status": "ok"}

    return app


def _plan_payload(plan):
    return {
        "warning_signs": list(plan.warning_signs),
        "helpful_steps": list(plan.helpful_steps),
        "trusted_contact": plan.trusted_contact,
        "professional_support": plan.professional_support,
        "emergency_contact": plan.emergency_contact,
    }


def _escalation_payload(result):
    if result.status.value == "blocked_consent":
        raise HTTPException(status_code=403, detail=result.message)
    if result.status.value in {"blocked_contact", "insufficient_data", "not_offered"}:
        raise HTTPException(status_code=409, detail=result.message)
    if result.status.value == "rate_limited":
        raise HTTPException(status_code=429, detail=result.message)
    if result.status.value == "delivery_failed":
        raise HTTPException(status_code=502, detail=result.message)
    return {"status": result.status.value, "message": result.message,
            "due_at": result.due_at, "mode": result.mode}


app = create_app()
