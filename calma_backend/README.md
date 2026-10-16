# CALMA AI Core dan Backend API

## Menjalankan backend

### Kunci enkripsi

API berhenti saat startup jika `CALMA_DATA_ENCRYPTION_KEY` kosong atau tidak
valid. Buat kunci sekali dengan perintah berikut, lalu simpan secara aman di
password manager/secret store lokal. Jangan membuat kunci baru untuk membuka
database yang sudah ada:

```powershell
$key = & .\.venv\Scripts\python.exe -c "from calma_backend.security import LocalDataCipher; print(LocalDataCipher.generate_key_for_operator())"
[Environment]::SetEnvironmentVariable('CALMA_DATA_ENCRYPTION_KEY', $key, 'User')
$env:CALMA_DATA_ENCRYPTION_KEY = $key
```

Perintah pertama menghasilkan secret. Jangan menaruh hasilnya di repository,
log, chat, atau screenshot. Tutup dan buka ulang PowerShell setelah key disimpan
ke environment Windows. `.env.example` adalah template saja; aplikasi tidak
membaca `.env` otomatis. Jika key hilang/salah, data tidak didekripsi dan key
baru tidak dibuat.

### Menjalankan server

Aktifkan virtual environment repository, lalu dari root proyek jalankan:

```powershell
.\.venv\Scripts\python.exe -m uvicorn calma_backend.api:app --host 127.0.0.1 --port 8000
```

OpenAPI interaktif tersedia di `http://127.0.0.1:8000/docs`; skema mentah di
`http://127.0.0.1:8000/openapi.json`. Backend hanya di-bind ke loopback secara
default pada perintah di atas. Tidak ada frontend yang dibuat pada pekerjaan ini.

DB akun terenkripsi dibuat pada `data/calma_backend.enc`; DB per akun berada di
`data/calma_backend_users/<user_id>.sqlite3.enc`. Semua akun memakai key lokal
yang sama. `CALMA_DB_PATH` dapat mengganti lokasi DB akun. File FIT dibaca dari
`CALMA_GARMIN_DIR/<user_id>/`, CSV/model metadata dapat dikonfigurasi melalui
`CALMA_DAILY_CSV` dan `CALMA_MODEL_METADATA`.

## Endpoint

| Method | Endpoint | Tujuan |
|---|---|---|
| GET | `/api/v1/health` | Status backend |
| GET | `/api/v1/baseline/status` | Kesiapan baseline dari FIT; consent data diperlukan |
| POST | `/api/v1/stress/analyze` | Analisis file lokal, bukan monitor live |
| GET | `/api/v1/stress/events` | Event tersimpan; consent penyimpanan diperlukan |
| POST | `/api/v1/stress/events/{id}/confirmation` | Jawaban `yes`, `no`, `unsure` |
| GET/PUT | `/api/v1/consents`, `/api/v1/consents/{purpose}` | Baca/ubah consent |
| GET/POST | `/api/v1/mood-checkins` | Simpan/baca check-in sesuai consent |
| PUT | `/api/v1/preferences/soft-mode` | Simpan preferensi Soft Mode |
| POST/GET | `/api/v1/quests/recommendations`, `/api/v1/quests` | Rekomendasi dan sesi quest |
| POST | `/api/v1/quests/{id}/complete`, `/cancel`, `/evaluation` | Selesaikan, lewati, evaluasi quest |
| GET/PUT/DELETE | `/api/v1/safety-plan` | Kelola safety plan lokal |
| POST | `/api/v1/safety-plan/migrate-legacy` | Migrasi JSON legacy dengan consent; file asal dipertahankan |
| GET/POST | `/api/v1/rewards/status`, `/claims` | Reward demo; maksimal tiga klaim per minggu |
| POST | `/api/v1/chatbot/messages` | Chatbot lokal/API opsional yang consent-gated |
| GET | `/api/v1/crisis-information` | Safety plan dan informasi 119 tanpa chatbot |
| GET | `/api/v1/support/status` | Opsi dukungan setelah tiga tanggal event berbeda |
| POST | `/api/v1/support/escalation/countdown`, `/cancel`, `/complete` | Countdown yang dapat dibatalkan dan provider simulasi |
| GET | `/api/v1/models/historical/evaluation` | Metadata evaluasi model yang tersimpan |

## Chatbot kontekstual

Chat menyertakan maksimal 12 giliran percakapan sebelumnya; riwayat ini hanya
dipakai selama sesi dan tidak disimpan backend. Tanpa provider eksternal, CALMA
menggunakan fallback lokal berbasis aturan sehingga cakupan jawabannya terbatas.
Untuk kemampuan bahasa yang lebih luas, atur provider OpenAI-compatible sebelum
menjalankan server:

```powershell
$env:CALMA_CHAT_API_KEY = '<API key dari provider pilihanmu>'
$env:CALMA_CHAT_API_URL = 'https://provider.example/v1/chat/completions'
$env:CALMA_CHAT_MODEL = '<nama model>'
```

Jangan masukkan API key ke repository, frontend, chat, atau screenshot. Pesan
beserta riwayat percakapan hanya dikirim ke provider setelah pengguna memberi
consent `external_chat_processing`; data mood dan fisiologis tidak ikut dikirim.
Provider tidak dikonfigurasi otomatis dan biaya/retensi datanya mengikuti
kebijakan provider pilihanmu.

Contoh consent sebelum menyimpan data:

```powershell
curl.exe -X PUT http://127.0.0.1:8000/api/v1/consents/data_storage `
  -H "Content-Type: application/json" -d "{`"granted`":true}"
```

Contoh check-in setelah consent `data_storage` dan `mood_personalization`
diberikan:

```json
{"mood":"low","energy":"low"}
```

Gunakan tes API dengan `python -m pytest tests/test_backend_api.py -q` dan suite
lengkap dengan `python -m pytest tests -q`.

## Arsitektur dan batasan

- `historical_model.py`: eksperimen skor Garmin harian, memakai fitur hari
  sebelumnya dan split kronologis.
- `database.py`: SQLite per akun untuk consent, baseline, event, mood, preferensi,
  quest, safety plan, reward, countdown, dan percobaan escalation.
- `auth.py`: password di-hash scrypt per akun; bearer token acak berlaku 60 menit,
  disimpan hanya sebagai hash dan bisa dicabut.
- `security.py` / `encrypted_sqlite.py`: seluruh file SQLite dienkripsi dengan
  Fernet saat tersimpan. SQLite berada plaintext di memori selama proses berjalan;
  ini bukan SQLCipher dan bukan enkripsi memory/swap.
- `services.py`: orkestrasi service tahap 1-7; tidak menghitung ulang formula.
- `schemas.py` dan `api.py`: kontrak Pydantic/FastAPI serta status HTTP.
- Safety plan lama dapat dimigrasikan melalui endpoint khusus setelah consent
  storage aktif; file JSON tidak dihapus otomatis.
- Provider SMS tetap simulasi. Countdown harus diselesaikan lewat API; tidak ada
  scheduler latar belakang. Booking telekonsultasi dan provider LLM belum
  dikonfigurasi.
- SQLCipher tidak tersedia sebagai wheel kompatibel di environment ini; Fernet
  dipakai untuk enkripsi seluruh file DB. Key rotation/backup restore belum punya
  prosedur otomatis.
- Data FIT per akun harus disediakan manual pada subfolder user-ID. CSV historis
  dan model metadata dibaca bersama sebagai data eksperimen statis, bukan data
  personal terisolasi.
- Server DB encrypted mendukung satu proses Uvicorn; jangan gunakan `--workers`
  lebih dari satu karena masing-masing proses menyimpan snapshot SQLite in-memory.
- Jika ditemukan database SQLite plaintext lama berisi row, startup ditolak.
  File tidak dihapus; migrasi pemilik data harus dilakukan eksplisit. Safety Plan
  legacy hanya dapat dimigrasikan dari path per user, tetap dengan sumber asli.
- Belum ada MFA, rate limit login, reset password, account deletion, backup/key
  rotation workflow, atau review keamanan profesional. Jangan expose ke jaringan
  publik.
- FIT yang tersedia hanya memberi 404 menit HR pada satu hari dan tidak memberi
  langkah per menit. Baseline API karena itu belum siap dan deteksi bersifat
  analisis file, bukan real-time.