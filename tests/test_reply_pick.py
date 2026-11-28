"""A post Dan picks in Telegram: drafted as a quote post (or a reply if it tags @truecfb), with the right
button, and posted the right way. X, Telegram and the model are stand-ins. Run: python tests/test_reply_pick.py"""
import json
import os
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import reply_agent as A  # noqa: E402
import reply_bot as RB  # noqa: E402

SEEN = {}


class Resp:
    def __init__(self, code, body):
        self.status_code, self._body = code, body

    def json(self):
        return self._body


def setup(text, mentions=()):
    bot, site = tempfile.mkdtemp(), tempfile.mkdtemp()
    os.environ.update(REPLY_POST="555", REPLY_NOTE="the playoff angle", REPLIES_LIVE="true", TELEGRAM_CHAT_ID="1")
    RB.auth = lambda: None
    RB.my_id = lambda a: "99"
    post = {"id": "555", "author_id": "7", "text": text, "conversation_id": "555", "images": [],
            "entities": {"mentions": [{"id": m} for m in mentions]}}
    RB.one_post = lambda a, pid: ([dict(post)], {})
    RB.R.Book = lambda *a: None

    def answer(book, text, parent, images=(), picked=None):
        SEEN["picked"] = picked
        return {"status": "drafted", "reply": "BYU can't climb on its own this week.", "note": "", "by": "stand-in",
                "lookups": ["what_if(BYU)"], "problems": [], "rejected": None}
    A.answer = answer
    return bot, site


def run_draft(bot, site):
    out = os.path.join(bot, "outbox.json")
    RB.draft(site, bot, out)
    return json.load(open(out)), json.load(open(os.path.join(bot, "replies.json")))


def test_quote_when_the_post_does_not_tag_us():
    bot, site = setup("BYU is in, right?")
    outbox, state = run_draft(bot, site)
    assert SEEN["picked"] == {"mode": "quote", "note": "the playoff angle"}
    assert outbox[0]["id"] == "555" and outbox[0]["mode"] == "quote" and "Quote post draft" in outbox[0]["text"]
    assert "Your note: the playoff angle" in outbox[0]["text"]
    assert state["items"]["555"]["mode"] == "quote" and state["newest"] is None
    assert not os.path.exists(os.path.join(site, "replies.json"))      # not a mention: the Worker's record is untouched
    sent = []
    RB.tg = lambda method, body: sent.append(body)
    RB.send(os.path.join(bot, "outbox.json"))
    assert sent[0]["reply_markup"]["inline_keyboard"][0][0] == {"text": "Post as quote", "callback_data": "rquote:555"}
    # Posting: a quote post, no reply field
    told, bodies = [], []
    RB.tell = lambda text, msg=None: told.append(text)
    RB.requests.get = lambda *a, **k: Resp(200, {"data": {"id": "555", "author_id": "7", "entities": {}}})
    RB.requests.post = lambda url, json=None, **k: bodies.append(json) or Resp(201, {"data": {"id": "777"}})
    RB.post(bot, "555", None, "quote")
    assert bodies == [{"text": "BYU can't climb on its own this week.", "quote_tweet_id": "555"}], bodies
    assert told[-1].startswith("Quote posted: https://x.com/truecfb/status/777")
    again = []
    RB.tell = lambda text, msg=None: again.append(text)
    RB.post(bot, "555", None, "quote")                                   # never twice
    assert again[-1].startswith("Already replied")


def test_reply_when_the_post_tags_us():
    bot, site = setup("@truecfb BYU is in, right?", mentions=["99"])
    outbox, state = run_draft(bot, site)
    assert SEEN["picked"]["mode"] == "reply" and outbox[0]["mode"] == "reply"
    sent = []
    RB.tg = lambda method, body: sent.append(body)
    RB.send(os.path.join(bot, "outbox.json"))
    assert sent[0]["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "rpost:555"


def test_own_post_and_drafted_post_are_not_drafted_again():
    bot, site = setup("BYU is in, right?")
    run_draft(bot, site)
    outbox, _ = run_draft(bot, site)
    assert outbox[0]["id"] is None and "already in Telegram" in outbox[0]["text"], outbox


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
