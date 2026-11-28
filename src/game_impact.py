"""TrueCFB: what one game changed.

For a finished game this works out, with the engine:
  - the Matchup Rating (the pot the two teams split) and each team's Game Rating
  - each team's Team Rating and rank before and after the game
  - the ripple: how every other team's rating moved because of this one result, with the biggest
    gainers and losers among the two teams' past opponents called out

"Before" and "after" differ by this one game only. Both are the season as of the end of the game's
day (every final that day counts, except this game in "before"), so on a Saturday each game is
measured on its own, everything else held equal. Ranks are plain rating order, as in the weekly
rankings; the head-to-head swap is applied only to the two end-of-season rankings, not here.

The numbers here come straight from the engine. post_text() turns one result into a post for X,
built from a fixed template, so a post never contains a number the engine did not produce.

Usage:
  game_impact.py <games.csv> <src_dir> <season> [--game ID ...] [--day YYYY-MM-DD] [--latest-day]
                 [--out impact.json] [--text]
  --game        one or more game ids
  --day         every game on that US game day
  --latest-day  every game on the season's most recent game day (the default)
  --out         write the results as JSON
  --text        print the post for each game
"""
import argparse
import json
import os
import re
import sys

import numpy as np
import pandas as pd

# The engine lives beside this file (src/), as run_all.py expects.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine as E  # noqa: E402

MAX_POST = 280
RIPPLE_SHOWN = 3      # gainers and losers kept in the JSON for the result card


# ---------- the season's starting point, exactly as run_all.py builds it ----------

def season_teams(s):
    return sorted(set(s.home[s.home_fbs]) | set(s.away[s.away_fbs]))


def prior_for(g, F, V, season):
    """Last season's final rating (after all bowl and playoff games), for every team, built the same
    way run_all.py builds it: 2013 seeds 2014, then each finished season's final seeds the next."""
    first = int(g.season.min())
    prior = E.rate(g[g.season == first], F, V)[0].rating
    for y in range(first + 1, season):
        s = g[g.season == y]
        prior = E.rate(s, F, V, prior=prior, teams=season_teams(s))[0].rating
    return prior


# ---------- one game ----------

def _ranks(tab):
    order = tab.sort_values("rating", ascending=False).index
    return {t: i + 1 for i, t in enumerate(order)}


def _site(row, team):
    if row.neutral:
        return "neutral"
    return "home" if row.home == team else "road"


PCT_MIN = 300         # percentiles are shown once the season has this many values to compare with


def _pct(values, x):
    """Where x falls among values, 0 to 100 (ties count half), or None early in a season."""
    values = values[~np.isnan(values)]
    if len(values) < PCT_MIN:
        return None
    return int(round(100 * ((values < x).sum() + 0.5 * (values == x).sum()) / len(values)))


def impact(asof, game_id, F, V, prior, teams):
    """asof: the season's games through the end of this game's day (including this game).
    Returns one result as a plain dict, ready for JSON."""
    gm = asof[asof.game_id == game_id]
    if gm.empty:
        raise ValueError(f"game {game_id} is not in the games table (not final yet, or a tie)")
    r = gm.iloc[0]
    before_tab, _ = E.rate(asof[asof.game_id != game_id], F, V, prior=prior, teams=teams)
    after_tab, det = E.rate(asof, F, V, prior=prior, teams=teams)
    rk_b, rk_a = _ranks(before_tab), _ranks(after_tab)

    gd = det[det.game_id == game_id]
    winner = r.home if r.margin_home > 0 else r.away
    sides = []
    for team, fbs, pts, opp_pts in ((r.home, r.home_fbs, r.home_pts, r.away_pts),
                                    (r.away, r.away_fbs, r.away_pts, r.home_pts)):
        side = {"team": team, "fbs": bool(fbs), "points": int(pts), "won": team == winner, "site": _site(r, team)}
        if fbs:
            line = gd[gd.team == team].iloc[0]
            b, a = float(before_tab.rating[team]), float(after_tab.rating[team])
            base = 70.0 if line.margin > 0 else 30.0
            before_limit = float(line.raw + line.venue + E.OPP_WEIGHT * (line.opp_rating - 50.0))
            post = float(line.post_both + (line.post_win if line.margin > 0 else 0.0))
            side.update({"parts": {"result": base, "strength": round(float(E.OPP_WEIGHT * (line.opp_rating - 50.0)), 1),
                                   "margin": float(line.raw - base), "venue": float(line.venue),
                                   "limit": round(min(max(before_limit, 0.0), 100.0) - before_limit, 2), "post": post},
                         "record": [int(after_tab.wins[team]), int(after_tab.losses[team])],
                         "game_rating_pct": _pct(det.game_rating.to_numpy(), float(line.game_rating)),
                         "game_rating": round(float(line.game_rating), 1),
                         "rating_before": round(b, 1), "rating_after": round(a, 1), "change": round(a - b, 1),
                         "rank_before": rk_b[team], "rank_after": rk_a[team],
                         "bonus": round(a - 50.0, 1), "post_both": float(line.post_both), "post_win": float(line.post_win)})
        else:
            side.update({"rating": E.FCS_RATING, "bonus": E.FCS_RATING - 50.0})
        sides.append(side)

    # The Matchup Rating, as the site shows it: 100 plus both bonuses (at today's ratings), plus the
    # postseason points both teams and the winner add. Without the 0-100 limit or postseason points the
    # two Game Ratings add up to it exactly: margin and venue move points from one side to the other.
    fbs_side = next(s for s in sides if s["fbs"])
    matchup = 100.0 + E.OPP_WEIGHT * (sides[0]["bonus"] + sides[1]["bonus"]) \
        + 2 * fbs_side["post_both"] + fbs_side["post_win"]

    # The ripple: every other team's change, and who each team played before this game.
    pair = {r.home, r.away}
    delta = (after_tab.rating - before_tab.rating).drop(labels=[t for t in pair if t in after_tab.index])
    played = asof[asof.game_id != game_id]
    past = {}
    for s in sides:
        if not s["fbs"]:
            continue
        t = s["team"]
        for x in played[(played.home == t) | (played.away == t)].itertuples():
            opp = x.away if x.home == t else x.home
            if opp in delta.index:   # FBS opponents only; FCS teams have no rating to move
                beat_t = (x.margin_home > 0) == (x.home == opp)
                link = {"vs": t, "result": "beat" if beat_t else "lost to"}
                if link not in past.setdefault(opp, []):   # teams that met twice are listed once per result
                    past[opp].append(link)

    def entry(t):
        return {"team": t, "change": round(float(delta[t]), 2), "rating_after": round(float(after_tab.rating[t]), 1),
                "rank_before": rk_b[t], "rank_after": rk_a[t], "link": past.get(t, [])}

    po = delta[list(past)] if past else delta.iloc[:0]
    # Where this game's Matchup Rating (the two Team Ratings added) falls among the season's FBS games so
    # far, at today's ratings. Display only.
    matchup_pct = None
    if r.home_fbs and r.away_fbs:
        ff = asof[asof.home_fbs & asof.away_fbs]
        sums = after_tab.rating.reindex(ff.home).to_numpy() + after_tab.rating.reindex(ff.away).to_numpy()
        matchup_pct = _pct(sums, float(after_tab.rating[r.home] + after_tab.rating[r.away]))
    return {
        "game_id": int(r.game_id), "season": int(r.season), "week": int(r.week), "day": r.day,
        "season_type": r.season_type, "note": None if pd.isna(r.note) else str(r.note),
        "overtime": bool(r.ot), "neutral": bool(r.neutral),
        "matchup_rating": round(matchup), "matchup_pct": matchup_pct, "winner": winner, "teams": sides,
        "ripple": {
            "past_opponents_gained": [entry(t) for t in po.sort_values(ascending=False).index[:RIPPLE_SHOWN] if po[t] > 0],
            "past_opponents_lost": [entry(t) for t in po.sort_values().index[:RIPPLE_SHOWN] if po[t] < 0],
            "biggest_movers": [entry(t) for t in delta.abs().sort_values(ascending=False).index[:5]],
            "teams_moved": int((delta.abs() >= 0.05).sum()),
        },
        "engine": {"name": E.NAME, "version": E.VERSION},
    }


# ---------- the post for X ----------

def weighted_length(text):
    """Length as X counts it (twitter-text v3): most Latin characters count 1, anything outside the
    light ranges (arrows, the true minus sign, emoji, CJK) counts 2."""
    light = ((0, 4351), (8192, 8205), (8208, 8223), (8242, 8247))
    return sum(1 if any(a <= ord(c) <= b for a, b in light) else 2 for c in text)


def _signed(x, nd=1):
    v = round(x, nd)
    return ("+" if v > 0 else "") + f"{v:.{nd}f}" if v != 0 else f"{0:.{nd}f}"


def _rank_move(s):
    if s["rank_before"] == s["rank_after"]:
        return f"#{s['rank_after']}"
    return f"#{s['rank_before']} → #{s['rank_after']}"


def _team_line(s, short=False):
    if not s["fbs"]:
        return f"{s['team']}: FCS (counts as {E.FCS_RATING:.0f})"
    parts = [f"{s['team']}: Game Rating {s['game_rating']:.1f}",
             f"Team Rating {s['rating_after']:.1f} ({_signed(s['change'])})"]
    if not short:
        parts.append(_rank_move(s))
    return " · ".join(parts)


def _ripple_line(res, n):
    items = []
    gained, lost = res["ripple"]["past_opponents_gained"], res["ripple"]["past_opponents_lost"]
    for e in (gained[:1] + lost[:1])[:n]:
        if abs(e["change"]) < 0.05:
            continue
        link = e["link"][0]
        items.append(f"{e['team']} {_signed(e['change'])} ({link['result']} {link['vs']})")
    return "Ripple: " + " · ".join(items) if items else None


def game_title(note):
    """A bowl or playoff game's name without the sponsor line ("... Presented by AT&T")."""
    return re.split(r"\s+(?:presented by|powered by)\s+", note, flags=re.I)[0].strip()


def post_text(res, hashtags=None):
    """One result as a post for X: a fixed template, no links, no mentions. Lines are dropped in a set
    order until it fits in 280 (rank moves, then the second ripple item, then the ripple line)."""
    w = next(s for s in res["teams"] if s["won"]); l = next(s for s in res["teams"] if not s["won"])
    tag = " (OT)" if res["overtime"] else ""
    where = "neutral site" if res["neutral"] else f"{w['site']} win"
    head = f"FINAL: {w['team']} {w['points']}, {l['team']} {l['points']}{tag} · {where}"
    if res["note"] and res["season_type"] == "postseason":
        head = f"{game_title(res['note'])}\n" + head
    tail = " ".join(hashtags or [])
    for short, n in ((False, 2), (True, 2), (True, 1), (True, 0)):
        lines = [head, f"Matchup Rating {res['matchup_rating']}", _team_line(w, short), _team_line(l, short)]
        rip = _ripple_line(res, n) if n else None
        if rip:
            lines.append(rip)
        if tail:
            lines.append(tail)
        text = "\n".join(lines)
        if weighted_length(text) <= MAX_POST:
            return text
    return text[:MAX_POST]   # only reached with absurdly long names or hashtags


def team_tags(res, path=None):
    """Each FBS team's hashtag from data/team_hashtags.json (missing teams get none)."""
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "team_hashtags.json")
    if not os.path.exists(path):
        return []
    tags = json.load(open(path)).get("teams", {})
    order = sorted(res["teams"], key=lambda s: not s["won"])   # the winner's first
    return [tags[s["team"]]["tag"] for s in order if s["fbs"] and s["team"] in tags]


UPSET_GAP = 5   # a win is called an upset when the loser was ranked at least this many spots higher


def _shown_change(s):
    """A Team Rating change as the card shows it: the rounded rating after minus the rounded one before."""
    return round(round(s["rating_after"], 1) - round(s["rating_before"], 1), 1)


def headline(res):
    """The result as one or more headline sentences, the winner first: its new TrueCFB rank, the score
    and who it beat, then its Team Rating, then the loser's rank if it moved. A fixed template: every
    number comes from the result. Returns the sentences, most important first."""
    w = next(s for s in res["teams"] if s["won"]); l = next(s for s in res["teams"] if not s["won"])
    score = f"{w['points']}-{l['points']}"
    road = w["site"] == "road"
    opp = f"#{l['rank_before']}-ranked {l['team']}" if l["fbs"] else f"FCS {l['team']}"
    out = []
    if not w["fbs"]:
        out.append(f"FCS {w['team']} beats {opp} {score}{' in overtime' if res['overtime'] else ''}"
                   f"{' on the road' if road else ''}.")
    else:
        a, b = w["rank_after"], w["rank_before"]
        rank = "TrueCFB ranking"
        upset = l["fbs"] and l["rank_before"] <= b - UPSET_GAP
        if upset:
            how = (" in overtime" if res["overtime"] else "") + (" on the road" if road else "")
            move = (f"and moves up to #{a} in the {rank}" if a < b else
                    f"and keeps its #{a} spot in the {rank}" if a == b else f"but slips to #{a} in the {rank}")
            out.append(f"{w['team']} upsets {opp} {score}{how} {move}.")
        else:
            kind = ("overtime " if res["overtime"] else "") + ("road " if road else "") + "win"
            if a < b:
                out.append(f"{w['team']} moves up to #{a} in the {rank} with a {score} {kind} over {opp}.")
            elif a == b:
                out.append(f"{w['team']} keeps its #{a} spot in the {rank} with a {score} {kind} over {opp}.")
            else:
                out.append(f"{w['team']} slips to #{a} in the {rank} despite a {score} {kind} over {opp}.")
        c = _shown_change(w)
        out.append(f"{w['team']}'s Team Rating " + (f"rises {c:.1f} to {w['rating_after']:.1f}." if c > 0 else
                                                    f"falls {-c:.1f} to {w['rating_after']:.1f}." if c < 0 else
                                                    f"stays level at {w['rating_after']:.1f}."))
    if l["fbs"] and l["rank_after"] != l["rank_before"]:
        out.append(f"{l['team']} falls to #{l['rank_after']}." if l["rank_after"] > l["rank_before"] else
                   f"{l['team']} moves up to #{l['rank_after']} despite the loss.")
    return out


def short_post(res, hashtags=None):
    """The post that goes with the result card: a headline (headline()) and each team's hashtag. The
    card holds the numbers; the long post_text() becomes the image's alt text. Sentences are dropped from
    the end until it fits in 280."""
    first = game_title(res["note"]) + "\n" if res["note"] and res["season_type"] == "postseason" else ""
    tail = "\n" + " ".join(hashtags) if hashtags else ""
    sents = headline(res)
    while True:
        text = first + " ".join(sents) + tail
        if weighted_length(text) <= MAX_POST or len(sents) == 1:
            return text[:MAX_POST]
        sents = sents[:-1]


# ---------- command line ----------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("games_csv"); ap.add_argument("src_dir"); ap.add_argument("season", type=int)
    ap.add_argument("--game", type=int, nargs="*"); ap.add_argument("--day")
    ap.add_argument("--latest-day", action="store_true"); ap.add_argument("--out"); ap.add_argument("--text", action="store_true")
    a = ap.parse_args()

    g = E.load_games(a.games_csv)
    F = E.margin_curve(g); V = E.home_edge(g, F)
    s = g[g.season == a.season]
    if s.empty:
        sys.exit(f"no finished games for {a.season}")
    if a.game:
        ids = a.game
    else:
        day = a.day or s.day.max()
        ids = list(s[s.day == day].game_id)
    prior = prior_for(g, F, V, a.season)
    teams = season_teams(s)
    out = []
    for gid in ids:
        row = s[s.game_id == gid]
        if row.empty:
            print(f"skip {gid}: not a finished {a.season} game", file=sys.stderr)
            continue
        res = impact(s[s.day <= row.iloc[0].day], gid, F, V, prior, teams)
        res["post"] = post_text(res)
        out.append(res)
        if a.text:
            print(res["post"], f"\n[{weighted_length(res['post'])} of {MAX_POST}]\n")
    if a.out:
        json.dump(out, open(a.out, "w"), indent=1, ensure_ascii=False)
    print(f"{len(out)} game(s)", file=sys.stderr)


if __name__ == "__main__":
    main()
