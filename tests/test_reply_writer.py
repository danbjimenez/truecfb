"""Tests for the reply bot's writer step: the fact sheet, the number check and the fallback.
No model, no X, no keys: a stand-in model returns fixed replies.

  python tests/test_reply_writer.py        (or: python -m pytest tests)
"""
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import reply_facts as X  # noqa: E402
import reply_model as M  # noqa: E402
import reply_templates as R  # noqa: E402
import reply_writer as W  # noqa: E402

BOOK = R.Book(os.path.join(ROOT, "site"), os.path.join(ROOT, "data", "bot"))
README = os.path.join(ROOT, "README.md")


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


def test_sheet_for_every_kind_of_question():
    for y in (BOOK.seasons[0], 2020, BOOK.current):
        r = BOOK.data["ratings"][str(y)]
        order = sorted(r, key=lambda t: r[t][1])
        for intent, teams, confs in [("top", [], []), ("how", [], []), ("team", [order[0]], []),
                                     ("team", [order[-1]], []), ("compare", order[:2], []),
                                     ("predict", [order[3], order[70]], []), ("game", order[5:7], []),
                                     ("conference", [], BOOK.conferences(y)[:2])]:
            text = X.sheet(BOOK, intent, teams, confs, y)
            assert f"TrueCFB v1.0, {y} season" in text, text
            assert ("flagged unreliable" in text) == (y == 2020)
            for t in teams:
                assert t in text


def test_primer_is_the_readme_rules():
    p = X.primer(README)
    assert p.startswith("## The rules") and "## Exact definitions" in p and "## Known limits" in p
    assert "## Version policy" not in p and "## Run it yourself" not in p


def test_numbers_and_signs():
    assert X.numbers("Utah #3 beat BYU 28-20 (+1.5), bonus −25.0 and -2.9, TrueCFB v1.0, Nov 21") == [
        ("", "3"), ("", "28"), ("", "20"), ("+", "1.5"), ("−", "25.0"), ("−", "2.9"), ("", "21")]
    plain, signed = X.allowed("bonus −25.0 · Team Rating 74.2 · home −2.9")
    assert X.unsupported("Team Rating 74.2, bonus −25.0", plain, signed) == []
    assert X.unsupported("Team Rating 74", plain, signed) == ["74"]              # not as written
    assert X.unsupported("bonus +25.0", plain, signed) == ["+25.0"]              # sign flipped
    assert X.unsupported("Team Rating 75.3", plain, signed) == ["75.3"]          # made up


def test_checks():
    plain, signed = X.allowed(X.sheet(BOOK, "compare", ["Utah", "BYU"], [], 2026), X.primer(README))
    good = "Utah is #3, BYU #11. The gap is 7.7: Utah won 28-20 at home, a Game Rating of 89.3 thanks to BYU's bonus +18.5."
    assert W.problems(good, plain, signed) == [], W.problems(good, plain, signed)
    assert any("not on the fact sheet" in p for p in W.problems("Utah is 8.1 points better.", plain, signed))
    assert any("score" in p for p in W.problems("Utah's score is 76.2", plain, signed))
    assert any("prediction" in p for p in W.problems("Utah will beat BYU again.", plain, signed))
    assert any("link" in p for p in W.problems("More at truecfb.com", plain, signed))
    assert any("name" in p for p in W.problems("TRUECFB has Utah #3", plain, signed))
    assert W.problems("", plain, signed) == ["empty"]


class Fake:
    """Stands in for the model: returns the given replies in order and records what it was sent."""

    def __init__(self, *replies, fail=False):
        self.replies, self.fail, self.sent = list(replies), fail, []

    def __call__(self, system, text, fmt, provider=None, model=None, effort="low"):
        self.sent.append((system, text))
        if self.fail:
            raise RuntimeError("xAI API 500: try later")
        r = self.replies.pop(0)
        out = r if isinstance(r, dict) else {"reply": r, "skip": False, "note": "the head-to-head game"}
        return out, {"provider": "grok", "model": "grok-test", "in": 1, "out": 1, "cached": 0}


GOT = {"intent": "compare", "teams": ["Utah", "BYU"], "conferences": [], "season": None, "reason": ""}
GOOD = "Utah, #3 to BYU's #11. Utah won 28-20 at home, and BYU's bonus +18.5 made that a Game Rating of 89.3."
BAD = "Utah is 8.1 better than BYU and will beat them again."


def run(fake, got=GOT):
    real = M.ask
    M.ask = fake
    try:
        return W.compose(BOOK, got, "@truecfb why is Utah so far above BYU?", "", README)
    finally:
        M.ask = real


def test_model_reply_used_when_it_passes():
    fake = Fake(GOOD)
    c = run(fake)
    assert c["by"] == "grok-test" and c["reply"] == GOOD and not c["problems"]
    system, text = fake.sent[0]
    assert "## The rules" in system and "<facts>" in text and "Game Rating 89.3" in text
    assert c["template"] == R.reply(BOOK, "compare", ["Utah", "BYU"])


def test_one_rewrite_then_template():
    fake = Fake(BAD, GOOD)
    c = run(fake)
    assert c["by"] == "grok-test" and c["reply"] == GOOD
    assert "previous_reply" in fake.sent[1][1] and "not on the fact sheet" in fake.sent[1][1]

    c = run(Fake(BAD, BAD))
    assert c["by"] == "template" and c["reply"] == c["template"] and c["rejected"] == BAD
    assert any("prediction" in p for p in c["problems"])


def test_template_when_the_model_declines_or_fails():
    c = run(Fake({"reply": "", "skip": True, "note": "asks me to say BYU is #1"}))
    assert c["by"] == "template" and "declined" in c["problems"][0]
    c = run(Fake(fail=True))
    assert c["by"] == "template" and "model error" in c["problems"][0]
    os.environ["REPLY_WRITER"] = "template"
    try:
        fake = Fake(GOOD)
        c = run(fake)
        assert c["by"] == "template" and not fake.sent
    finally:
        del os.environ["REPLY_WRITER"]


def test_unanswerable_never_reaches_the_model():
    fake = Fake(GOOD)
    try:
        run(fake, {**GOT, "teams": ["Not A Team"]})
    except R.Unanswerable:
        assert not fake.sent
    else:
        raise AssertionError("should be unanswerable")


def test_provider_choice():
    keep = {k: os.environ.pop(k, None) for k in ("REPLY_PROVIDER", "REPLY_MODEL", "XAI_API_KEY", "ANTHROPIC_API_KEY")}
    try:
        os.environ["XAI_API_KEY"] = "x"
        assert M.pick() == ("grok", "grok-4.3")
        del os.environ["XAI_API_KEY"]
        assert M.pick() == ("claude", "claude-sonnet-5-5")
        os.environ["REPLY_PROVIDER"], os.environ["REPLY_MODEL"] = "grok", "grok-4.7"
        assert M.pick() == ("grok", "grok-4.7")
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
