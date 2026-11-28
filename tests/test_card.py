"""TrueCFB result card: draws every kind of game without error. Run: python tests/test_card.py"""
import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import card as C  # noqa: E402

BASE = {"game_id": 1, "season": 2026, "week": 13, "day": "2026-11-27", "season_type": "regular", "note": None,
        "overtime": False, "neutral": False, "matchup_rating": 121, "matchup_pct": 86, "winner": "Iowa",
        "teams": [
            {"team": "Iowa", "fbs": True, "points": 31, "won": True, "site": "home", "game_rating": 78.2, "game_rating_pct": 92,
             "rating_before": 64.4, "rating_after": 65.6, "change": 1.2, "rank_before": 15, "rank_after": 14, "bonus": 15.6,
             "post_both": 0.0, "post_win": 0.0, "record": [10, 2],
             "parts": {"result": 70.0, "strength": 5.2, "margin": 6.0, "venue": -3.0, "limit": 0.0, "post": 0.0}},
            {"team": "Nebraska", "fbs": True, "points": 7, "won": False, "site": "road", "game_rating": 42.6, "game_rating_pct": 40,
             "rating_before": 56.5, "rating_after": 55.2, "change": -1.2, "rank_before": 34, "rank_after": 39, "bonus": 5.2,
             "post_both": 0.0, "post_win": 0.0, "record": [7, 5],
             "parts": {"result": 30.0, "strength": 15.6, "margin": -6.0, "venue": 3.0, "limit": 0.0, "post": 0.0}}],
        "ripple": {"past_opponents_gained": [], "past_opponents_lost": []}}


def check(res):
    img = C.render(res)
    assert img.size == (1200, 675)


def test_regular():
    check(BASE)


def test_visitor_on_the_left():
    away, home = C.sides(BASE)
    assert (away["team"], home["team"]) == ("Nebraska", "Iowa")


def test_fcs_overtime_postseason_and_old_results():
    fcs = copy.deepcopy(BASE)
    fcs["teams"][1] = {"team": "Tennessee Tech", "fbs": False, "points": 16, "won": False, "site": "road", "rating": 25.0, "bonus": -25.0}
    fcs["matchup_pct"] = None
    check(fcs)
    ot = copy.deepcopy(BASE); ot["overtime"] = True; check(ot)
    post = copy.deepcopy(BASE)
    post.update(season_type="postseason", note="CFP National Championship", neutral=True)
    for t in post["teams"]:
        t["site"] = "neutral"; t["post_both"] = 15.0
    post["teams"][0].update(post_win=40.0, game_rating=155.0)
    post["teams"][0]["parts"].update(limit=-10.3, post=55.0, venue=0.0)
    post["teams"][1]["parts"].update(post=15.0, venue=0.0)
    check(post)
    old = copy.deepcopy(BASE)
    for t in old["teams"]:
        for k in ("parts", "record", "game_rating_pct"):
            t.pop(k)
    old.pop("matchup_pct")
    check(old)


def test_formats():
    assert C.compact(6.0) == "6" and C.compact(5.25) == "5.25" and C.compact(-3.0) == "3"
    assert C.ordinal(1) == "1st" and C.ordinal(92) == "92nd" and C.ordinal(100) == "99th" and C.ordinal(13) == "13th"
    assert C.num(-1.3) == "−1.3"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
