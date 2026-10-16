"""Tahap 3b - Deteksi potensi stres (skor > ambang selama >= 10 menit) + evaluasi."""
from dataclasses import dataclass
import pandas as pd
from tahap2_baseline.fitur import THRESHOLD, MIN_MINUTES


@dataclass(frozen=True)
class StressEvent:
    start: pd.Timestamp
    alert_time: pd.Timestamp   # saat syarat 10 menit terpenuhi -> minta konfirmasi
    end: pd.Timestamp
    peak: float
    motion_checked: bool = True   # False = tanpa data langkah; bisa saja gerak badan


def detect_events(score: pd.Series, threshold: float = THRESHOLD,
                  min_minutes: int = MIN_MINUTES,
                  motion_checked: bool = True) -> list[StressEvent]:
    if not isinstance(score.index, pd.DatetimeIndex):
        raise TypeError("Skor deteksi harus memiliki indeks timestamp")
    if score.index.has_duplicates:
        raise ValueError("Timestamp skor tidak boleh duplikat")
    if min_minutes < 1:
        raise ValueError("Durasi minimum harus sedikitnya satu menit")

    score = score.sort_index()
    above = (score > threshold).fillna(False)
    events = []

    def add_event(timestamps: list[pd.Timestamp]) -> None:
        if len(timestamps) < min_minutes:
            return
        segment = score.loc[timestamps]
        events.append(StressEvent(
            timestamps[0], timestamps[min_minutes - 1], timestamps[-1],
            float(segment.max()), motion_checked,
        ))

    run: list[pd.Timestamp] = []
    for timestamp, qualifies in above.items():
        timestamp = pd.Timestamp(timestamp)
        if not qualifies:
            add_event(run)
            run = []
            continue
        if run and timestamp - run[-1] != pd.Timedelta(minutes=1):
            add_event(run)
            run = []
        run.append(timestamp)
    add_event(run)
    return events


def evaluate(events: list[StressEvent], truth: pd.Series) -> dict:
    """Evaluasi tingkat-event terhadap label simulator (precision/recall)."""
    true_runs = (truth != truth.shift()).cumsum()[truth]
    true_eps = [(g.index[0], g.index[-1]) for _, g in truth[truth].groupby(true_runs)]
    tp = sum(any(e.start <= te and e.end >= ts for ts, te in true_eps) for e in events)
    hit = sum(any(e.start <= te and e.end >= ts for e in events) for ts, te in true_eps)
    return {"episode_nyata": len(true_eps), "terdeteksi": hit,
            "alert": len(events), "alert_benar": tp,
            "precision": tp / len(events) if events else float("nan"),
            "recall": hit / len(true_eps) if true_eps else float("nan")}
