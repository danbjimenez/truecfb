"""TrueCFB reply bot: the reply text for one question, built from the engine's published numbers.

Every number in a reply comes from files the frozen v1.0 engine wrote:
  site/data.json          each season's Team Ratings, ranks and records, and the current week
  site/history.json       each conference's Conference Rating and rank
  site/sched_{season}.json every team's games, with each Game Rating and the Team Rating after it
  data/bot/drafts.json    recent results worked out by game_impact.py (the Matchup Rating)
Nothing here computes a rating. The model (reply_model.py) only says what is being asked and about
which teams; the fixed templates below write every word of the reply.

  reply(book, intent, teams, conferences, season) -> text, or raises Unanswerable
  check(text) -> list of rule problems (empty when the text is fine)
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from game_impact import weighted_length, MAX_POST  # noqa: E402

INTENTS = ["team", "compare", "game", "top", "conference", "how", "predict", "skip"]
INDEPENDENTS = "FBS Independents"
UNRELIABLE = {2020}            # flagged on the site; never special-cased in the formula
TOP_N = 5
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class Unanswerable(Exception):
    """The question names something the engine has no numbers for (a team not in FBS that season,
    a season not rated, two teams that did not play). The draft job reports it to Dan instead."""


def load(path, default=None):
    return json.load(open(path)) if os.path.exists(path) else default


class Book:
    """The engine's published numbers, read once."""

    def __init__(self, site_dir, bot_dir=None):
        self.site_dir = site_dir
        self.data = load(os.path.join(site_dir, "data.json"))
        self.history = load(os.path.join(site_dir, "history.json"), {"conf": {}})
        self.drafts = load(os.path.join(bot_dir, "drafts.json"), {}) if bot_dir else {}
        self._sched = {}
        self.current = int(self.data["current"]["season"])
        self.seasons = sorted(int(y) for y in self.data["ratings"])

    # ----- lookups -----

    def season(self, season):
        y = self.current if season in (None, "", "current", 0) else int(season)
        if str(y) not in self.data["ratings"]:
            raise Unanswerable(f"no TrueCFB ratings for {y} (seasons {self.seasons[0]} to {self.seasons[-1]})")
        return y

    def teams(self, season=None):
        return sorted(self.data["ratings"][str(self.season(season))])

    def conferences(self, season=None):
        y = str(self.season(season))
        return sorted(c for c, v in self.history["conf"].items() if y in v and c != INDEPENDENTS)

    def team(self, t, y):
        r = self.data["ratings"][str(y)].get(t)
        if r is None:
            raise Unanswerable(f"{t} is not an FBS team in {y}")
        rating, rank, w, l = r
        return {"team": t, "rating": rating, "rank": rank, "wins": w, "losses": l}

    def sched(self, y):
        if y not in self._sched:
            self._sched[y] = load(os.path.join(self.site_dir, f"sched_{y}.json"), {"games": {}})["games"]
        return self._sched[y]

    def games(self, t, y):
        """[date, opponent, site, points for, points against, ot, Game Rating, opp rating, FCS flag,
        postseason bonus, winner bonus, Team Rating after, rank after, snapshot], oldest first."""
        return self.sched(y).get(t, [])

    def conf(self, c, y):
        pairs = self.history["conf"].get(c, {}).get(str(y))
        if not pairs or c == INDEPENDENTS:
            raise Unanswerable(f"no Conference Rating for {c} in {y}")
        ranked = [k for k, v in self.history["conf"].items()
                  if str(y) in v and v[str(y)][-1] is not None and k != INDEPENDENTS]
        return {"conf": c, "rating": pairs[-2], "rank": pairs[-1], "of": len(ranked)}

    def when(self, y):
        """Which point in the season the numbers are from, as a phrase."""
        cur = self.data["current"]
        if y == self.current and str(y) == str(cur["season"]) and cur.get("default") != "final":
            label = cur["now_label"]
            return label[0].lower() + label[1:]
        return f"{y} final"

    def meeting(self, a, b, y):
        """The latest game between a and b in season y: (a's line, b's line), or None."""
        la = [g for g in self.games(a, y) if g[1] == b]
        if not la:
            return None
        ga = la[-1]
        gb = next((g for g in reversed(self.games(b, y)) if g[1] == a and g[0] == ga[0]), None)
        return ga, gb

    def impact(self, a, b, y, day=None):
        """game_impact's saved result for a game between a and b, if the X bot drafted one."""
        best = None
        for d in self.drafts.values():
            imp = d.get("impact") or {}
            if int(imp.get("season", 0)) != y or set(d.get("teams", [])) != {a, b}:
                continue
            if day and imp.get("day", "")[5:] != day:
                continue
            if best is None or imp["day"] > best["day"]:
                best = imp
        return best


# ---------- formatting ----------

def r1(x):
    return f"{x:.1f}"


def rec(t):
    return f"{t['wins']}-{t['losses']}"


def date(md):
    m, d = md.split("-")
    return f"{MONTHS[int(m) - 1]} {int(d)}"


def where(site, opp):
    return {"H": f"vs {opp}", "A": f"at {opp}"}.get(site, f"vs {opp} (neutral site)")


def header(book, y):
    line = f"TrueCFB v1.0, {book.when(y)}"
    return line + (" (2020 is flagged unreliable)" if y in UNRELIABLE else "")


def team_line(t):
    return f"{t['team']} #{t['rank']} · Team Rating {r1(t['rating'])} · {rec(t)}"


def last_game_line(book, t, y):
    gs = book.games(t, y)
    if not gs:
        return None
    g = gs[-1]
    result = "Won" if g[3] > g[4] else "Lost"
    return f"Last game: {result} {max(g[3], g[4])}-{min(g[3], g[4])} {where(g[2], g[1])} · {date(g[0])} · Game Rating {r1(g[6])}"


def meeting_lines(book, a, b, y):
    """The head-to-head game, if a and b played in season y: one line, or None."""
    m = book.meeting(a, b, y)
    if not m:
        return None
    ga, gb = m
    w, l = (a, b) if ga[3] > ga[4] else (b, a)
    line = f"{w} beat {l} {max(ga[3], ga[4])}-{min(ga[3], ga[4])} ({date(ga[0])})"
    if gb is None:
        return line
    gr = {a: ga[6], b: gb[6]}
    return line + f": Game Ratings {w} {r1(gr[w])}, {l} {r1(gr[l])}"


# ---------- the templates ----------

def t_team(book, teams, y):
    t = book.team(teams[0], y)
    lines = [f"{t['team']}: #{t['rank']} in TrueCFB v1.0, {book.when(y)}",
             f"Team Rating {r1(t['rating'])} · {rec(t)}"]
    optional = [last_game_line(book, t["team"], y)]
    if y in UNRELIABLE:
        lines.append("2020 is flagged unreliable")
    return lines, [x for x in optional if x]


def t_compare(book, teams, y, lead=None):
    if len(teams) == 1:
        lines, optional = t_team(book, teams, y)
        return ([lead] if lead else []) + lines, optional
    a, b = book.team(teams[0], y), book.team(teams[1], y)
    a, b = sorted([a, b], key=lambda t: t["rank"])
    lines = ([lead] if lead else []) + [header(book, y), team_line(a), team_line(b)]
    h2h = meeting_lines(book, a["team"], b["team"], y)
    return lines + ([h2h] if h2h else []), []


def t_game(book, teams, y):
    if len(teams) == 1:
        gs = book.games(teams[0], y)
        if not gs:
            raise Unanswerable(f"{teams[0]} has no games in {y}")
        opp = gs[-1][1]
        if opp not in book.data["ratings"][str(y)]:   # an FCS opponent: just the team's own line
            return t_team(book, teams, y)
        teams = [teams[0], opp]
    a, b = teams[0], teams[1]
    book.team(a, y); book.team(b, y)
    m = book.meeting(a, b, y)
    if not m:
        return t_compare(book, teams, y)
    imp = book.impact(a, b, y, m[0][0])
    if imp:
        w = next(s for s in imp["teams"] if s["won"]); l = next(s for s in imp["teams"] if not s["won"])
        ot = " (OT)" if imp.get("overtime") else ""
        lines = [f"{w['team']} {w['points']}, {l['team']} {l['points']}{ot} ({date(imp['day'][5:])})",
                 f"Matchup Rating {imp['matchup_rating']}"]
        for s in (w, l):
            if s["fbs"]:
                lines.append(f"{s['team']}: Game Rating {r1(s['game_rating'])} · #{s['rank_before']} → #{s['rank_after']}")
        return lines + ["TrueCFB v1.0"], []
    ga, gb = m
    w, wl, l, ll = (a, ga, b, gb) if ga[3] > ga[4] else (b, gb, a, ga)
    ot = " (OT)" if ga[5] else ""
    lines = [f"{w} {max(ga[3], ga[4])}, {l} {min(ga[3], ga[4])}{ot} ({date(ga[0])})"]
    for name, g in ((w, wl), (l, ll)):
        if g:
            after = f" · Team Rating after {r1(g[11])}, #{g[12]}" if g[11] is not None else ""
            lines.append(f"{name}: Game Rating {r1(g[6])}{after}")
    return lines + ["TrueCFB v1.0" + (" (2020 is flagged unreliable)" if y in UNRELIABLE else "")], []


def t_top(book, y):
    r = book.data["ratings"][str(y)]
    order = sorted(r, key=lambda t: r[t][1])[:TOP_N]
    lines = [f"TrueCFB v1.0 top {TOP_N}, {book.when(y)}"]
    lines += [f"{r[t][1]}. {t} {r1(r[t][0])} ({r[t][2]}-{r[t][3]})" for t in order]
    if y in UNRELIABLE:
        lines.append("2020 is flagged unreliable")
    return lines, []


def t_conference(book, confs, y):
    if not confs:
        raise Unanswerable("no conference named")
    rows = sorted((book.conf(c, y) for c in confs[:2]), key=lambda c: c["rank"])
    lines = [f"Conference Rating, TrueCFB v1.0, {book.when(y)}"]
    lines += [f"{c['conf']} {r1(c['rating'])} · #{c['rank']} of {c['of']}" for c in rows]
    return lines, []


HOW = ["TrueCFB v1.0: Unbiased, Deterministic, Open Source Rankings",
       "Every FBS team rated on results alone. Every game counts. Open source formula.",
       "The full method is on the How it works page of the TrueCFB site."]


def fit(lines, optional):
    """Join the lines, adding optional ones only while the reply stays within 280."""
    text = "\n".join(lines)
    for extra in optional:
        longer = text + "\n" + extra
        if weighted_length(longer) <= MAX_POST:
            text = longer
    if weighted_length(text) > MAX_POST:
        raise Unanswerable(f"reply would be {weighted_length(text)} characters")
    return text


def reply(book, intent, teams=(), conferences=(), season=None):
    """The reply for one question. teams and conferences use the engine's names exactly."""
    teams = [t for i, t in enumerate(teams) if t and t not in teams[:i]][:2]
    if intent == "skip":
        raise Unanswerable("nothing to answer")
    if intent == "how":
        return fit(HOW, [])
    y = book.season(season)
    if intent == "top":
        return fit(*t_top(book, y))
    if intent == "conference":
        return fit(*t_conference(book, list(conferences), y))
    if not teams:
        raise Unanswerable(f"{intent}: no team named")
    if intent == "team":
        return fit(*t_team(book, teams, y))
    if intent == "compare":
        return fit(*t_compare(book, teams, y))
    if intent == "game":
        return fit(*t_game(book, teams, y))
    if intent == "predict":
        return fit(*t_compare(book, teams, y, lead="TrueCFB rates results, not predictions."))
    raise Unanswerable(f"unknown intent {intent}")


# ---------- the rules every reply must follow ----------

def check(text):
    """Problems with a reply, by the brand and X rules (docs/BRAND.md, docs/X-BOT.md). Empty when fine."""
    problems = []
    if weighted_length(text) > MAX_POST:
        problems.append("longer than 280")
    if re.search(r"\bscores?\b", text, re.I):
        problems.append('says "score" (TrueCFB numbers are Ratings)')
    for m in re.finditer(r"true\s*cfb", text, re.I):
        if m.group(0) != "TrueCFB":
            problems.append(f'name written "{m.group(0)}"')
    if re.search(r"v1(?!\.0)|version 1\b", text):
        problems.append("version not written v1.0")
    if re.search(r"https?://|www\.|\.(com|org|net|io)\b", text, re.I):
        problems.append("has a link (X charges $0.20 a post)")
    if "@" in text:
        problems.append("mentions an account")
    if "#" in re.sub(r"#\d+", "", text):
        problems.append("has a hashtag")
    if re.search(r"[\U0001F300-\U0001FAFF☀-➿]", text):
        problems.append("has an emoji")
    return problems
