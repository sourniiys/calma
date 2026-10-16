# CALMA Development Status

Pembaruan terakhir: 2026-10-16

## Status Tahap

| Tahap | Status | Catatan |
|---|---|---|
| 1 - Data | SUDAH DIUJI | Loader FIT dan simulator tersedia; keterbatasan data dicatat di README. |
| 2 - Baseline | SUDAH DIUJI | Baseline personal, status kesiapan, dan filter aktivitas tersedia. |
| 3 - Deteksi | SUDAH DIUJI | Skor dan deteksi threshold tersedia; validasi berdasarkan data nyata masih terbatas. |
| 4 - Interaksi | SUDAH DIUJI | Consent, mood, Soft Mode pilihan pengguna, dan konfirmasi event. |
| 5 - Stress Quest | SUDAH DIUJI | Rekomendasi, pencatatan, evaluasi, personalisasi aturan, reward demo. |
| 6 - Keselamatan | SUDAH DIUJI | Safety plan lokal, consent gate, countdown simulasi, rate limit, crisis access. |
| 7 - Chatbot | SUDAH DIUJI | Fallback lokal, just-listen, gate consent untuk mood/API, akses krisis sebelum provider. |
| 8 - UI | SUDAH DIUJI | Aplikasi Streamlit lokal; seluruh navigasi diuji dengan AppTest. |
| 9 - Integrasi | SUDAH DIUJI | UI lama memanggil modul; backend FastAPI/SQLite kini juga menghubungkan service dan diuji. |
| 10 - Pengujian akhir | SEBAGIAN DIUJI | Suite otomatis lulus; QA privasi, keamanan lokal, dan uji manual belum lengkap. |

## Prioritas Keamanan (pembaruan 2026-10-16)

- Akun: email unik, password scrypt+salt, login generic failure, bearer token 60 menit disimpan sebagai hash, logout/revoke; semua `/api/v1` privat kecuali health/register/login.
- Isolasi: DB encrypted terpisah per server-generated user-ID; lokasi FIT juga per-user. Tes memeriksa pengguna A tidak melihat mood/quest pengguna B.
- At-rest: seluruh file SQLite akun/per-user disimpan sebagai Fernet ciphertext. Key wajib dari `CALMA_DATA_ENCRYPTION_KEY`; missing/wrong key menghentikan startup/dekripsi. Tidak ada auto-key. Legacy plaintext DB berisi row menolak startup dan tidak dihapus.
- Batas enkripsi: DB berada plaintext di memori saat proses berjalan; backup, swap, memory dump, Safety Plan legacy source, dan data yang diekspor tidak otomatis dienkripsi. SQLCipher tidak tersedia sebagai wheel kompatibel Python 3.15 di environment ini.
- Operasional: satu proses Uvicorn saja; belum ada multi-worker locking, MFA, login rate limit, reset password, penghapusan akun, atau prosedur key rotation/restore.

## Perubahan Tahap 6

- Menambahkan `DATA_STORAGE` pada consent Tahap 4 agar izin penyimpanan terpisah.
- Menambahkan `tahap6_keamanan/plan.py` untuk safety plan lokal dengan validasi input, baca/hapus setelah pencabutan, dan riwayat percobaan.
- Menambahkan `tahap6_keamanan/escalation.py` untuk countdown 10 menit yang dapat dibatalkan, pengecekan ulang consent/kontak, provider simulasi, dan batas satu percobaan per 24 jam.
- Menambahkan penawaran dukungan profesional setelah event terjadi pada tiga tanggal berbeda; booking belum terintegrasi.
- Menambahkan `tahap6_keamanan/crisis.py` untuk akses langsung safety plan, kontak darurat, dan 119.
- Menambahkan `tests/test_tahap6.py` dan dokumentasi tahap.

## Perubahan Tahap 7

- Menambahkan `tahap7_chatbot/chatbot.py`: fallback suportif Bahasa Indonesia, just-listen, saran Stress Quest, dan jalur krisis lokal.
- Menambahkan provider chat-completions opsional dengan timeout, konfigurasi melalui environment, fallback saat error, dan gate `EXTERNAL_CHAT_PROCESSING`.
- Mood hanya dipakai setelah consent `MOOD_PERSONALIZATION`; provider eksternal hanya menerima teks pengguna, bukan HR, skor, atau mood.
- Menambahkan `tests/test_tahap7.py` dan dokumentasi tahap.

## Perubahan Tahap 8

- Menambahkan `app.py` dengan onboarding, dashboard, consent, mood, quest, riwayat, chatbot, safety plan, dan Crisis Mode.
- Menambahkan Streamlit pada `requirements.txt` dan `tests/test_app.py` dengan AppTest.
- Dashboard memisahkan ringkasan harian dari deteksi personal dan menyatakan keterbatasan Garmin.
- Status penyimpanan: consent/safety plan lokal; state quest, mood, dan chat masih session-only.

## Perubahan Tahap 9

- Menambahkan `tests/test_end_to_end.py` untuk menghubungkan deteksi event sintetis, konfirmasi, consent, mood, Stress Quest, evaluasi pemulihan, personalisasi, chatbot, crisis access, dan countdown simulasi yang dapat dibatalkan.
- Event dan skor dalam tes integrasi adalah data sintetis untuk tes, bukan data Garmin.

## AI Core dan Backend API (pembaruan 2026-10-16)

- `calma_backend/historical_model.py` dievaluasi pada CSV asli. Data mempunyai 774 baris, 635 target valid, 629 pasangan target dengan fitur hari sebelumnya, dan 559 baris yang dapat dipakai saat persistence baseline juga memerlukan skor sebelumnya.
- Artefak validasi terbaru disimpan terpisah di `hasil/model_historis/validation_20261016/`; file model/metadata lama tidak ditimpa.
- Split kronologis menghasilkan 447 baris train dan 112 test (2026-04-02–2026-10-06). Random Forest: MAE 10.1898, RMSE 14.3492, R² -0.0484. Baseline mean: MAE 10.1543, RMSE 14.1331, R² -0.0171. Model belum mengungguli mean baseline. Skor yang diprediksi adalah skor Garmin, bukan kondisi mental klinis.
- `calma_backend/database.py` menyimpan consent, baseline, event/konfirmasi, mood, preferensi, quest/evaluasi, safety plan, attempts countdown, dan reward demo.
- `calma_backend/services.py`, `schemas.py`, dan `api.py` menghubungkan domain service ke FastAPI. Endpoint resmi tercantum di `calma_backend/README.md` dan OpenAPI `/docs`.
- Safety Plan JSON legacy dimigrasikan melalui endpoint dengan consent storage; sumber tidak dihapus dan migrasi berulang tidak menggandakan data.
- `tests/test_backend_api.py`, `tests/test_backend_database.py`, dan `tests/test_historical_model.py` menguji kontrak, persistence, consent, dan ML.

## Verifikasi

Interpreter: `.venv\\Scripts\\python.exe` (Python yang tersedia di repo).

Perintah sebelum perubahan Tahap 6:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Hasil: 26 passed, exit code 0.

Tes fokus Tahap 6:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tahap6.py -q
```

Hasil: 10 passed, exit code 0.

Suite lengkap setelah Tahap 6:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Hasil: 36 passed, exit code 0.

Tes fokus Tahap 7:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tahap7.py -q
```

Hasil: 9 passed, exit code 0.

Suite lengkap setelah Tahap 7:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Hasil: 45 passed, exit code 0.

Tes fokus UI:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_app.py -q
```

Hasil: 5 passed, exit code 0.

Suite lengkap setelah Tahap 8:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Hasil: 50 passed, exit code 0.

Tes fokus integrasi:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_end_to_end.py -q
```

Hasil: 2 passed, exit code 0.

Suite lengkap terakhir setelah Tahap 9:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Hasil sebelum backend API: 52 passed, exit code 0.

Suite lengkap terakhir setelah penambahan backend:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Hasil: 81 passed, exit code 0; terdapat warning deprecation dari `fitparse` pada Python 3.15 serta warning penggunaan HTTPX oleh `starlette.testclient`. Keduanya tidak menyebabkan kegagalan tes.

## Integrasi dan Simulasi

- Provider bawaan tidak mengirim pesan nyata. Status `SIMULATED_ONLY` secara eksplisit berarti tidak ada SMS/pesan terkirim.
- Tidak ada provider telekonsultasi atau booking.
- Chatbot fallback adalah rule-based, bukan LLM. Belum ada API key atau provider eksternal yang dikonfigurasi.
- API countdown dipersistenkan, tetapi penyelesaian masih perlu dipanggil melalui endpoint; belum ada scheduler latar belakang.
- API belum memiliki autentikasi; data SQLite lokal sensitif tidak dienkripsi.
- API menyimpan safety plan, countdown, dan percobaan escalation di SQLite; service legacy `SafetyPlanStore` masih dapat memakai JSON. Penyimpanan lokal belum dienkripsi dan autentikasi aplikasi belum ada.
- Tidak ada data pribadi yang dicatat ke log aplikasi oleh modul Tahap 6.

## Data dan Keterbatasan

- `data/calma_harian_bersih.csv`: 774 baris, 18 kolom ringkasan harian.
- FIT Garmin memberi 404 menit HR valid pada 2026-10-06 10:57–17:40; data per-menit tidak memiliki langkah.
- Karena itu, aplikasi belum memiliki pemantauan real-time, validasi 5.000 langkah dari perangkat, atau deret pemulihan nyata yang cukup.
- `Proposal CALMA.pdf` tidak ditemukan di workspace. Dokumentasi repo dan spesifikasi pengguna dipakai sebagai acuan.
- Streamlit 1.66.0 terpasang di `.venv`, dan UI ada di `app.py`.
- Backend API tersedia di `calma_backend/api.py`; jalankan dengan Uvicorn sesuai `calma_backend/README.md`.

## Lanjutkan

1. Jalankan API FastAPI lokal dan cek endpoint melalui OpenAPI `/docs`.
2. Lakukan review keamanan manual; autentikasi dan enkripsi database belum tersedia.
3. Jangan expose API ke jaringan publik atau mengaktifkan pengiriman nyata tanpa provider dan izin terkonfigurasi.