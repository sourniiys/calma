# Tahap 5 - Stress Quest

`quest.py` menyediakan pilihan Micro (jalan 10 menit), Standard (5.000 langkah),
dan Full (gym minimal 60 menit atau berenang minimal 90 menit).

- `recommend_quest(...)` memakai energi, kondisi yang dilaporkan, preferensi,
  Soft Mode, dan respons positif terdahulu. Skor stres bukan input rekomendasi.
  Kondisi sakit, pemulihan, atau cedera menghasilkan pilihan istirahat/lewati.
- `QuestTracker` mencatat mulai, selesai, skip tanpa penalti, dan sumber
  `user_reported` atau `device_detected`.
- `evaluate_recovery(...)` membandingkan 10 menit sebelum aktivitas dengan 10
  menit terakhir dalam jendela pemulihan 30-60 menit. Data menit yang hilang
  menghasilkan `insufficient_data`. Penurunan minimal 10 poin disebut respons
  awal positif, bukan bukti bahwa aktivitas menjadi penyebabnya.
- `RewardTracker` bersifat opsional, maksimal tiga reward per minggu, dan hanya
  mencatat demonstrasi lokal. Tidak ada transaksi atau integrasi layanan makanan.

Contoh rekomendasi yang menghormati Soft Mode dari Tahap 4:

```python
from tahap4_interaksi import Energy, Mood, MoodSettings
from tahap5_stress_quest import EnergyLevel, recommend_quest

settings = MoodSettings()
settings.check_in(Mood.LOW, Energy.LOW)
settings.set_soft_mode(True)  # pilihan eksplisit pengguna
quest = recommend_quest(EnergyLevel.HIGH, soft_mode=settings.soft_mode)
print(quest.option.title, quest.option.target)
```

Contoh tes: `python -m pytest tests/test_tahap5.py -q`.

Status: logika lokal dan tes sudah dibuat. Langkah, aktivitas, dan skor pemulihan
belum tersambung ke perangkat; penyelesaian saat ini dicatat dari sumber yang
dinyatakan, bukan diverifikasi oleh integrasi Garmin.