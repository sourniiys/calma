"""Tahap 1 - Pembaca file wellness Garmin (.fit) -> DataFrame per menit untuk CALMA.

Keluaran kolom: hr (bpm) dan garmin_stress (hanya pembanding, bukan input CALMA).
Catatan: file wellness ini tidak punya langkah per menit, jadi kolom steps tidak ada.
Waktu dikembalikan dalam waktu lokal (UTC + offset dari file, mis. WIB = +7).
"""
import glob
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import fitparse

FIT_EPOCH = datetime(1989, 12, 31)


def _to_fit(dt: datetime) -> int:
    return int((dt - FIT_EPOCH).total_seconds())


def read_wellness(paths) -> dict[str, pd.DataFrame]:
    hr, steps, stress, acts = [], [], [], []
    offset = timedelta(0)
    for path in sorted(paths):
        last = None                               # timestamp penuh terakhir (detik FIT)
        for m in fitparse.FitFile(path).get_messages():
            d = {f.name: f.value for f in m if f.value is not None}
            if m.name == "monitoring_info" and "local_timestamp" in d:
                offset = d["local_timestamp"] - d["timestamp"]
            if m.name == "stress_level":
                stress.append((d["stress_level_time"], d["stress_level_value"]))
            if m.name != "monitoring":
                continue
            if "timestamp" in d:
                last = _to_fit(d["timestamp"])
            ts16 = d.get("timestamp_16")
            if ts16 is not None and last is not None:      # rekonstruksi timestamp 16-bit
                t = (last & ~0xFFFF) | int(ts16)
                if t < last - 1:
                    t += 0x10000
                last = t
                if "heart_rate" in d:
                    hr.append((FIT_EPOCH + timedelta(seconds=t), d["heart_rate"]))
            if "steps" in d and last is not None:
                steps.append((FIT_EPOCH + timedelta(seconds=last), d["steps"], d.get("activity_type")))
            if "activity_type" in d and "timestamp" in d:
                acts.append((d["timestamp"], d["activity_type"], d.get("intensity")))
    loc = lambda s: pd.DatetimeIndex(s) + offset
    out = {}
    h = pd.DataFrame(hr, columns=["t", "hr"]); h["t"] = loc(h["t"])
    out["hr"] = h.set_index("t")["hr"].sort_index()
    st = pd.DataFrame(stress, columns=["t", "v"]).drop_duplicates("t"); st["t"] = loc(st["t"])
    out["garmin_stress"] = st.set_index("t")["v"].sort_index()
    sp = pd.DataFrame(steps, columns=["t", "steps", "act"]); sp["t"] = loc(sp["t"])
    out["steps_raw"] = sp.set_index("t").sort_index()
    ac = pd.DataFrame(acts, columns=["t", "act", "intensity"]); ac["t"] = loc(ac["t"])
    out["activity"] = ac.set_index("t").sort_index()
    out["offset"] = offset
    return out


def load_minutely(folder: str) -> pd.DataFrame:
    raw = read_wellness(glob.glob(f"{folder}/*WELLNESS.fit"))
    hr = raw["hr"]
    hr = hr[(hr > 30) & (hr < 220)]                 # 0 = tidak terukur
    hr = hr[~hr.index.duplicated()].resample("1min").mean().interpolate(limit=3)
    return pd.DataFrame({"hr": hr}).join(raw["garmin_stress"].rename("garmin_stress")
                                         .resample("1min").last())
