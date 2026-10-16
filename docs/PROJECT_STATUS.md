# CALMA Project Status

## Ringkasan

Proyek CALMA saat ini sudah berfungsi sebagai prototype backend lokal yang mengolah data historis, mendukung autentikasi lokal, dan menyimpan data sensitif per akun dalam format terenkripsi. Fungsionalitas inti untuk analisis data, consent, mood, quest, keamanan dasar, dan API teruji secara otomatis.

Namun, proyek ini belum siap untuk produksi, real-time wearable, atau diagnosis klinis. Integrasi layanan eksternal dan model AI masih terbatas pada lingkungan lokal dan data historis.

## Status fitur

### Sudah terverifikasi
- backend FastAPI lokal
- autentikasi lokal dengan akun per user
- bearer token dan revoke
- data per-user terisolasi
- file SQLite terenkripsi dengan Fernet
- guard atas key yang hilang/salah
- protection terhadap legacy SQLite plaintext yang masih berisi data
- evaluasi model historis dan baseline
- suite automated test yang berjalan

### Masih terbatas
- model prediksi belum lebih baik dari mean baseline
- warning dependency `starlette.testclient`/`httpx` dan `fitparse` masih muncul
- tidak ada integrasi real ke smartwatch, SMS, WhatsApp, atau teleconsultation
- tidak ada MFA, reset password, atau delete akun yang lengkap
- tidak ada key rotation otomatis dan backup/restore workflow formal

## Status nyata

### Backend
Status: prototype lokal yang berfungsi dengan data historis.

### AI model
Status: eksperimen, bukan prediksi klinis.

### Keamanan
Status: aman untuk lingkungan lokal yang dibatasi, belum siap untuk deployment publik.

### Integrasi eksternal
Status: simulasi/fallback lokal, belum terhubung ke layanan nyata.

## Tindakan berikutnya paling masuk akal

1. Mengurangi warning dependency yang tersisa.
2. Menyelesaikan dokumentasi model, deployment, security, dan migration.
3. Menutup QA final tanpa klaim melebihi bukti hasil tes.
