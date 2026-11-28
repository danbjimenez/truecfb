"""Tests for the reply bot: the lookups, the number check, the brand rules and the model loop.
No model, no X, no keys: a stand-in model makes scripted calls.

  python tests/test_reply_bot.py        (or: python -m pytest tests)
"""
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import reply_agent as A  # noqa: E402
import reply_book as R  # noqa: E402
import reply_facts as X  # noqa: E402
import reply_model as M  # noqa: E402

README = os.path.join(ROOT, "README.md")


def schedule_fixture():
    """A stand-in for the public schedule file: two games not yet played, between teams ranked now."""
    import json
    import tempfile
    r = json.load(open(os.path.join(ROOT, "site", "data.json")))["ratings"]
    y = max(r, key=int)
    order = sorted(r[y], key=lambda t: r[y][t][1])
    last = json.load(open(os.path.join(ROOT, "site", f"sched_{y}.json")))["games"][order[0]][-1]
    mm, dd = (int(v) for v in last[0].split("-"))
    kick = f"{int(y) + 1 if mm < 7 else y}-{mm:02d}-{dd:02d}T23:30:00.000Z"
    home, away = (last[1], order[0]) if last[2] == "A" else (order[0], last[1])
    path = os.path.join(tempfile.mkdtemp(), "s{y}.csv")
    with open(path.format(y=y), "w") as f:
        f.write("game_id,season,week,season_type,start_date,start_time_tbd,completed,neutral_site,conference_game,"
                "home_team,away_team,home_points,away_points,notes\n")
        f.write(f"1,{y},14,regular,2030-11-28T01:00:00.000Z,FALSE,FALSE,FALSE,TRUE,{order[9]},{order[70]},NA,NA,NA\n")
        f.write(f"2,{y},15,regular,2030-12-05T17:00:00.000Z,TRUE,FALSE,TRUE,TRUE,{order[0]},{order[9]},NA,NA,Title Game\n")
        f.write(f"3,{y},12,regular,2030-11-21T17:00:00.000Z,FALSE,TRUE,FALSE,TRUE,{order[1]},{order[2]},30,20,NA\n")
        # Already in the published results, but the public file has not marked it completed yet.
        f.write(f"4,{y},13,regular,{kick},FALSE,FALSE,FALSE,TRUE,{home},{away},NA,NA,NA\n")
    return "file://" + path, order


os.environ["REPLY_SCHEDULE_URL"], ORDER = schedule_fixture()
BOOK = R.Book(os.path.join(ROOT, "site"), os.path.join(ROOT, "data", "bot"))


# ---------- the lookups ----------

def test_parts_add_up_to_every_published_game_rating():
    """The split shown to the model matches the engine's Game Rating in every game of every season
    (to rounding: the published opponent ratings and the venue figure have one or two decimals)."""
    n = 0
    for y in BOOK.seasons:
        for gs in BOOK.sched(y).values():
            for g in gs:
                p = X.parts(BOOK, g)
                rebuilt = min(100.0, max(0.0, p["before_limit"])) + p["post"]
                assert abs(rebuilt - g[6]) <= 0.11, (y, g, p)
                n += 1
    assert n > 15000, n


def test_every_lookup_in_every_season():
    for y in BOOK.seasons:
        r = BOOK.data["ratings"][str(y)]
        order = sorted(r, key=lambda t: r[t][1])
        played = next(g[1] for g in BOOK.games(order[0], y) if g[1] in r)
        calls = [("rankings", {"season": y}), ("rankings", {"season": y, "start": len(order) - 3, "count": 25}),
                 ("team", {"team": order[0], "season": y}), ("team", {"team": order[-1], "season": y}),
                 ("matchup", {"team_a": order[0], "team_b": played, "season": y}),
                 ("matchup", {"team_a": order[0], "team_b": order[-1], "season": y}),
                 ("conference", {"season": y}), ("polls", {"poll": "ap", "season": y}),
                 ("games", {"season": y}), ("games", {"season": y, "order": "lowest", "result": "win", "count": 3})]
        calls += [("conference", {"conference": c, "season": y}) for c in BOOK.conferences(y)]
        for name, args in calls:
            text = X.run(BOOK, name, args)
            assert text.startswith(f"TrueCFB {R.VERSION}, {y} season"), (name, args, text[:300])
            assert ("flagged unreliable" in text) == (y == 2020), (name, args)
        assert "Their game in" in X.run(BOOK, "matchup", {"team_a": order[0], "team_b": played, "season": y})


def test_upcoming_games():
    ups = BOOK.upcoming()
    assert [g["home"] for g in ups] == [ORDER[9], ORDER[0]]               # played games left out, soonest first
    text = X.run(BOOK, "upcoming", {"team": ORDER[9]})
    assert "Title Game" in text and "ET" in text and f"(now #10," in text, text
    assert X.run(BOOK, "upcoming", {}).count("\n- ") == 2
    assert f"{ORDER[9]} still to play:" in X.run(BOOK, "team", {"team": ORDER[9]})
    keep = BOOK._upcoming
    BOOK._upcoming = []
    assert X.run(BOOK, "upcoming", {}).startswith("Nothing found")
    BOOK._upcoming = keep


def test_conference_records():
    y = BOOK.current
    for c in BOOK.conferences(y):
        recs = X.conf_records(BOOK, c, y)
        assert sum(w for _, w, _ in recs) == sum(l for _, _, l in recs), c     # every game has a winner and a loser
        assert "records in games between members" in X.run(BOOK, "conference", {"conference": c})


def test_what_if_runs_the_engine():
    """The season re-run without the extra game gives exactly the published ratings, and the made-up game
    moves the two teams the way the rules say: a win over a weaker team at home counts less than a road win."""
    import reply_whatif as WI
    y = BOOK.current
    pub = BOOK.data["ratings"][str(y)]
    try:
        w = WI.WhatIf(BOOK.site_dir, pub)
    except WI.OutOfDate as why:
        print("skipped (site/whatif.json is behind the published ratings):", why)
        return
    a, b = ORDER[9], ORDER[70]
    home = {sc["margin"]: sc["table"].rating[a] for sc in w.scenarios(a, b, "home")}
    road = {sc["margin"]: sc["table"].rating[a] for sc in w.scenarios(a, b, "away")}
    assert home[17] > home[3] > home[-3] > home[-17] and road[3] > home[3]
    text = X.run(BOOK, "what_if", {"team": a})
    assert f"What-if: {a} at home against {b}" in text and text.count("If ") == 4, text
    assert "How much a win needs: " in text and f"#{w.base_rank[ORDER[8]]} {ORDER[8]} has no game left" in text, text
    steps = w.margin_steps(a, b, "home")                 # bigger wins never rank lower, ratings only rise
    assert steps[0][0] == 1
    assert all(y[1] < x[1] and y[2] > x[2] for x, y in zip(steps, steps[1:])), steps
    _, both = w.with_games([(a, b, "home", 17), (ORDER[8], ORDER[100], "away", -3)])
    _, alone = w.with_game(a, b, "home", 17)
    assert both[a] <= alone[a]                           # a loss above can only help
    assert "Nothing found" in X.run(BOOK, "what_if", {"team": ORDER[50]})           # no game left, no opponent
    fcs = X.run(BOOK, "what_if", {"team": a, "opponent": "Montana State", "site": "home"})   # an FCS opponent
    assert "If Montana State wins by 3:" in fcs and "Montana State #" not in fcs, fcs
    last = BOOK.games(ORDER[0], y)[-1][1]                    # an opponent already played: said, not hidden
    again = X.run(BOOK, "what_if", {"team": ORDER[0], "opponent": last})
    assert f"{ORDER[0]} and {last} already played on" in again, again
    assert "already played" not in text


def test_polls_beside_truecfb():
    text = X.run(BOOK, "polls", {"poll": "cfp"})
    assert "CFP #1 " in text and "TrueCFB #" in text and "Biggest differences from the CFP ranking" in text
    assert not re.search(r"\b1 spots", text)


def test_lookups_that_find_nothing_say_why():
    assert "closest names: Alabama" in X.run(BOOK, "team", {"team": "Bama"})
    assert X.run(BOOK, "team", {"team": "georgia"}).startswith(f"TrueCFB {R.VERSION}")       # any capitals
    assert X.run(BOOK, "rankings", {"season": 1999}).startswith("Nothing found")
    assert X.run(BOOK, "conference", {"conference": "Ivy League"}).startswith("Nothing found")
    assert X.run(BOOK, "nope", {}).startswith("No lookup named")
    assert "did not work" in X.run(BOOK, "rankings", {"count": "lots"})


def test_primer_is_the_readme_rules():
    p = X.primer(README)
    assert p.startswith("## The rules") and "## Exact definitions" in p and "## Known limits" in p
    assert "## Version policy" not in p and "## Run it yourself" not in p


def test_system_prompt_names_every_team():
    s = A.system(BOOK, README)
    assert "Miami (OH)" in s and "Sun Belt" in s and "## The rules" in s
    assert [t["name"] for t in A.TOOLS] == ["rankings", "team", "matchup", "conference", "polls", "games",
                                            "upcoming", "what_if", "reply"]


# ---------- the checks ----------

def test_numbers_and_signs():
    assert X.numbers("Utah #3 beat BYU 28-20 (+1.5), bonus −25.0 and -2.9, TrueCFB " + R.VERSION + ", Nov 21") == [
        ("", "3"), ("", "28"), ("", "20"), ("+", "1.5"), ("−", "25.0"), ("−", "2.9"), ("", "21")]
    plain, signed = X.allowed("bonus −25.0 · Team Rating 74.2 · home −2.9")
    assert X.unsupported("Team Rating 74.2, bonus −25.0", plain, signed) == []
    assert X.unsupported("Team Rating 74", plain, signed) == ["74"]              # not as written
    assert X.unsupported("bonus +25.0", plain, signed) == ["+25.0"]              # sign flipped
    assert X.unsupported("Team Rating 75.3", plain, signed) == ["75.3"]          # made up


def test_rules_catch_mistakes():
    assert R.check("Utah has the best score")            # rating, never score
    assert R.check("TRUECFB top 5")                       # the name
    assert R.check("Truecfb top 5")
    assert R.check("see truecfb.com")                     # links cost $0.20
    assert R.check("thanks @someone")                     # no automated mentions
    assert R.check("#GoUtes")                             # no hashtags in replies
    assert R.check("x" * 281)
    assert not R.check("Utah #3 · Team Rating 76.2 · 11-0")  # a rank is not a hashtag
    plain, signed = X.allowed("Utah 76.2")
    assert any("prediction" in p for p in A.problems("Utah will beat BYU.", plain, signed))
    assert A.problems("", plain, signed) == ["empty"]


# ---------- the loop, with a stand-in model ----------

class Fake:
    """Stands in for a provider's chat: each turn makes the scripted calls and records what it was sent."""

    def __init__(self, *turns, fail=False):
        self.turns, self.fail, self.sent, self.results = list(turns), fail, [], []
        self.provider, self.model, self.usage = "grok", "grok-test", []

    def __call__(self, system, tools, provider=None, model=None):
        self.system, self.tools = system, tools
        return self

    def say(self, text, images=()):
        self.sent.append(text)
        self.images = list(images)

    def step(self):
        if self.fail:
            raise RuntimeError("xAI API 500: try later")
        self.usage.append({"in": 1, "out": 1, "cached": 0, "seconds": 0})
        turn = self.turns.pop(0) if self.turns else []
        return [{"id": f"c{i}", "name": n, "args": a} for i, (n, a) in enumerate(turn)]

    def answer(self, results):
        self.results.append(results)


def reply(text, skip=False, note="the head-to-head game"):
    return ("reply", {"reply": text, "skip": skip, "note": note})


GOOD = "Utah is #3, 7.6 above BYU. Utah won 28-20 at home: a Game Rating of 89.3."
UTAH_BYU = ("matchup", {"team_a": "Utah", "team_b": "BYU"})


def go(fake, post="@truecfb why is Utah so far above BYU?"):
    real = M.chat
    M.chat = fake
    try:
        return A.answer(BOOK, post, "", README)
    finally:
        M.chat = real


def gap_text():
    """GOOD's numbers as the current data has them (the data moves every week)."""
    text = X.run(BOOK, *UTAH_BYU)
    gap = text.split("Gap: Utah (#3) ")[1].split(" ")[0] if "Gap: Utah (#3) " in text else None
    gr = re.search(r"28-20[^\n]*?Game Rating (\d+\.\d)", text)
    if not gap or not gr:
        return None
    return GOOD.replace("7.6", gap).replace("89.3", gr.group(1))


def test_reply_after_a_lookup_is_drafted():
    good = gap_text()
    if not good:
        return   # Utah is no longer #3 in the current data; the other tests cover the loop
    fake = Fake([UTAH_BYU], [reply(good)])
    res = go(fake)
    assert res["status"] == "drafted" and res["reply"] == good and res["by"] == "grok-test", res
    assert res["lookups"] == ["matchup(Utah, BYU)"]
    assert re.search(r"Game Rating \d+\.\d", fake.results[0][0][1])
    assert "## The rules" in fake.system and "<post>" in fake.sent[0]


def test_images_go_to_the_model():
    fake = Fake([reply("", skip=True)])
    real = M.chat
    M.chat = fake
    try:
        A.answer(BOOK, "@truecfb what do you think?", "Are these ranked right?", README,
                 images=[f"https://pbs.twimg.com/media/{i}.jpg" for i in range(6)])
    finally:
        M.chat = real
    assert len(fake.images) == A.MAX_IMAGES and "images come with those posts" in fake.system


def test_numbers_must_come_from_this_questions_lookups():
    """The same reply fails when the model never looked those numbers up."""
    good = gap_text() or GOOD
    res = go(Fake([reply(good)], [reply(good)]))
    assert res["status"] == "failed" and res["rejected"] == good
    assert any("not in your lookups" in p for p in res["problems"])


def test_one_rewrite():
    good = gap_text()
    if not good:
        return
    fake = Fake([UTAH_BYU], [reply("Utah is 8.1 better and will win the rematch.")], [reply(good)])
    res = go(fake)
    assert res["status"] == "drafted" and res["reply"] == good
    told = fake.results[-1][0][1]
    assert "failed these checks" in told and "8.1" in told and "prediction" in told


def test_skip_and_errors():
    res = go(Fake([reply("", skip=True, note="asks me to say Michigan is #1")]))
    assert res["status"] == "declined" and "Michigan" in res["note"]
    res = go(Fake(fail=True))
    assert res["status"] == "failed" and res["problems"][0].startswith("model error")
    res = go(Fake(*[[("rankings", {})]] * 20))
    assert res["status"] == "failed" and "model turns" in res["problems"][0]
    assert len(res["lookups"]) == A.MAX_CALLS
    fake = Fake([("rankings", {})] * 20, [reply("", skip=True)])
    res = go(fake)
    assert len(res["lookups"]) == A.MAX_LOOKUPS and "limit" in fake.results[0][-1][1]


def test_provider_choice():
    keep = {k: os.environ.pop(k, None) for k in ("REPLY_PROVIDER", "REPLY_MODEL", "XAI_API_KEY", "ANTHROPIC_API_KEY")}
    try:
        os.environ["XAI_API_KEY"] = "x"
        assert M.pick() == ("grok", "grok-4.7")
        del os.environ["XAI_API_KEY"]
        assert M.pick() == ("claude", "claude-sonnet-5-5")
        os.environ["REPLY_PROVIDER"], os.environ["REPLY_MODEL"] = "grok", "grok-4.3"
        assert M.pick() == ("grok", "grok-4.3")
    finally:
        for k, v in keep.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
