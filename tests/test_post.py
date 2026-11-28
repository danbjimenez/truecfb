"""TrueCFB result post: the headline caption for each kind of result. Run: python tests/test_post.py"""
import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import game_impact as GI  # noqa: E402
from test_card import BASE  # noqa: E402


def side(res, team):
    return next(s for s in res["teams"] if s["team"] == team)


def test_rank_up_with_team_rating_and_loser():
    text = GI.short_post(BASE, ["#Hawkeyes", "#GBR"])
    assert text == ("Iowa moves up to #14 in the TrueCFB ranking with a 31-7 win over #34-ranked Nebraska. "
                    "Iowa's Team Rating rises 1.2 to 65.6. Nebraska falls to #39.\n#Hawkeyes #GBR"), text


def test_same_rank_level_rating_road_overtime():
    r = copy.deepcopy(BASE)
    iowa = side(r, "Iowa")
    iowa.update(site="road", rank_after=15, rating_after=64.4)
    side(r, "Nebraska").update(rank_after=34)
    r["overtime"] = True
    assert GI.headline(r) == ["Iowa keeps its #15 spot in the TrueCFB ranking with a 31-7 overtime road win "
                              "over #34-ranked Nebraska.", "Iowa's Team Rating stays level at 64.4."]


def test_upset_needs_a_gap():
    r = copy.deepcopy(BASE)
    side(r, "Nebraska").update(rank_before=10, rank_after=16)
    assert GI.headline(r)[0] == "Iowa upsets #10-ranked Nebraska 31-7 and moves up to #14 in the TrueCFB ranking."
    side(r, "Nebraska").update(rank_before=12)       # 3 spots higher: not called an upset
    assert GI.headline(r)[0].startswith("Iowa moves up to #14")


def test_winner_slips_and_loser_rises():
    r = copy.deepcopy(BASE)
    side(r, "Iowa").update(rank_after=16, rating_after=64.0)
    side(r, "Nebraska").update(rank_after=30)
    assert GI.headline(r) == ["Iowa slips to #16 in the TrueCFB ranking despite a 31-7 win over #34-ranked Nebraska.",
                              "Iowa's Team Rating falls 0.4 to 64.0.", "Nebraska moves up to #30 despite the loss."]


def test_fcs_and_postseason():
    r = copy.deepcopy(BASE)
    r["teams"][1] = {"team": "Tennessee Tech", "fbs": False, "points": 16, "won": False, "site": "road",
                     "rating": 25.0, "bonus": -25.0}
    assert "31-16 win over FCS Tennessee Tech." in GI.headline(r)[0]
    r = copy.deepcopy(BASE)
    r["teams"][0] = {"team": "Montana State", "fbs": False, "points": 31, "won": True, "site": "home",
                     "rating": 25.0, "bonus": -25.0}
    assert GI.headline(r) == ["FCS Montana State beats #34-ranked Nebraska 31-7.", "Nebraska falls to #39."]
    r = copy.deepcopy(BASE)
    r.update(season_type="postseason", note="Rose Bowl Game Presented by Prudential")
    assert GI.short_post(r).startswith("Rose Bowl Game\nIowa moves up to #14")


def test_fits_in_a_post():
    r = copy.deepcopy(BASE)
    for s in r["teams"]:
        s["team"] = s["team"] + " State University of Very Long Names"
    text = GI.short_post(r, ["#" + "x" * 40, "#" + "y" * 40])
    assert GI.weighted_length(text) <= GI.MAX_POST and "Team Rating" not in text, text


def test_winner_hashtag_first():
    import json
    import tempfile
    path = os.path.join(tempfile.mkdtemp(), "tags.json")
    json.dump({"teams": {"Iowa": {"tag": "#Hawkeyes"}, "Nebraska": {"tag": "#GBR"}}}, open(path, "w"))
    r = copy.deepcopy(BASE)
    r["teams"].reverse()
    assert GI.team_tags(r, path) == ["#Hawkeyes", "#GBR"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
