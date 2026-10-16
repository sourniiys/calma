import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd
from tahap1_data.simulator import simulate, NotWorn
from tahap2_baseline.baseline import BaselineModel
from tahap2_baseline.fitur import MIN_SIGMA, add_features

def _flat(n=3000, spike=False):
    idx = pd.date_range("2026-01-01", periods=n, freq="min")
    hr = pd.Series(70.0 + np.random.default_rng(0).normal(0, 1, n), index=idx)
    if spike: hr.iloc[500:560] += 40
    return pd.DataFrame({"hr": hr})

def test_sigma_floor():
    idx = pd.date_range("2026-01-01", periods=2000, freq="min")
    assert BaselineModel().fit(pd.DataFrame({"hr": 70.0, "steps": 0.0}, index=idx)).sigma == MIN_SIGMA

def test_robust_sigma_resists_spikes():
    clean = BaselineModel(robust=False).fit(_flat()).sigma
    plain = BaselineModel(robust=False).fit(_flat(spike=True)).sigma
    rob = BaselineModel(robust=True).fit(_flat(spike=True)).sigma
    assert plain > clean + 2 and rob <= plain - 2

def test_ready_needs_min_days():
    df = simulate(8, seed=2)
    short = BaselineModel().fit(df.iloc[:3 * 1440])
    assert not short.ready and short.threshold == 80
    full = BaselineModel().fit(df)
    assert full.ready and full.threshold == 70

def test_exclude_confirmed_stress():
    df = _flat(spike=True); mask = pd.Series(False, index=df.index); mask.iloc[500:560] = True
    assert BaselineModel(robust=False).fit(df, exclude=mask).sigma < BaselineModel(robust=False).fit(df).sigma

def test_works_without_steps_and_with_gaps():
    df = simulate(9, seed=5, has_steps=False, dropout=0.03, not_worn=(NotWorn(0, 0, 600),))
    assert BaselineModel(by_hour=True).fit(df).sigma >= MIN_SIGMA


def test_missing_step_data_is_not_assumed_inactive():
    df = simulate(2, seed=7, has_steps=False)
    features = add_features(df)
    assert not features["motion_checked"].any()
    assert features["valid"].any()


def test_five_minute_hr_window_does_not_bridge_timestamp_gap():
    index = pd.date_range("2026-01-01", periods=12, freq="min")
    data = pd.DataFrame({"hr": 70.0, "steps": 0.0}, index=index).drop(index[5])
    features = add_features(data)
    assert pd.isna(features.loc[index[6], "hr5"])
    assert not features.loc[index[6], "valid"]


def test_missing_steps_in_window_are_not_treated_as_low_activity():
    index = pd.date_range("2026-01-01", periods=12, freq="min")
    data = pd.DataFrame({"hr": 70.0, "steps": 0.0}, index=index)
    data.loc[index[3], "steps"] = np.nan
    features = add_features(data)
    assert not features.loc[index[3], "motion_checked"]
    assert not features.loc[index[3], "valid"]
