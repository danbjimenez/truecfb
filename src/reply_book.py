"""TrueCFB reply bot: the engine's published numbers, read once, and the rules every reply must keep.

The bot reads only files the frozen v1.0 engine wrote:
  site/data.json           each season's Team Ratings, ranks and records, settings, the current week
  site/history.json        each conference's Conference Rating and rank
  site/sched_{season}.json every team's games, with each Game Rating and the Team Rating after it
  site/rank_{season}.json  the ranking at each point of the season, with the CFP and AP ranks beside it
  data/bot/drafts.json     recent results worked out by game_impact.py (the Matchup Rating)
  site/whatif.json         the newest season's engine inputs, for what-ifs (reply_whatif.py)
and, for games not yet played, the public schedule file the ratings jobs also read.
Nothing here computes a rating.

  Book(site_dir, bot_dir) -> the files above
  check(text) -> list of brand and X rule problems (empty when the text is fine)
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from game_impact import weighted_length, MAX_POST  # noqa: E402

INDEPENDENTS = "FBS Independents"
SCHEDULE_URL = "https://raw.githubusercontent.com/sportsdataverse/cfbfastR-data/main/schedules/csv/cfb_schedules_{y}.csv"
UNRELIABLE = {2020}            # flagged on the site; never special-cased in the formula
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class Unanswerable(Exception):
    """A lookup names something the engine has no numbers for (a team not in FBS that season, a season
    not rated). The model is told so and can look up something else."""


def load(path, default=None):
    return json.load(open(path)) if os.path.exists(path) else default


class Book:
    """The engine's published numbers, read once."""

    def __init__(self, site_dir, bot_dir=None):
        self.site_dir = site_dir
        self.data = load(os.path.join(site_dir, "data.json"))
        self.history = load(os.path.join(site_dir, "history.json"), {"conf": {}})
        self.drafts = load(os.path.join(bot_dir, "drafts.json"), {}) if bot_dir else {}
        self._sched, self._snaps, self._upcoming = {}, {}, None
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

    def snaps(self, y):
        """{snapshot id: [[rank, team, Team Rating, wins, losses, CFP rank, AP rank], ...]} in season order
        ("w5" is the ranking going into week 5; "final" after the postseason; "now" the latest games)."""
        if y not in self._snaps:
            self._snaps[y] = load(os.path.join(self.site_dir, f"rank_{y}.json"), {})
        return self._snaps[y]

    def upcoming(self):
        """The current season's games not yet played, from the public schedule file the ratings jobs read
        (sportsdataverse/cfbfastR-data; REPLY_SCHEDULE_URL overrides it). Each: {"when" (UTC datetime),
        "tbd", "home", "away", "neutral", "conference_game", "note"}, soonest first. None when the file
        cannot be read: the lookups then say the schedule is not available."""
        if self._upcoming is None:
            import csv
            import io
            import urllib.request
            from datetime import datetime
            url = os.environ.get("REPLY_SCHEDULE_URL") or SCHEDULE_URL
            try:
                with urllib.request.urlopen(url.format(y=self.current), timeout=60) as r:
                    rows = list(csv.DictReader(io.StringIO(r.read().decode("utf-8"))))
            except Exception as err:
                print(f"::warning::schedule not available: {err}")
                self._upcoming = []
                return None
            yes = lambda x: str(x).strip().upper() == "TRUE"
            out = []
            for x in rows:
                if yes(x.get("completed")) or not x.get("start_date"):
                    continue
                out.append({"when": datetime.fromisoformat(x["start_date"].replace("Z", "+00:00")),
                            "tbd": yes(x.get("start_time_tbd")), "home": x["home_team"], "away": x["away_team"],
                            "neutral": yes(x.get("neutral_site")), "conference_game": yes(x.get("conference_game")),
                            "note": "" if x.get("notes") in (None, "", "NA") else x["notes"]})
            self._upcoming = sorted(out, key=lambda g: g["when"])
        return self._upcoming or None

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
