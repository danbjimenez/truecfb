"""TrueCFB reply bot: what the model may know when it writes a reply.

  primer(readme_path) -> the README's rules, word for word (the system prompt's knowledge of v1.0)
  sheet(book, intent, teams, conferences, season) -> the fact sheet: every number the reply may use
  parts(book, line) -> one schedule line's Game Rating split into the rule's parts

Every number on the sheet comes from files the frozen v1.0 engine wrote (site/data.json,
site/history.json, site/sched_{season}.json, data/bot/drafts.json). Nothing here computes a rating.
The parts of a Game Rating are split the same way the site's How it works page does it (site/js/how.js),
from the engine's published settings and margin curve; they are display only, and the published Game
Rating is always the number that counts. Gaps and changes are plain subtractions of published numbers,
shown so the model never has to do arithmetic.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reply_templates import Unanswerable, UNRELIABLE, INDEPENDENTS, r1, date  # noqa: E402

# The README sections the model learns v1.0 from, in order. Read at run time, so the model always
# knows the version the engine runs, never an older copy.
PRIMER_FROM = "## The rules"
PRIMER_UNTIL = "## Version policy"
MINUS = "−"
NEIGHBORS = 2          # teams listed above and below each team in focus
TOP_SHEET = 10


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
    margin = 1 if ot else abs(pf - pa)
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
        who = f"{opp} (#{rank}, {r1(g[7])})" if rank else f"{opp} ({r1(g[7])})"
    where = {"H": "vs", "A": "at"}.get(g[2], "vs")
    site = "" if g[2] in ("H", "A") else ", neutral site"
    res = "won" if p["won"] else "lost"
    ot = " in OT (counts as a 1-point margin)" if p["ot"] else ""
    venue = {"H": f"home {signed(p['venue'])}", "A": f"road {signed(p['venue'])}"}.get(g[2], "neutral 0.0")
    kind = "win" if p["won"] else "loss"
    split = (f"{r1(p['result'])} for a {p['margin']}-point {kind}, {venue}, "
             f"{opp}'s bonus {signed(p['bonus'])}")
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
             + f" · bonus {signed(info['rating'] - 50)} (what {t} adds to an opponent's Game Rating)"]
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


def top_block(book, y, n=TOP_SHEET):
    r = book.data["ratings"][str(y)]
    order = sorted(r, key=lambda t: r[t][1])[:n]
    return [f"Top {n}: " + " · ".join(f"#{r[t][1]} {t} {r1(r[t][0])} ({r[t][2]}-{r[t][3]})" for t in order)]


def conf_block(book, c, y):
    info = book.conf(c, y)
    r = book.data["ratings"][str(y)]
    members = sorted((t for t, k in book.data["team_conf"].get(str(y), {}).items() if k == c and t in r),
                     key=lambda t: r[t][1])
    return [f"{c}: Conference Rating {r1(info['rating'])} · #{info['rank']} of {info['of']} conferences "
            f"(the plain average of its {len(members)} members' Team Ratings)",
            f"{c} members: " + " · ".join(f"{t} #{r[t][1]} {r1(r[t][0])}" for t in members)]


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


def sheet(book, intent, teams=(), conferences=(), season=None):
    """The fact sheet for one question, as plain text. Raises Unanswerable like the templates do."""
    y = book.season(season)
    teams = [t for i, t in enumerate(teams) if t and t not in list(teams)[:i]][:2]
    head = [f"TrueCFB v1.0, {y} season, numbers {book.when(y)}."]
    if y in UNRELIABLE:
        head.append("2020 is flagged unreliable: most conferences played only themselves, so nothing ties "
                    "one conference's level to another's. Say so if you use 2020 numbers.")
    body = []
    if intent == "how":
        return "\n".join(head)
    if intent == "top":
        body += top_block(book, y)
    elif intent == "conference":
        confs = [c for c in conferences if c != INDEPENDENTS][:2]
        if not confs:
            raise Unanswerable("no conference named")
        for c in confs:
            body += conf_block(book, c, y)
        if len(confs) == 2:
            a, b = (book.conf(c, y) for c in confs)
            hi, lo = sorted([a, b], key=lambda c: c["rank"])
            body.append(f"Gap: {hi['conf']} {r1(hi['rating'] - lo['rating'])} above {lo['conf']} in Conference Rating.")
    else:
        if not teams:
            raise Unanswerable(f"{intent}: no team named")
        for t in teams:
            body += team_block(book, t, y) + [neighbors(book, t, y), ""]
        if len(teams) == 2:
            a, b = (book.team(t, y) for t in teams)
            hi, lo = sorted([a, b], key=lambda t: t["rank"])
            body.append(f"Gap: {hi['team']} (#{hi['rank']}) {r1(hi['rating'] - lo['rating'])} above "
                        f"{lo['team']} (#{lo['rank']}) in Team Rating.")
            body += game_impact_block(book, teams[0], teams[1], y)
    return "\n".join(head + [""] + [x for x in body]).strip()


# ---------- which numbers a reply may use ----------

NUMBER = re.compile(r"(?<![\w.])([+\-−]?)(\d+(?:\.\d+)?)")


def numbers(text):
    """The numbers in a text as (sign, digits): "−25.0" -> ("−", "25.0"), "28-20" -> ("", "28"), ("", "20").
    "v1.0" is the version, not a number."""
    text = text.replace("v1.0", " ")
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
