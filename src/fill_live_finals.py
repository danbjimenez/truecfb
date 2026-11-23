"""TrueCFB: add finals the public game files do not have yet, straight from CollegeFootballData.

The public files the pipeline reads can run hours to a day behind on game day. This asks the
CollegeFootballData API for the season's games (one call) and adds any final with at least one FBS
team that the games table is missing, in the same columns build_games.py writes. It also updates
the current season's week status, so a week reads as complete once all its games are final.

Usage: CFBD_API_KEY=... fill_live_finals.py <games.csv> <latest_poll.json> <season>
Without a key it does nothing, so the rest of the pipeline still runs.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

import pandas as pd

API = "https://api.collegefootballdata.com/games"


def fetch_games(season, key):
    q = urllib.parse.urlencode({"year": season, "seasonType": "both"})
    req = urllib.request.Request(f"{API}?{q}", headers={"Authorization": f"Bearer {key}", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def game_day(start):
    """The US game day: a late Saturday kickoff is already Sunday in UTC (as in build_games.py)."""
    return (pd.Timestamp(start).tz_convert("UTC") - pd.Timedelta(hours=8)).strftime("%Y-%m-%d")


def to_row(x, season):
    hl, al = x.get("homeLineScores") or [], x.get("awayLineScores") or []
    return {
        "game_id": int(x["id"]), "season": season, "week": int(x["week"]), "season_type": x["seasonType"],
        "date": str(x["startDate"])[:10], "neutral": bool(x.get("neutralSite")), "day": game_day(x["startDate"]),
        "home_id": int(x["homeId"]), "home": x["homeTeam"], "home_fbs": x.get("homeClassification") == "fbs",
        "home_conf": x.get("homeConference"),
        "away_id": int(x["awayId"]), "away": x["awayTeam"], "away_fbs": x.get("awayClassification") == "fbs",
        "away_conf": x.get("awayConference"),
        "home_pts": int(x["homePoints"]), "away_pts": int(x["awayPoints"]), "note": x.get("notes"), "src": "cfbd-live",
        "conf_game": bool(x.get("conferenceGame")),
        "ot": max(len(hl), len(al)) > 4, "home_rank": None, "away_rank": None, "ot_known": bool(hl or al),
    }


def fill(games_csv, poll_json, season, api_games):
    g = pd.read_csv(games_csv, low_memory=False)
    have = set(g.game_id.astype("int64"))
    add = []
    for x in api_games:
        if not x.get("completed") or x.get("homePoints") is None or x.get("awayPoints") is None:
            continue
        if int(x["id"]) in have or x.get("seasonType") not in ("regular", "postseason"):
            continue
        if x.get("homeClassification") != "fbs" and x.get("awayClassification") != "fbs":
            continue
        if x["homePoints"] == x["awayPoints"]:
            continue
        add.append(to_row(x, season))
    if add:
        g = pd.concat([g, pd.DataFrame(add)], ignore_index=True)
        g = g.sort_values(["season", "date", "game_id"]).reset_index(drop=True)
        g.to_csv(games_csv, index=False)
    # Week status for the current season: count finals from the API, which is the freshest source.
    poll = json.load(open(poll_json))
    if int(poll.get("season", 0)) == season and "weeks" in poll:
        now = pd.Timestamp.now(tz="UTC")
        for w, st in poll["weeks"].items():
            wk = [x for x in api_games if x.get("seasonType") == "regular" and str(x.get("week")) == w
                  and "fbs" in (x.get("homeClassification"), x.get("awayClassification"))]
            if not wk:
                continue
            final = sum(1 for x in wk if x.get("completed"))
            recent = sum(1 for x in wk if not x.get("completed")
                         and pd.Timestamp(x["startDate"]).tz_convert("UTC") > now - pd.Timedelta(hours=36))
            st.update({"games": len(wk), "final": final, "open": recent})
        json.dump(poll, open(poll_json, "w"))
    return [r["game_id"] for r in add]


def main():
    games_csv, poll_json, season = sys.argv[1], sys.argv[2], int(sys.argv[3])
    key = os.environ.get("CFBD_API_KEY")
    if not key:
        print("no CFBD_API_KEY: skipping same-day finals")
        return
    added = fill(games_csv, poll_json, season, fetch_games(season, key))
    print(f"same-day finals added from CollegeFootballData: {len(added)}", added[:20])


if __name__ == "__main__":
    main()
