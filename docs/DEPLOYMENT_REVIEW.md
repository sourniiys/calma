# Deployment Review

## Scope

Dokumen ini menjelaskan pendekatan deployment yang didukung oleh kode saat ini.

## Model deployment yang didukung

Saat ini backend CALMA mendukung:
- server lokal loopback
- proses Uvicorn tunggal
- data lokal dan encrypted SQLite
- runtime environment yang memuat `CALMA_DATA_ENCRYPTION_KEY`

## Yang tidak didukung secara aman

- multi-process / multi-worker public deployment
- exposure ke internet publik
- live smartwatch sync
- real external integrations
- production-grade load balancing
- real-time health monitoring

## Persyaratan runtime

Sebelum menjalankan server:

```powershell
$key = & .\.venv\Scripts\python.exe -c "from calma_backend.security import LocalDataCipher; print(LocalDataCipher.generate_key_for_operator())"
$env:CALMA_DATA_ENCRYPTION_KEY = $key
```

Lalu jalankan:

```powershell
.\.venv\Scripts\python.exe -m uvicorn calma_backend.api:app --host 127.0.0.1 --port 8000
```

## Batasan yang harus dijaga

- satu worker saja
- bind hanya ke loopback
- jangan mempublikasikan port ke jaringan publik
- jangan memindahkan key ke Git atau file yang di-commit
- jangan mengaktifkan worker multiproses tanpa evaluasi database dan locking yang jelas

## Kesimpulan

Deployment yang didukung saat ini adalah deployment lokal prototype untuk pengujian developer. Ini bukan deployment final untuk produksi atau penggunaan public.
