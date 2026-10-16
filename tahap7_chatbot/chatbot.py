"""Pendamping CALMA lokal dengan provider eksternal yang opsional dan consent-gated."""
from dataclasses import dataclass
import json
import os
from typing import Protocol
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from tahap4_interaksi import ConsentManager, ConsentPurpose, MoodSettings
from tahap5_stress_quest import EnergyLevel, QuestRecommendation, recommend_quest
from tahap6_keamanan import CrisisAccess, SafetyPlanStore, open_crisis_access


SYSTEM_PROMPT = (
    "Anda adalah pendamping CALMA yang berbahasa Indonesia, suportif, dan tidak menghakimi. "
    "Gunakan riwayat percakapan untuk memahami konteks, bedakan fakta dari dugaan, dan "
    "ajukan pertanyaan jika informasi belum cukup. Saat diminta saran, berikan satu sampai "
    "tiga langkah kecil yang realistis. "
    "Validasi sebelum memberi saran. Jangan mendiagnosis, menjanjikan hasil, mengklaim "
    "mengetahui perasaan dari detak jantung, atau menggantikan tenaga profesional. "
    "Jangan menyatakan skor sensor sebagai diagnosis."
)
CRISIS_PHRASES = (
    "bunuh diri", "ingin mati", "mengakhiri hidup", "menyakiti diri",
    "melukai diri", "tidak ingin hidup", "ingin menghilang selamanya",
)


class ChatProvider(Protocol):
    def reply(self, message: str, history: list[dict[str, str]] | None = None) -> str:
        """Menghasilkan balasan untuk teks yang secara eksplisit diizinkan pengguna."""


class ChatProviderError(RuntimeError):
    pass


class OpenAICompatibleProvider:
    """Provider chat completions; tidak menerima skor, HR, atau mood sebagai payload."""

    def __init__(self, api_key: str, endpoint: str, model: str, timeout: float = 10):
        parsed = urlparse(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Endpoint chat harus berupa URL HTTP/HTTPS")
        if not api_key.strip() or not model.strip():
            raise ValueError("API key dan nama model wajib tersedia")
        if not 1 <= timeout <= 30:
            raise ValueError("Timeout harus antara 1 dan 30 detik")
        self._api_key = api_key
        self.endpoint = endpoint
        self.model = model
        self.timeout = timeout

    @classmethod
    def from_environment(cls) -> "OpenAICompatibleProvider | None":
        api_key = os.getenv("CALMA_CHAT_API_KEY")
        endpoint = os.getenv("CALMA_CHAT_API_URL")
        model = os.getenv("CALMA_CHAT_MODEL")
        if not api_key or not endpoint or not model:
            return None
        return cls(api_key, endpoint, model)

    def reply(self, message: str, history: list[dict[str, str]] | None = None) -> str:
        body = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                *(history or []),
                {"role": "user", "content": message},
            ],
        }).encode("utf-8")
        request = Request(
            self.endpoint,
            data=body,
            headers={"Authorization": f"Bearer {self._api_key}",
                     "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            answer = payload["choices"][0]["message"]["content"]
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("Jawaban provider kosong")
            return answer.strip()
        except (URLError, TimeoutError, OSError, ValueError, KeyError, IndexError, TypeError) as exc:
            raise ChatProviderError("Provider chat tidak tersedia atau memberi respons tidak valid") from exc


class RuleBasedProvider:
    """Fallback lokal berbasis aturan, bukan model bahasa besar."""

    def reply(self, message: str, history: list[dict[str, str]] | None = None) -> str:
        normalized = " ".join(message.casefold().split())
        conversation = " ".join(
            turn["content"].casefold() for turn in (history or [])
            if turn.get("role") == "user"
        )
        topic = next((label for label, terms in (
            ("pekerjaan", ("kerja", "kantor", "deadline", "atasan")),
            ("keluarga", ("keluarga", "orang tua", "rumah")),
            ("pertemanan atau hubungan", ("teman", "pasangan", "hubungan")),
            ("sekolah atau kuliah", ("sekolah", "kuliah", "tugas", "ujian")),
            ("istirahat dan energi", ("lelah", "capek", "tidur", "istirahat")),
        ) if any(term in f"{conversation} {normalized}" for term in terms)), None)

        if any(phrase in normalized for phrase in (
            "apa yang harus", "harus bagaimana", "mulai dari mana", "minta saran",
            "butuh saran", "bingung harus", "apa sebaiknya",
        )):
            context = f" soal {topic}" if topic else ""
            return (
                f"Kedengarannya kamu sedang mencari langkah berikutnya{context}. "
                "Kita bisa mulai dari satu hal kecil: pilih bagian yang paling mendesak, "
                "lalu tentukan tindakan yang bisa dilakukan dalam 10 menit. "
                "Apa yang paling perlu dibereskan atau terasa paling berat sekarang?"
            )

        if "kerja" in normalized or "deadline" in normalized or "kantor" in normalized:
            return (
                "Tekanan pekerjaan bisa terasa menumpuk. Kalau membantu, tulis satu tugas "
                "yang paling mendesak dan langkah pertama yang bisa selesai dalam 10 menit. "
                "Bagian mana yang paling membuatmu terbebani?"
            )
        if any(term in normalized for term in ("cemas", "khawatir", "panik", "takut")):
            return (
                "Rasa cemas bisa membuat semuanya terasa mendesak. Coba sebutkan satu hal "
                "yang kamu tahu pasti saat ini, lalu satu hal yang masih belum pasti. "
                "Kekhawatiran apa yang paling kuat sekarang?"
            )
        if any(term in normalized for term in ("sedih", "kesepian", "sendirian")):
            return (
                "Aku menangkap ini terasa berat dan kamu tidak harus langsung mencari solusi. "
                "Kalau kamu mau, ceritakan apa yang terjadi sebelum perasaan ini muncul."
            )
        return (
            "Terima kasih sudah bercerita. Aku ingin memahami situasinya lebih utuh, "
            "bukan menebak-nebak. Apa yang terjadi, sejak kapan, dan bagian mana yang "
            "paling kamu butuhkan bantuannya sekarang?"
        )


@dataclass(frozen=True)
class MoodContext:
    mood: str
    energy: str


@dataclass(frozen=True)
class ChatResponse:
    text: str
    mode: str
    just_listen: bool = False
    crisis_access: CrisisAccess | None = None
    quest_recommendation: QuestRecommendation | None = None
    mood_context: MoodContext | None = None


class CalmaChatbot:
    def __init__(self, consent: ConsentManager, safety_store: SafetyPlanStore,
                 mood_settings: MoodSettings | None = None,
                 external_provider: ChatProvider | None = None):
        self.consent = consent
        self.safety_store = safety_store
        self.mood_settings = mood_settings or MoodSettings()
        self.external_provider = external_provider
        self.local_provider = RuleBasedProvider()

    def respond(self, message: str, *, just_listen: bool = False,
                request_quest: bool = False,
                energy: EnergyLevel | str | None = None,
                history: list[dict[str, str]] | None = None) -> ChatResponse:
        if not isinstance(message, str):
            raise TypeError("Pesan harus berupa teks")
        message = message.strip()
        if not message:
            return ChatResponse("Silakan tulis pesan, atau pilih mode hanya ingin didengarkan.",
                                "rule_based_fallback", just_listen)

        if self._possible_crisis(message):
            access = open_crisis_access(self.safety_store)
            return ChatResponse(
                "Aku turut prihatin kamu sedang menghadapi hal berat. Aku tidak dapat menilai keadaanmu dari chat, "
                "tetapi kamu bisa membuka rencana keselamatan, menghubungi orang tepercaya, atau layanan darurat 119 sekarang.",
                "local_safety_route", crisis_access=access,
            )

        history = self._bounded_history(history)
        context = self._mood_context()
        if just_listen:
            text = "Aku di sini untuk mendengarkan. Kamu boleh bercerita tanpa harus menerima saran sekarang."
            return ChatResponse(text, "rule_based_fallback", just_listen=True, mood_context=context)

        recommendation = None
        if request_quest:
            selected_energy = energy
            if selected_energy is None and context is not None:
                selected_energy = context.energy
            recommendation = recommend_quest(
                EnergyLevel(selected_energy or EnergyLevel.LOW.value),
                soft_mode=self.mood_settings.soft_mode,
            )

        if (self.external_provider is not None
                and self.consent.has_consent(ConsentPurpose.EXTERNAL_CHAT_PROCESSING)):
            try:
                text = self.external_provider.reply(message, history)
                mode = "configured_external_provider"
            except Exception:
                text = self.local_provider.reply(message, history)
                mode = "rule_based_fallback"
        else:
            text = self.local_provider.reply(message, history)
            mode = "rule_based_fallback"

        if recommendation is not None and recommendation.option is not None:
            text += (f" Kalau kamu mau, pilihan yang sesuai kondisi yang dilaporkan adalah "
                     f"{recommendation.option.title.lower()} ({recommendation.option.target}).")
        return ChatResponse(text, mode, quest_recommendation=recommendation, mood_context=context)

    @staticmethod
    def _bounded_history(history: list[dict[str, str]] | None) -> list[dict[str, str]]:
        if not isinstance(history, list):
            return []
        allowed = []
        for turn in history[-12:]:
            if not isinstance(turn, dict) or turn.get("role") not in {"user", "assistant"}:
                continue
            content = turn.get("content")
            if not isinstance(content, str) or not content.strip():
                continue
            if CalmaChatbot._possible_crisis(content):
                continue
            allowed.append({"role": turn["role"], "content": content.strip()[:1000]})
        return allowed

    def _mood_context(self) -> MoodContext | None:
        if not self.consent.has_consent(ConsentPurpose.MOOD_PERSONALIZATION):
            return None
        check_in = self.mood_settings.latest_check_in
        if check_in is None:
            return None
        return MoodContext(check_in.mood.value, check_in.energy.value)

    @staticmethod
    def _possible_crisis(message: str) -> bool:
        normalized = " ".join(message.casefold().split())
        return any(phrase in normalized for phrase in CRISIS_PHRASES)
