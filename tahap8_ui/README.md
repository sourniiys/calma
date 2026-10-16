# Tahap 8 - Antarmuka Streamlit

`app.py` menghubungkan modul Tahap 4-7 tanpa menyalin rumus atau aturan bisnis.
Menu mencakup onboarding, Dashboard/status baseline, consent, mood/Soft Mode,
Stress Quest, riwayat, chatbot, Safety Plan, dan Crisis Mode.

Jalankan dari PowerShell di root repository:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Streamlit ditambahkan ke `requirements.txt`. Smoke test UI memakai `AppTest`:
`python -m pytest tests/test_app.py -q`.

Dashboard membaca data aktual di `data/`; ia menandai pemantauan real-time belum
tersedia karena cakupan FIT terbatas dan tidak ada langkah per menit. Untuk tes
terisolasi, path bisa diarahkan lewat `CALMA_DATA_DIR`, `CALMA_GARMIN_DIR`, dan
`CALMA_DAILY_CSV`.

Consent dan safety plan disimpan lokal sesuai izin. Quest, mood, serta riwayat
chat disimpan di session state dan belum bertahan setelah sesi Streamlit berakhir.
Countdown perlu diperiksa pengguna setelah 10 menit dan provider tetap simulasi.
UI belum mempunyai autentikasi, enkripsi lokal, koneksi smartwatch, atau layanan
telekonsultasi.