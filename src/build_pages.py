"""TrueCFB: write the plain-HTML parts of the site from the data files run_all.py just wrote, so search
engines, AI assistants and anyone without JavaScript can read the ranking.
Usage: build_pages.py <site_dir>        (run_all.py also calls build() at the end of every run)

It only reads site/data.json, site/rank_{year}.json and site/sched_{year}.json, and it computes no rating.
The few display figures it derives (strength, Matchup Rating, average opponent) use the same arithmetic and
rounding as site/js/site.js and site/js/team.js, so the page reads the same before and after the script runs.

Writes to <site_dir>:
  team/<slug>.html  one page per team (/team/utah), filled in for the team's latest season
  team.html         the team index (/team), between its <!--gen:...--> markers
  index.html        the top 25, the status line, the description and the structured data, between markers
  rankings.json     the current ranking of every FBS team, for anyone to use
  llms.txt          a plain-text summary for AI assistants
  sitemap.xml       every page, including every team page"""
import json, math, os, re, sys, unicodedata
from decimal import Decimal, ROUND_HALF_UP
from string import Template

SITE = "https://truecfb.com"
INDEP = "FBS Independents"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
STATIC_PAGES = ["/conferences", "/how-it-works", "/about"]


# ---------- the same helpers as site/js/site.js ----------

def slug(team):
    """'Texas A&M' -> 'texas-am', "Hawai'i" -> 'hawaii', 'San José State' -> 'san-jose-state'. Same as TC.slug."""
    s = "".join(c for c in unicodedata.normalize("NFKD", team) if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"['&]", "", s)).strip("-")


def esc(s):
    return "".join({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}.get(c, c) for c in str(s))


def js_round(x):                      # Math.round
    return int(math.floor(x + 0.5))


def fixed(x, places=1):               # Number.prototype.toFixed: exact value, ties away from zero
    return str(Decimal(x).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def num(x):                           # how JavaScript prints a number: 25.0 -> "25"
    return str(int(x)) if float(x).is_integer() else str(x)


def day(s):
    if not s:
        return ""
    p = [int(x) for x in s.split("-")]
    return f"{p[2]} {MONTHS[p[1] - 1]} {p[0]}" if len(p) == 3 else f"{p[1]} {MONTHS[p[0] - 1]}"


def signed(n):
    v = js_round(n)
    return ("+" if v > 0 else "−" if v < 0 else "") + str(abs(v))


def ordinal(n):
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def team_href(team, season=None):
    return f"/team/{slug(team)}" + (f"#season={season}" if season else "")


def team_link(team, season=None):
    return f'<a class="tm" href="{team_href(team, season)}">{esc(team)}</a>'


def chip(d):
    cls = "up" if d > 0 else "down" if d < 0 else "same"
    return cls, (f"+{d}" if d > 0 else f"−{-d}" if d < 0 else "=")


def move_chip(now, before):
    if now is None or before is None:
        return ""
    d = js_round((now - before) * 10) / 10
    cls = "up" if d > 0 else "down" if d < 0 else "same"
    return f'<span class="gap {cls}">' + (f"+{fixed(d)}" if d > 0 else f"−{fixed(-d)}" if d < 0 else "=") + "</span>"


def poll_cell(ours, theirs):
    if not theirs:
        return '<span class="nr">NR</span>'
    cls, text = chip(theirs - ours)
    return f'<span class="pr">{theirs}</span><span class="gap {cls}">{text}</span>'


class Site:
    def __init__(self, site_dir):
        self.dir = site_dir
        self.D = json.load(open(os.path.join(site_dir, "data.json")))
        self.b = self.D["settings"]["b"]
        cur = self.D["current"]
        self.year = cur["season"]
        self.snap = next(s for s in self.D["seasons"][self.year] if s["id"] == cur["default"])
        self.ranking = self.load(f"rank_{self.year}.json")[cur["default"]]
        self.sched = {}

    def load(self, name):
        return json.load(open(os.path.join(self.dir, name)))

    def games(self, y):
        if y not in self.sched:
            self.sched[y] = self.load(f"sched_{y}.json")
        return self.sched[y]

    def bonus(self, rating):
        return signed(self.b * (rating - 50))

    def matchup(self, team_rating, g):
        return js_round(100 + self.b * (team_rating - 50) + self.b * (g[7] - 50) + 2 * g[9] + g[10])

    # The point in the season the site opens on, in words: "through week 12" / "at the end of the 2025 season".
    def through_words(self):
        cur = self.D["current"]
        if cur["default"] == "final":
            return f"at the end of the {self.year} season"
        if cur["default"] == "reg":
            return f"at the end of the {self.year} regular season"
        if cur["default"] == "post":
            return f"during the {self.year} bowls and playoff"
        return self.snap["label"][0].lower() + self.snap["label"][1:] + f" of {self.year}"

    def status(self):
        cur = self.D["current"]
        s = f"{self.year} season · " + self.snap["label"].replace(" (after bowls and playoff)", "")
        if cur["through"]:
            s += " · " + day(cur["through"])
        return s


# ---------- one team's page ----------

def result_text(g):
    return ("W " if g[3] > g[4] else "L ") + f"{g[3]}-{g[4]}" + (" OT" if g[5] else "")


def where(g):
    return "vs " if g[2] == "H" else "at " if g[2] == "A" else "vs (N) "


def start_note(S, t, y, rating):
    if str(int(y) - 1) in S.D["history"].get(t, {}):
        return "Last season's final Team Rating"
    first = sorted(S.D["seasons"])[0]
    fcs = S.D["settings"]["fcs"]
    return f"The final {int(y) - 1} Team Rating" if y == first and rating != fcs else f"A team new to FBS starts at {num(fcs)}"


def team_page(S, t, tpl):
    D, cur = S.D, S.D["current"]
    y = max(k for k in D["ratings"] if t in D["ratings"][k])     # the team's latest FBS season
    is_current = y == cur["season"]
    link_season = None if is_current else y
    info = D["ratings"][y][t]
    rating, rank, wins, losses = info
    conf = D["team_conf"].get(y, {}).get(t)
    n_teams = len(D["ratings"][y])

    rating_label = "TrueCFB Team Rating, " + (
        "at season's end after bowls and playoff" if not is_current
        else cur["now_label"].lower() + (f" ({day(cur['now_through'])})" if cur["now_through"] else "") if cur["complete"]
        else "with this week still being played")

    # Every game, as team.js draws it
    sched = S.games(y)
    games = sched.get("games", {}).get(t, [])
    start = sched.get("start", {}).get(t)
    prev = start[0] if start else None
    first = (f'<tr><td>Start of season<span class="sub2">{esc(start_note(S, t, y, start[0]))}</span></td><td></td><td></td>'
             f'<td class="rt">{fixed(start[0])}<span class="sub2">#{start[1]}</span></td></tr>') if start else ""
    rows = []
    for g in games:
        pot = S.matchup(rating, g)
        post = (" · " + ("playoff" if g[9] == 15 else "bowl") + f" +{g[9] + (g[10] if g[3] > g[4] else 0)}") if g[9] else ""
        opp = esc(g[1]) + ' <span class="rec">FCS</span>' if g[8] else team_link(g[1], link_season)
        after = "" if g[11] is None else fixed(g[11]) + '<span class="sub2">' + move_chip(g[11], prev) + (f" #{g[12]}" if g[12] else "") + "</span>"
        if g[11] is not None:
            prev = g[11]
        rows.append(f'<tr><td>{where(g)}{opp}<span class="sub2"><span>{day(g[0])} · strength {S.bonus(g[7])} ·</span> '
                    f'<span>Matchup Rating {pot}{post}</span></span></td><td>{result_text(g)}</td><td>{fixed(g[6])}</td>'
                    f'<td class="rt">{after}</td></tr>')
    game_rows = first + ("".join(rows) or '<tr><td colspan="4">No games played yet this season.</td></tr>')

    tiles = [[S.bonus(rating), f"Strength: what {t} adds to anyone who plays it, win or lose"]]
    if games:
        best = low = games[0]
        for g in games[1:]:
            if g[6] > best[6]: best = g
            if g[6] < low[6]: low = g
        avg_opp = sum(g[7] for g in games) / len(games)
        tiles.append([fixed(best[6], 0), f"Best Game Rating: {result_text(best)} {where(best)}{best[1]}"])
        tiles.append([fixed(low[6], 0), f"Lowest Game Rating: {result_text(low)} {where(low)}{low[1]}"])
        tiles.append([fixed(avg_opp, 0), "Average opponent Team Rating (an average team is 50)"])
    tile_html = "".join(f"<div><b>{esc(a)}</b><span>{esc(b)}</span></div>" for a, b in tiles)

    # Conference table
    conf_note = conf_rows = ""
    if conf:
        allc = D["conf"][y]
        own = next((c for c in allc if c[0] == conf), None)
        ranked = [c for c in allc if c[0] != INDEP]
        ci = next((i for i, c in enumerate(ranked) if c[0] == conf), -1)
        members = sorted((x for x, c in D["team_conf"][y].items() if c == conf and x in D["ratings"][y]),
                         key=lambda x: D["ratings"][y][x][1])
        conf_note = (f"TrueCFB Conference Rating {fixed(ranked[ci][2])}, {ordinal(ci + 1)} of {len(ranked)} conferences. "
                     "It is the plain average of these teams' ratings." if ci >= 0
                     else f"Independents are not a conference. The plain average of these teams' ratings is {fixed(own[2])}." if own else "")
        conf_rows = "".join(
            f'<tr><td class="rk">{i + 1}</td><td>{esc(m) if m == t else team_link(m, link_season)}'
            f'<span class="rec">{r[2]}-{r[3]}</span></td><td class="rt">{fixed(r[0])}</td><td>{r[1]}</td></tr>'
            for i, m in enumerate(members) for r in [D["ratings"][y][m]])

    url = SITE + team_href(t)
    when = S.through_words() if is_current else f"at the end of the {y} season"
    description = (f"{t} is #{rank} of {n_teams} FBS teams in the TrueCFB college football rankings {when}, "
                   f"with a Team Rating of {fixed(rating)} ({wins}-{losses}). Every game with its Game Rating, and the Team Rating since 2014.")
    jsonld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "TrueCFB", "item": SITE + "/"},
        {"@type": "ListItem", "position": 2, "name": "Teams", "item": SITE + "/team"},
        {"@type": "ListItem", "position": 3, "name": t, "item": url}]}
    return tpl.substitute(
        title=esc(f"{t} Football Rating and Rank, {y} · TrueCFB"), og_title=esc(f"{t} · TrueCFB"),
        description=esc(description), url=url, jsonld=ld(jsonld), team=esc(t), team_attr=esc(t), season=y,
        status=esc(f"{y} season" + (f" · {conf}" if conf else "") + f" · {wins}-{losses}"),
        rating=fixed(rating), rating_label=esc(rating_label), rank=f"#{rank}", rank_label=f"of {n_teams} FBS teams",
        tiles=tile_html, carry_hidden=" hidden" if wins + losses >= D["settings"]["carry"] else "",
        built=esc(f"{t}|{y}"), games=game_rows,
        conf_hidden="" if conf else " hidden", conf_title=esc(conf or "Conference"), conf_note=esc(conf_note), conf_rows=conf_rows)


def ld(obj):
    # JSON-LD inside <script>: keep "</" out of it.
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


# ---------- the rankings page, the team index and the files for machines ----------

def ranking_rows(S, n=25):
    s, out = S.snap, []
    for r in S.ranking[:n]:
        cell = lambda has, theirs: "" if not has else poll_cell(r[0], theirs) if theirs else '<span class="nr">NR</span>' if r[0] <= 25 else ""
        out.append(f'<tr><td class="rk">{r[0]}</td><td>{team_link(r[1])}<span class="rec">{r[3]}-{r[4]}</span></td>'
                   f'<td class="rt">{fixed(r[2])}</td><td>{S.bonus(r[2])}</td><td>{cell(s["cfp"], r[5])}</td><td>{cell(s["ap"], r[6])}</td></tr>')
    return "".join(out)


def home_parts(S):
    top = ", ".join(f"{r[0]} {r[1]} {fixed(r[2])}" for r in S.ranking[:3])
    desc = (f"TrueCFB college football rankings, {S.through_words()}: {top}. "
            "Every FBS team rated on results alone. Every game counts. Open source formula.")
    meta = (f'<meta name="description" content="{esc(desc)}">\n'
            f'<meta property="og:description" content="{esc(desc)}">')
    D, cur = S.D, S.D["current"]
    graph = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebSite", "name": "TrueCFB", "url": SITE + "/",
         "description": "Every FBS team rated on results alone. Every game counts. Open source formula."},
        {"@type": "Dataset", "name": "TrueCFB college football rankings",
         "description": f"TrueCFB {D['version']} Team Ratings and ranks for every FBS team, from game results alone, "
                        "at every point of every season since 2014. Rebuilt by a public, deterministic formula after each week's games.",
         "url": SITE + "/", "license": "https://opensource.org/licenses/MIT", "isAccessibleForFree": True,
         "creator": {"@type": "Person", "name": "Dan Jimenez"},
         "temporalCoverage": f"{min(D['seasons'])}/{max(D['seasons'])}",
         "dateModified": cur["through"] or cur["now_through"] or f"{S.year}-12-31",
         "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": SITE + "/rankings.json"}]}]}
    return {"desc": meta, "ld": f'<script type="application/ld+json">{ld(graph)}</script>',
            "status": esc(S.status()), "rows": ranking_rows(S)}


def team_index(S):
    D, y = S.D, S.year
    rated = D["ratings"][y]
    out = []
    confs = [c for c in D["conf"][y] if c[0] != INDEP] + [c for c in D["conf"][y] if c[0] == INDEP]
    for i, c in enumerate(confs):
        members = sorted((t for t, k in D["team_conf"][y].items() if k == c[0] and t in rated), key=lambda t: rated[t][1])
        note = (f"Conference Rating {fixed(c[2])}, {ordinal(i + 1)} of {len(confs) - (1 if any(x[0] == INDEP for x in confs) else 0)} conferences."
                if c[0] != INDEP else "Independents are not a conference.")
        rows = "".join(f'<tr><td class="rk">{k + 1}</td><td>{team_link(t)}<span class="rec">{rated[t][2]}-{rated[t][3]}</span></td>'
                       f'<td class="rt">{fixed(rated[t][0])}</td><td>{rated[t][1]}</td></tr>' for k, t in enumerate(members))
        out.append(f'<section class="panel"><h2>{esc(c[0])}</h2><p class="note">{esc(note)}</p><div class="tablewrap"><table class="t-rank">'
                   f'<thead><tr><th>#</th><th>Team</th><th>Rating</th><th>FBS rank</th></tr></thead><tbody>{rows}</tbody></table></div></section>')
    gone = sorted(t for t in D["history"] if t not in rated)
    if gone:
        items = " · ".join(f"{team_link(t)} <span class=\"rec\">last FBS season {max(D['history'][t])}</span>" for t in gone)
        out.append(f'<section class="panel"><h2>Former FBS teams</h2><p>{items}</p></section>')
    status = esc(S.status())
    return {"status": status, "list": "\n".join(out)}


def rankings_json(S):
    D, cur, y = S.D, S.D["current"], S.year
    return {
        "name": "TrueCFB", "version": D["version"], "url": SITE + "/",
        "about": "Every FBS team rated on results alone. Every game counts. Open source formula.",
        "source": "https://github.com/danbjimenez/truecfb", "license": "MIT",
        "season": int(y), "point": S.snap["label"], "games_through": cur["through"],
        "season_complete": cur["default"] == "final",
        "fields": {"rank": "TrueCFB rank among FBS teams", "rating": "Team Rating: the average of the team's Game Ratings, 0 to 100 (above 100 is possible after the postseason)",
                   "bonus": "Strength: what the team adds to anyone who plays it, win or lose: Team Rating minus 50 (the key is still named bonus, its name before 27 Nov 2026)",
                   "cfp_rank": "College Football Playoff committee rank at this point, or null", "ap_rank": "AP poll rank at this point, or null"},
        "teams": [{"rank": r[0], "team": r[1], "conference": D["team_conf"][y].get(r[1]), "rating": r[2], "wins": r[3], "losses": r[4],
                   "bonus": js_round(S.b * (r[2] - 50)), "cfp_rank": r[5], "ap_rank": r[6], "url": SITE + team_href(r[1])} for r in S.ranking],
    }


def llms_txt(S):
    D, y = S.D, S.year
    top = "\n".join(f"{r[0]}. [{r[1]}]({SITE}{team_href(r[1])}): Team Rating {fixed(r[2])}, {r[3]}-{r[4]}, {D['team_conf'][y].get(r[1], '')}"
                    for r in S.ranking[:25])
    return f"""# TrueCFB

> TrueCFB is an open source college football ranking. Every FBS team is rated on game results alone, by a public, deterministic formula (TrueCFB {D['version']}; any change to a rule is a new version, with every season re-run). Every game counts. It measures the season that was played; it does not predict games.

TrueCFB numbers are ratings, not points. A score is points on the scoreboard (28-20); a rating is TrueCFB's measure.

- Game Rating: what one team earns for one game, 0 to 100 (above 100 in the postseason). A win starts at 70 and a loss at 30; add the opponent's strength; add 1 point for every 4 points of margin (up to 10) for a win, or take it off for a loss; add 3 on the road or subtract 3 at home; and keep it within 0 to 100.
- Team Rating: the average of a team's Game Ratings. Teams are ranked by it.
- Strength: what a team adds to anyone who plays it, win or lose: its Team Rating minus 50.
- Matchup Rating: the pot the two teams in a game split, 100 plus both teams' strengths.
- Conference Rating: the plain average of its members' Team Ratings. Published, not used in the formula.

## Current ranking: {y} season, {S.snap['label'].lower()}{f" (games through {day(D['current']['through'])})" if D['current']['through'] else ""}

{top}

All {len(S.ranking)} FBS teams, with conference, record, strength (the key `bonus`) and the AP and CFP ranks: [rankings.json]({SITE}/rankings.json)

## Pages

- [Rankings]({SITE}/): the current ranking and every week of every season since 2014, beside the AP poll and CFP ranking
- [Teams]({SITE}/team): every FBS team by conference. Each team has a page at {SITE}/team/<name>, for example {SITE}/team/ohio-state, with every game and its Game Rating
- [Conferences]({SITE}/conferences): Conference Ratings and their history
- [How it works]({SITE}/how-it-works): the seven rules in plain English
- [About]({SITE}/about): why TrueCFB exists, and how to send a change

## Source

- [Code and exact rules](https://github.com/danbjimenez/truecfb): the README defines every rule and number; the formula is one file, src/engine.py. MIT License.
- Game data from CollegeFootballData.com and ESPN. TrueCFB is not affiliated with the College Football Playoff, the Associated Press, ESPN or any school or conference.
- Updates: after each week's games, and on X at @truecfb.
"""


def sitemap(S, teams):
    cur = S.D["current"]
    mod = cur["through"] or cur["now_through"]
    url = lambda loc, lastmod=None: f"  <url><loc>{SITE}{loc}</loc>" + (f"<lastmod>{lastmod}</lastmod>" if lastmod else "") + "</url>"
    lines = [url("/", mod), url("/team", mod)] + [url(p) for p in STATIC_PAGES]
    lines += [url(team_href(t), mod if t in S.D["ratings"][S.year] else None) for t in teams]
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(lines) + "\n</urlset>\n"


def fill(path, parts):
    """Replace what sits between <!--gen:name--> and <!--/gen:name--> in a hand-written page."""
    text = open(path, encoding="utf-8").read()
    for name, content in parts.items():
        pat = re.compile(rf"(<!--gen:{name}-->).*?(<!--/gen:{name}-->)", re.S)
        if not pat.search(text):
            raise SystemExit(f"{path}: marker gen:{name} not found")
        text = pat.sub(lambda m: m.group(1) + content + m.group(2), text)
    write(path, text)


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def build(site_dir):
    S = Site(site_dir)
    teams = sorted(S.D["history"])
    slugs = {}
    for t in teams:
        s = slug(t)
        if s in slugs:
            raise SystemExit(f"two teams share the address /team/{s}: {slugs[s]} and {t}")
        slugs[s] = t
    tpl = Template(open(os.path.join(TEMPLATES, "team.html"), encoding="utf-8").read())
    folder = os.path.join(site_dir, "team")
    os.makedirs(folder, exist_ok=True)
    for name in os.listdir(folder):                    # a page for a team no longer in the data goes
        if name.endswith(".html") and name[:-5] not in slugs:
            os.remove(os.path.join(folder, name))
    for s, t in slugs.items():
        write(os.path.join(folder, s + ".html"), team_page(S, t, tpl))
    fill(os.path.join(site_dir, "index.html"), home_parts(S))
    fill(os.path.join(site_dir, "team.html"), team_index(S))
    write(os.path.join(site_dir, "rankings.json"), json.dumps(rankings_json(S), ensure_ascii=False, indent=1) + "\n")
    write(os.path.join(site_dir, "llms.txt"), llms_txt(S))
    write(os.path.join(site_dir, "sitemap.xml"), sitemap(S, teams))
    print(f"pages: {len(slugs)} team pages, index, team index, rankings.json, llms.txt, sitemap.xml")


if __name__ == "__main__":
    build(sys.argv[1])
