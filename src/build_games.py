"""TrueCFB: merge CFBD-derived schedules (base) with ESPN schedules (overtime flag, poll rank at game time,
missing postseason games, and finals the base file does not have yet) into one clean games table.
Usage: build_games.py <schedules_dir> <espn_dir> <out_csv> <latest_poll_json>

Sources (GitHub raw):
  sportsdataverse/cfbfastR-data      schedules/csv/cfb_schedules_{year}.csv
  sportsdataverse/cfbfastR-cfb-raw   cfb/schedules/parquet/cfb_schedule_{year}.parquet
"""
import sys, os, json
import pandas as pd

sched_dir, espn_dir, out, poll_out = sys.argv[1:5]
FIRST, LAST = 2013, 2026


def rk(x):
    try:
        x = int(x)
    except (TypeError, ValueError):
        return None
    return x if 0 < x <= 25 else None


rows = []
latest_poll = {}
for y in range(FIRST, LAST + 1):
    call = pd.read_csv(os.path.join(sched_dir, f"cfb_schedules_{y}.csv"), low_memory=False)
    id_name = dict(zip(call.home_id, call.home_team)); id_name.update(dict(zip(call.away_id, call.away_team)))
    e = pd.read_parquet(os.path.join(espn_dir, f"cfb_schedule_{y}.parquet"))
    e["gid"] = e.game_id.astype("int64")
    # The base file can lag by a day on game day. Where ESPN already has a final for a game the base
    # still lists as unplayed, take the final score from ESPN.
    fin = {r.gid: (int(r.home_id), int(r.home_score), int(r.away_score))
           for r in e[e.status_type_completed == True].itertuples()}
    late = call.index[(call.completed != True) & call.game_id.isin(list(fin))]
    for i in late:
        hid, hs, as_ = fin[int(call.at[i, "game_id"])]
        if hid != int(call.at[i, "home_id"]):
            hs, as_ = as_, hs
        call.at[i, "home_points"], call.at[i, "away_points"], call.at[i, "completed"] = hs, as_, True
    filled = len(late)
    if y == LAST:   # how complete each week of the current season is
        rg = call[(call.season_type == "regular") & ((call.home_division == "fbs") | (call.away_division == "fbs"))]
        start = pd.to_datetime(rg.start_date, utc=True, errors="coerce")
        # "open" = not final yet, and kicking off in the future or within the last 36 hours.
        # A game that never got a final (cancelled) stops counting as open after that.
        still_open = (rg.completed != True) & (start > pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=36))
        week_status = {int(w): {"games": int((rg.week == w).sum()),
                                "final": int(((rg.completed == True) & (rg.week == w)).sum()),
                                "open": int((still_open & (rg.week == w)).sum())} for w in sorted(rg.week.unique())}
    c = call[(call.completed == True) & call.home_points.notna() & call.away_points.notna()]
    c = c[(c.home_division == "fbs") | (c.away_division == "fbs")].copy()
    base = pd.DataFrame({
        "game_id": c.game_id.astype("int64"), "season": y, "week": c.week, "season_type": c.season_type,
        "date": c.start_date.str[:10], "neutral": c.neutral_site.astype(bool),
        # the US game day: a late Saturday kickoff is already Sunday in UTC
        "day": (pd.to_datetime(c.start_date, utc=True) - pd.Timedelta(hours=8)).dt.strftime("%Y-%m-%d"),
        "home_id": c.home_id.astype("int64"), "home": c.home_team, "home_fbs": c.home_division == "fbs",
        "home_conf": c.home_conference,
        "away_id": c.away_id.astype("int64"), "away": c.away_team, "away_fbs": c.away_division == "fbs",
        "away_conf": c.away_conference,
        "home_pts": c.home_points.astype(int), "away_pts": c.away_points.astype(int), "note": c.notes, "src": "cfbd",
        "conf_game": c.conference_game.astype(bool)})
    rank_at = {}
    for r in e.itertuples():
        rank_at[(r.gid, int(r.home_id))] = rk(r.home_current_rank)
        rank_at[(r.gid, int(r.away_id))] = rk(r.away_current_rank)
    if y == LAST:   # ranks shown on this week's and next week's games = the latest poll
        done_weeks = e[(e.season_type == 2) & (e.status_type_completed == True)].week
        cur = int(done_weeks.max())
        for r in e[(e.season_type == 2) & (e.week >= cur)].itertuples():
            for tid, v in ((int(r.home_id), rk(r.home_current_rank)), (int(r.away_id), rk(r.away_current_rank))):
                if v and tid in id_name:
                    latest_poll[id_name[tid]] = v
        latest_poll = {"season": y, "espn_week": cur, "ranks": latest_poll, "weeks": week_status}
    ec = e[e.status_type_completed == True].copy()
    ec["ot"] = ec.status_period.astype(float) > 4
    base = base.merge(ec[["gid", "ot"]].drop_duplicates("gid"), left_on="game_id", right_on="gid", how="left").drop(columns="gid")
    base["home_rank"] = [rank_at.get((g, t)) for g, t in zip(base.game_id, base.home_id)]
    base["away_rank"] = [rank_at.get((g, t)) for g, t in zip(base.game_id, base.away_id)]
    matched = base.ot.notna().mean()
    # postseason games ESPN has that the base lacks (bowls / playoff), excluding all-star games
    ep = ec[(ec.season_type == 3) & (~ec.gid.isin(base.game_id)) & (ec.type_abbreviation != "ALLSTAR")]
    fbs_ids = set(base.home_id[base.home_fbs]) | set(base.away_id[base.away_fbs])
    names = dict(zip(base.home_id, base.home)); names.update(dict(zip(base.away_id, base.away)))
    add = []
    for r in ep.itertuples():
        h, a = int(r.home_id), int(r.away_id)
        if h not in fbs_ids or a not in fbs_ids:
            continue
        add.append({"game_id": r.gid, "season": y, "week": 99, "season_type": "postseason", "date": str(r.date)[:10],
                    "day": (pd.to_datetime(r.date, utc=True) - pd.Timedelta(hours=8)).strftime("%Y-%m-%d"),
                    "neutral": bool(r.neutral_site), "home_id": h, "home": names[h], "home_fbs": True, "home_conf": None,
                    "away_id": a, "away": names[a], "away_fbs": True, "away_conf": None, "home_pts": int(r.home_score),
                    "away_pts": int(r.away_score), "note": r.notes_headline, "src": "espn", "ot": bool(r.ot),
                    "conf_game": False, "home_rank": rk(r.home_current_rank), "away_rank": rk(r.away_current_rank)})
    full = pd.concat([base, pd.DataFrame(add)], ignore_index=True) if add else base
    print(y, "games", len(full), "| finals taken from ESPN", filled, "| ot flag known %.0f%%" % (100 * matched), "| postseason", int((full.season_type == "postseason").sum()),
          "| games with a ranked team", int((full.home_rank.notna() | full.away_rank.notna()).sum()))
    rows.append(full)
g = pd.concat(rows, ignore_index=True)
g["ot_known"] = g.ot.notna()
g["ot"] = g.ot.fillna(False).astype(bool)
g = g.sort_values(["season", "date", "game_id"]).reset_index(drop=True)
g.to_csv(out, index=False)
json.dump(latest_poll, open(poll_out, "w"))
print("total", len(g), "| latest poll teams", len(latest_poll["ranks"]), "espn week", latest_poll["espn_week"])
