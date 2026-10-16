from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[1] / "app.py"


def _isolate_app_data(monkeypatch, tmp_path):
    monkeypatch.setenv("CALMA_DATA_DIR", str(tmp_path / "local-data"))
    monkeypatch.setenv("CALMA_GARMIN_DIR", str(tmp_path / "no-garmin-files"))
    monkeypatch.setenv("CALMA_DAILY_CSV", str(tmp_path / "no-daily-data.csv"))


def test_streamlit_app_loads_and_shows_real_data_limitations(monkeypatch, tmp_path):
    _isolate_app_data(monkeypatch, tmp_path)
    app = AppTest.from_file(str(APP)).run(timeout=20)
    app.radio[0].set_value("Dashboard").run(timeout=20)

    assert not app.exception
    assert any("Pemantauan real-time belum tersedia" in item.value for item in app.info)
    assert any("CALMA" in item.value for item in app.markdown)


def test_onboarding_routes_to_consent_settings(monkeypatch, tmp_path):
    _isolate_app_data(monkeypatch, tmp_path)
    app = AppTest.from_file(str(APP)).run(timeout=20)
    assert any("Selamat datang" in item.value for item in app.subheader)

    app.button(key="onboarding_consent").click().run(timeout=20)
    assert not app.exception
    assert any("Consent & Privasi" in item.value for item in app.title)


def test_crisis_mode_is_directly_navigable_without_chatbot(monkeypatch, tmp_path):
    _isolate_app_data(monkeypatch, tmp_path)
    app = AppTest.from_file(str(APP)).run(timeout=20)
    app.radio[0].set_value("Crisis Mode").run(timeout=20)

    assert not app.exception
    visible_text = " ".join(
        item.value for elements in (app.markdown, app.caption, app.error)
        for item in elements
    )
    assert "119" in visible_text
    assert "bukan layanan darurat" in visible_text


def test_soft_mode_toggle_changes_user_controlled_state(monkeypatch, tmp_path):
    _isolate_app_data(monkeypatch, tmp_path)
    app = AppTest.from_file(str(APP)).run(timeout=20)
    app.radio[0].set_value("Mood Check-in").run(timeout=20)
    app.button(key="toggle_soft_mode").click().run(timeout=20)

    assert not app.exception
    assert app.session_state["calma_services"]["mood"].soft_mode is True


def test_all_navigation_pages_render_without_exceptions(monkeypatch, tmp_path):
    _isolate_app_data(monkeypatch, tmp_path)
    app = AppTest.from_file(str(APP)).run(timeout=20)
    for page in ("Dashboard", "Consent & Privasi", "Mood Check-in", "Stress Quest",
                 "Riwayat", "Chatbot", "Safety Plan", "Crisis Mode"):
        app.radio[0].set_value(page).run(timeout=20)
        assert not app.exception, f"Halaman {page} menimbulkan exception"