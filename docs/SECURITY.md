# Security Review

## Ringkasan implementasi

Sistem backend lokal saat ini telah menambahkan beberapa perlindungan dasar:

- password akun di-hash dengan scrypt dan salt unik
- bearer token disimpan sebagai hash, bukan token plaintext
- endpoint privat memerlukan autentikasi dan data per user terisolasi
- file database per akun dan per-user disimpan dalam bentuk terenkripsi (Fernet)
- key enkripsi wajib tersedia dari environment variable `CALMA_DATA_ENCRYPTION_KEY`
- wrong/missing key gagal dengan status fail-closed
- legacy SQLite plaintext berisi data akan memblokir startup

## Apakah ini aman untuk produksi?

Tidak. Ini masih prototype lokal.

## Batasan yang masih ada

- belum ada MFA
- belum ada reset password
- belum ada delete akun penuh
- belum ada rate limiting login yang formal
- belum ada backup/restore workflow yang aman dan otomatis
- file SQLite tetap plaintext di RAM selama proses hidup
- backend belum dibangun untuk deployment multi-worker public
- belum ada review keamanan profesional / penetration test

## Kunci enkripsi

Key harus dikelola secara manual dan disimpan di secret manager lokal atau environment variable yang tidak di-commit ke Git.

Syarat yang wajib dipatuhi:
- secret tidak boleh berada di source code
- key tidak dibuat ulang secara otomatis
- key hilang atau salah akan membuat database yang terenkripsi tidak bisa dibuka
- rotasi key harus direncanakan dengan backup dan migrasi eksplisit

## Risk summary

- data sensitif tidak sepenuhnya aman untuk deployment publik
- environment masih disiapkan untuk penggunaan lokal saja
- data yang dibackup, disalin, atau diekspor tanpa enkripsi tambahan tetap berisiko

## Status akhir

Keamanan saat ini cukup untuk prototype lokal yang dibatasi, tetapi belum membuktikan keamanan production-ready.
