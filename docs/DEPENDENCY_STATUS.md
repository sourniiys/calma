# Dependency Status

## Ringkasan

Environment saat ini masih menampilkan warning deprecation dari library pihak ketiga:
- `starlette.testclient` / `httpx`
- `fitparse`

Warning ini tidak menyebabkan kegagalan test dan bukan indikasi bug logika di backend, tetapi tetap perlu dicatat dan ditindaklanjuti bila ingin mengurangi risiko compatibility di masa depan.

## Status saat ini

### `starlette.testclient` / `httpx`
- Warning berasal dari penggunaan TestClient pada FastAPI/Starlette.
- Root cause yang terverifikasi: stack yang dipakai masih menggunakan `httpx 0.28.x`, sementara Starlette/FastAPI testing path yang digunakan masih mengandalkan API lama dan memunculkan deprecation warning.
- Solusi yang aman dan terbukti untuk repo ini adalah memaksa `httpx` ke range pra-deprecation (`httpx<0.28`) agar perilaku TestClient tetap kompatibel tanpa menutup warning secara global.
- Setelah pin ini diterapkan, suite diuji ulang untuk memastikan tidak merusak fungsionalitas.

### `fitparse`
- Warning berasal dari penggunaan `datetime.datetime.utcfromtimestamp()` di library `fitparse`.
- Ini berasal dari library pihak ketiga, bukan dari kalimat custom CALMA.
- Tidak ada versi terbaru yang tersedia dari package yang sudah terpasang di environment ini yang secara jelas memperbaiki masalah tanpa perubahan besar.
- Statusnya: documented warning; tidak dihapus dengan cara yang mengubah API atau memperbesar scope refactor.

## Kesimpulan

Status dependency saat ini adalah:
- functional: YA
- clean: TIDAK
- production-grade: BELUM

Tidak ada klaim bahwa dependency warning sudah diselesaikan secara penuh. Yang ada adalah: warning sudah diterima sebagai keterbatasan verifikasi saat ini dan didokumentasikan dengan jelas.
