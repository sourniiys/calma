# Tahap 7 - Chatbot CALMA

`CalmaChatbot` menggunakan `RuleBasedProvider` lokal sebagai fallback. Fitur
`just_listen` tidak memberi saran, kata kunci krisis membuka safety plan dan
informasi 119 langsung sebelum provider dipanggil, dan permintaan quest memakai
modul Tahap 5.

Konteks mood hanya dibaca setelah consent `MOOD_PERSONALIZATION` aktif. Provider
eksternal opsional hanya dipakai dengan consent `EXTERNAL_CHAT_PROCESSING`.
Provider OpenAI-compatible membaca `CALMA_CHAT_API_KEY`, `CALMA_CHAT_API_URL`,
dan `CALMA_CHAT_MODEL` dari environment; konteks mood, HR, dan skor tidak
dikirim. Pesan teks pengguna hanya dikirim setelah izin tersebut aktif.

Jika API tidak dikonfigurasi, gagal, atau tidak mendapat izin, chatbot tetap
berjalan secara lokal. Fallback adalah aturan sederhana, bukan LLM.

Jalankan tes: `python -m pytest tests/test_tahap7.py -q`.

Status: logika lokal dan tes sudah dibuat. Jawaban provider eksternal tidak dapat
dijamin selalu aman; jalur krisis lokal tetap berjalan sebelum pemanggilan API.