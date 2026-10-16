"""Tahap 2 - Jalankan: bentuk personal baseline & bandingkan metodenya."""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))          # agar bisa dijalankan dari folder mana saja
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

import pandas as pd
from tahap1_data.simulator import simulate
from tahap1_data.garmin_loader import load_minutely
from tahap2_baseline.baseline import BaselineModel

print("=== A. Simulasi: baseline dari 14 hari data ===")
train = simulate(14, seed=42)
models = {
    "1. Global, std biasa (persis proposal)": BaselineModel(robust=False),
    "2. Global, robust (median/MAD)":          BaselineModel(robust=True),
    "3. Per jam + cooldown 30 mnt, robust":    BaselineModel(by_hour=True, cooldown=30, robust=True),
}
for name, m in models.items():
    print(f"{name}\n    {m.fit(train).summary()}")

print("\n=== B. Data Garmin nyata (baru <1 hari -> baseline darurat 3 jam pertama) ===")
g = load_minutely(str(ROOT / "data" / "garmin_user1"))
g = g.loc[g["hr"].dropna().index.min():]
first3h = g.loc[: g.index[0] + pd.Timedelta(hours=3)]
for robust in (False, True):
    print(f"robust={robust}: {BaselineModel(min_samples=120, robust=robust).fit(first3h).summary()}")

m = models["3. Per jam + cooldown 30 mnt, robust"]
hrs = sorted(m.mu_hour)
fig, ax = plt.subplots(figsize=(9, 4))
ax.plot(hrs, [m.mu_hour[h] for h in hrs], marker="o", label="mu per jam")
ax.axhspan(0, 0, alpha=0); ax.fill_between(hrs, [m.mu_hour[h] - m.sigma for h in hrs],
                                           [m.mu_hour[h] + m.sigma for h in hrs], alpha=.2, label="±1 sigma")
ax.set_xlabel("Jam"); ax.set_ylabel("HR normal (bpm)"); ax.legend()
ax.set_title("Baseline per jam (simulasi): HR normal naik-turun sepanjang hari")
out = ROOT / "hasil" / "tahap2_baseline.png"; fig.tight_layout(); fig.savefig(out, dpi=100)
print("\nGrafik tersimpan:", out)
