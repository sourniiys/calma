# CALMA Backend QA Checklist

## Otomatis

```powershell
python -m pytest tests -q
```

Suite ini mencakup password hashing, login salah, token expiry/revoke, akses
anonim, isolasi akun, encrypted SQLite at rest, salah/hilang key, legacy DB
plaintext, consent, endpoint, dan alur FIT lokal. Ganti hasil suite di dokumen
status hanya dengan output aktual terbaru.

## Walkthrough `/docs`

1. Provision satu `CALMA_DATA_ENCRYPTION_KEY` yang kuat dan simpan di secret
   manager lokal. Jangan commit secret.
2. Jalankan satu worker pada loopback:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn calma_backend.api:app --host 127.0.0.1 --port 8000
   ```

3. Buka `http://127.0.0.1:8000/docs`; registrasi lewat
   `POST /api/v1/auth/register`, lalu login di `POST /api/v1/auth/login`.
4. Authorize dengan bearer token. Token rahasia jangan disalin ke screenshot/log.
5. Tanpa token, endpoint privat harus `401`; health/register/login tetap publik.
6. Setelah token, grant `data_storage`; grant consent fitur terpisah sebelum
   memakai mood, HR, atau kontak. Revocation harus membuat write berikutnya `403`.
7. Uji Safety Plan/reward/quest; uji malformed JSON dan ID tidak ditemukan
   (422/404). Periksa file `data/calma_backend_users/<user_id>.sqlite3.enc`
   diawali Fernet token, bukan header `SQLite format 3`.
8. Buat akun kedua dan pastikan daftar mood/quest kosong serta DB user-ID berbeda.
9. Uji crisis information; 119 harus tersedia bagi user terautentikasi, tanpa
   bergantung pada chatbot. Countdown provider hanya simulasi.
10. Uji key salah/hilang hanya pada DB test terpisah; jangan merotasi key DB
    utama untuk QA.

## Batas QA

- Automated TestClient/OpenAPI sudah diuji. Browser/manual `/docs` tidak diklaim
  selesai sampai manusia menjalankan checklist ini.
- Belum dilakukan penetration test, review kriptografi profesional, backup/restore,
  key rotation, multi-process concurrency, atau stress test login.
- Jangan gunakan data pribadi nyata pada QA.