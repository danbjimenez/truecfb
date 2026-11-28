"""TrueCFB reply bot: the lookups the model can make, and which numbers a reply may use.

  primer(readme_path) -> the README's rules, word for word (the system prompt's knowledge of the rules)
  LOOKUPS, run(book, name, args) -> the tools the model calls and their text answers
  parts(book, line) -> one schedule line's Game Rating split into the rule's parts
  allowed(*texts), unsupported(reply, ...) -> the number check

Every number a lookup returns comes from files the engine wrote (reply_book.Book).
Nothing here computes a rating.
The parts of a Game Rating are split the same way the site's How it works page does it (site/js/how.js),
from the engine's published settings and margin curve; they are display only, and the published Game
Rating is always the number that counts. Gaps and changes are plain subtractions of published numbers,
shown so the model never has to do arithmetic.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reply_book import Unanswerable, UNRELIABLE, INDEPENDENTS, MONTHS, VERSION, r1, date  # noqa: E402

# The README sections the model learns the rules from, in order. Read at run time, so the model always
# knows the version the engine runs, never an older copy.
PRIMER_FROM = "## The rules"
PRIMER_UNTIL = "## Version policy"
MINUS = "−"
NEIGHBORS = 2          # teams listed above and below each team in focus
MAX_LIST = 25         # most rows one lookup returns


def signed(x):
    """One decimal with a real minus sign: +2.4, −25.0, 0.0."""
    v = round(x, 1)
    if v > 0:
        return f"+{v:.1f}"
    if v < 0:
        return f"{MINUS}{-v:.1f}"
    return "0.0"


def primer(readme_path):
    text = open(readme_path, encoding="utf-8").read()
    start, end = text.find(PRIMER_FROM), text.find(PRIMER_UNTIL)
    if start < 0 or end < start:
        raise RuntimeError(f"README sections {PRIMER_FROM!r} .. {PRIMER_UNTIL!r} not found")
    return text[start:end].strip()


# ---------- one game, split into the rule's parts ----------

def parts(book, g):
    """g: one line of a team's schedule (see Book.games). Returns the parts of its Game Rating."""
    S, F = book.data["settings"], book.data["F"]
    pf, pa, ot = g[3], g[4], bool(g[5])
    won = pf > pa
    margin = abs(pf - pa)          # overtime games count by their final score (since 2026.2)
    w = S["win"][0] + (S["win"][1] - S["win"][0]) * F[min(margin, len(F) - 1)]
    result = w if won else 100.0 - w
    venue = {"H": -S["venue"], "A": S["venue"]}.get(g[2], 0.0)
    bonus = S["b"] * (g[7] - 50.0)
    before_limit = result + venue + bonus
    post = g[9] + (g[10] if won else 0.0)
    return {"won": won, "margin": margin, "ot": ot, "result": result, "venue": venue, "bonus": bonus,
            "before_limit": before_limit, "limited": before_limit > 100 or before_limit < 0,
            "post_both": g[9], "post_win": g[10] if won else 0.0, "post": post,
            "game_rating": g[6], "fcs": bool(g[8])}


def game_line(book, team, g, y):
    p = parts(book, g)
    opp = g[1]
    ranks = book.data["ratings"][str(y)]
    if p["fcs"]:
        who = f"{opp} (FCS, rated {r1(book.data['settings']['fcs'])})"
    else:
        rank = ranks.get(opp, [None, None])[1]
        # The opponent's rank and rating now: the rating is what its strength uses, the rank is not where it
        # stood on the day of the game, so it is labeled "now".
        who = f"{opp} (now #{rank}, {r1(g[7])})" if rank else f"{opp} ({r1(g[7])})"
    where = {"H": "vs", "A": "at"}.get(g[2], "vs")
    site = "" if g[2] in ("H", "A") else ", neutral site"
    res = "won" if p["won"] else "lost"
    ot = " in OT" if p["ot"] else ""
    venue = {"H": f"home {signed(p['venue'])}", "A": f"road {signed(p['venue'])}"}.get(g[2], "neutral 0.0")
    kind = "win" if p["won"] else "loss"
    split = (f"{r1(p['result'])} for a {p['margin']}-point {kind}, {opp}'s strength {signed(p['bonus'])}, "
             f"{venue}")
    if p["limited"]:
        split += f", kept between 0 and 100 ({r1(p['before_limit'])} before the limit)"
    if p["post"]:
        extra = f"postseason +{r1(p['post_both'])}" + (f" +{r1(p['post_win'])} for the win" if p["post_win"] else "")
        split += f", {extra}"
    after = f" · Team Rating after {r1(g[11])} (#{g[12]})" if g[11] is not None else ""
    return (f"- {date(g[0])} {where} {who}{site}: {res} {max(g[3], g[4])}-{min(g[3], g[4])}{ot} · "
            f"Game Rating {r1(g[6])} = {split}{after}")


# ---------- the sheet ----------

def team_block(book, t, y):
    info = book.team(t, y)
    conf = book.data["team_conf"].get(str(y), {}).get(t)
    gs = book.games(t, y)
    lines = [f"{t}: #{info['rank']} · Team Rating {r1(info['rating'])} · {info['wins']}-{info['losses']}"
             + (f" · {conf}" if conf else "")
             + f" · strength {signed(info['rating'] - 50)} (what {t} adds to an opponent's Game Rating)"]
    carry = book.data["settings"]["carry"]
    start = load_start(book, y).get(t)
    if len(gs) < carry:
        if start:
            lines.append(f"{t} has played {len(gs)} games: its {y - 1} final Team Rating, {r1(start[0])}, "
                         f"still fills {carry - len(gs)} of the {carry} placeholder games.")
        else:
            lines.append(f"{t} is new to FBS: it started at {r1(book.data['settings']['fcs'])}, "
                         f"which still fills {carry - len(gs)} of the {carry} placeholder games.")
    elif start:
        lines.append(f"{t} started {y} at its {y - 1} final Team Rating, {r1(start[0])} (#{start[1]}); "
                     f"after {carry} games only this season's games count.")
    if gs:
        lines.append(f"{t}'s games, oldest first:")
        lines += [game_line(book, t, g, y) for g in gs]
        rated = sorted(gs, key=lambda g: g[6])
        best, worst = rated[-1], rated[0]
        lines.append(f"{t}'s highest Game Rating: {r1(best[6])} ({'won' if best[3] > best[4] else 'lost'} "
                     f"{'vs' if best[2] != 'A' else 'at'} {best[1]}); lowest: {r1(worst[6])} "
                     f"({'won' if worst[3] > worst[4] else 'lost'} {'vs' if worst[2] != 'A' else 'at'} {worst[1]})")
        if len(gs) > 1 and gs[-2][11] is not None and gs[-1][11] is not None:
            lines.append(f"{t}'s Team Rating moved {signed(gs[-1][11] - gs[-2][11])} with its latest game "
                         f"({r1(gs[-2][11])} to {r1(gs[-1][11])}).")
    return lines


def load_start(book, y):
    if not hasattr(book, "_start"):
        book._start = {}
    if y not in book._start:
        import json
        path = os.path.join(book.site_dir, f"sched_{y}.json")
        book._start[y] = json.load(open(path)).get("start", {}) if os.path.exists(path) else {}
    return book._start[y]


def neighbors(book, t, y):
    r = book.data["ratings"][str(y)]
    order = sorted(r, key=lambda x: r[x][1])
    i = order.index(t)
    near = order[max(0, i - NEIGHBORS): i + NEIGHBORS + 1]
    return f"Ranked around {t}: " + " · ".join(f"#{r[x][1]} {x} {r1(r[x][0])}" for x in near)


def conf_records(book, c, y):
    """Each member's record in games against other members (published results), best first. Games
    after November are left out: they are title games, which do not count in the standings."""
    tc = book.data["team_conf"].get(str(y), {})
    r = book.data["ratings"][str(y)]
    out = []
    for t in (t for t, k in tc.items() if k == c and t in r):
        gs = [g for g in book.games(t, y) if tc.get(g[1]) == c and int(g[0].split("-")[0]) not in (12, 1)]
        w = sum(g[3] > g[4] for g in gs)
        out.append((t, w, len(gs) - w))
    return sorted(out, key=lambda x: (-x[1], x[2], r[x[0]][1]))


def when(g):
    """An upcoming game's kickoff in US Eastern time: "Thu Nov 26, 8:00 PM ET" (the date only if TBD)."""
    from zoneinfo import ZoneInfo
    t = g["when"].astimezone(ZoneInfo("America/New_York"))
    day = f"{t.strftime('%a')} {MONTHS[t.month - 1]} {t.day}"
    return day if g["tbd"] else f"{day}, {t.strftime('%I:%M %p').lstrip('0')} ET"


def who_now(book, t, y):
    r = book.data["ratings"][str(y)].get(t)
    return f"{t} (now #{r[1]}, {r1(r[0])})" if r else f"{t} (FCS)"


def upcoming_line(book, g, y):
    sep = " vs " if g["neutral"] else " at "
    what = g["note"] or ("conference game" if g["conference_game"] else "")
    return (f"- {when(g)}: {who_now(book, g['away'], y)}{sep}{who_now(book, g['home'], y)}"
            + (", neutral site" if g["neutral"] else "") + (f" · {what}" if what else ""))


def next_games(book, t):
    ups = book.upcoming()
    return None if ups is None else [g for g in ups if t in (g["home"], g["away"])]


def conf_block(book, c, y):
    info = book.conf(c, y)
    r = book.data["ratings"][str(y)]
    members = sorted((t for t, k in book.data["team_conf"].get(str(y), {}).items() if k == c and t in r),
                     key=lambda t: r[t][1])
    return [f"{c}: Conference Rating {r1(info['rating'])} · #{info['rank']} of {info['of']} conferences "
            f"(the plain average of its {len(members)} members' Team Ratings)",
            f"{c} members: " + " · ".join(f"{t} #{r[t][1]} {r1(r[t][0])}" for t in members),
            f"{c} records in games between members (title game not counted): "
            + " · ".join(f"{t} {w}-{l}" for t, w, l in conf_records(book, c, y))]


def game_impact_block(book, a, b, y):
    m = book.meeting(a, b, y)
    if not m:
        return [f"{a} and {b} have not played each other in {y}."]
    imp = book.impact(a, b, y, m[0][0])
    if not imp:
        return []
    lines = [f"What the {a}-{b} game did: Matchup Rating {imp['matchup_rating']} (the pot the two teams split)"]
    for s in imp["teams"]:
        if s["fbs"]:
            lines.append(f"{s['team']}: Game Rating {r1(s['game_rating'])} · Team Rating {r1(s['rating_before'])} "
                         f"to {r1(s['rating_after'])} ({signed(s['change'])}) · #{s['rank_before']} to #{s['rank_after']}")
    rip = imp.get("ripple") or {}
    moved = (rip.get("past_opponents_gained") or [])[:2] + (rip.get("past_opponents_lost") or [])[:2]
    if moved:
        lines.append("Ripple to past opponents: " + " · ".join(f"{x['team']} {signed(x['change'])}" for x in moved))
    return lines


# ---------- the lookups ----------

def header(book, y):
    lines = [f"TrueCFB {VERSION}, {y} season, numbers {book.when(y)}."]
    if y in UNRELIABLE:
        lines.append("2020 is flagged unreliable: most conferences played only themselves, so nothing ties "
                     "one conference's level to another's. Say so if you use 2020 numbers.")
    return lines


def team_name(book, name, y):
    """The engine's spelling of a team, or Unanswerable with the closest names."""
    names = book.teams(y)
    if name in names:
        return name
    low = {n.lower(): n for n in names}
    if str(name).lower() in low:
        return low[str(name).lower()]
    import difflib
    near = difflib.get_close_matches(str(name), names, n=4, cutoff=0.5)
    raise Unanswerable(f"{name!r} is not an FBS team TrueCFB rated in {y}"
                       + (f"; closest names: {', '.join(near)}" if near else ""))


def conf_name(book, name, y):
    names = book.conferences(y)
    low = {n.lower(): n for n in names}
    if str(name).lower() in low:
        return low[str(name).lower()]
    raise Unanswerable(f"no Conference Rating for {name!r} in {y}; conferences: {', '.join(names)}")


def look_rankings(book, season=None, start=1, count=10):
    y = book.season(season)
    r = book.data["ratings"][str(y)]
    order = sorted(r, key=lambda t: r[t][1])
    start, count = max(1, int(start or 1)), max(1, min(int(count or 10), MAX_LIST))
    rows = order[start - 1: start - 1 + count]
    if not rows:
        raise Unanswerable(f"{y} has {len(order)} ranked teams")
    return header(book, y) + [f"Ranking #{start} to #{start + len(rows) - 1} of {len(order)}:"] + [
        f"#{r[t][1]} {t} · Team Rating {r1(r[t][0])} · {r[t][2]}-{r[t][3]} · "
        f"{book.data['team_conf'].get(str(y), {}).get(t, '')}" for t in rows]


def look_team(book, team, season=None):
    y = book.season(season)
    t = team_name(book, team, y)
    lines = header(book, y) + team_block(book, t, y) + [neighbors(book, t, y)]
    c = book.data["team_conf"].get(str(y), {}).get(t)
    if c and c != INDEPENDENTS:
        rec = next(((w, l) for x, w, l in conf_records(book, c, y) if x == t), None)
        if rec:
            lines.append(f"{t}'s {c} record (games between members): {rec[0]}-{rec[1]}")
    if y == book.current:
        ups = next_games(book, t)
        if ups:
            lines.append(f"{t} still to play:")
            lines += [upcoming_line(book, g, y) for g in ups]
        elif ups is not None:
            lines.append(f"{t} has no games left on the schedule file.")
    return lines


def look_matchup(book, team_a, team_b, season=None):
    y = book.season(season)
    a, b = team_name(book, team_a, y), team_name(book, team_b, y)
    if a == b:
        raise Unanswerable("two different teams are needed")
    ta, tb = book.team(a, y), book.team(b, y)
    hi, lo = sorted([ta, tb], key=lambda t: t["rank"])
    lines = header(book, y) + [f"{t['team']}: #{t['rank']} · Team Rating {r1(t['rating'])} · {t['wins']}-{t['losses']}"
                               for t in (hi, lo)]
    lines.append(f"Gap: {hi['team']} (#{hi['rank']}) {r1(hi['rating'] - lo['rating'])} above "
                 f"{lo['team']} (#{lo['rank']}) in Team Rating.")
    m = book.meeting(a, b, y)
    if m:
        lines.append(f"Their game in {y}:")
        lines += [game_line(book, name, g, y).replace("- ", f"- {name}: ", 1) for name, g in zip((a, b), m) if g]
    lines += game_impact_block(book, a, b, y)
    return lines


def look_conference(book, conference=None, season=None):
    y = book.season(season)
    if conference:
        return header(book, y) + conf_block(book, conf_name(book, conference, y), y)
    rows = sorted((book.conf(c, y) for c in book.conferences(y)), key=lambda c: c["rank"])
    return header(book, y) + ["Conference Ratings (each the plain average of its members' Team Ratings):"] + [
        f"#{c['rank']} {c['conf']} {r1(c['rating'])}" for c in rows]


SNAP_LABEL = {"reg": "at the end of the regular season", "final": "final, after the postseason"}


def snap_label(key):
    return SNAP_LABEL.get(key, f"going into week {key[1:]}" if key[1:].isdigit() else key)


def look_polls(book, poll="cfp", season=None, week=None):
    y = book.season(season)
    poll = str(poll or "cfp").lower()
    if poll not in ("cfp", "ap"):
        raise Unanswerable("poll must be cfp or ap")
    col, name = (5, "CFP ranking") if poll == "cfp" else (6, "AP poll")
    snaps = book.snaps(y)
    keys = [k for k, rows in snaps.items() if any(row[col] for row in rows)]
    if week:
        keys = [k for k in keys if k == f"w{int(week)}"]
    if not keys:
        raise Unanswerable(f"no {name} on file for {y}" + (f" week {week}" if week else ""))
    key = keys[-1]
    rows = snaps[key]
    polled = sorted((row for row in rows if row[col]), key=lambda row: (row[col], row[0]))
    lines = header(book, y) + [f"The {name} {snap_label(key)}, with TrueCFB's ranking at the same point "
                               f"(Team Rating and record):"]
    for row in polled:
        gap = row[0] - row[col]
        say = ("same spot" if gap == 0 else
               f"{abs(gap)} spot{'s' if abs(gap) > 1 else ''} {'lower' if gap > 0 else 'higher'} in TrueCFB")
        lines.append(f"{name.split()[0]} #{row[col]} {row[1]} · TrueCFB #{row[0]} · {r1(row[2])} · "
                     f"{row[3]}-{row[4]} · {say}")
    left_out = [row for row in rows if not row[col] and row[0] <= 25]
    if left_out:
        lines.append(f"In TrueCFB's top 25 but not in the {name}: " + " · ".join(
            f"TrueCFB #{row[0]} {row[1]} {r1(row[2])} ({row[3]}-{row[4]})" for row in left_out))
    far = sorted(polled, key=lambda row: -abs(row[0] - row[col]))[:5]
    lines.append(f"Biggest differences from the {name}: " + " · ".join(
        f"{row[1]} ({name.split()[0]} #{row[col]}, TrueCFB #{row[0]})" for row in far))
    return lines


def look_games(book, season=None, order="highest", result="any", count=10):
    """Every FBS team's games in a season, sorted by Game Rating."""
    y = book.season(season)
    result, count = str(result or "any").lower(), max(1, min(int(count or 10), MAX_LIST))
    rows = []
    for t, gs in book.sched(y).items():
        for g in gs:
            won = g[3] > g[4]
            if (result == "win" and not won) or (result == "loss" and won):
                continue
            rows.append((g[6], t, g))
    rows.sort(key=lambda x: x[0], reverse=str(order).lower() != "lowest")
    what = {"win": "wins", "loss": "losses"}.get(result, "games")
    lines = header(book, y) + [f"The {count} {'lowest' if str(order).lower() == 'lowest' else 'highest'} "
                               f"Game Ratings in {what}, {y} (each team's side of a game):"]
    lines += [game_line(book, t, g, y).replace("- ", f"- {t} ", 1) for _, t, g in rows[:count]]
    return lines


def look_upcoming(book, team=None, count=12):
    """Games not yet played: one team's, or the next week's biggest by TrueCFB rank."""
    y = book.current
    ups = book.upcoming()
    if ups is None:
        raise Unanswerable("the schedule of games not yet played is not available right now")
    count = max(1, min(int(count or 12), MAX_LIST))
    if team:
        t = team_name(book, team, y)
        mine = [g for g in ups if t in (g["home"], g["away"])]
        if not mine:
            return header(book, y) + [f"{t} has no games left on the schedule file."]
        return header(book, y) + [f"{t}'s games still to play:"] + [upcoming_line(book, g, y) for g in mine]
    soon = [g for g in ups if (g["when"] - ups[0]["when"]).days < 8]
    r = book.data["ratings"][str(y)]
    best = lambda g: min(r.get(g["home"], [0, 999])[1], r.get(g["away"], [0, 999])[1])
    soon.sort(key=best)
    return header(book, y) + [f"The next week's games, the {min(count, len(soon))} with the highest-ranked teams first:"] + [
        upcoming_line(book, g, y) for g in soon[:count]]


def look_what_if(book, team, opponent=None, site=None):
    """What a win or loss in one game would do, by re-running the engine with that game added."""
    import reply_whatif as WI
    y = book.current
    t = team_name(book, team, y)
    game = None
    ups = next_games(book, t) or []
    if opponent:
        try:
            o = team_name(book, opponent, y)
        except Unanswerable:
            o = str(opponent)          # an FCS opponent: it counts as a 25, like any FCS team
        game = next((g for g in ups if o in (g["home"], g["away"])), None)
    elif ups:
        game = ups[0]
        o = game["away"] if game["home"] == t else game["home"]
    else:
        raise Unanswerable(f"{t} has no game left on the schedule file; give an opponent")
    if game and not site:
        site = "neutral" if game["neutral"] else ("home" if game["home"] == t else "away")
    site = site if site in ("home", "away", "neutral") else "neutral"
    if not hasattr(book, "_whatif"):
        try:
            book._whatif = WI.WhatIf(book.site_dir, book.data["ratings"][str(y)])
        except WI.OutOfDate as why:
            book._whatif = str(why)
    if isinstance(book._whatif, str):
        raise Unanswerable(book._whatif)
    w = book._whatif
    if w.season != y:
        raise Unanswerable("what-if data is for another season")
    pub = book.data["ratings"][str(y)]
    where = {"home": f"at home against {o}", "away": f"at {o}", "neutral": f"against {o} at a neutral site"}[site]
    lines = header(book, y) + [
        f"What-if: {t} {where}" + (f" ({when(game)}" + (f", {game['note']}" if game and game["note"] else "") + ")" if game else "")
        + ". The engine re-run on this season with this one game added and nothing else changed "
          "(other games still to be played will move the numbers too).",
        "Now: " + " · ".join(f"{x} #{pub[x][1]}, Team Rating {r1(pub[x][0])}" for x in (t, o) if x in pub)]
    met = None if game else book.meeting(t, o, y)
    if met:
        g = met[0]
        lines.append(f"{t} and {o} already played on {MONTHS[int(g[0][:2]) - 1]} {int(g[0][3:])}: {t} "
                     f"{'won' if g[3] > g[4] else 'lost'} {g[3]}-{g[4]}, and that result is in the numbers above. "
                     "This what-if adds a second game between them; say so, or answer about the game played.")
    base = w.base_rank
    for sc in w.scenarios(t, o, site):
        m, table, rank = sc["margin"], sc["table"], sc["rank"]
        winner = t if m > 0 else o
        parts = []
        for x in (t, o):
            if x not in pub:
                continue
            new = round(float(table.rating[x]), 1)
            move = (f"#{base[x]} to #{rank[x]}" if rank[x] != base[x] else f"stays #{rank[x]}")
            parts.append(f"{x} {r1(new)} ({signed(new - pub[x][0])}), {move}")
        passed = [x for x in base if base[x] < base[t] and rank[x] > rank[t]]
        behind = [x for x in base if base[x] > base[t] and rank[x] < rank[t]]
        extra = ""
        if passed:
            extra += f" · {t} moves past " + ", ".join(sorted(passed, key=base.get)[:4])
        if behind:
            extra += f" · {t} falls behind " + ", ".join(sorted(behind, key=base.get)[:4])
        lines.append(f"If {winner} wins by {abs(m)}: " + " · ".join(parts) + extra)
    return lines


SEASON = {"type": "integer", "description": "A season from 2014 on. Leave it out for the current season."}
LOOKUPS = [
    {"name": "rankings", "fn": look_rankings,
     "description": "TrueCFB's ranking: rank, Team Rating, record and conference for a slice of teams.",
     "parameters": {"type": "object", "properties": {
         "season": SEASON,
         "start": {"type": "integer", "description": "First rank to list (default 1)."},
         "count": {"type": "integer", "description": f"How many teams (default 10, at most {MAX_LIST})."}}}},
    {"name": "team", "fn": look_team,
     "description": "One team's season: rank, Team Rating, record, conference, its strength, where it started, "
                    "every game with its Game Rating split into the rule's parts and the Team Rating after it, "
                    "its highest and lowest Game Rating, and the teams ranked around it.",
     "parameters": {"type": "object", "properties": {
         "team": {"type": "string", "description": "The team's name exactly as in the team list."},
         "season": SEASON}, "required": ["team"]}},
    {"name": "matchup", "fn": look_matchup,
     "description": "Two teams side by side: ranks, Team Ratings, the gap, and their game that season if they "
                    "played (each side's Game Rating, and what the game did to the ranking when it was recent).",
     "parameters": {"type": "object", "properties": {
         "team_a": {"type": "string"}, "team_b": {"type": "string"}, "season": SEASON},
         "required": ["team_a", "team_b"]}},
    {"name": "conference", "fn": look_conference,
     "description": "One conference's Conference Rating, rank and members in order; or, with no conference "
                    "given, every conference's Conference Rating in order.",
     "parameters": {"type": "object", "properties": {
         "conference": {"type": "string", "description": "Leave it out for all conferences."},
         "season": SEASON}}},
    {"name": "polls", "fn": look_polls,
     "description": "The CFP ranking or AP poll beside TrueCFB's ranking at the same point of the season: each "
                    "poll team's TrueCFB rank and how far apart the two are, TrueCFB top-25 teams the poll left "
                    "out, and the biggest differences. The latest one on file unless a week is given.",
     "parameters": {"type": "object", "properties": {
         "poll": {"type": "string", "enum": ["cfp", "ap"]}, "season": SEASON,
         "week": {"type": "integer", "description": "Leave it out for the latest."}}}},
    {"name": "games", "fn": look_games,
     "description": "The highest or lowest Game Ratings of a season across all FBS teams, in wins, losses or "
                    "all games. For best wins, best losses, worst losses, the biggest results of the season.",
     "parameters": {"type": "object", "properties": {
         "season": SEASON, "order": {"type": "string", "enum": ["highest", "lowest"]},
         "result": {"type": "string", "enum": ["any", "win", "loss"]},
         "count": {"type": "integer", "description": f"Default 10, at most {MAX_LIST}."}}}},
]
LOOKUPS += [
    {"name": "upcoming", "fn": look_upcoming,
     "description": "Games not yet played this season, with kickoff times and each team's rank and Team Rating "
                    "now: one team's remaining games (including a conference title game once it is set), or, "
                    "with no team, the next week's games with the highest-ranked teams.",
     "parameters": {"type": "object", "properties": {
         "team": {"type": "string", "description": "Leave it out for the week's biggest games."},
         "count": {"type": "integer", "description": f"Default 12, at most {MAX_LIST}."}}}},
    {"name": "what_if", "fn": look_what_if,
     "description": "What one game not yet played would do: the engine re-run with that game added, for a "
                    "close and a two-score result each way. Gives both teams' new Team Rating, the change, the "
                    "new rank and who they pass or fall behind. With no opponent, it uses the team's next game.",
     "parameters": {"type": "object", "properties": {
         "team": {"type": "string"},
         "opponent": {"type": "string", "description": "Leave it out for the team's next game."},
         "site": {"type": "string", "enum": ["home", "away", "neutral"],
                  "description": "From the team's side. Leave it out to use the schedule."}},
         "required": ["team"]}},
]
BY_NAME = {x["name"]: x for x in LOOKUPS}


def run(book, name, args):
    """One lookup's answer as text. A lookup that finds nothing says why, so the model can try another."""
    if name not in BY_NAME:
        return f"No lookup named {name!r}."
    import inspect
    fn = BY_NAME[name]["fn"]
    known = inspect.signature(fn).parameters
    try:
        return "\n".join(fn(book, **{k: v for k, v in (args or {}).items() if k in known and v not in (None, "")}))
    except Unanswerable as why:
        return f"Nothing found: {why}"
    except (TypeError, ValueError) as err:
        return f"That lookup did not work ({err}). Check its fields."


# ---------- which numbers a reply may use ----------

NUMBER = re.compile(r"(?<![\w.])([+\-−]?)(\d+(?:\.\d+)?)")


def numbers(text):
    """The numbers in a text as (sign, digits): "−25.0" -> ("−", "25.0"), "28-20" -> ("", "28"), ("", "20").
    "2026.2" is the version, not a number."""
    text = text.replace(VERSION, " ")
    out = []
    for m in NUMBER.finditer(text):
        sign, digits = m.group(1), m.group(2)
        if sign == "-" and m.start() > 0 and text[m.start() - 1].isdigit():
            sign = ""
        out.append(("−" if sign in ("-", MINUS) else sign, digits))
    return out


def allowed(*texts):
    """Every number written in the given texts: the set of digits, and the set of signed forms."""
    plain, signed_forms = set(), set()
    for t in texts:
        for sign, digits in numbers(t):
            plain.add(digits)
            if sign:
                signed_forms.add(sign + digits)
    return plain, signed_forms


def unsupported(reply, plain, signed_forms):
    """Numbers in the reply that are not written on the sheet or in the rules (with their sign, if given)."""
    bad = []
    for sign, digits in numbers(reply):
        if digits not in plain or (sign and sign + digits not in signed_forms):
            bad.append(sign + digits)
    return bad
