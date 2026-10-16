# Tahap 4 - Consent, Mood, dan State Machine

Paket ini menambahkan logika interaksi pengguna tanpa mengubah modul Tahap 1-3.

- `consent.py`: consent per tujuan (pengumpulan data, pemrosesan fisiologis,
  kontak tepercaya, dan dukungan profesional). Semua consent tertutup secara
  default. Berikan path JSON saat membuat `ConsentManager` untuk menyimpan dan
  meninjau riwayat perubahan lokal; pencabutan langsung menutup izin berikutnya.
- `mood.py`: check-in sederhana (`good`, `okay`, `low`) dan energi
  (`low`, `medium`, `high`). Mood rendah hanya menyarankan Soft Mode; pengguna
  tetap harus memanggil `set_soft_mode(True)` sendiri.
- `state.py`: state machine yang menerima `StressEvent` dari Tahap 3 lalu
  mencatat jawaban `yes`, `no`, atau `unsure`. Skor sensor tidak mengonfirmasi
  stres dengan sendirinya.

Contoh pemeriksaan: `python -m pytest tests/test_tahap4.py -q`.

Status: logika dan tes lokal sudah dibuat. Belum ada UI onboarding, penyimpanan
check-in mood/state, atau aplikasi siap produksi.