"""TrueCFB: run every season 2014-2026 with the current engine version: weekly snapshots, regular-season final, season final,
conference tables, each team's schedule line, and each snapshot's full ranking beside the AP and CFP polls.
Usage: run_all.py <games.csv> <src_dir> <latest_poll.json> <out_dir> <cfp_final.json> [polls_dir]

Writes to <out_dir>:
  data.json        settings, the list of snapshots per season, final ratings, conferences, team colours
  rank_{year}.json every snapshot's full ranking: [rank, team, rating, wins, losses, CFP rank, AP rank]
  sched_{year}.json every team's rating at the start of the season and every game, with the Team Rating after it
  history.json     every team's and every conference's rating and rank at every snapshot of every season
  whatif.json      the newest season's engine inputs, unrounded, for the reply bot's what-if lookup
and then, from those files, the team pages, rankings.json, llms.txt and sitemap.xml (see build_pages.py)"""
import sys, json, os
import numpy as np, pandas as pd
sys.path.insert(0, sys.argv[2])
import engine as E

SELECTION = {2014: "2014-12-07", 2015: "2015-12-06", 2016: "2016-12-04", 2017: "2017-12-03", 2018: "2018-12-02",
             2019: "2019-12-08", 2020: "2020-12-20", 2021: "2021-12-05", 2022: "2022-12-04", 2023: "2023-12-03",
             2024: "2024-12-08", 2025: "2025-12-07", 2026: "2026-12-06"}
g = E.load_games(sys.argv[1]); latest = json.load(open(sys.argv[3])); out_dir = sys.argv[4]
CFP_FINAL = json.load(open(sys.argv[5]))   # final committee rankings (Wikipedia season ranking pages)
LAST = int(g.season.max())                 # the newest season in the games table
# A season's regular season is closed once its selection date is above and its final CFP ranking is in
# cfp_final.json. Until then it counts regular-season games only; after it, bowl and playoff games count
# too, and the season stays the current one until its title game is played.
closed = lambda y: y in SELECTION and str(y) in CFP_FINAL
POLLS_DIR = sys.argv[6] if len(sys.argv) > 6 else None
# Team colours for the Top 25 chart (saved by fetch_colors.py beside the CFP list). Display only.
COLORS_FILE = os.path.join(os.path.dirname(os.path.abspath(sys.argv[5])), "team_colors.json")
COLORS = json.load(open(COLORS_FILE)) if os.path.exists(COLORS_FILE) else {}


def load_polls(folder):
    """Weekly AP and CFP rankings saved by fetch_polls.py: {season: {"regular": {week: {"ap": {team: rank},
    "cfp": {team: rank}}}, "postseason": {...}}}. A season with no file is simply missing."""
    out = {}
    if not folder or not os.path.isdir(folder):
        return out
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".json"):
            continue
        raw = json.load(open(os.path.join(folder, name)))
        out[int(raw["season"])] = {kind: {int(w): {p: {team: int(rk) for rk, team in pairs} for p, pairs in polls.items()}
                                          for w, polls in raw.get(kind, {}).items()} for kind in ("regular", "postseason")}
    return out


POLLS = load_polls(POLLS_DIR)
print("poll files for seasons:", sorted(POLLS) or "none")
F = E.margin_curve(g); V = E.home_edge(g, F)
print("settings: win range", E.WIN_RANGE, "opp weight", E.OPP_WEIGHT, "venue %.2f" % V, "FCS", E.FCS_RATING,
      "| bowl", E.BOWL_BONUS, "playoff", E.PLAYOFF_BONUS, E.PLAYOFF_WIN_BONUS)


def poll_from(rows):
    p = {}
    for r in rows.itertuples():
        if pd.notna(r.home_rank): p[r.home] = int(r.home_rank)
        if pd.notna(r.away_rank): p[r.away] = int(r.away_rank)
    return p


def snapshot(sid, label, games, teams, prior, poll, poll_name, h2h, ap=None, cfp=None):
    """poll / poll_name: the one poll used for the printed report. ap / cfp: {team: rank} for the two
    columns on the site, or None when that poll was not published for this point in the season."""
    det = None
    if len(games) == 0:
        tab = pd.DataFrame({"rating": [prior.get(t, E.FCS_RATING) if prior is not None else 50.0 for t in teams],
                            "wins": 0, "losses": 0}, index=teams)
        order = list(tab.sort_values("rating", ascending=False).index); iters = 0
    else:
        tab, det = E.rate(games, F, V, prior=prior, teams=teams)
        iters = tab.attrs["iters"]
        order = E.rank_with_h2h(tab, games)[0] if h2h else list(tab.sort_values("rating", ascending=False).index)
    rank = {t: i + 1 for i, t in enumerate(order)}
    seen = {t: p for t, p in poll.items() if t in rank}
    gap = float(np.mean([abs(rank[t] - p) for t, p in seen.items()])) if seen else None
    row = lambda t: [rank[t], t, round(float(tab.rating[t]), 1), int(tab.wins[t]), int(tab.losses[t]), seen.get(t)]
    full = [[rank[t], t, round(float(tab.rating[t]), 1), int(tab.wins[t]), int(tab.losses[t]),
             (cfp or {}).get(t), (ap or {}).get(t)] for t in order]
    for name, p in (("CFP", cfp), ("AP", ap)):
        lost = sorted(t for t in (p or {}) if t not in rank)
        if lost: print(f"  note: {name} teams not matched to an FBS team in {sid}: {lost}")
    return {"id": sid, "label": label, "poll": poll_name, "gap": None if gap is None else round(gap, 1), "n": len(seen),
            "cfp": cfp is not None, "ap": ap is not None, "all": full,
            "rows": [row(t) for t in order[:25]],
            "others": sorted([row(t) for t in seen if rank[t] > 25], key=lambda x: x[5])}, tab, rank, iters, det


def team_conf(s):
    conf = dict(zip(s.home[s.home_fbs & s.home_conf.notna()], s.home_conf[s.home_fbs & s.home_conf.notna()]))
    conf.update(dict(zip(s.away[s.away_fbs & s.away_conf.notna()], s.away_conf[s.away_fbs & s.away_conf.notna()])))
    return conf


def conf_table(s, tab):
    conf = team_conf(s)
    out = []
    x = s[s.home_fbs & s.away_fbs]
    for c in sorted(set(conf.values())):
        teams = [t for t in tab.index if conf.get(t) == c]
        if not teams: continue
        ts = set(teams); nc = x[(x.home.isin(ts) ^ x.away.isin(ts))]
        w = int(((nc.home.isin(ts)) & (nc.margin_home > 0)).sum() + ((nc.away.isin(ts)) & (nc.margin_home < 0)).sum())
        out.append([c, len(teams), round(float(tab.rating[teams].mean()), 1), w, len(nc) - w])
    return sorted(out, key=lambda r: -r[2])


def note_after(after, games, tab, rank, sid):
    """Record each team's Team Rating and rank once these games are counted, and the snapshot (sid)
    that is the first to hold them."""
    for r in games.itertuples():
        for t, fbs in ((r.home, r.home_fbs), (r.away, r.away_fbs)):
            if fbs: after[(t, r.game_id)] = (round(float(tab.rating[t]), 1), int(rank[t]), sid)


INDEPENDENTS = "FBS Independents"   # listed with the conferences, but not ranked as one


def note_history(hist, y, conf, tab, rank):
    """Add one snapshot to the rating history: every team's Team Rating and rank, and every conference's
    Conference Rating (the plain average of its members' Team Ratings) and rank among conferences."""
    for t in tab.index:
        hist["teams"].setdefault(t, {}).setdefault(str(y), []).extend([round(float(tab.rating[t]), 1), int(rank[t])])
    avg = {}
    for c in sorted(set(conf.values())):
        members = [t for t in tab.index if conf.get(t) == c]
        if members: avg[c] = round(float(tab.rating[members].mean()), 1)
    order = sorted((c for c in avg if c != INDEPENDENTS), key=lambda c: -avg[c])
    for c, v in avg.items():
        hist["conf"].setdefault(c, {}).setdefault(str(y), []).extend([v, order.index(c) + 1 if c in order else None])


def schedule_lines(s, det, tab, after):
    """Per team: [date, opponent, site, points for, points against, overtime, Game Rating, opponent rating,
    FCS flag, postseason bonus for both teams, extra bonus the winner of that round gets,
    Team Rating after the game, rank after the game, the snapshot that first holds the game].
    "After" means once that week's games are counted in the regular season, or that day's in the postseason."""
    info = s.set_index("game_id")
    out = {}
    for r in det.itertuples():
        gi = info.loc[r.game_id]
        home = gi.home == r.team
        opp = gi.away if home else gi.home
        pf, pa = (gi.home_pts, gi.away_pts) if home else (gi.away_pts, gi.home_pts)
        site = "N" if gi.neutral else ("H" if home else "A")
        out.setdefault(r.team, []).append([gi.day[5:], opp, site, int(pf), int(pa), int(bool(gi.ot)),
                                           round(float(r.game_rating), 1), round(float(r.opp_rating), 1), int(r.opp == "FCS"),
                                           int(r.post_both), int(r.post_win)] + list(after.get((r.team, r.game_id), (None, None, None))))
    return out


data = {"name": E.NAME, "version": E.VERSION,
        "settings": {"win": E.WIN_RANGE, "b": E.OPP_WEIGHT, "fcs": E.FCS_RATING, "carry": E.CARRY, "venue": round(V, 2),
                     "post": {"bowl": E.BOWL_BONUS, "playoff": E.PLAYOFF_BONUS, "win": E.PLAYOFF_WIN_BONUS}},
        "F": [round(float(x), 4) for x in F[:61]], "seasons": {}, "history": {}, "conf": {}, "ratings": {}, "team_conf": {}}
t13, _ = E.rate(g[g.season == 2013], F, V); prior = t13.rating      # 2013 only seeds the 2014 carryover
weekly_gaps = {}; max_iters = 0; report = []; finals = []
history = {"teams": {}, "conf": {}}
for y in range(2014, LAST + 1):
    s = g[g.season == y]; reg = s[s.season_type == "regular"]
    teams = sorted(set(s.home[s.home_fbs]) | set(s.away[s.away_fbs]))
    weeks = sorted(int(w) for w in reg.week.unique())
    snaps = []; after = {}; start = {}
    conf_of = team_conf(s if closed(y) else reg)
    P = POLLS.get(y, {"regular": {}, "postseason": {}})
    for i, w in enumerate(weeks):
        poll = latest["ranks"] if (y == LAST and w == max(weeks)) else poll_from(reg[reg.week == w])
        label = "Preseason" if i == 0 else f"Through week {weeks[i - 1]}"
        pw = P["regular"].get(w, {})    # the polls published going into week w
        cfp_w = pw.get("cfp")
        # Where this is the committee's final ranking, use the checked list (the committee has no ties).
        if cfp_w and str(y) in CFP_FINAL and sorted(cfp_w, key=cfp_w.get) == CFP_FINAL[str(y)]:
            cfp_w = {t: k + 1 for k, t in enumerate(CFP_FINAL[str(y)])}
        sn, tab, rank, it, _ = snapshot(f"w{w}", label, reg[reg.week < w], teams, prior, poll, "Poll", False,
                                        ap=pw.get("ap"), cfp=cfp_w)
        max_iters = max(max_iters, it); snaps.append(sn); note_history(history, y, conf_of, tab, rank)
        if i == 0: start = {t: [round(float(tab.rating[t]), 1), int(rank[t])] for t in teams}   # the season's starting point
        else: note_after(after, reg[reg.week == weeks[i - 1]], tab, rank, sn["id"])   # this snapshot is the first to hold last week's games
        if sn["gap"] is not None and sn["n"] >= 10: weekly_gaps.setdefault(w, []).append(sn["gap"])
    if closed(y):
        rs = reg[reg.date <= SELECTION[y]]
        late = s[~s.game_id.isin(rs.game_id)]   # bowl and playoff games, and any regular-season game after selection day
        cfp = {t: i + 1 for i, t in enumerate(CFP_FINAL[str(y)])}
        # The polls of selection day are the last regular-season entry. The saved final CFP list is the
        # check: if the entry's CFP ranking is not that list (2020, where the last entry is a week
        # early), its AP poll is a week early too and is left out.
        last = P["regular"].get(max(P["regular"]), {}) if P["regular"] else {}
        on_time = sorted(last.get("cfp", {}), key=last.get("cfp", {}).get) == CFP_FINAL[str(y)]
        sn, tab, rank, it, _ = snapshot("reg", "Regular season final", rs, teams, prior, cfp, "CFP", True,
                                        ap=last.get("ap") if on_time else None, cfp=cfp); snaps.append(sn)
        report.append((y, sn, rank, cfp, tab)); note_history(history, y, conf_of, tab, rank)
        note_after(after, rs[rs.week == weeks[-1]], tab, rank, "reg")
        done = (late.season_type == "postseason").any() and any(
            E.playoff_round(n, y) == "final" for n in late.note[late.season_type == "postseason"])
        if done:   # the title game is in: the season is finished
            post = P["postseason"].get(min(P["postseason"]), {}) if P["postseason"] else {}   # the AP poll after the bowls
            sid, sn2, tabf, rankf, it, detf = ("final",) + snapshot("final", "Season final (after bowls and playoff)", s, teams,
                                                                     prior, {}, None, True, ap=post.get("ap"))
        else:      # bowls and playoff still being played: the season stays the current one
            sid, sn2, tabf, rankf, it, detf = ("post",) + snapshot("post", "Postseason so far", s, teams, prior, {}, None, True)
        if done or len(late):   # with no game after selection day yet, the regular-season final is the latest point
            snaps.append(sn2); note_history(history, y, conf_of, tabf, rankf)
        if done:
            fin = detf[detf["round"] == "final"]
            champ, runner = fin[fin.margin > 0].team.iloc[0], fin[fin.margin < 0].team.iloc[0]
            finals.append((y, champ, rankf[champ], runner, rankf[runner], [f"{r[1]} {r[2]}" for r in sn2["rows"][:5]], rank, rankf))
        else:
            now_label = "Through the postseason so far" if len(late) else "Through the regular season"
            data["current"] = {"season": str(y), "default": sid if len(late) else "reg", "week": None, "complete": True,
                               "through": s.day.max(), "now_through": s.day.max(), "now_label": now_label}
        prior_next = tabf.rating; cur = None
        # Bowl and playoff games (and any regular-season game after selection day): the Team Rating
        # after each one, from a ranking run through that day.
        days = sorted(late.day.unique())
        for d in days:
            if d == days[-1]:
                note_after(after, late[late.day == d], tabf, rankf, sid)
                continue
            td, _ = E.rate(pd.concat([rs, late[late.day <= d]]), F, V, prior=prior, teams=teams)
            rd = {t: k + 1 for k, t in enumerate(td.sort_values("rating", ascending=False).index)}
            note_after(after, late[late.day == d], td, rd, sid)
    else:
        # The current season. The page opens on the last fully completed week; if the newest week is
        # still being played, "now" holds every final so far and is labelled as in progress.
        cur_w = max(weeks)
        st = latest.get("weeks", {}).get(str(cur_w), {})
        complete = st.get("open", 0) == 0
        now_label = (f"Through week {cur_w}" if complete
                     else f"Week {cur_w} in progress ({st.get('final', 0)} of {st.get('games', 0)} games final)")
        # Polls that include this week's games are numbered as going into the next week. Until they are
        # published (the AP on Sunday, the CFP on Tuesday) the two columns stay empty.
        nxt = P["regular"].get(cur_w + 1, {}) if complete else {}
        sn2, tabf, rankf, it, detf = snapshot("now", now_label, reg, teams, prior, latest["ranks"], "CFP", False,
                                              ap=nxt.get("ap"), cfp=nxt.get("cfp"))
        snaps.append(sn2); cur = snaps[-2]; prior_next = prior
        note_history(history, y, conf_of, tabf, rankf)
        shown = reg if complete else reg[reg.week < cur_w]
        prev_w = weeks[weeks.index(cur_w) - 1] if weeks.index(cur_w) > 0 else None
        data["current"] = {"season": str(y), "default": "now" if complete else f"w{cur_w}",
                           "week": int(cur_w) if complete else (int(prev_w) if prev_w is not None else None),
                           "complete": bool(complete), "through": shown.day.max() if len(shown) else None,
                           "now_through": reg.day.max(), "now_label": now_label}
        note_after(after, reg[reg.week == cur_w], tabf, rankf, "now")
        s = reg
    for t in teams:
        data["history"].setdefault(t, {})[str(y)] = [round(float(tabf.rating[t]), 1), rankf[t]]
    data["ratings"][str(y)] = {t: [round(float(tabf.rating[t]), 1), rankf[t], int(tabf.wins[t]), int(tabf.losses[t])] for t in teams}
    data["conf"][str(y)] = conf_table(s, tabf)
    data["team_conf"][str(y)] = {t: c for t, c in sorted(team_conf(s).items()) if t in tabf.index}
    json.dump({"start": start, "games": schedule_lines(s, detf, tabf, after)}, open(f"{out_dir}/sched_{y}.json", "w"),
              separators=(",", ":"), ensure_ascii=False)
    json.dump({sn["id"]: sn["all"] for sn in snaps}, open(f"{out_dir}/rank_{y}.json", "w"), separators=(",", ":"), ensure_ascii=False)
    data["seasons"][str(y)] = snaps
    if y == LAST:
        # The newest season's engine inputs, unrounded, so the reply bot's what-if lookup (reply_whatif.py)
        # can re-run the engine with one made-up result added and start from exactly the published ranking.
        cols = ["season", "week", "home", "away", "home_fbs", "away_fbs", "margin_home", "neutral",
                "season_type", "note", "game_id"]
        rows = [[int(r.season), int(r.week), r.home, r.away, bool(r.home_fbs), bool(r.away_fbs), int(r.margin_home),
                 bool(r.neutral), r.season_type, None if pd.isna(r.note) else str(r.note), str(r.game_id)]
                for r in s[cols].itertuples(index=False)]
        json.dump({"season": y, "about": "Engine inputs for the newest season (display only; see src/reply_whatif.py)",
                   "venue": float(V), "F": [float(x) for x in F], "h2h": bool(closed(y)), "teams": teams,
                   "prior": {t: float(prior[t]) for t in prior.index}, "columns": cols, "games": rows},
                  open(f"{out_dir}/whatif.json", "w"), separators=(",", ":"), ensure_ascii=False)
    prior = prior_next
if "current" not in data:   # every season in the run is finished
    last_y = max(data["seasons"])
    data["current"] = {"season": last_y, "default": "final", "week": None, "complete": True, "through": None,
                       "now_through": None, "now_label": None}
data["colors"] = {t: COLORS[t] for t in sorted(data["history"]) if t in COLORS}
# data.json lists each season's snapshots; the rankings themselves are in rank_{year}.json.
full_seasons = data["seasons"]
data["seasons"] = {y: [{"id": sn["id"], "label": sn["label"], "cfp": sn["cfp"], "ap": sn["ap"]} for sn in snaps]
                   for y, snaps in full_seasons.items()}
json.dump(data, open(f"{out_dir}/data.json", "w"), separators=(",", ":"), ensure_ascii=False)
# history.json: per team and per conference, per season, a flat list [rating, rank, rating, rank, ...] with one
# pair for each of that season's snapshots, in the order data.json lists them.
json.dump(history, open(f"{out_dir}/history.json", "w"), separators=(",", ":"), ensure_ascii=False)
# The plain-HTML pages, rankings.json, llms.txt and sitemap.xml, written from the files above.
import build_pages
build_pages.build(out_dir)
data["seasons"] = full_seasons
print("max iterations in any snapshot:", max_iters)
print("\nREGULAR SEASON FINAL vs FINAL CFP RANKING")
allgap = []
for y, sn, rank, cfp, tab in report:
    top4 = [f"{r[1]} ({r[3]}-{r[4]}) {r[2]}" for r in sn["rows"][:4]]; cfp4 = [t for t, k in sorted(cfp.items(), key=lambda kv: kv[1])[:4]]
    allgap.append(sn["gap"])
    print(f"{y}: gap {sn['gap']}, {sum(1 for r in sn['rows'] if r[5])} of CFP 25 in ours | ours: {', '.join(top4)} | CFP: {', '.join(cfp4)} | same four: {set(r[1] for r in sn['rows'][:4]) == set(cfp4)}")
print("average gap over seasons: %.2f" % np.mean(allgap))
print("\nSEASON FINAL (after postseason)")
for y, champ, kc, runner, kr, top5, rank, rankf in finals:
    print(f"{y}: champion {champ} #{kc}, runner-up {runner} #{kr} | top 5: {', '.join(top5)}")
print("champion 1st:", sum(f[2] == 1 for f in finals), "of", len(finals), "| runner-up 2nd:", sum(f[4] == 2 for f in finals))
print("\nAVERAGE GAP TO THE POLL BY WEEK:", {w: round(float(np.mean(v)), 1) for w, v in sorted(weekly_gaps.items())})
print(f"\n{LAST} preseason top 8:", [f"{r[1]} {r[2]}" for r in data["seasons"][str(LAST)][0]["rows"][:8]])
if cur is not None:   # the newest season is still in its regular season
    print(f"{LAST} latest weekly snapshot vs latest CFP: gap", cur["gap"], "| in our 25:", sum(1 for r in cur["rows"] if r[5]))
    for r in cur["rows"][:10]: print(f"{r[0]:>2}. {r[1]} ({r[3]}-{r[4]}) {r[2]}  CFP {r[5] or 'NR'}")
print("rating range 2025 final:", min(v[0] for v in data["ratings"]["2025"].values()), max(v[0] for v in data["ratings"]["2025"].values()))
print("files:", {f: os.path.getsize(f"{out_dir}/{f}") for f in sorted(os.listdir(out_dir)) if f.endswith(".json")})
