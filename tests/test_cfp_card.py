"""Tests for the "TrueCFB vs the CFP ranking" card and post (src/cfp_card.py). No X, no keys.

  python tests/test_cfp_card.py        (or: python -m pytest tests)

Checks the post fits X and has no link (X charges $0.20 for a post with one), the alt text fits X, every number in the post and alt text is one the engine
published in site/rankings.json, the brand words hold, and the same snapshot always draws the same card.
"""
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import cfp_card as C  # noqa: E402
import game_impact as GI  # noqa: E402

SITE, DATA = os.path.join(ROOT, "site"), os.path.join(ROOT, "data")


def snap():
    s = C.snapshot(SITE, DATA)
    if s is None:   # the current point has no CFP ranking (before the first one, or a week between)
        print("skipped: no CFP ranking at the current point")
    return s


def published(s):
    R = json.load(open(os.path.join(SITE, "rankings.json")))
    out = {str(R["season"]), "12", "25"} | set(re.findall(r"\d+", R["point"]))
    for t in R["teams"]:
        for k in ("rank", "cfp_rank", "wins", "losses"):
            if t[k] is not None:
                out.add(str(t[k]))
        out.add(f"{t['rating']:.1f}")
    return out


def test_post_and_alt():
    s = snap()
    if s is None:
        return
    post, alt = C.post_text(s), C.alt_text(s)
    assert GI.weighted_length(post) <= GI.MAX_POST, GI.weighted_length(post)
    # The same pattern as reply_templates.check: a bare domain is a link to X too.
    assert not re.search(r"https?://|www\.|\.(com|org|net|io)\b", post, re.I), "the post has a link"
    assert "@" not in post
    assert len(alt) <= 1000, len(alt)
    ok = published(s)
    for text in (post, alt):
        nums = re.findall(r"\d+(?:\.\d)?", text)
        bad = [n for n in nums if n not in ok]
        assert not bad, f"numbers not from the engine: {bad}"
        assert "TRUECFB" not in text and "Truecfb" not in text
        assert not re.search(r"\bscore", text, re.I)


def test_render_is_deterministic():
    s = snap()
    if s is None:
        return
    a, b = C.render(s), C.render(json.loads(json.dumps(s)))   # as saved in drafts.json and read back
    assert a.size == (2400, 1350)
    assert a.tobytes() == b.tobytes()


if __name__ == "__main__":
    test_post_and_alt()
    test_render_is_deterministic()
    print("ok")
