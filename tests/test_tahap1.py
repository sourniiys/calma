import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from tahap1_data.simulator import simulate, StressEpisode, NotWorn

def test_shape_and_label():
    df = simulate(2, seed=1, episodes=(StressEpisode(1, 10, 30, 10),))
    assert len(df) == 2 * 1440 and df["true_stress"].sum() == 30

def test_no_steps_and_not_worn():
    df = simulate(2, seed=1, has_steps=False, not_worn=(NotWorn(0, 0, 600),), dropout=0.02)
    assert "steps" not in df and df["hr"].isna().sum() >= 600
