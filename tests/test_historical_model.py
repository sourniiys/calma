import sys
import pathlib
import json

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from calma_backend.historical_model import prepare_prior_day_data, train_historical_model


def _synthetic_daily_data(rows=60):
    dates = pd.date_range("2025-01-01", periods=rows, freq="D")
    steps = np.arange(rows) * 10 + 1000
    return pd.DataFrame({
        "date": dates,
        "steps": steps,
        "resting_hr_bpm": 60 + np.arange(rows) % 10,
        "garmin_average_stress": np.clip(20 + steps / 200, 0, 100),
    })


def test_features_are_shifted_from_previous_calendar_day():
    source = _synthetic_daily_data(4)
    prepared, feature_names = prepare_prior_day_data(source)
    assert len(prepared) == 3
    assert feature_names == ("resting_hr_bpm", "steps", "garmin_average_stress")
    assert prepared.iloc[0]["date"] == pd.Timestamp("2025-01-02")
    assert prepared.iloc[0]["previous_steps"] == source.iloc[0]["steps"]
    assert prepared.iloc[0]["previous_steps"] != source.iloc[1]["steps"]
    assert prepared.iloc[0]["previous_garmin_average_stress"] == source.iloc[0]["garmin_average_stress"]


def test_training_uses_chronological_split_and_persists_metadata(tmp_path):
    result = train_historical_model(_synthetic_daily_data(), tmp_path)
    assert result.train_rows > result.test_rows
    assert result.model_path.exists()
    assert result.metadata_path.exists()
    assert result.test_start > "2025-01-01"
    assert set(result.metrics) == {
        "model_mae", "model_rmse", "mean_baseline_mae", "mean_baseline_rmse",
        "median_baseline_mae", "median_baseline_rmse",
        "persistence_baseline_mae", "persistence_baseline_rmse",
        "model_r2", "mean_baseline_r2", "median_baseline_r2",
        "persistence_baseline_r2",
    }
    assert all(value >= 0 for name, value in result.metrics.items()
               if name.endswith("_mae") or name.endswith("_rmse"))
    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert metadata["source_rows"] == 60
    assert metadata["valid_target_rows"] == 60
    assert metadata["usable_prior_day_rows"] == 59
    assert metadata["duplicate_dates"] == 0
    assert metadata["test_fraction_requested"] == 0.2
    assert metadata["model_parameters"]["n_estimators"] == 200
    assert metadata["baselines"]["persistence"].startswith("previous calendar day")


def test_training_rejects_duplicate_dates_and_insufficient_data(tmp_path):
    data = _synthetic_daily_data(40)
    data.loc[1, "date"] = data.loc[0, "date"]
    with pytest.raises(ValueError, match="duplikat"):
        prepare_prior_day_data(data)
    with pytest.raises(ValueError, match="belum cukup"):
        train_historical_model(_synthetic_daily_data(10), tmp_path)
