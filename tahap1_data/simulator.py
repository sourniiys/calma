"""Tahap 1 - Simulator data smartwatch (bpm & langkah per menit).

Dipakai untuk menguji pipeline CALMA tanpa perangkat asli. Opsi realisme
(dari temuan data Garmin nyata): has_steps=False (perangkat tanpa langkah per
menit), not_worn (jam tidak dipakai -> HR kosong), dropout (data hilang acak).
Kolom keluaran: hr, [steps], true_stress (label kebenaran untuk evaluasi).
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class StressEpisode:
    day: int            # indeks hari (0 = hari pertama)
    start_hour: float   # jam mulai, mis. 10.5 = 10:30
    duration_min: int
    bump_bpm: float     # kenaikan detak jantung akibat stres


@dataclass(frozen=True)
class NotWorn:
    day: int
    start_hour: float
    duration_min: int


def simulate(days: int, seed: int = 0, resting_hr: float = 68.0,
             episodes: tuple[StressEpisode, ...] = (), has_steps: bool = True,
             not_worn: tuple[NotWorn, ...] = (), dropout: float = 0.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = days * 1440
    idx = pd.date_range("2026-01-05", periods=n, freq="min")
    mod = (idx.hour * 60 + idx.minute).to_numpy()

    # Ritme sirkadian: terendah ~04:00, tertinggi ~16:00
    hr = resting_hr - 5 * np.cos(2 * np.pi * (mod - 240) / 1440)
    hr = hr + pd.Series(rng.normal(0, 6, n)).ewm(span=8).mean().to_numpy()

    steps = rng.poisson(1.5, n).astype(float)
    sleeping = (mod >= 23 * 60) | (mod < 6 * 60)
    hr[sleeping] -= 6
    steps[sleeping] = 0

    # Aktivitas harian: jalan kaki (3x/hari) dan olahraga (50% hari)
    for d in range(days):
        base = d * 1440
        for _ in range(3):
            s = base + int(rng.integers(7 * 60, 21 * 60))
            dur = int(rng.integers(5, 26))
            steps[s:s + dur] = rng.normal(95, 10, dur).clip(60)
            hr[s:s + dur] += 18
            tail = 12 * np.exp(-np.arange(10) / 4)           # pemulihan HR
            hr[s + dur:s + dur + 10] += tail[: len(hr[s + dur:s + dur + 10])]
        if rng.random() < 0.5:
            s = base + int(rng.integers(17 * 60, 19 * 60))
            steps[s:s + 30] = rng.normal(140, 15, 30)
            hr[s:s + 30] += 50

    # Episode stres: HR naik, langkah rendah (duduk/diam)
    truth = np.zeros(n, dtype=bool)
    for e in episodes:
        s = e.day * 1440 + int(e.start_hour * 60)
        ramp = np.minimum(1.0, np.arange(e.duration_min) / 5)
        hr[s:s + e.duration_min] += e.bump_bpm * ramp
        steps[s:s + e.duration_min] = rng.poisson(1, e.duration_min)
        truth[s:s + e.duration_min] = True

    # Realisme perangkat: jam tidak dipakai & data hilang acak
    for w in not_worn:
        s = w.day * 1440 + int(w.start_hour * 60)
        hr[s:s + w.duration_min] = np.nan
        truth[s:s + w.duration_min] = False
    if dropout:
        hr[rng.random(n) < dropout] = np.nan

    out = pd.DataFrame({"hr": np.round(hr, 1)}, index=idx)
    if has_steps:
        out["steps"] = steps.round()
    out["true_stress"] = truth
    return out
