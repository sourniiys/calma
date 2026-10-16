"""Tahap 3a - Skor stres 0-100 (z-score terhadap baseline pribadi)."""
import numpy as np
import pandas as pd
from tahap2_baseline.fitur import add_features
from tahap2_baseline.baseline import BaselineModel


def hitung_skor(model: BaselineModel, df: pd.DataFrame) -> pd.DataFrame:
    """z = (HR5 - mu) / sigma ;  skor = clip(50 + 20 z, 0, 100).
    Menit yang tidak valid (sedang aktif / jam tidak dipakai) -> skor NaN."""
    f = add_features(df, model.cooldown)
    f["z"] = (f["hr5"] - model.mu_untuk(f.index)) / model.sigma
    f["score"] = (50 + 20 * f["z"]).clip(0, 100)
    f.loc[~f["valid"], "score"] = np.nan
    return f
