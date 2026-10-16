"""Tahap 2 (tambahan) - Uji drift baseline pada data HARIAN nyata (resting HR).

Pertanyaan: kalau baseline dibekukan dari 14 hari pertama, berapa hari yang
salah ditandai 'tinggi'? Bandingkan dengan baseline yang diperbarui (EWMA).
Catatan: ini hanya menguji kebutuhan adaptasi baseline, BUKAN akurasi deteksi stres.
"""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from tahap2_baseline.fitur import MIN_SIGMA

df = pd.read_csv(ROOT / "data" / "calma_harian_bersih.csv", parse_dates=["date"], dayfirst=False)
x = df.set_index("date")["resting_hr_bpm"].dropna()
print(f"Hari dengan resting HR: {len(x)} ({x.index.min():%d %b %Y} - {x.index.max():%d %b %Y})")

# A. Baseline beku dari 14 hari pertama
mu0, sd0 = x.iloc[:14].mean(), max(x.iloc[:14].std(ddof=0), MIN_SIGMA)
rest = x.iloc[14:]
score_static = 50 + 20 * (rest - mu0) / sd0

# B. Baseline diperbarui tiap hari (EWMA), skor dihitung SEBELUM hari itu dipakai memperbarui
alpha, mu, dev = 0.1, mu0, sd0
sc_adapt = []
for v in rest:
    sc_adapt.append(50 + 20 * (v - mu) / max(dev, MIN_SIGMA))
    mu = (1 - alpha) * mu + alpha * v
    dev = (1 - alpha) * dev + alpha * abs(v - mu)
score_adapt = pd.Series(sc_adapt, index=rest.index)

for name, s in [("A. Baseline BEKU", score_static), ("B. Baseline DIPERBARUI (EWMA 0,1)", score_adapt)]:
    hi = (s > 70)
    print(f"{name}: {hi.sum()} dari {len(s)} hari ({hi.mean():.0%}) ditandai tinggi; "
          f"per tahun: {hi.groupby(s.index.year).mean().round(2).to_dict()}")

fig, ax = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
ax[0].plot(x.index, x.values, ".", ms=3, color="firebrick"); ax[0].axhline(mu0, ls=":", color="k")
ax[0].set_ylabel("Resting HR (bpm)"); ax[0].set_title("Resting HR harian (garis putus = baseline beku)")
ax[1].plot(score_static.index, score_static, lw=.7, label="baseline beku")
ax[1].plot(score_adapt.index, score_adapt, lw=.7, label="baseline diperbarui")
ax[1].axhline(70, ls="--", color="red"); ax[1].legend(); ax[1].set_ylabel("Skor harian")
fig.tight_layout(); fig.savefig(ROOT / "hasil" / "drift_baseline_harian.png", dpi=100)
