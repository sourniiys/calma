# CALMA – Proyek AI per Tahap

Folder ini disusun **per tahap**. Kerjakan berurutan; tiap folder punya README sendiri
dan satu skrip `jalankan.py`.

## Mulai dari sini (3 langkah)

```bash
pip install -r requirements.txt          # 1. pasang library (sekali saja)
python tahap1_data/jalankan.py           # 2. jalankan Tahap 1, lihat hasilnya
python -m pytest tests                   # 3. pastikan semua tes lolos
```
Lalu lanjut `tahap2_baseline/jalankan.py` dan `tahap3_deteksi/jalankan.py`.
Grafik hasil tersimpan di folder `hasil/`.

## Peta tahap

| Tahap | Folder | Pertanyaan yang dijawab | Status |
|---|---|---|---|
| 1 | `tahap1_data/` | Dari mana datanya? (simulator + data Garmin nyata) | ✅ selesai |
| 2 | `tahap2_baseline/` | Berapa detak jantung "normal" pengguna ini? | ✅ selesai |
| 3 | `tahap3_deteksi/` | Kapan detak jantung cukup menyimpang = potensi stres? | ✅ selesai |
| 4 | `tahap4_interaksi/` | Consent, mood check-in, dan state machine konfirmasi pengguna | ✅ selesai (logic diuji) |
| 5 | `tahap5_stress_quest/` | Stress Quest, evaluasi pemulihan, dan personalisasi | ✅ selesai (logic diuji; belum terhubung ke perangkat) |
| 6 | `tahap6_keamanan/` | Safety plan, consent-based escalation, crisis access | ✅ selesai (simulasi lokal; logic diuji) |
| 7 | `tahap7_chatbot/` | Chatbot suportif, just-listen, dan fallback lokal | ✅ selesai (logic diuji) |
| 8 | `app.py` | UI Streamlit onboarding hingga Crisis Mode | ✅ selesai (halaman diuji) |
| 9 | `tests/test_end_to_end.py` | Integrasi lintas modul CALMA | ✅ selesai (alur sintetis diuji) |
| 10 | _(QA akhir)_ | Pengujian manual, privasi, dan keterbatasan produksi | ⏳ |
| Backend | `calma_backend/` | Model historis, SQLite, FastAPI | ✅ implementasi diuji; belum siap produksi |

## Alur data (cara tahap saling terhubung)

```
Tahap 1: data per menit (hr, steps)
   └─> Tahap 2: BaselineModel.fit(data)  -> mu, sigma pribadi
          └─> Tahap 3: hitung_skor(model, data) -> skor 0-100
                 └─> detect_events(skor)  -> "potensi stres" -> (Tahap 4: tanya pengguna)
```

## Struktur
```
README.md  requirements.txt
app.py                    aplikasi Streamlit lokal
data/garmin_user1/     file .fit Garmin pengguna
hasil/                 grafik keluaran
tahap1_data/           simulator.py, garmin_loader.py, jalankan.py
tahap2_baseline/       fitur.py, baseline.py, jalankan.py
tahap3_deteksi/        skor.py, deteksi.py, jalankan.py
tahap4_interaksi/   consent, mood, dan state machine pengguna
tahap5_stress_quest/ rekomendasi, pencatatan, evaluasi, dan reward demo
tahap6_keamanan/    safety plan, consent countdown, crisis access
tahap7_chatbot/     fallback suportif dan provider API opsional
tahap8_ui/          dokumentasi antarmuka Streamlit
calma_backend/      model historis, repository SQLite, service, API FastAPI
tests/                 tes tahap 1-7, UI, dan integrasi end-to-end
```

## Backend API

Pasang dependensi dan jalankan API dari PowerShell di root proyek:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn calma_backend.api:app --host 127.0.0.1 --port 8000
```

Dokumentasi endpoint tersedia di `http://127.0.0.1:8000/docs`. SQLite runtime
disimpan di `data/calma_backend.sqlite3`. Cara kerja dan endpoint lengkap ada di
`calma_backend/README.md`.

Untuk mengulang evaluasi ML pada CSV asli tanpa menimpa model lama:

```powershell
.\.venv\Scripts\python.exe -c "from calma_backend.historical_model import train_historical_model; print(train_historical_model('data/calma_harian_bersih.csv', 'hasil/model_historis/validation_20261016'))"
```

Aplikasi Streamlit lama tetap ada, tetapi tidak dikembangkan atau diubah pada
pekerjaan backend ini.

Tahap 4 menyimpan riwayat consent secara lokal bila diberi path JSON; seluruh
consent tertutup secara default. Check-in mood hanya menyarankan Soft Mode,
yang tetap harus diaktifkan pengguna. State machine menerima event dari Tahap 3
dan mencatat jawaban ya/tidak/belum yakin tanpa mengubah skor sensor menjadi
konfirmasi stres.

Tahap 6 menggunakan consent Tahap 4, termasuk consent penyimpanan yang terpisah.
Safety plan disimpan lokal setelah izin diberikan. Countdown kontak 10 menit
dapat dibatalkan; provider bawaan hanya simulasi dan tidak mengirim pesan nyata.
Chatbot lokal berbasis aturan tersedia tanpa API. Provider eksternal hanya dipakai
dengan konfigurasi dan consent khusus. Lihat `DEVELOPMENT_STATUS.md` untuk
progres, hasil tes, dan keterbatasan.

## Temuan penting sejauh ini
1. Baseline global persis proposal menghasilkan banyak alert palsu (precision ~0,12 di simulasi);
   baseline **per jam** + cooldown pasca-aktivitas menaikkannya ke ~0,50.
2. Tanpa data langkah/gerak, precision turun ke ~0,20. **Data gerak diperlukan.**
3. Data Garmin yang ada baru < 1 hari (perlu 7–14 hari) sehingga baseline masih **sementara**.
4. Data harian nyata (`data/calma_harian_bersih.csv`, 774 hari): resting HR bergeser jauh (±50–103 bpm). Baseline beku menandai 34% hari di 2026 sebagai 'tinggi', baseline diperbarui hanya 7% (`tahap2_baseline/uji_drift_harian.py`).
5. Semua angka dari simulasi **bukan bukti akurasi**; butuh data nyata + label dari pengguna.
