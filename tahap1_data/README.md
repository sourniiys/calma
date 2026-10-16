# Tahap 1 – Data

**Tujuan:** menyediakan data detak jantung (bpm) & langkah per menit, tanpa harus menunggu perangkat.

| File | Fungsi |
|---|---|
| `simulator.py` | `simulate(days, ...)` membuat data buatan: ritme sirkadian, tidur, jalan kaki, olahraga, episode stres (`StressEpisode`), jam tidak dipakai (`NotWorn`), data hilang (`dropout`), perangkat tanpa langkah (`has_steps=False`). |
| `garmin_loader.py` | `load_minutely(folder)` membaca file `*_WELLNESS.fit` Garmin → data per menit (`hr`, `garmin_stress`). |
| `jalankan.py` | Demo + grafik `hasil/tahap1_data.png`. |

**Jalankan:** `python tahap1_data/jalankan.py`

**Yang perlu kamu tahu**
- Kolom `true_stress` di simulator = label kebenaran, dipakai untuk menguji tahap 3.
- Data Garmin: HR hanya ada dari 10:57–17:40 (sebelumnya jam belum dipakai) dan **tidak ada langkah per menit**.
- `garmin_stress` hanya pembanding, **bukan** input CALMA.

**Untuk mengganti ke data kamu sendiri:** taruh file `.fit` baru di `data/` lalu panggil `load_minutely("data/folder_baru")`.
