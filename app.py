"""Antarmuka lokal CALMA; aturan bisnis tetap berada di paket tahap masing-masing."""
from datetime import datetime, timezone
import os
from pathlib import Path
import warnings

import pandas as pd
import streamlit as st

from tahap1_data.garmin_loader import load_minutely
from tahap2_baseline.baseline import BaselineModel
from tahap4_interaksi import (
    ConsentManager, ConsentPurpose, Energy, Mood, MoodSettings,
    UserConfirmation, UserStateMachine,
)
from tahap5_stress_quest import (
    ActivityType, EnergyLevel, QuestTracker, QuestTier, RewardTracker,
    UserCondition, get_option, recommend_quest,
)
from tahap6_keamanan import (
    EscalationStatus, PersonalSafetyPlan, SafetyContact, SafetyPlanStore,
    TrustedContactEscalation, open_crisis_access,
)
from tahap7_chatbot import CalmaChatbot, OpenAICompatibleProvider


ROOT = Path(__file__).resolve().parent
PAGES = (
    "Onboarding", "Dashboard", "Consent & Privasi", "Mood Check-in", "Stress Quest",
    "Riwayat", "Chatbot", "Safety Plan", "Crisis Mode",
)
PURPOSE_LABELS = {
    ConsentPurpose.DATA_COLLECTION: "Pengumpulan data",
    ConsentPurpose.PHYSIOLOGICAL_PROCESSING: "Pemrosesan data fisiologis",
    ConsentPurpose.DATA_STORAGE: "Penyimpanan lokal yang diperlukan",
    ConsentPurpose.MOOD_PERSONALIZATION: "Personalisasi berdasarkan mood",
    ConsentPurpose.EXTERNAL_CHAT_PROCESSING: "Pemrosesan chat oleh provider eksternal",
    ConsentPurpose.TRUSTED_CONTACT: "Kontak tepercaya",
    ConsentPurpose.PROFESSIONAL_SUPPORT: "Dukungan profesional",
}
MOOD_LABELS = {Mood.GOOD: "Cukup baik", Mood.OKAY: "Biasa saja", Mood.LOW: "Lagi berat"}
ENERGY_LABELS = {Energy.LOW: "Rendah", Energy.MEDIUM: "Sedang", Energy.HIGH: "Tinggi"}
QUEST_ENERGY_LABELS = {
    EnergyLevel.LOW: "Rendah", EnergyLevel.MEDIUM: "Sedang", EnergyLevel.HIGH: "Tinggi",
}
CONDITION_LABELS = {
    UserCondition.OKAY: "Baik untuk aktivitas ringan",
    UserCondition.NOT_FEELING_WELL: "Sedang kurang sehat",
    UserCondition.RECOVERING: "Sedang pemulihan",
    UserCondition.INJURED: "Sedang mengalami cedera",
}
ACTIVITY_LABELS = {
    ActivityType.WALK: "Jalan kaki",
    ActivityType.STEP_TARGET: "Target langkah",
    ActivityType.GYM: "Gym",
    ActivityType.SWIM: "Berenang",
}


def _data_dir() -> Path:
    configured = os.getenv("CALMA_DATA_DIR")
    if configured:
        return Path(configured).expanduser()
    local_app_data = os.getenv("LOCALAPPDATA")
    return Path(local_app_data) / "CALMA" if local_app_data else Path.home() / ".calma"


def _daily_csv() -> Path:
    return Path(os.getenv("CALMA_DAILY_CSV", ROOT / "data" / "calma_harian_bersih.csv"))


def _garmin_dir() -> Path:
    return Path(os.getenv("CALMA_GARMIN_DIR", ROOT / "data" / "garmin_user1"))


def _services() -> dict:
    if "calma_services" not in st.session_state:
        directory = _data_dir()
        consent = ConsentManager(directory / "consent.json")
        store = SafetyPlanStore(consent, directory / "safety_plan.json")
        mood = MoodSettings()
        st.session_state.calma_services = {
            "consent": consent,
            "safety_store": store,
            "mood": mood,
            "user_state": UserStateMachine(),
            "quests": QuestTracker(),
            "rewards": RewardTracker(),
            "escalation": TrustedContactEscalation(consent, store),
            "chat": CalmaChatbot(consent, store, mood, OpenAICompatibleProvider.from_environment()),
        }
    return st.session_state.calma_services


def _apply_style(soft_mode: bool) -> None:
    background = "#f7f1e9" if soft_mode else "#f2f6f7"
    accent = "#a75e43" if soft_mode else "#245d83"
    st.markdown(
        f"""<style>
        .stApp {{ background: {background}; }}
        h1, h2, h3 {{ color: #18374a; font-family: Georgia, 'Times New Roman', serif; }}
        .calma-brand {{ color: {accent}; font-size: 13px; font-weight: 700; }}
        .calma-note {{ border-left: 4px solid {accent}; padding: 0.7rem 1rem;
          background: rgba(255,255,255,.72); border-radius: 4px; }}
        @media (prefers-reduced-motion: reduce) {{ *, *::before, *::after {{ animation: none !important; transition: none !important; }} }}
        </style>""",
        unsafe_allow_html=True,
    )


def _render_dashboard(services: dict) -> None:
    st.title("CALMA")
    st.caption("Your Stress, Understood")
    st.markdown("### Ringkasan hari ini")
    csv_path = _daily_csv()
    fit_dir = _garmin_dir()
    daily_rows = None
    if csv_path.exists():
        try:
            daily_rows = len(pd.read_csv(csv_path, usecols=["date"]))
        except (OSError, ValueError, pd.errors.ParserError):
            st.warning("Ringkasan historis tidak dapat dibaca.")
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning,
                                    module=r"fitparse\.processors")
            minute_data = load_minutely(str(fit_dir))
        valid_hr = int(minute_data["hr"].notna().sum())
        model = BaselineModel().fit(minute_data)
        baseline_status = f"Sementara: {model.days_covered}/7 hari data valid"
        covered_from = minute_data.index.min()
        covered_to = minute_data.index.max()
        has_minute_steps = "steps" in minute_data.columns
    except (OSError, ValueError, KeyError, TypeError) as exc:
        valid_hr = 0
        baseline_status = "Belum tersedia: data valid belum cukup untuk estimasi baseline"
        covered_from = covered_to = None
        has_minute_steps = False
        st.caption(f"Status loader: {type(exc).__name__}")

    columns = st.columns(3)
    columns[0].metric("Baseline personal", baseline_status)
    columns[1].metric("HR per menit valid di file", valid_hr)
    columns[2].metric("Riwayat harian Garmin", f"{daily_rows} hari" if daily_rows is not None else "Tidak tersedia")
    if covered_from is not None:
        st.caption(f"Cakupan FIT lokal: {covered_from} sampai {covered_to}.")
    st.info(
        "Pemantauan real-time belum tersedia. File FIT yang ada hanya mencakup sebagian hari "
        "dan tidak menyediakan langkah per menit; CALMA tidak menganggapnya sebagai bukti aktivitas rendah."
    )
    st.markdown("### Potensi stres")
    st.write("Belum ada notifikasi personal yang dapat ditampilkan dari data ini. Skor harian Garmin adalah analisis historis terpisah, bukan deteksi stres per menit.")
    st.markdown("### Status perangkat")
    st.write("Data lokal tersedia" if valid_hr else "Data lokal belum tersedia", "· perangkat tidak terhubung secara live")
    if services["mood"].soft_mode:
        st.markdown('<div class="calma-note">Mode Lembut aktif. Kamu dapat memilih satu langkah kecil atau beristirahat.</div>', unsafe_allow_html=True)


def _render_onboarding(services: dict) -> None:
    st.title("CALMA")
    st.caption("Your Stress, Understood")
    st.subheader("Selamat datang")
    st.write("CALMA adalah prototipe lokal untuk membantu meninjau data, check-in, dan memilih dukungan. Ini bukan alat diagnosis atau layanan darurat.")
    st.info("Data Fitbit/Garmin di komputer belum menunjukkan pemantauan real-time. Consent kontak dan layanan eksternal selalu pilihan terpisah dan tertutup secara default.")
    st.markdown("#### Mulai dengan pilihanmu")
    st.write("Tinjau izin sebelum memilih fitur. Kamu dapat mengubah atau mencabutnya kapan saja.")
    if st.button("Tinjau consent dan privasi", key="onboarding_consent"):
        st.session_state.next_page = "Consent & Privasi"
        st.rerun()
    if st.button("Lanjutkan ke dashboard", key="onboarding_dashboard"):
        st.session_state.onboarding_complete = True
        st.session_state.next_page = "Dashboard"
        st.rerun()


def _render_consent(services: dict) -> None:
    st.title("Consent & Privasi")
    st.write("Izin diatur terpisah. Mencabut izin akan memblokir tindakan berikutnya yang membutuhkannya.")
    manager = services["consent"]
    with st.form("consent_form"):
        selections = {
            purpose: st.checkbox(label, value=manager.has_consent(purpose), key=f"consent_{purpose.value}")
            for purpose, label in PURPOSE_LABELS.items()
        }
        submitted = st.form_submit_button("Simpan pilihan izin")
    if submitted:
        try:
            for purpose, granted in selections.items():
                if granted != manager.has_consent(purpose):
                    (manager.grant if granted else manager.revoke)(purpose)
            st.success("Pilihan izin tersimpan secara lokal.")
            st.session_state.onboarding_complete = True
        except OSError:
            st.error("Pilihan izin gagal disimpan; status sebelumnya dipertahankan.")
    st.caption("Consent kontak dan layanan eksternal tidak aktif secara default. Tidak ada data yang dikirim keluar tanpa konfigurasi dan izin.")


def _render_mood(services: dict) -> None:
    st.title("Mood Check-in")
    mood_settings = services["mood"]
    with st.form("mood_checkin"):
        mood = st.selectbox("Bagaimana rasanya saat ini?", list(Mood), format_func=lambda item: MOOD_LABELS[item])
        energy = st.selectbox("Bagaimana energimu?", list(Energy), format_func=lambda item: ENERGY_LABELS[item])
        submitted = st.form_submit_button("Simpan check-in")
    if submitted:
        result = mood_settings.check_in(mood, energy)
        st.session_state.last_mood_checkin = result
        if result.soft_mode_suggested:
            st.info("Mode Lembut bisa menjadi pilihan. Mode ini tidak aktif otomatis.")
    if mood_settings.latest_check_in is not None:
        st.write(f"Check-in terakhir: {MOOD_LABELS[mood_settings.latest_check_in.mood]} · energi {ENERGY_LABELS[mood_settings.latest_check_in.energy]}.")
    action = "Nonaktifkan" if mood_settings.soft_mode else "Aktifkan"
    if st.button(f"{action} Mode Lembut", key="toggle_soft_mode"):
        mood_settings.set_soft_mode(not mood_settings.soft_mode)
        st.rerun()
    st.caption("Mode Lembut mengurangi penekanan skor/reward dan memprioritaskan aktivitas ringan. Akses keselamatan tetap tersedia.")


def _render_quest(services: dict) -> None:
    st.title("Stress Quest")
    tracker = services["quests"]
    with st.form("quest_recommendation"):
        energy = st.selectbox("Energi yang kamu rasakan", list(EnergyLevel), format_func=lambda item: QUEST_ENERGY_LABELS[item])
        condition = st.selectbox("Kondisi tubuh", list(UserCondition), format_func=lambda item: CONDITION_LABELS[item])
        preferred = st.selectbox("Preferensi aktivitas (opsional)", [None, *ActivityType], format_func=lambda item: "Tidak ada" if item is None else ACTIVITY_LABELS[item])
        submitted = st.form_submit_button("Perbarui rekomendasi")
    recommendation = recommend_quest(
        energy, condition, preferred, tracker.history, services["mood"].soft_mode,
    )
    if recommendation.option is None:
        st.info(recommendation.reason)
    else:
        option = recommendation.option
        st.subheader(option.title)
        st.write(f"Target: **{option.target}**")
        st.write(option.instructions)
        st.caption(recommendation.reason)
        left, right = st.columns(2)
        if tracker.active_session is None:
            if left.button("Mulai · saya melaporkan aktivitas", key="start_quest"):
                tracker.start(recommendation, at=datetime.now(timezone.utc))
                st.rerun()
            if right.button("Lewati tanpa penalti", key="skip_quest"):
                tracker.skip(recommendation)
                st.rerun()
        else:
            st.info(f"Aktivitas {tracker.active_session.option.title} sedang berlangsung (dilaporkan pengguna).")
            if st.button("Catat selesai", key="complete_quest"):
                tracker.complete()
                st.rerun()
    if tracker.history:
        st.markdown("#### Aktivitas dan evaluasi")
        st.write(f"Total catatan di sesi aplikasi ini: {len(tracker.history)}")
        st.info("Evaluasi skor pemulihan memerlukan data skor bertimestamp sebelum aktivitas dan 30–60 menit sesudahnya. Data Garmin lokal saat ini belum menyediakan rangkaian yang cukup; respons belum dinilai.")
    offer = services["rewards"].offer(soft_mode=services["mood"].soft_mode)
    if offer.available:
        st.markdown("#### Reward opsional · demo lokal")
        choice = st.selectbox("Pilihan demo", offer.suggestions, key="reward_choice")
        if st.button("Catat pilihan demo", key="claim_reward"):
            services["rewards"].claim(choice)
            st.success("Pilihan demo dicatat. Tidak ada transaksi nyata.")
    else:
        st.caption("Batas reward minggu ini tercapai.")


def _render_history(services: dict) -> None:
    st.title("Riwayat")
    records = []
    for session in services["quests"].history:
        records.append({
            "Aktivitas": session.option.title,
            "Status": session.status.value,
            "Sumber": session.source.value if session.source else "tidak ada",
            "Mulai": session.started_at.isoformat() if session.started_at else "-",
            "Selesai": session.ended_at.isoformat() if session.ended_at else "-",
            "Evaluasi": session.evaluation.status.value if session.evaluation else "belum dievaluasi",
        })
    if records:
        st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)
    else:
        st.info("Belum ada aktivitas tercatat dalam sesi aplikasi ini.")
    machine = services["user_state"]
    st.markdown("#### Konfirmasi potensi stres")
    if machine.confirmation_history:
        st.write(f"Tersimpan di sesi ini: {len(machine.confirmation_history)} jawaban konfirmasi.")
    else:
        st.write("Belum ada event bertimestamp yang siap dikonfirmasi dari data lokal.")


def _render_chat(services: dict) -> None:
    st.title("Pendamping CALMA")
    st.caption("Fallback lokal berbasis aturan; bukan diagnosis dan bukan pengganti tenaga profesional.")
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    for item in st.session_state.chat_history:
        with st.chat_message(item["role"]):
            st.write(item["text"])
            if item.get("emergency"):
                st.info("Akses langsung: buka Crisis Mode atau hubungi 119 bila membutuhkan bantuan segera.")
    with st.form("chat_form", clear_on_submit=True):
        message = st.text_input("Pesan")
        mode = st.radio("Cara menemani", ["Boleh memberi saran", "Saya hanya ingin didengarkan"], horizontal=True)
        request_quest = st.checkbox("Sertakan pilihan aktivitas ringan")
        energy = st.selectbox("Energi (untuk saran aktivitas)", list(EnergyLevel), format_func=lambda item: QUEST_ENERGY_LABELS[item])
        submitted = st.form_submit_button("Kirim")
    if submitted:
        response = services["chat"].respond(
            message, just_listen=(mode == "Saya hanya ingin didengarkan"),
            request_quest=request_quest, energy=energy,
        )
        st.session_state.chat_history.extend([
            {"role": "user", "text": message},
            {"role": "assistant", "text": response.text,
             "emergency": response.crisis_access is not None},
        ])
        st.rerun()
    if st.button("Hapus riwayat chat sesi ini", key="clear_chat"):
        st.session_state.chat_history = []
        st.rerun()


def _render_safety_plan(services: dict) -> None:
    st.title("Personal Safety Plan")
    st.caption("Hanya tersimpan lokal setelah consent penyimpanan aktif. Baca dan hapus tetap tersedia setelah izin dicabut.")
    store = services["safety_store"]
    plan = store.get_plan()
    with st.form("safety_plan_form"):
        warning_signs = st.text_area("Tanda atau situasi ketika kamu membutuhkan bantuan", value="\n".join(plan.warning_signs) if plan else "")
        helpful_steps = st.text_area("Langkah yang biasanya membantu", value="\n".join(plan.helpful_steps) if plan else "")
        trusted_name = st.text_input("Nama kontak tepercaya", value=plan.trusted_contact.name if plan and plan.trusted_contact else "")
        trusted_phone = st.text_input("Nomor kontak tepercaya", value=plan.trusted_contact.phone if plan and plan.trusted_contact else "")
        emergency_name = st.text_input("Nama kontak darurat", value=plan.emergency_contact.name if plan and plan.emergency_contact else "")
        emergency_phone = st.text_input("Nomor kontak darurat", value=plan.emergency_contact.phone if plan and plan.emergency_contact else "")
        professional_support = st.text_area("Pilihan dukungan profesional", value=plan.professional_support if plan else "")
        save = st.form_submit_button("Simpan safety plan")
    if save:
        try:
            trusted = SafetyContact(trusted_name, trusted_phone) if trusted_name or trusted_phone else None
            emergency = SafetyContact(emergency_name, emergency_phone) if emergency_name or emergency_phone else None
            store.update_plan(PersonalSafetyPlan(
                warning_signs=tuple(warning_signs.splitlines()),
                helpful_steps=tuple(helpful_steps.splitlines()),
                trusted_contact=trusted,
                emergency_contact=emergency,
                professional_support=professional_support,
            ))
            st.success("Safety plan tersimpan lokal.")
            st.rerun()
        except (PermissionError, ValueError, TypeError, OSError) as exc:
            st.error(f"Safety plan tidak tersimpan: {exc}")
    if plan is not None and st.button("Hapus safety plan lokal", key="delete_safety_plan"):
        try:
            store.delete_plan()
            st.success("Safety plan dihapus.")
            st.rerun()
        except OSError:
            st.error("Safety plan belum dapat dihapus dari penyimpanan lokal.")


def _render_crisis(services: dict) -> None:
    st.title("Crisis Mode")
    access = open_crisis_access(services["safety_store"])
    st.error(access.message)
    st.subheader("Bantuan darurat")
    st.markdown(f"**{access.emergency_number}**")
    st.caption("Gunakan nomor darurat sesuai ketersediaan layanan di lokasi kamu.")
    st.caption(access.scope_note)
    if access.emergency_contact:
        st.write(f"Kontak darurat yang kamu atur: {access.emergency_contact.name} · {access.emergency_contact.phone}")
    if access.safety_plan:
        st.markdown("#### Rencana pribadi")
        st.write("Tanda bantuan:", ", ".join(access.safety_plan.warning_signs) or "belum diisi")
        st.write("Langkah yang membantu:", ", ".join(access.safety_plan.helpful_steps) or "belum diisi")
        if access.safety_plan.professional_support:
            st.write("Dukungan profesional yang kamu atur:", access.safety_plan.professional_support)
    st.markdown("#### Dukungan profesional")
    st.write("Pemesanan telekonsultasi belum tersedia. Kamu dapat menggunakan pilihan dukungan profesional yang telah kamu atur.")
    escalation = services["escalation"]
    if escalation.pending is None:
        st.markdown("#### Minta ditemani oleh kontak tepercaya")
        st.write("Atas permintaanmu, countdown 10 menit dapat dimulai. Provider bawaan hanya simulasi dan tidak mengirim pesan.")
        if st.button("Mulai countdown kontak", key="start_countdown"):
            result = escalation.start_countdown(datetime.now(timezone.utc))
            st.session_state.crisis_notice = result
            st.rerun()
    else:
        st.info(f"Countdown berjalan sampai {escalation.pending.due_at.isoformat()}.")
        if st.button("Batalkan countdown", key="cancel_countdown"):
            st.session_state.crisis_notice = escalation.cancel()
            st.rerun()
        if st.button("Periksa dan selesaikan countdown", key="finish_countdown"):
            st.session_state.crisis_notice = escalation.complete(datetime.now(timezone.utc))
            st.rerun()
    notice = st.session_state.get("crisis_notice")
    if notice is not None:
        st.info(notice.message)


def main() -> None:
    st.set_page_config(page_title="CALMA · Your Stress, Understood", page_icon="C", layout="wide")
    next_page = st.session_state.pop("next_page", None)
    if next_page in PAGES:
        st.session_state.page_navigation = next_page
    services = _services()
    soft_mode = services["mood"].soft_mode
    _apply_style(soft_mode)
    with st.sidebar:
        st.markdown('<div class="calma-brand">CALMA · YOUR STRESS, UNDERSTOOD</div>', unsafe_allow_html=True)
        st.caption("Prototipe lokal · data tidak live")
        default_page = "Dashboard" if st.session_state.get("onboarding_complete") else "Onboarding"
        page = st.radio("Navigasi", PAGES, index=PAGES.index(default_page),
                label_visibility="collapsed", key="page_navigation")
        st.divider()
        st.write("Mode Lembut:", "Aktif" if soft_mode else "Nonaktif")
        st.caption("Data kesehatan tetap berada di perangkat lokal.")

    renderers = {
        "Onboarding": _render_onboarding,
        "Dashboard": _render_dashboard,
        "Consent & Privasi": _render_consent,
        "Mood Check-in": _render_mood,
        "Stress Quest": _render_quest,
        "Riwayat": _render_history,
        "Chatbot": _render_chat,
        "Safety Plan": _render_safety_plan,
        "Crisis Mode": _render_crisis,
    }
    renderers[page](services)


if __name__ == "__main__":
    main()
