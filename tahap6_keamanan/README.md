# Tahap 6 - Safety Plan dan Eskalasi

- `SafetyPlanStore` membaca dan mengubah safety plan pribadi. Perubahan hanya
  dapat disimpan jika consent `DATA_STORAGE` aktif. Data JSON disimpan lokal;
  file belum dienkripsi. Membaca atau menghapus plan tetap dimungkinkan setelah
  consent dicabut agar pengguna dapat mengakses atau menghapus datanya.
- Countdown kontak perlu consent `TRUSTED_CONTACT` dan `DATA_STORAGE` serta
  kontak tepercaya yang tersimpan. Izin dan kontak dicek ulang setelah 10 menit.
  Pembatalan menghentikan alur. Provider bawaan hanya simulasi dan mencatat
  `SIMULATED_ONLY`, bukan pengiriman nyata.
- Percobaan dikunci maksimal satu kali per 24 jam, termasuk percobaan gagal,
  sebagai batas konservatif. Isi pesan tetap "Lagi butuh ditemani".
- `repeated_stress_offer(...)` menghitung tanggal berbeda, menampilkan opsi
  setelah tiga hari, dan tidak mengklaim pemesanan telekonsultasi.
- `open_crisis_access(...)` menyediakan safety plan dan nomor darurat 119 tanpa
  perlu melalui chatbot.

Jalankan tes: `python -m pytest tests/test_tahap6.py -q`.

Keterbatasan: file lokal berisi informasi sensitif dan belum dienkripsi atau
dilindungi autentikasi aplikasi. Jangan gunakan untuk eskalasi dunia nyata.