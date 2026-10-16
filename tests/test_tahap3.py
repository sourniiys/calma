import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pandas as pd
from tahap1_data.simulator import simulate, StressEpisode
from tahap2_baseline.baseline import BaselineModel
from tahap3_deteksi.skor import hitung_skor
from tahap3_deteksi.deteksi import detect_events

def test_score_bounds_and_activity_filter():
    df = simulate(3, seed=1); res = hitung_skor(BaselineModel().fit(df), df)
    assert res["score"].dropna().between(0, 100).all()
    assert res.loc[~res["valid"], "score"].isna().all()

def test_detect_needs_10_minutes():
    s = pd.Series(50.0, index=pd.date_range("2026-01-01", periods=30, freq="min"))
    s.iloc[5:14] = 90
    assert detect_events(s) == []
    s.iloc[5:15] = 90
    assert len(detect_events(s)) == 1


def test_detect_does_not_bridge_missing_timestamp():
    index = pd.date_range("2026-01-01", periods=11, freq="min")
    score = pd.Series(80.0, index=index).drop(index[5])
    assert len(score) == 10
    assert detect_events(score) == []


def test_detects_clear_stress():
    df = simulate(15, seed=3, episodes=(StressEpisode(14, 10, 40, 12),))
    m = BaselineModel(by_hour=True, cooldown=30).fit(df.iloc[:14 * 1440])
    assert len(detect_events(hitung_skor(m, df.iloc[14 * 1440:])["score"])) >= 1
