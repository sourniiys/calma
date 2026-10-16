"""Tahap 1 - Jalankan: lihat data simulasi & baca data Garmin nyata."""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))          # agar bisa dijalankan dari folder mana saja
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

from tahap1_data.simulator import simulate, StressEpisode
from tahap1_data.garmin_loader import load_minutely

print("=== A. Data simulasi (3 hari, 1 episode stres hari ke-2 jam 10:00) ===")
sim = simulate(3, seed=1, episodes=(StressEpisode(1, 10.0, 40, 12),))
print(sim.head(3).to_string(), "\n...")
print(f"jumlah baris: {len(sim)} (1 baris = 1 menit), menit stres sebenarnya: {int(sim.true_stress.sum())}")

print("\n=== B. Data Garmin nyata ===")
g = load_minutely(str(ROOT / "data" / "garmin_user1"))
valid = g["hr"].dropna()
print(f"HR valid: {len(valid)} menit, {valid.index.min():%d %b %H:%M} - {valid.index.max():%H:%M}")
print(g.dropna(subset=['hr']).head(3).to_string())

fig, ax = plt.subplots(3, 1, figsize=(11, 8))
day = sim.loc["2026-01-06"]
ax[0].plot(day.index, day["hr"], lw=.8); ax[0].set_ylabel("HR (bpm)")
ax[0].fill_between(day.index, day.hr.min(), day.hr.max(), where=day.true_stress, color="orange", alpha=.2)
ax[0].set_title("Simulasi hari ke-2 (oranye = stres sebenarnya)")
ax[1].plot(day.index, day["steps"], lw=.8, color="green"); ax[1].set_ylabel("Langkah/menit")
ax[2].plot(g.index, g["hr"], lw=.8, color="firebrick"); ax[2].set_ylabel("HR Garmin (bpm)")
ax[2].set_title("Data Garmin nyata (kosong = jam belum dipakai)")
out = ROOT / "hasil" / "tahap1_data.png"; fig.tight_layout(); fig.savefig(out, dpi=100)
print("\nGrafik tersimpan:", out)
