"""Konstanta CALMA + penyiapan fitur (filter aktivitas, rata-rata HR 5 menit)."""
import numpy as np
import pandas as pd

# --- Parameter dari proposal (Bab 3.2.3) ---
STEP_LIMIT = 100          # langkah 5 menit terakhir harus < 100 agar data dipakai
WINDOW = 5                # menit untuk rata-rata HR & jendela langkah
MIN_SIGMA = 3.0           # batas bawah sigma (bpm)
THRESHOLD = 70            # skor > 70 ...
MIN_MINUTES = 10          # ... selama >= 10 menit berturut-turut
MIN_DAYS = 7              # baseline "siap" setelah >= 7 hari data

# --- Penyesuaian dari uji data nyata ---
MAD_K = 1.4826            # MAD -> setara simpangan baku
PROVISIONAL_THRESHOLD = 80   # ambang lebih ketat selama baseline masih sementara


def add_features(df: pd.DataFrame, cooldown: int = 0) -> pd.DataFrame:
    """Tambah kolom: hr5 (rata-rata HR 5 menit), steps5, valid (boleh dipakai).

    cooldown: menit setelah aktivitas yang datanya diabaikan, karena HR masih
    tinggi akibat pemulihan fisik. 0 = persis proposal.
    Jika langkah tidak tersedia, HR tetap dapat dianalisis tetapi `motion_checked`
    bernilai False sehingga hasil tidak dianggap telah lolos filter aktivitas.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("Data fitur harus memiliki indeks timestamp")
    if df.index.has_duplicates:
        raise ValueError("Timestamp data fitur tidak boleh duplikat")
    out = df.sort_index().copy()
    consecutive_minutes = out.index.to_series().diff().eq(pd.Timedelta(minutes=1))
    continuous_window = consecutive_minutes.rolling(WINDOW - 1, min_periods=WINDOW - 1).sum().eq(WINDOW - 1)
    out["hr5"] = out["hr"].rolling(WINDOW, min_periods=WINDOW).mean()
    out.loc[~continuous_window, "hr5"] = np.nan
    if "steps" in out:
        out["steps5"] = out["steps"].rolling(WINDOW, min_periods=WINDOW).sum()
        out.loc[~continuous_window, "steps5"] = np.nan
        out["motion_checked"] = out["steps5"].notna()
        active = out["steps5"].ge(STEP_LIMIT).fillna(False)
    else:
        out["motion_checked"] = False
        active = pd.Series(False, index=out.index)
    if cooldown:
        active = active.rolling(cooldown + 1, min_periods=1).max().astype(bool)
    step_window_valid = out["motion_checked"] if "steps" in out else True
    out["valid"] = ~active & out["hr5"].notna() & out["hr"].notna() & step_window_valid
    return out


def center_scale(x: pd.Series, robust: bool) -> tuple[float, float]:
    """Pusat & skala. robust=True: median & MAD (tahan lonjakan);
    False: rata-rata & simpangan baku (persis proposal)."""
    if robust:
        med = float(x.median())
        return med, float(max((x - med).abs().median() * MAD_K, MIN_SIGMA))
    return float(x.mean()), float(max(x.std(ddof=0), MIN_SIGMA))
