"""Akses langsung ke rencana pribadi dan informasi bantuan darurat."""
from dataclasses import dataclass

from .plan import PersonalSafetyPlan, SafetyContact, SafetyPlanStore


@dataclass(frozen=True)
class CrisisAccess:
    safety_plan: PersonalSafetyPlan | None
    emergency_contact: SafetyContact | None
    emergency_number: str = "119"
    message: str = "Jika kamu membutuhkan bantuan segera, hubungi layanan darurat atau orang tepercaya."
    scope_note: str = "CALMA bukan layanan darurat dan tidak mendeteksi semua kondisi krisis."


def open_crisis_access(store: SafetyPlanStore) -> CrisisAccess:
    plan = store.get_plan()
    return CrisisAccess(plan, plan.emergency_contact if plan else None)
