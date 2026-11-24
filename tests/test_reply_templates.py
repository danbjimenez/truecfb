"""Tests for the reply bot's templates, run on every season the site holds. No model, no X, no keys.

  python tests/test_reply_templates.py        (or: python -m pytest tests)

Checks that every reply keeps the brand and X rules (reply_templates.check) and that every number in
a reply is one the engine published in the files the reply was built from.
"""
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import reply_templates as R  # noqa: E402

BOOK = R.Book(os.path.join(ROOT, "site"), os.path.join(ROOT, "data", "bot"))


def published_numbers(y):
    """Every number the engine published for season y, as it would be written in a reply."""
    out = {"1.0", str(y), "2020"} | {str(i) for i in range(1, 32)}   # the version, years, days of the month
    def add(v):
        if isinstance(v, bool) or v is None:
            return
        if isinstance(v, int):
            out.add(str(v))
        elif isinstance(v, float):
            out.add(R.r1(v)); out.add(str(int(v)) if v == int(v) else R.r1(v))
        elif isinstance(v, (list, tuple)):
            for x in v:
                add(x)
        elif isinstance(v, dict):
            for x in v.values():
                add(x)
    add(BOOK.data["ratings"][str(y)])
    add([v.get(str(y)) for v in BOOK.history["conf"].values()])
    add(BOOK.sched(y))
    add([d.get("impact") for d in BOOK.drafts.values() if (d.get("impact") or {}).get("season") == y])
    add(R.TOP_N)
    return out


def assert_ok(text, y, what):
    problems = R.check(text)
    assert not problems, f"{what}: {problems}\n{text}"
    allowed = published_numbers(y)
    for n in re.findall(r"\d+(?:\.\d+)?", text):
        assert n in allowed, f"{what}: {n} is not a number the engine published for {y}\n{text}"


def cases():
    for y in BOOK.seasons:
        r = BOOK.data["ratings"][str(y)]
        order = sorted(r, key=lambda t: r[t][1])
        picks = order[:3] + order[60:62] + order[-2:]
        yield y, "top", [], []
        yield y, "how", [], []
        for c in BOOK.conferences(y):
            yield y, "conference", [], [c]
        for t in picks:
            yield y, "team", [t], []
            yield y, "game", [t], []
        for a, b in zip(picks, picks[1:]):
            yield y, "compare", [a, b], []
            yield y, "predict", [a, b], []
        # every pair of teams that played each other, in a slice of the season
        for t in order[:20]:
            for g in BOOK.games(t, y)[-3:]:
                if g[1] in r:
                    yield y, "game", [t, g[1]], []


def test_every_season():
    n = 0
    for y, intent, teams, confs in cases():
        text = R.reply(BOOK, intent, teams, confs, y)
        assert_ok(text, y, f"{y} {intent} {teams} {confs}")
        n += 1
    assert n > 500, n


def test_rules_catch_mistakes():
    assert R.check("Utah has the best score")            # rating, never score
    assert R.check("TRUECFB top 5")                       # the name
    assert R.check("Truecfb top 5")
    assert R.check("see truecfb.com")                     # links cost $0.20
    assert R.check("thanks @someone")                     # no automated mentions
    assert R.check("#GoUtes")                             # no hashtags in replies
    assert R.check("x" * 281)
    assert not R.check("Utah #3 · Team Rating 76.2 · 11-0")  # a rank is not a hashtag


def test_unanswerable():
    for args in [("team", ["Not A Team"]), ("compare", []), ("conference", [], []), ("skip", [])]:
        try:
            R.reply(BOOK, *args)
        except R.Unanswerable:
            continue
        raise AssertionError(f"{args} should be unanswerable")
    try:
        R.reply(BOOK, "top", season=1999)
    except R.Unanswerable:
        pass
    else:
        raise AssertionError("1999 is not rated")


def test_current_season_wording():
    text = R.reply(BOOK, "team", ["Georgia"])
    assert "TrueCFB v1.0" in text and "Team Rating" in text


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
