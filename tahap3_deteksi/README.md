# Tahap 3 – Skor Stres & Deteksi

**Tujuan:** mengubah HR menjadi skor 0–100, lalu menandai *potensi stres*.

| File | Fungsi |
|---|---|
| `skor.py` | `hitung_skor(model, data)`: z = (HR5 − μ)/σ ; skor = 50 + 20z, dibatasi 0–100. Menit aktif/tidak valid → skor kosong (NaN). |
| `deteksi.py` | `detect_events`: skor > ambang selama ≥ 10 menit berturut-turut. `evaluate`: precision/recall terhadap label simulator. |
| `jalankan.py` | Perbandingan 4 konfigurasi + uji pada data Garmin + grafik `hasil/tahap3_deteksi.png`. |

**Jalankan:** `python tahap3_deteksi/jalankan.py`

**Cara baca hasil**
- *recall* = dari semua stres nyata, berapa yang tertangkap.
- *precision* = dari semua alert, berapa yang benar. Alert palsu ditangani konfirmasi pengguna (Tahap 4).
- `motion_checked=False` pada event = tidak ada data langkah, jadi bisa saja itu gerak badan.

**Hasil ringkas (simulasi):** proposal murni 25 alert (precision 0,12) → per jam + cooldown 6 alert (0,50);
tanpa data langkah 15 alert (0,20).
