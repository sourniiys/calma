# Model Evaluation Report

## Tujuan

Model ini memprediksi skor harian Garmin, bukan kondisi kesehatan mental atau diagnosis klinis. Tujuan ini harus dipahami dengan jelas agar tidak terjadi overclaim.

## Data yang dipakai

Dataset yang dipakai adalah file CSV historis lokal: `data/calma_harian_bersih.csv`.

Ciri penting:
- data historis, bukan streaming real-time
- targetnya adalah `garmin_average_stress`
- split waktu kronologis, tidak di-shuffle
- baris dengan target tidak valid atau lag feature tidak tersedia dikeluarkan

## Proses evaluasi

Model yang dievaluasi adalah Random Forest Regressor yang dibuat dari fitur hari sebelumnya untuk memprediksi target hari berikutnya.

Rincian evaluasi:
- train rows: 447
- test rows: 112
- split: kronologis
- target: `garmin_average_stress`
- kumpulan fitur: fitur sebelum target pada hari sebelumnya

## Hasil aktual

Berdasarkan metadata hasil yang ada di `hasil/model_historis/validation_20261016/garmin_daily_stress.metadata.json`:

- model MAE: 10.1898
- model RMSE: 14.3492
- mean baseline MAE: 10.1543
- mean baseline RMSE: 14.1331
- model R²: -0.0484
- mean baseline R²: -0.0171

## Kesimpulan

Model yang saat ini tersedia tidak membuktikan keunggulan yang signifikan terhadap baseline mean sederhana. Dengan kata lain:
- model belum lebih baik secara konsisten daripada baseline rata-rata
- hasil model masih bersifat eksperimen
- tidak dapat dipakai untuk diagnosis psikologis atau medis
- hasilnya hanya relevan untuk analisis data historis Garmin dan prototipe backend

## Interpretasi yang benar

Prediksi model adalah prediksi skor Garmin, bukan prediksi stres psikologis manusia. Ini bukan alat diagnosis. Model hanya sesuai untuk konteks prototipe analisis data, bukan untuk keputusan klinis atau penggunaan real-time.
