"""TrueCFB rating engine, version 2026.2, 27 Nov 2026  (results only; team-blind; reproducible)
Versions are numbered year.release: 2026.1 was the first public version (released as "v1.0" on
21 Nov 2026); 2026.2 changed the margin rule (1 point per 4 points of margin instead of a curve,
overtime games count by their final score) and fixed venue at 3. Every other rule is as in 2026.1.
Any change to a rule or number below is a new version, with every season re-run.

GAME RATING, computed for each FBS team in each game:
  1. Start: a win is 70, a loss is 30.
  2. Opponent: + (opponent's rating - 50), the opponent's "strength" (called the bonus before 2026.2).  Any FCS opponent counts as a 25.
  3. Margin: 1 point for every 4 points of final margin, up to a 40-point margin.
        win  = 70 + min(m, 40) / 4        loss = 30 - min(m, 40) / 4
     m is the final score margin, overtime included.
  4. Venue: road team +3, home team -3, neutral site 0 (the measured edge of home teams in
     conference games on this scale, 2.75, rounded).
  5. Keep the result between 0 and 100.
  6. Postseason games are worth more, added on top of step 5 (so they can exceed 100):
        regular bowl   +10 to both teams
        playoff game   +15 to both teams, and the winner adds +10 in rounds before the
                       quarterfinals, +20 in a quarterfinal, +30 in a semifinal, +40 in the final
TEAM RATING = average of its Game Ratings this season. Every game counts. Until a team has played
  6 games, last season's final rating (after all postseason games) stands in for each game not
  yet played.
Opponent ratings come from this same calculation: start everyone at 50 and repeat until no
  rating moves. Starting at 50 is part of the rule. In every season except 2020 any starting point
  gives the same answer (checked on all 191 snapshots for 2026.1,
  and on 179 weekly and end-of-season snapshots for 2026.2). In late 2020, with conference-only schedules,
  nothing ties one conference's level to another's, so that season's ratings depend on the start
  and are treated as unreliable.
"""
import numpy as np
import pandas as pd

NAME = "TrueCFB"              # named 22 Nov 2026; the name is not part of the formula
VERSION = "2026.2"          # year.release; 2026.1 was released as "v1.0"
WIN_RANGE = (70.0, 80.0)      # a win before margin .. a win by MARGIN_CAP or more; losses mirror it (30 .. 20)
VENUE = 3.0                   # road +3, home -3, neutral 0 (the measured edge, 2.75, rounded; 2.86 measured before 2026.2)
MARGIN_CAP = 40               # margin stops counting here: 1 point per 4 points, at most 10 (2026.1 used a curve)
OPP_WEIGHT = 1.0              # the opponent's strength at full value (0.9 in a draft before the public release)
FCS_RATING = 25.0
CARRY = 6
H2H_WINDOW = 1.0
REF_SEASONS = range(2014, 2026)
BOWL_BONUS = 10.0             # both teams, regular bowl
PLAYOFF_BONUS = 15.0          # both teams, any playoff game
PLAYOFF_WIN_BONUS = {"final": 40.0, "semifinal": 30.0, "quarterfinal": 20.0, "earlier": 10.0}
FIRST_PLAYOFF_SEASON = 2014


def load_games(path):
    """Every game with its final score margin (overtime included since 2026.2). Ties are dropped."""
    g = pd.read_csv(path, low_memory=False)
    g["margin_home"] = (g.home_pts - g.away_pts).astype(int)
    return g[g.margin_home != 0].copy()


def playoff_round(note, season):
    """Which playoff round a postseason game is, from its name; None for a regular bowl."""
    if season < FIRST_PLAYOFF_SEASON:
        return None
    n = str(note).lower()
    if "national championship" in n:
        return "final"
    if "semifinal" in n:
        return "semifinal"
    if "quarterfinal" in n:
        return "quarterfinal"
    if "playoff" in n and "round" in n:
        return "earlier"
    return None


def postseason_bonus(season_type, note, season):
    """(bonus for both teams, extra bonus for the winner, round name or 'bowl' or '')."""
    if season_type != "postseason":
        return 0.0, 0.0, ""
    rd = playoff_round(note, season)
    if rd is None:
        return BOWL_BONUS, 0.0, "bowl"
    return PLAYOFF_BONUS, PLAYOFF_WIN_BONUS[rd], rd


def margin_curve(games, cap=MARGIN_CAP):
    """F[m]: how much of the margin range a win by m points uses, min(m, cap) / cap, for every margin up to
    the largest in `games`. raw_rating turns it into 70 + m / 4 for a win (2026.2). 2026.1 used the share of
    2014-2025 games decided by fewer than m points instead."""
    mx = max(int(games.margin_home.abs().max()), cap)
    return np.minimum(np.arange(mx + 1), cap) / cap


def raw_rating(margin, F, win=WIN_RANGE):
    w = win[0] + (win[1] - win[0]) * F[np.abs(margin)]
    return np.where(margin > 0, w, 100.0 - w)


def measured_home_edge(games, F, win=WIN_RANGE, seasons=REF_SEASONS):
    """The average edge of home teams in FBS conference games on this scale (2.75 under the 2026.2 rules)."""
    ref = games[games.season.isin(seasons) & games.home_fbs & games.away_fbs & games.conf_game & ~games.neutral]
    return float(raw_rating(ref.margin_home.to_numpy(), F, win).mean() - 50.0)


def home_edge(games=None, F=None):
    """The venue points: a fixed VENUE (3.0), the measured home edge rounded to a whole number. The rules
    before 2026.2 used the measured edge itself (2.86). Arguments are accepted and ignored, so callers that
    measured it still work."""
    return VENUE


def rate(games, F, v, win=WIN_RANGE, b=OPP_WEIGHT, prior=None, carry=CARRY, fcs=FCS_RATING,
         tol=1e-10, start=None, teams=None, postseason_bonuses=True):
    """games: one season's rows up to the cutoff. v: venue points. prior: Series of last season's final
    ratings (or None). teams: full list of this season's FBS teams, so teams that have not played yet
    still appear (at their carried-over rating). Returns (team table, per-game detail)."""
    g = games
    fbs = sorted(set(g.home[g.home_fbs]) | set(g.away[g.away_fbs]) | set(teams or []))
    idx = {t: i for i, t in enumerate(fbs)}
    n = len(fbs)
    recs = []
    for r in g.itertuples():
        hv, av = (0.0, 0.0) if r.neutral else (-v, v)
        both, extra, rd = postseason_bonus(r.season_type, r.note, r.season) if postseason_bonuses else (0.0, 0.0, "")
        if r.home_fbs:
            recs.append((idx[r.home], idx[r.away] if r.away_fbs else -1, r.margin_home, hv, r.game_id, both, extra, rd))
        if r.away_fbs:
            recs.append((idx[r.away], idx[r.home] if r.home_fbs else -1, -r.margin_home, av, r.game_id, both, extra, rd))
    team = np.array([x[0] for x in recs], dtype=int); opp = np.array([x[1] for x in recs], dtype=int)
    mar = np.array([x[2] for x in recs], dtype=int); ven = np.array([x[3] for x in recs])
    both = np.array([x[5] for x in recs], dtype=float); extra = np.array([x[6] for x in recs], dtype=float)
    post_add = both + np.where(mar > 0, extra, 0.0)
    raw = raw_rating(mar, F, win)
    gp = np.bincount(team, minlength=n).astype(float)
    if prior is None:
        pr = np.full(n, 50.0); npri = np.zeros(n)
    else:
        pr = np.array([prior.get(t, fcs) for t in fbs], dtype=float)
        npri = np.clip(carry - gp, 0, None)
    rating = np.full(n, 50.0) if start is None else np.asarray(start, dtype=float).copy()

    def game_ratings(rt):
        oq = np.where(opp >= 0, rt[np.clip(opp, 0, None)], fcs)
        return np.clip(raw + ven + b * (oq - 50.0), 0.0, 100.0) + post_add, oq

    for it in range(100000):
        adj, _ = game_ratings(rating)
        new = (np.bincount(team, weights=adj, minlength=n) + npri * pr) / np.maximum(gp + npri, 1)
        delta = np.max(np.abs(new - rating)); rating = new
        if delta < tol:
            break
    adj, oq = game_ratings(rating)
    wins = np.bincount(team, weights=(mar > 0), minlength=n).astype(int)
    names = np.array(fbs + ["FCS"])
    table = pd.DataFrame({"team": fbs, "rating": rating, "games": gp.astype(int), "wins": wins,
                          "losses": gp.astype(int) - wins,
                          "avg_raw": np.bincount(team, weights=raw, minlength=n) / np.maximum(gp, 1),
                          "avg_opp": np.bincount(team, weights=oq, minlength=n) / np.maximum(gp, 1)}).set_index("team")
    table.attrs["iters"] = it + 1
    detail = pd.DataFrame({"game_id": [x[4] for x in recs], "team": names[team], "opp": names[opp],
                           "margin": mar, "venue": ven, "raw": raw, "opp_rating": oq, "game_rating": adj,
                           "post_both": both, "post_win": extra, "round": [x[7] for x in recs]})
    return (table if teams is not None else table[table.games > 0]), detail


def rank_with_h2h(table, games, x=H2H_WINDOW):
    """Order by rating. Then, top-down: if the team directly below is within x points and won the
    head-to-head (and never lost to the team above), the two swap."""
    order = list(table.sort_values("rating", ascending=False).index)
    won = {}
    for r in games.itertuples():
        w, l = (r.home, r.away) if r.margin_home > 0 else (r.away, r.home)
        won[(w, l)] = won.get((w, l), 0) + 1
    swaps = []
    i = 0
    while i < len(order) - 1:
        a, c = order[i], order[i + 1]
        if table.rating[a] - table.rating[c] < x and won.get((c, a), 0) > 0 and won.get((a, c), 0) == 0:
            order[i], order[i + 1] = c, a
            swaps.append((c, a)); i += 2
        else:
            i += 1
    return order, swaps
