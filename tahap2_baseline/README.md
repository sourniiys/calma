# Tahap 2 – Personal Baseline

**Tujuan:** mempelajari detak jantung "normal" tiap pengguna (μ = pusat, σ = sebaran) dari 7–14 hari pertama.

| File | Fungsi |
|---|---|
| `fitur.py` | Semua **angka parameter** (ambang 70, 10 menit, σ min 3, dst.) + `add_features`: rata-rata HR 5 menit & filter aktivitas (langkah 5 menit < 100). |
| `baseline.py` | `BaselineModel`: `fit`, `update` (EWMA), `ready`, `threshold`, `summary`. |
| `jalankan.py` | Membandingkan 3 cara baseline + grafik `hasil/tahap2_baseline.png`. |

**Jalankan:** `python tahap2_baseline/jalankan.py`

**Pilihan di `BaselineModel(...)`**
- `robust=True` → median/MAD, tahan lonjakan HR (False = rata-rata/std persis proposal).
- `by_hour=True` → baseline per jam (menangani HR yang naik-turun sepanjang hari).
- `cooldown=30` → abaikan 30 menit setelah aktivitas.
- `fit(data, exclude=...)` → keluarkan menit stres terkonfirmasi agar baseline tidak bias.

**Status baseline:** `ready` hanya jika ≥ 7 hari data. Sebelum itu baseline *sementara*
dan ambang otomatis naik 70 → 80.

**Mau ubah parameter proposal?** Cukup edit konstanta di `fitur.py`.

**Tambahan:** `uji_drift_harian.py` menguji pada data harian nyata mengapa baseline harus diperbarui (hasil: `hasil/drift_baseline_harian.png`).
