"""Tahap 2 - Personal baseline (mu & sigma) per pengguna."""
import pandas as pd
from .fitur import (add_features, center_scale, MIN_SIGMA, MIN_DAYS,
                    THRESHOLD, PROVISIONAL_THRESHOLD)


class BaselineModel:
    """Baseline personal.

    by_hour=False : satu mu & sigma global.
    by_hour=True  : mu per jam-dalam-sehari (ritme sirkadian & tidur); sigma =
                    skala residual gabungan (min 3 bpm). Jam kurang data -> mu global.
    robust=True   : median/MAD sebagai ganti rata-rata/simpangan baku.
    Status `ready` bila data valid mencakup >= min_days hari; sebelum itu
    baseline SEMENTARA dan `threshold` otomatis lebih ketat.
    """

    def __init__(self, by_hour: bool = False, min_samples_hour: int = 60,
                 cooldown: int = 0, min_samples: int = 300, robust: bool = True,
                 min_days: int = MIN_DAYS):
        self.by_hour, self.cooldown, self.robust = by_hour, cooldown, robust
        self.min_samples_hour, self.min_samples, self.min_days = min_samples_hour, min_samples, min_days
        self.mu_global: float | None = None
        self.sigma: float | None = None
        self.mu_hour: dict[int, float] = {}
        self.n_valid = 0
        self.days_covered = 0

    def _args(self):
        return dict(by_hour=self.by_hour, min_samples_hour=self.min_samples_hour,
                    cooldown=self.cooldown, min_samples=self.min_samples,
                    robust=self.robust, min_days=self.min_days)

    @property
    def ready(self) -> bool:
        return self.days_covered >= self.min_days

    @property
    def threshold(self) -> float:
        return THRESHOLD if self.ready else PROVISIONAL_THRESHOLD

    def fit(self, df: pd.DataFrame, exclude: pd.Series | None = None) -> "BaselineModel":
        """exclude: Series bool (indeks waktu) menit yang tidak boleh masuk baseline,
        mis. episode stres yang sudah dikonfirmasi pengguna."""
        v = add_features(df, self.cooldown)
        ok = v["valid"]
        if exclude is not None:
            ok = ok & ~exclude.reindex(v.index, fill_value=False).astype(bool)
        v = v[ok]
        if len(v) < self.min_samples:
            raise ValueError("Data valid belum cukup untuk membentuk baseline")
        self.n_valid = len(v)
        self.days_covered = int((v.groupby(v.index.date).size() >= 60).sum())
        self.mu_global, self.sigma = center_scale(v["hr5"], self.robust)
        if self.by_hour:
            agg = "median" if self.robust else "mean"
            self.mu_hour = {int(h): float(getattr(g["hr5"], agg)())
                            for h, g in v.groupby(v.index.hour)
                            if len(g) >= self.min_samples_hour}
            resid = v["hr5"] - v.index.hour.map(
                lambda h: self.mu_hour.get(h, self.mu_global)).to_numpy()
            self.sigma = center_scale(resid, self.robust)[1]
        return self

    def update(self, df: pd.DataFrame, alpha: float = 0.1,
               exclude: pd.Series | None = None) -> "BaselineModel":
        """Perbarui berkala (EWMA). Berikan `exclude` untuk episode stres
        terkonfirmasi agar baseline tidak bergeser naik."""
        new = BaselineModel(**self._args()).fit(df, exclude)
        mix = lambda o, n: (1 - alpha) * o + alpha * n
        self.mu_global = mix(self.mu_global, new.mu_global)
        self.sigma = max(mix(self.sigma, new.sigma), MIN_SIGMA)
        for h, m in new.mu_hour.items():
            self.mu_hour[h] = mix(self.mu_hour[h], m) if h in self.mu_hour else m
        self.days_covered += new.days_covered
        self.n_valid += new.n_valid
        return self

    def mu_untuk(self, index: pd.DatetimeIndex) -> pd.Series:
        """Nilai normal (mu) pengguna untuk setiap menit pada `index`."""
        if self.by_hour:
            return pd.Series(index.hour.map(
                lambda h: self.mu_hour.get(h, self.mu_global)).to_numpy(), index=index)
        return pd.Series(self.mu_global, index=index)

    def summary(self) -> str:
        st = "SIAP" if self.ready else f"SEMENTARA ({self.days_covered}/{self.min_days} hari)"
        return (f"baseline {st}: mu={self.mu_global:.1f}, sigma={self.sigma:.1f} bpm, "
                f"{self.n_valid} menit valid, ambang={self.threshold:.0f}")
