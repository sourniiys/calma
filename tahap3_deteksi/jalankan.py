"""Tahap 3 - Jalankan: skor stres & deteksi, simulasi + data Garmin nyata."""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))          # agar bisa dijalankan dari folder mana saja
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

import pandas as pd
from tahap1_data.simulator import simulate, StressEpisode, NotWorn
from tahap1_data.garmin_loader import load_minutely
from tahap2_baseline.baseline import BaselineModel
from tahap3_deteksi.skor import hitung_skor
from tahap3_deteksi.deteksi import detect_events, evaluate

EPISODES = (StressEpisode(14, 10.0, 40, 12), StressEpisode(15, 15.0, 25, 10),
            StressEpisode(16, 9.0, 15, 9))
full = simulate(17, seed=42, episodes=EPISODES)
nosteps = simulate(17, seed=42, episodes=EPISODES, has_steps=False, dropout=0.03,
                   not_worn=(NotWorn(0, 0, 600), NotWorn(5, 13, 180)))

print("=== A. Simulasi: 14 hari baseline + 3 hari uji (3 episode stres nyata) ===")
CONFIGS = [("A. Persis proposal (global, std biasa)", full, False, 0, False),
           ("B. + per jam + cooldown 30 mnt", full, True, 30, False),
           ("C. + median/MAD (robust)", full, True, 30, True),
           ("D. C pada data REALISTIS (tanpa langkah, bolong)", nosteps, True, 30, True)]
for name, data, by_hour, cd, robust in CONFIGS:
    train, test = data.iloc[:14 * 1440], data.iloc[14 * 1440:]
    m = BaselineModel(by_hour=by_hour, cooldown=cd, robust=robust).fit(train)
    res = hitung_skor(m, test)
    ev = detect_events(res["score"], threshold=m.threshold, motion_checked="steps" in data)
    r = evaluate(ev, test["true_stress"])
    print(f"{name}\n   alert={r['alert']} benar={r['alert_benar']} | "
          f"precision={r['precision']:.2f} recall={r['recall']:.2f}")
    if name.startswith("C"):
        day_res = res.loc["2026-01-19"]

print("\n=== B. Data Garmin nyata (baseline darurat 3 jam pertama) ===")
g = load_minutely(str(ROOT / "data" / "garmin_user1"))
g = g.loc[g["hr"].dropna().index.min():]
cut = g.index[0] + pd.Timedelta(hours=3)
m = BaselineModel(min_samples=120).fit(g.loc[:cut])
gres = hitung_skor(m, g); test = gres.loc[cut:]
print(m.summary())
ev = detect_events(test["score"], threshold=m.threshold, motion_checked=False)
for e in ev:
    gs = g.loc[e.start:e.end, "garmin_stress"]
    print(f"  [tanpa data langkah] {e.start:%H:%M}-{e.end:%H:%M} puncak skor {e.peak:.0f} | "
          f"Garmin stress rata2 {gs[gs > 0].mean():.0f}")
both = test[["score"]].join(g["garmin_stress"]).dropna(); both = both[both.garmin_stress > 0]
print(f"Korelasi skor CALMA vs stress Garmin: Pearson {both.corr().iloc[0,1]:.2f}")

fig, ax = plt.subplots(2, 1, figsize=(11, 7))
ax[0].plot(day_res.index, day_res["score"], color="teal"); ax[0].axhline(70, ls="--", color="red")
ax[0].fill_between(day_res.index, 0, 100, where=day_res["true_stress"], color="orange", alpha=.2)
ax[0].set_title("Simulasi: skor stres (oranye = stres sebenarnya)"); ax[0].set_ylabel("Skor")
ax[1].plot(gres.index, gres["score"], color="teal", label="Skor CALMA")
ax[1].plot(g.index, g["garmin_stress"].where(g["garmin_stress"] > 0), color="orange", alpha=.7, label="Stress Garmin")
ax[1].axhline(m.threshold, ls="--", color="red")
for e in ev: ax[1].axvspan(e.start, e.end, color="red", alpha=.15)
ax[1].set_title("Data Garmin nyata (merah = potensi stres terdeteksi)"); ax[1].legend()
out = ROOT / "hasil" / "tahap3_deteksi.png"; fig.tight_layout(); fig.savefig(out, dpi=100)
print("\nGrafik tersimpan:", out)
