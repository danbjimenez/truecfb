"""TrueCFB engine: the 2026.2 margin rule and overtime. Run: python tests/test_engine.py"""
import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import engine as E  # noqa: E402

COLS = "game_id,season,week,season_type,date,neutral,day,home_id,home,home_fbs,home_conf,away_id,away,away_fbs,away_conf,home_pts,away_pts,note,src,conf_game,ot,home_rank,away_rank,ot_known"


def games(rows):
    """A tiny games.csv: (home, away, home_pts, away_pts, ot)."""
    lines = [COLS] + [f"{i},2025,1,regular,2025-09-0{i},True,2025-09-0{i},{i},{h},True,X,{i + 50},{a},True,X,{hp},{ap},,t,False,{ot},,,True"
                      for i, (h, a, hp, ap, ot) in enumerate(rows, 1)]
    f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False)
    f.write("\n".join(lines) + "\n"); f.close()
    return E.load_games(f.name)


def test_version():
    assert E.VERSION == "2026.2"


def test_venue():
    assert E.home_edge() == 3.0


def test_margin_rule():
    g = games([("A", "B", 100, 0, False)])
    F = E.margin_curve(g)
    win = lambda m: float(E.raw_rating(np.array([m]), F)[0])
    assert win(1) == 70.25 and win(4) == 71 and win(14) == 73.5 and win(40) == 80 and win(77) == 80
    assert float(E.raw_rating(np.array([-1]), F)[0]) == 29.75     # a loss mirrors a win
    assert float(E.raw_rating(np.array([-50]), F)[0]) == 20


def test_overtime_counts_by_final_score():
    g = games([("A", "B", 31, 24, True), ("C", "D", 20, 23, True)])
    assert list(g.margin_home) == [7, -3]


def test_curve_covers_big_margins():
    g = games([("A", "B", 84, 0, False)])
    assert len(E.margin_curve(g)) == 85


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
