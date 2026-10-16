"""Eksperimen prediksi skor harian Garmin; bukan prediksi kondisi klinis."""
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline


TARGET = "garmin_average_stress"
DATE = "date"
FEATURE_CANDIDATES = (
    "resting_hr_bpm", "min_hr_bpm", "max_hr_bpm", "steps",
    "body_battery_charged", "body_battery_drained", "body_battery_highest",
    "body_battery_lowest", "activity_minutes", "hrv_ms",
    "health_status_hr_bpm", "respiration_bpm",
)
RANDOM_STATE = 42
N_ESTIMATORS = 200
MIN_SAMPLES_LEAF = 3


@dataclass(frozen=True)
class HistoricalModelResult:
    model_path: Path
    metadata_path: Path
    train_rows: int
    test_rows: int
    feature_names: tuple[str, ...]
    metrics: dict[str, float]
    test_start: str
    test_end: str


def _load_frame(source: str | Path | pd.DataFrame) -> pd.DataFrame:
    if isinstance(source, pd.DataFrame):
        return source.copy()
    return pd.read_csv(source)


def prepare_prior_day_data(source: str | Path | pd.DataFrame) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """Target hari t memakai fitur dan skor Garmin yang tersedia pada hari t-1."""
    frame = _load_frame(source)
    missing = {DATE, TARGET}.difference(frame.columns)
    if missing:
        raise ValueError(f"Kolom wajib tidak tersedia: {', '.join(sorted(missing))}")

    frame[DATE] = pd.to_datetime(frame[DATE], errors="coerce").dt.normalize()
    frame[TARGET] = pd.to_numeric(frame[TARGET], errors="coerce")
    frame = frame.dropna(subset=[DATE]).sort_values(DATE)
    if frame[DATE].duplicated().any():
        raise ValueError("Tanggal harian duplikat; sumber harus diagregasi secara eksplisit")
    frame = frame[frame[TARGET].between(0, 100)].copy()
    feature_names = tuple(name for name in FEATURE_CANDIDATES if name in frame.columns)
    if not feature_names:
        raise ValueError("Tidak ada kolom fitur historis yang didukung")

    features = frame[[DATE, *feature_names, TARGET]].copy()
    features[DATE] = features[DATE] + pd.Timedelta(days=1)
    predictors = (*feature_names, TARGET)
    features = features.rename(columns={name: f"previous_{name}" for name in predictors})
    prepared = frame[[DATE, TARGET]].merge(features, on=DATE, how="inner", validate="one_to_one")
    prepared = prepared.replace([np.inf, -np.inf], np.nan)
    prepared = prepared.dropna(subset=[TARGET, f"previous_{TARGET}"]).reset_index(drop=True)
    prepared = prepared[prepared[f"previous_{TARGET}"].between(0, 100)]
    return prepared.reset_index(drop=True), predictors


def train_historical_model(source: str | Path | pd.DataFrame,
                           output_dir: str | Path,
                           test_fraction: float = 0.2,
                           min_rows: int = 30) -> HistoricalModelResult:
    """Latih Random Forest dan bandingkan dengan prediksi rerata data train."""
    if not 0.1 <= test_fraction <= 0.4:
        raise ValueError("test_fraction harus berada di antara 0.1 dan 0.4")
    raw_frame = _load_frame(source)
    prepared, features = prepare_prior_day_data(raw_frame)
    if len(prepared) < min_rows:
        raise ValueError(f"Data berlabel valid belum cukup: {len(prepared)} baris, minimum {min_rows}")

    raw_dates = pd.to_datetime(raw_frame[DATE], errors="coerce").dt.normalize()
    raw_targets = pd.to_numeric(raw_frame[TARGET], errors="coerce")
    valid_target_mask = raw_dates.notna() & raw_targets.between(0, 100)
    feature_missing_counts = {
        name: int(raw_frame[name].isna().sum())
        for name in FEATURE_CANDIDATES if name in raw_frame.columns
    }

    feature_columns = [f"previous_{name}" for name in features]
    split_at = int(len(prepared) * (1 - test_fraction))
    split_at = min(max(split_at, 1), len(prepared) - 1)
    train, test = prepared.iloc[:split_at], prepared.iloc[split_at:]
    x_train, x_test = train[feature_columns], test[feature_columns]
    y_train, y_test = train[TARGET].astype(float), test[TARGET].astype(float)

    estimator = make_pipeline(
        SimpleImputer(strategy="median", keep_empty_features=True),
        RandomForestRegressor(n_estimators=N_ESTIMATORS,
                      min_samples_leaf=MIN_SAMPLES_LEAF,
                      random_state=RANDOM_STATE, n_jobs=1),
    )
    estimator.fit(x_train, y_train)
    predictions = np.clip(estimator.predict(x_test), 0, 100)
    baseline_predictions = {
        "mean": np.full(len(y_test), y_train.mean()),
        "median": np.full(len(y_test), y_train.median()),
        "persistence": test[f"previous_{TARGET}"].to_numpy(dtype=float),
    }
    metrics = {
        "model_mae": float(mean_absolute_error(y_test, predictions)),
        "model_rmse": float(np.sqrt(mean_squared_error(y_test, predictions))),
    }
    for name, values in baseline_predictions.items():
        metrics[f"{name}_baseline_mae"] = float(mean_absolute_error(y_test, values))
        metrics[f"{name}_baseline_rmse"] = float(np.sqrt(mean_squared_error(y_test, values)))
    if len(y_test) >= 2 and y_test.nunique() > 1:
        metrics["model_r2"] = float(r2_score(y_test, predictions))
        for name, values in baseline_predictions.items():
            metrics[f"{name}_baseline_r2"] = float(r2_score(y_test, values))

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    model_path = output / "garmin_daily_stress.joblib"
    metadata_path = output / "garmin_daily_stress.metadata.json"
    metadata: dict[str, Any] = {
        "model_type": "RandomForestRegressor",
        "target": TARGET,
        "target_interpretation": "Skor stres Garmin harian, bukan keadaan psikologis atau diagnosis klinis.",
        "source_rows": len(raw_frame),
        "rows_with_valid_date": int(raw_dates.notna().sum()),
        "valid_target_rows": int(valid_target_mask.sum()),
        "usable_prior_day_rows": len(prepared),
        "duplicate_dates": int(raw_dates[raw_dates.notna()].duplicated().sum()),
        "feature_missing_counts": feature_missing_counts,
        "target_min": float(raw_targets[valid_target_mask].min()),
        "target_max": float(raw_targets[valid_target_mask].max()),
        "features": [f"previous_{name}" for name in features],
        "feature_timing": "fitur dan skor Garmin hari sebelumnya (t-1); target hari t",
        "train_rows": len(train),
        "test_rows": len(test),
        "train_start": train[DATE].iloc[0].date().isoformat(),
        "train_end": train[DATE].iloc[-1].date().isoformat(),
        "test_start": test[DATE].iloc[0].date().isoformat(),
        "test_end": test[DATE].iloc[-1].date().isoformat(),
        "split": "chronological; no shuffle",
        "test_fraction_requested": test_fraction,
        "random_state": RANDOM_STATE,
        "model_parameters": {
            "n_estimators": N_ESTIMATORS,
            "min_samples_leaf": MIN_SAMPLES_LEAF,
            "n_jobs": 1,
        },
        "baselines": {
            "mean": "constant mean of training target on the test rows",
            "median": "constant median of training target on the test rows",
            "persistence": "previous calendar day's Garmin score on rows where it exists",
        },
        "missing_value_strategy": "median imputation fitted on train only; invalid targets and unavailable lagged target excluded",
        "metrics": metrics,
        "test_comparison_uses_same_rows": True,
        "scikit_learn_version": sklearn.__version__,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    joblib.dump(estimator, model_path)
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return HistoricalModelResult(
        model_path, metadata_path, len(train), len(test), features, metrics,
        metadata["test_start"], metadata["test_end"],
    )
