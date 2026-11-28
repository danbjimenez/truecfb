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


PART_NAMES = (("result", "win/loss"), ("strength", "opponent strength"), ("margin", "margin"), ("venue", "venue"),
              ("limit", "the 0-100 limit"), ("post", "postseason points"), ("other", "last season's carryover"))


def breakdown(book, t, y):
    """A Team Rating split into its average parts, the same four (plus the limit and postseason points) that
    every Game Rating adds up: win/loss (70 a win, 30 a loss), opponent strength, margin, venue. "other" is
    what the season's own games do not cover (last season's carryover early on, and rounding)."""
    gs = book.games(t, y)
    if not gs:
        return None
    tot = dict.fromkeys(("result", "strength", "margin", "venue", "limit", "post"), 0.0)
    for g in gs:
        p = parts(book, g)
        base = 70.0 if p["won"] else 30.0
        tot["result"] += base
        tot["margin"] += p["result"] - base
        tot["strength"] += p["bonus"]
        tot["venue"] += p["venue"]
        tot["post"] += p["post"]
        if p["limited"]:
            tot["limit"] += min(100.0, max(0.0, p["before_limit"])) - p["before_limit"]
    n = len(gs)
    out = {k: v / n for k, v in tot.items()}
    out["other"] = book.team(t, y)["rating"] - sum(out.values())
    out["games"] = n
    return out


def breakdown_line(book, t, y):
    d = breakdown(book, t, y)
    if not d:
        return None
    shown = [f"{name} {r1(d[k]) if k == 'result' else signed(d[k])}" for k, name in PART_NAMES
             if k in ("result", "strength", "margin", "venue") or abs(d[k]) >= 0.05]
    return (f"{t}'s Team Rating {r1(book.team(t, y)['rating'])}, split into its average parts over {d['games']} games: "
            + " · ".join(shown) + " (win/loss averages 70 for a win and 30 for a loss).")


def gap_parts(book, hi, lo, y):
    """Why hi is above lo, part by part: hi's average part minus lo's, and the part that decides it."""
    a, b = breakdown(book, hi, y), breakdown(book, lo, y)
    if not a or not b:
        return []
    diff = {k: a[k] - b[k] for k, _ in PART_NAMES}
    shown = [(k, name) for k, name in PART_NAMES
             if k in ("result", "strength", "margin", "venue") or abs(diff[k]) >= 0.05]
    lines = [f"Why {hi} is above {lo}, part by part ({hi}'s average minus {lo}'s; they add up to the gap): "
             + " · ".join(f"{name} {signed(diff[k])}" for k, name in shown) + "."]
    pro = sorted((k for k, _ in shown if diff[k] >= 0.05), key=lambda k: -diff[k])
    con = sorted((k for k, _ in shown if diff[k] <= -0.05), key=lambda k: diff[k])
    names = dict(PART_NAMES)
    gap = sum(diff.values())
    against = sum(diff[k] for k in con)
    if pro:
        top = pro[0]
        if against > -0.5:
            share = "most of the gap" if diff[top] >= 0.5 * gap else "the biggest part"
        else:
            share = f"the biggest part in its favor; together the parts in {hi}'s favor outweigh those in {lo}'s"
        lines.append(f"The part that puts {hi} ahead: {names[top]} ({signed(diff[top])}), {share}."
                     + (f" Also in {hi}'s favor: " + ", ".join(f"{names[k]} ({signed(diff[k])})" for k in pro[1:]) + "."
                        if pro[1:] else ""))
    if con:
        lines.append(f"Parts that favor {lo}: " + ", ".join(f"{names[k]} ({signed(diff[k])})" for k in con) + ".")
    lines.append(f"What each part means: win/loss is the record (70 for a win, 30 for a loss, averaged), opponent "
                 f"strength is who they played, margin is how much they won or lost by, venue is where they played.")
    return lines


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
        last = gs[-1]
        imp = book.impact(t, last[1], y, last[0])
        side = next((x for x in (imp or {}).get("teams", []) if x["team"] == t and x.get("fbs")), None)
        if side:
            b, a = round(side["rating_before"], 1), round(side["rating_after"], 1)
            lines.append(f"What {t}'s latest game did, as its result card shows: Team Rating {r1(b)} without that "
                         f"game, {r1(a)} with it ({signed(a - b)}); rank #{side['rank_before']} to #{side['rank_after']}.")
        if len(gs) > 1 and gs[-2][11] is not None and last[11] is not None:
            lines.append(f"Since its previous game, other teams' results included, {t}'s Team Rating has moved "
                         f"{signed(last[11] - gs[-2][11])} ({r1(gs[-2][11])} to {r1(last[11])}). This is not what "
                         "the latest game alone did" + ("; use the line above for that." if side else "."))
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


def finished(book, t, y=None):
    """A team with no game left on the schedule file, said so it can't be read as idle this week: "has played
    every game on its schedule (the last: won 48-27 vs TCU on Nov 26; title games and bowls are added only
    once set)"."""
    y = y or book.current
    gs = book.games(t, y)
    last = ""
    if gs:
        g = gs[-1]
        last = (f"the last: {'won' if g[3] > g[4] else 'lost'} {max(g[3], g[4])}-{min(g[3], g[4])} "
                f"{'at' if g[2] == 'A' else 'vs'} {g[1]} on {MONTHS[int(g[0][:2]) - 1]} {int(g[0][3:])}; ")
    return (f"has played every game on its schedule ({last}title games and bowls are added only once set). "
            "It is done, not idle this week")


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
    split = breakdown_line(book, t, y)
    if split:
        lines.append(split)
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
            lines.append(f"{t} {finished(book, t, y)}.")
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
    lines += [x for x in (breakdown_line(book, hi["team"], y), breakdown_line(book, lo["team"], y)) if x]
    lines += gap_parts(book, hi["team"], lo["team"], y)
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
            return header(book, y) + [f"{t} {finished(book, t, y)}."]
        return header(book, y) + [f"{t}'s games still to play:"] + [upcoming_line(book, g, y) for g in mine]
    soon = [g for g in ups if (g["when"] - ups[0]["when"]).days < 8]
    r = book.data["ratings"][str(y)]
    best = lambda g: min(r.get(g["home"], [0, 999])[1], r.get(g["away"], [0, 999])[1])
    soon.sort(key=best)
    return header(book, y) + [f"The next week's games, the {min(count, len(soon))} with the highest-ranked teams first:"] + [
        upcoming_line(book, g, y) for g in soon[:count]]


def look_what_if(book, team, opponent=None, site=None, margin=None):
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
        return look_help(book, t)
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
    redo = met and w.played(t, o)
    if redo:
        g = met[0]
        site = redo[1]
        lines[next(i for i, x in enumerate(lines) if x.startswith("What-if: "))] = (f"What-if, a game already played: {t} and {o} played on {MONTHS[int(g[0][:2]) - 1]} "
                    f"{int(g[0][3:])} ({'at home' if site == 'home' else 'on the road' if site == 'away' else 'neutral site'} "
                    f"for {t}), and {t} {'won' if g[3] > g[4] else 'lost'} {max(g[3], g[4])}-{min(g[3], g[4])}. The lines below re-run the "
                    "season with that one result changed and nothing else: say \"would have\", since later games "
                    "might have gone differently too.")
    elif met:
        g = met[0]
        lines.append(f"{t} and {o} already played on {MONTHS[int(g[0][:2]) - 1]} {int(g[0][3:])}: {t} "
                     f"{'won' if g[3] > g[4] else 'lost'} {max(g[3], g[4])}-{min(g[3], g[4])}, and that result is in the numbers above. "
                     "This what-if adds a second game between them; say so, or answer about the game played.")
    elif not game:
        lines.append(f"{t} vs {o} is not on the schedule file: a made-up game. Call it hypothetical, and do not call "
                     "it a title game, a bowl or a playoff game unless the post did.")
    base = w.base_rank
    try:
        margin = int(margin) if margin not in (None, "") else None
    except (TypeError, ValueError):
        margin = None
    if margin == 0:
        raise Unanswerable("a game cannot end in a tie; give a margin other than 0")
    if redo:
        won = met[0][3] > met[0][4]
        ms = [margin] if margin is not None else ([-3, -17] if won else [3, 17])
        scen = [dict(zip(("table", "rank"), w.changed(t, o, m)), margin=m) for m in ms]
    elif margin is None:
        scen = w.scenarios(t, o, site)
    else:
        table, rank = w.with_game(t, o, site, margin)
        scen = [{"margin": margin, "table": table, "rank": rank}]
    for sc in scen:
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
        lines.append((f"Had {winner} won by {abs(m)}: " if redo else f"If {winner} wins by {abs(m)}: ")
                     + " · ".join(parts) + extra)
    if not redo:
        lines += what_it_takes(book, w, t, o, site, pub)
    return lines


def look_help(book, t):
    """A team with no game left: which losses by the teams just above would move it up (engine re-runs)."""
    import reply_whatif as WI
    y = book.current
    if not hasattr(book, "_whatif"):
        try:
            book._whatif = WI.WhatIf(book.site_dir, book.data["ratings"][str(y)])
        except WI.OutOfDate as why:
            book._whatif = str(why)
    if isinstance(book._whatif, str):
        raise Unanswerable(book._whatif)
    w = book._whatif
    pub = book.data["ratings"][str(y)]
    base = w.base_rank
    lines = header(book, y) + [
        f"{t} {finished(book, t, y)}, so for now only other results can move it. "
        f"Now: {t} #{base[t]}, Team Rating {r1(pub[t][0])}."]
    losses = []
    for a in sorted((x for x in base if base[t] - HELP_ABOVE - 1 <= base[x] < base[t]), key=base.get):
        g = next(iter(next_games(book, a) or []), None)
        if not g:
            lines.append(f"#{base[a]} {a} {finished(book, a, y)}.")
            continue
        b = g["away"] if g["home"] == a else g["home"]
        a_site = "neutral" if g["neutral"] else ("home" if g["home"] == a else "away")
        rank = w.with_game(a, b, a_site, -HELP_LOSS)[1]
        if rank[t] < rank[a]:
            losses.append((a, b, a_site))
            lines.append(f"If #{base[a]} {a} loses to {b} ({when(g)}), even by {HELP_LOSS}, {t} moves past it, to #{rank[t]}.")
        else:
            lines.append(f"#{base[a]} {a} losing to {b} by {HELP_LOSS} would not drop it below {t}.")
    if len(losses) > 1:
        rank = w.with_games([(a, b, s, -HELP_LOSS) for a, b, s in losses])[1]
        lines.append(f"If all of those lose ({', '.join(a for a, _, _ in losses)}), {t} would be #{rank[t]}.")
    return lines


HELP_ABOVE = 3      # teams just above that the what-if checks for help from other games
HELP_LOSS = 3       # the loss by a team above used when asking what other results would add (a close one)


def what_it_takes(book, w, t, o, site, pub):
    """How big a win team t needs to move up, and which other results (teams just above losing their next
    game) would move it further. Display only: the engine re-run with those games added."""
    import reply_whatif as WI
    base = w.base_rank
    steps = w.margin_steps(t, o, site)
    cap = WI.E.MARGIN_CAP
    out = []
    if len(steps) == 1:
        out.append(f"How much a win needs: any win leaves {t} at #{steps[0][1]}, even one by {cap} or more "
                   f"(margin stops counting at {cap}).")
    else:
        out.append(f"How much a win needs: " + " · ".join(
            f"by {m} or more, #{r}" if i else f"by 1 or more, #{r}" for i, (m, r, _) in enumerate(steps))
            + f" (margin stops counting at {cap}).")
    table, rank = w.with_game(t, o, site, cap)
    best = rank[t]
    if best > 1:
        ahead = next(x for x in rank if rank[x] == best - 1)
        gap = round(float(table.rating[ahead]) - float(table.rating[t]), 1)
        if gap > 0:
            out.append(f"Even after a win by {cap}, {t} would be {r1(gap)} below #{best - 1} {ahead} in Team Rating.")
    above = sorted((x for x in base if base[t] - HELP_ABOVE <= base[x] < base[t]), key=base.get)
    _, solo = w.with_game(t, o, site, 1)
    for a in above:
        if solo[t] < solo[a]:
            continue                       # any win already passes it: no help needed
        g = next((g for g in (next_games(book, a) or []) if t not in (g["home"], g["away"])), None)
        if not g:
            out.append(f"#{base[a]} {a} {finished(book, a)}, so for now {t} can only pass it on its own results.")
            continue
        b = g["away"] if g["home"] == a else g["home"]
        a_site = "neutral" if g["neutral"] else ("home" if g["home"] == a else "away")
        need = None
        for m in range(1, cap + 1):
            _, both = w.with_games([(t, o, site, m), (a, b, a_site, -HELP_LOSS)])
            if both[t] < both[a]:
                need = (m, both[t])
                break
        if need:
            m, r = need
            own = w.with_game(t, o, site, m)[1][t]
            out.append(f"Help from elsewhere: if #{base[a]} {a} loses to {b} ({when(g)}), even by {HELP_LOSS}, a {t} win "
                       f"by {m} or more puts {t} past {a}, at #{r} (#{own} with that win and no help)." if m > 1 else
                       f"Help from elsewhere: if #{base[a]} {a} loses to {b} ({when(g)}), even by {HELP_LOSS}, any {t} "
                       f"win puts {t} past {a}, at #{r} (#{own} with a win and no help).")
        else:
            out.append(f"#{base[a]} {a} losing to {b} by {HELP_LOSS} would not be enough: even with a win by {cap}, "
                       f"{t} stays behind {a}.")
    return out


STAKES_MAX = 8


def look_stakes(book, start=9, count=6):
    """The playoff picture around a cut: for a slice of TrueCFB's ranking, each team's committee rank, its
    next game, and what a close win, the biggest win and a close loss would do to its rank (engine re-runs,
    one game added each)."""
    import reply_whatif as WI
    y = book.current
    try:
        start, count = max(1, int(start)), max(1, min(int(count), STAKES_MAX))
    except (TypeError, ValueError):
        start, count = 9, 6
    if not hasattr(book, "_whatif"):
        try:
            book._whatif = WI.WhatIf(book.site_dir, book.data["ratings"][str(y)])
        except WI.OutOfDate as why:
            book._whatif = str(why)
    if isinstance(book._whatif, str):
        raise Unanswerable(book._whatif)
    w = book._whatif
    pub = book.data["ratings"][str(y)]
    base = w.base_rank
    snaps = book.snaps(y)
    cfp_key = next((k for k in reversed(list(snaps)) if any(r[5] for r in snaps[k])), None)
    cfp = {r[1]: r[5] for r in snaps[cfp_key]} if cfp_key else {}
    cap = WI.E.MARGIN_CAP
    order = sorted(base, key=base.get)[start - 1: start - 1 + count]
    lines = header(book, y) + [
        f"The picture from TrueCFB #{start} to #{start + len(order) - 1}: each team's next game and what it would do "
        "to its TrueCFB rank, with that one game added and nothing else changed. CFP ranks are the committee's "
        f"latest ({'going into week ' + cfp_key[1:] if cfp_key and cfp_key.startswith('w') else cfp_key or 'none yet'}). Ranks are TrueCFB's; the committee's field also gives spots to conference champions."]
    for t in order:
        tag = f"#{base[t]} {t} ({r1(pub[t][0])}" + (f", CFP #{cfp[t]})" if cfp.get(t) else ", not in the CFP ranking)")
        g = next(iter(next_games(book, t) or []), None)
        if not g:
            lines.append(f"{tag}: {finished(book, t, y)}.")
            continue
        o = g["away"] if g["home"] == t else g["home"]
        site = "neutral" if g["neutral"] else ("home" if g["home"] == t else "away")
        where = {"home": f"vs {o}", "away": f"at {o}", "neutral": f"vs {o} (neutral)"}[site]
        close = w.with_game(t, o, site, 3)[1][t]
        big = w.with_game(t, o, site, cap)[1][t]
        loss = w.with_game(t, o, site, -3)[1][t]
        above = next((x for x in base if base[x] == base[t] - 1), None)
        if above:
            need = next((m for m in range(1, cap + 1) if w.with_game(t, o, site, m)[1][t] < base[t]), None)
            own = (f"a win by {need} or more moves it up on its own" if need and need > 1 else
                   "any win moves it up on its own" if need else f"no win moves it past #{base[t] - 1} {above} on its own")
        else:
            own = "it is #1"
        lines.append(f"{tag}: {where} ({when(g)}) · a close win: #{close} · a win by {cap}: #{big} · a close loss: "
                     f"#{loss} · {own}.")
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
    {"name": "stakes", "fn": look_stakes,
     "description": "The playoff picture around a cut in one call: for a slice of TrueCFB's ranking, each team's "
                    "committee rank, its next game, its TrueCFB rank after a close win, a win by 40 and a close "
                    "loss, and whether a win alone moves it up. For bubble, \"who controls their destiny\" and "
                    "\"playoff picture\" questions; then what_if for the team that matters most.",
     "parameters": {"type": "object", "properties": {
         "start": {"type": "integer", "description": "First TrueCFB rank (default 9)."},
         "count": {"type": "integer", "description": f"How many teams (default 6, at most {STAKES_MAX})."}}}},
    {"name": "what_if", "fn": look_what_if,
     "description": "What one game not yet played would do: the engine re-run with that game added, for a "
                    "close and a two-score result each way. Gives both teams' new Team Rating, the change, the "
                    "new rank and who they pass or fall behind; how big a win it takes to move up (by 1 to 40, "
                    "where margin stops counting); and which losses by the teams just above would move it further. "
                    "With no opponent, it uses the team's next game. For a game already played, it re-runs the "
                    "season with that result changed (\"what if they had won\"). Use it for playoff and \"what do "
                    "they need\" questions too.",
     "parameters": {"type": "object", "properties": {
         "team": {"type": "string"},
         "opponent": {"type": "string", "description": "Leave it out for the team's next game."},
         "site": {"type": "string", "enum": ["home", "away", "neutral"],
                  "description": "From the team's side. Leave it out to use the schedule."},
         "margin": {"type": "integer", "description": "One exact result to run, from the team's side: 30 for a "
                    "30-point win, -7 for a 7-point loss. Leave it out for a close and a two-score result each way."}},
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
