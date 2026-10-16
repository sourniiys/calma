import sys
import pathlib

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from tahap4_interaksi import ConsentManager, ConsentPurpose, Energy, Mood, MoodSettings
from tahap5_stress_quest import EnergyLevel, QuestTier
from tahap6_keamanan import PersonalSafetyPlan, SafetyContact, SafetyPlanStore
from tahap7_chatbot import CalmaChatbot, OpenAICompatibleProvider


class FakeProvider:
    def __init__(self, result="Balasan uji", fail=False):
        self.result = result
        self.fail = fail
        self.messages = []
        self.histories = []

    def reply(self, message, history=None):
        self.messages.append(message)
        self.histories.append(history or [])
        if self.fail:
            raise RuntimeError("simulated provider failure")
        return self.result


def _chat(tmp_path, mood=None, provider=None):
    consent = ConsentManager()
    consent.grant(ConsentPurpose.DATA_STORAGE)
    store = SafetyPlanStore(consent, tmp_path / "safety.json")
    store.update_plan(PersonalSafetyPlan(
        helpful_steps=("Hubungi teman",),
        emergency_contact=SafetyContact("Keluarga", "+628123456789"),
    ))
    return consent, store, CalmaChatbot(consent, store, mood, provider)


def test_empty_input_is_handled_without_provider_call(tmp_path):
    provider = FakeProvider()
    _, _, chatbot = _chat(tmp_path, provider=provider)
    response = chatbot.respond("  ")
    assert "tulis pesan" in response.text.lower()
    assert response.mode == "rule_based_fallback"
    assert provider.messages == []


def test_normal_response_is_indonesian_supportive_and_non_diagnostic(tmp_path):
    _, _, chatbot = _chat(tmp_path)
    response = chatbot.respond("Hari ini terasa berat")
    assert "Terima kasih" in response.text
    assert "diagnosis" not in response.text.lower()
    assert response.mode == "rule_based_fallback"


def test_local_fallback_uses_conversation_context_for_practical_advice(tmp_path):
    _, _, chatbot = _chat(tmp_path)
    response = chatbot.respond(
        "Apa yang harus kulakukan?",
        history=[{"role": "user", "content": "Aku kewalahan dengan deadline kerja."}],
    )
    assert "pekerjaan" in response.text
    assert "10 menit" in response.text


def test_just_listen_does_not_append_advice(tmp_path):
    _, _, chatbot = _chat(tmp_path)
    response = chatbot.respond("Aku ingin cerita", just_listen=True)
    assert response.just_listen
    assert "mendengarkan" in response.text.lower()
    assert "saran" in response.text.lower()


def test_quest_suggestion_uses_reported_energy_and_soft_mode(tmp_path):
    _, _, chatbot = _chat(tmp_path)
    response = chatbot.respond("Boleh saran aktivitas?", request_quest=True,
                               energy=EnergyLevel.HIGH)
    assert response.quest_recommendation.option.tier == QuestTier.STANDARD
    assert "target langkah" in response.text.lower()


def test_mood_context_is_used_only_with_specific_consent(tmp_path):
    mood = MoodSettings()
    mood.check_in(Mood.LOW, Energy.LOW)
    consent, _, chatbot = _chat(tmp_path, mood)
    assert chatbot.respond("Halo").mood_context is None

    consent.grant(ConsentPurpose.MOOD_PERSONALIZATION)
    context = chatbot.respond("Halo").mood_context
    assert context.mood == "low"
    assert context.energy == "low"


def test_external_provider_requires_consent_and_failure_falls_back(tmp_path):
    consent, _, chatbot = _chat(tmp_path, provider=FakeProvider())
    assert chatbot.respond("Halo").mode == "rule_based_fallback"
    assert chatbot.external_provider.messages == []

    consent.grant(ConsentPurpose.EXTERNAL_CHAT_PROCESSING)
    history = [{"role": "user", "content": "Aku sedang banyak pikiran."}]
    assert chatbot.respond("Halo", history=history).mode == "configured_external_provider"
    assert chatbot.external_provider.histories[-1] == history

    failing = FakeProvider(fail=True)
    _, _, fallback_chat = _chat(tmp_path / "other", provider=failing)
    fallback_chat.consent.grant(ConsentPurpose.EXTERNAL_CHAT_PROCESSING)
    response = fallback_chat.respond("Halo")
    assert response.mode == "rule_based_fallback"
    assert "Terima kasih" in response.text


def test_crisis_phrase_opens_safety_access_without_calling_provider(tmp_path):
    provider = FakeProvider()
    _, _, chatbot = _chat(tmp_path, provider=provider)
    response = chatbot.respond("Saya ingin mengakhiri hidup")
    assert response.mode == "local_safety_route"
    assert response.crisis_access.emergency_number == "119"
    assert response.crisis_access.emergency_contact.name == "Keluarga"
    assert provider.messages == []


def test_api_provider_configuration_is_optional_and_validated(monkeypatch):
    for key in ("CALMA_CHAT_API_KEY", "CALMA_CHAT_API_URL", "CALMA_CHAT_MODEL"):
        monkeypatch.delenv(key, raising=False)
    assert OpenAICompatibleProvider.from_environment() is None
    with pytest.raises(ValueError, match="HTTP/HTTPS"):
        OpenAICompatibleProvider("key", "not-a-url", "model")


def test_remote_provider_does_not_receive_mood_or_physiological_context(tmp_path):
    consent, _, chatbot = _chat(tmp_path, provider=FakeProvider())
    mood = MoodSettings()
    mood.check_in(Mood.LOW, Energy.LOW)
    chatbot.mood_settings = mood
    consent.grant(ConsentPurpose.MOOD_PERSONALIZATION)
    consent.grant(ConsentPurpose.EXTERNAL_CHAT_PROCESSING)

    chatbot.respond("Saya merasa lelah", history=[{
        "role": "user", "content": "Aku khawatir soal pekerjaan.",
    }])
    assert chatbot.external_provider.messages == ["Saya merasa lelah"]
    assert chatbot.external_provider.histories[-1] == [{
        "role": "user", "content": "Aku khawatir soal pekerjaan.",
    }]