"""TrueCFB reply bot: answer posts that tag @truecfb, in draft mode first. Plan: docs/REPLY-BOT.md.

  draft:  reply_bot.py draft <site_dir> <bot_dir> <outbox.json>
          Reads new mentions of @truecfb (newer than the last one handled), skips what should not get a
          reply, asks the model what each one asks (reply_model.py), builds the reply from the engine's
          files (reply_templates.py), and saves the drafts in <bot_dir>/replies.json. Writes the newest
          handled mention to <site_dir>/replies.json, which the Cloudflare Worker reads so it stops
          asking, and the Telegram messages to send to <outbox.json> (not committed).
  send:   reply_bot.py send <outbox.json>
          Sends each draft to Telegram with Post reply and Skip buttons (Skip only while posting is
          off). Run it after replies.json is committed: the post job reads the draft from the repo.
  post:   reply_bot.py post <bot_dir> <mention id> [telegram message id]
          Posts one approved draft as a reply to the post that tagged @truecfb. Only when REPLIES_LIVE
          is "true".

Environment: X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET (OAuth 1.0a, @truecfb);
X_USER_ID (optional; looked up once if missing); TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID;
ANTHROPIC_API_KEY or XAI_API_KEY with REPLY_PROVIDER / REPLY_MODEL (reply_model.py); REPLIES_LIVE.

The repo is public, so replies.json keeps only post ids, what the bot understood, the reply text and
what happened; never the text people wrote. Opt-outs are kept as hashes of the user id.
"""
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import requests
from requests_oauthlib import OAuth1

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reply_model as M  # noqa: E402
import reply_templates as R  # noqa: E402

HANDLE = "truecfb"
API = "https://api.x.com/2"
MAX_DRAFTS_PER_RUN = 10          # a pile-up under a popular post waits for the next run
MAX_PER_USER_PER_THREAD = 1      # one reply per person per conversation
KEEP = 2000                      # entries kept in replies.json
FIRST_LOOK_HOURS = 2             # with no history yet, only mentions this recent count
OPT_OUT = re.compile(r"^\s*(stop|unsubscribe|opt[\s-]?out)\b", re.I)


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(path, default):
    return json.load(open(path)) if os.path.exists(path) else default


def save(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")


def who(user_id):
    """A user id as stored in the public repo: a short hash, enough to match, not to look up."""
    return hashlib.sha256(f"truecfb:{user_id}".encode()).hexdigest()[:16]


def live():
    return os.environ.get("REPLIES_LIVE", "").strip().lower() == "true"


def auth():
    return OAuth1(os.environ["X_API_KEY"], os.environ["X_API_SECRET"],
                  os.environ["X_ACCESS_TOKEN"], os.environ["X_ACCESS_SECRET"])


def x_error(r):
    try:
        j = r.json()
        return f"{j.get('title', '')} {j.get('detail', '')}".strip() or json.dumps(j.get("errors", j))[:200]
    except ValueError:
        return r.text[:200]


def scrub(err):
    """Error text without the Telegram token (requests puts the URL in its errors)."""
    text = str(err)
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    return text.replace(token, "<token>") if token else text


# ---------- Telegram ----------

def tg(method, body):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    r = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=body, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Telegram {method} {r.status_code}: {r.text[:200]}")
    return r.json()


def tell(text, reply_to=None):
    if not (os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID")):
        print(text)
        return
    body = {"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text[:4000],
            "link_preview_options": {"is_disabled": True}}
    if reply_to:
        body["reply_parameters"] = {"message_id": int(reply_to), "allow_sending_without_reply": True}
    try:
        tg("sendMessage", body)
    except Exception as err:
        print(f"::warning::Telegram message failed: {scrub(err)}")


# ---------- X ----------

def my_id(a):
    uid = os.environ.get("X_USER_ID", "").strip()
    if uid:
        return uid
    r = requests.get(f"{API}/users/me", auth=a, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"X users/me {r.status_code}: {x_error(r)}")
    uid = r.json()["data"]["id"]
    print(f"@{HANDLE} user id: {uid} (set it as X_USER_ID: a GitHub variable, and in Cloudflare for the Worker)")
    return uid


def mentions(a, uid, since_id):
    """New posts that mention @truecfb, oldest first, with the posts they reply to or quote."""
    params = {"max_results": 100,
              "tweet.fields": "author_id,conversation_id,created_at,referenced_tweets,entities,possibly_sensitive,in_reply_to_user_id",
              "expansions": "referenced_tweets.id"}
    if since_id:
        params["since_id"] = since_id
    else:
        start = datetime.now(timezone.utc) - timedelta(hours=FIRST_LOOK_HOURS)
        params["start_time"] = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    posts, above, token = [], {}, None
    for _ in range(5):   # at most 500 mentions a run
        if token:
            params["pagination_token"] = token
        r = requests.get(f"{API}/users/{uid}/mentions", params=params, auth=a, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"X mentions {r.status_code}: {x_error(r)}")
        j = r.json()
        posts += j.get("data", [])
        above.update({t["id"]: t for t in j.get("includes", {}).get("tweets", [])})
        token = j.get("meta", {}).get("next_token")
        if not token:
            break
    return sorted(posts, key=lambda p: int(p["id"])), above


def parent_of(post, above):
    for ref in post.get("referenced_tweets", []):
        if ref["type"] in ("replied_to", "quoted") and ref["id"] in above:
            return above[ref["id"]]
    return None


def question_text(text):
    """The post without the @handles at its start (replies begin with them)."""
    return re.sub(r"^(\s*@\w+)+\s*", "", text).strip()


# ---------- draft ----------

def draft(site_dir, bot_dir, outbox_path):
    state_path = os.path.join(bot_dir, "replies.json")
    state = load(state_path, {"newest": None, "items": {}})
    optout_path = os.path.join(bot_dir, "optout.json")
    optout = set(load(optout_path, {"users": []})["users"])
    a = auth()
    uid = my_id(a)
    posts, above = mentions(a, uid, state.get("newest"))
    print(f"{len(posts)} new mention(s)")
    book = R.Book(site_dir, bot_dir)
    teams = sorted({t for y in book.seasons for t in book.teams(y)})
    confs = sorted({c for y in book.seasons for c in book.conferences(y)})
    seen_threads = {(i.get("user"), i.get("thread")) for i in state["items"].values() if i.get("status") in ("drafted", "posted")}
    outbox, skipped, drafted = [], [], 0

    for p in posts:
        pid, user = p["id"], who(p.get("author_id", ""))
        state["newest"] = pid if not state.get("newest") or int(pid) > int(state["newest"]) else state["newest"]
        if pid in state["items"] or p.get("author_id") == uid:
            continue
        if any(ref["type"] == "retweeted" for ref in p.get("referenced_tweets", [])):
            continue   # a repost of someone else's mention: they did not tag @truecfb themselves
        item = {"at": now(), "user": user, "thread": p.get("conversation_id")}
        state["items"][pid] = item
        text = question_text(p.get("text", ""))
        link = f"https://x.com/i/status/{pid}"
        if OPT_OUT.match(text):
            optout.add(user); item["status"] = "opted_out"
            skipped.append(f"opted out (no more replies to them): {link}")
            continue
        if user in optout:
            item["status"] = "skipped"; item["why"] = "opted out"
            continue
        if p.get("possibly_sensitive"):
            item["status"] = "skipped"; item["why"] = "marked sensitive"
            skipped.append(f"marked sensitive: {link}")
            continue
        if (user, item["thread"]) in seen_threads and MAX_PER_USER_PER_THREAD == 1:
            item["status"] = "skipped"; item["why"] = "already answered them in this thread"
            skipped.append(f"already answered them in this thread: {link}")
            continue
        if drafted >= MAX_DRAFTS_PER_RUN:
            item["status"] = "skipped"; item["why"] = "too many at once"
            skipped.append(f"too many at once: {link}")
            continue
        par = parent_of(p, above)
        par_text = question_text(par.get("text", "")) if par else ""
        try:
            got, info = M.read(text, par_text, teams, confs, book.seasons, book.current)
        except Exception as err:
            item["status"] = "failed"; item["why"] = f"model: {str(err)[:150]}"
            skipped.append(f"model error ({str(err)[:80]}): {link}")
            continue
        item.update({"intent": got["intent"], "teams": got["teams"], "conferences": got["conferences"],
                     "season": got["season"], "model": info["model"]})
        if got["intent"] == "skip":
            item["status"] = "skipped"; item["why"] = "model: nothing to answer"   # its reason goes to Telegram only
            skipped.append(f"{got['reason'] or 'nothing to answer'}: {link}")
            continue
        try:
            reply = R.reply(book, got["intent"], got["teams"], got["conferences"], got["season"])
        except R.Unanswerable as why:
            item["status"] = "skipped"; item["why"] = str(why)
            skipped.append(f"{why}: {link}")
            continue
        problems = R.check(reply)
        if problems:
            item["status"] = "failed"; item["why"] = "; ".join(problems)
            skipped.append(f"template broke a rule ({'; '.join(problems)}): {link}")
            continue
        item.update({"status": "drafted", "reply": reply})
        seen_threads.add((user, item["thread"]))
        drafted += 1
        read_as = f"{got['intent']} · {', '.join(got['teams'] + got['conferences']) or '-'}"
        if got["season"]:
            read_as += f" · {got['season']}"
        outbox.append({"id": pid, "text": "\n".join([
            "Reply draft" + ("" if live() else " (draft mode: posting is off)"),
            "",
            f"Asked: {text[:500]}",
            *([f"Above: {par_text[:500]}"] if par_text else []),
            link,
            f"Read as: {read_as} ({info['model']})",
            f"Why: {got['reason']}" if got["reason"] else "",
            "",
            reply,
        ]).replace("\n\n\n", "\n\n")})

    if skipped:
        outbox.append({"id": None, "text": "Mentions not drafted:\n" + "\n".join(f"- {s}" for s in skipped)})
    # keep the newest entries only
    if len(state["items"]) > KEEP:
        state["items"] = dict(sorted(state["items"].items(), key=lambda kv: int(kv[0]))[-KEEP:])
    save(state_path, state)
    save(optout_path, {"about": "Hashes of users who asked @truecfb's reply bot to stop (reply_bot.who).",
                       "users": sorted(optout)})
    save(os.path.join(site_dir, "replies.json"), {"newest": state.get("newest"), "updated": now()})
    save(outbox_path, outbox)
    print(f"{drafted} draft(s), {len(skipped)} not drafted")


def send(outbox_path):
    outbox = load(outbox_path, [])
    chat = os.environ["TELEGRAM_CHAT_ID"]
    for m in outbox:
        body = {"chat_id": chat, "text": m["text"][:4000], "link_preview_options": {"is_disabled": True}}
        if m["id"]:
            buttons = [{"text": "Skip", "callback_data": f"rskip:{m['id']}"}]
            if live():
                buttons.insert(0, {"text": "Post reply", "callback_data": f"rpost:{m['id']}"})
            body["reply_markup"] = {"inline_keyboard": [buttons]}
        try:
            tg("sendMessage", body)
        except Exception as err:
            print(f"::warning::could not send to Telegram: {scrub(err)}")
    print(f"sent {len(outbox)} message(s)")


# ---------- post ----------

def post(bot_dir, mention_id, msg_id=None):
    mention_id = str(int(mention_id))
    if not live():
        tell("Not posted: posting is off (set the GitHub variable REPLIES_LIVE to true).", msg_id)
        sys.exit("REPLIES_LIVE is not true")
    state_path = os.path.join(bot_dir, "replies.json")
    state = load(state_path, {"newest": None, "items": {}})
    item = state["items"].get(mention_id)
    if not item or not item.get("reply"):
        tell(f"No reply draft for {mention_id}. Nothing posted.", msg_id)
        sys.exit("no draft")
    if item.get("status") == "posted":
        tell(f"Already replied: https://x.com/{HANDLE}/status/{item['reply_id']}", msg_id)
        return
    optout = set(load(os.path.join(bot_dir, "optout.json"), {"users": []})["users"])
    if item.get("user") in optout:
        tell("Not posted: they asked the bot to stop.", msg_id)
        sys.exit("opted out")

    a = auth()
    uid = my_id(a)
    # The post must still be there, and it must tag @truecfb (X only allows replies when it does).
    r = requests.get(f"{API}/tweets/{mention_id}", auth=a, timeout=30,
                     params={"tweet.fields": "author_id,entities,in_reply_to_user_id"})
    data = r.json().get("data") if r.status_code == 200 else None
    if not data:
        item["status"] = "gone"; save(state_path, state)
        tell("Not posted: the post that tagged @truecfb is gone.", msg_id)
        return
    tagged = {m.get("id") for m in data.get("entities", {}).get("mentions", [])}
    if uid not in tagged:
        tell("Not posted: that post no longer tags @truecfb.", msg_id)
        sys.exit("not tagged")
    # Reply to the asker only: leave out everyone else the thread would mention by default.
    others = (tagged | {data.get("in_reply_to_user_id")}) - {data.get("author_id"), uid, None}
    body = {"text": item["reply"], "reply": {"in_reply_to_tweet_id": mention_id}}
    if others:
        body["reply"]["exclude_reply_user_ids"] = sorted(others)
    r = requests.post(f"{API}/tweets", json=body, auth=a, timeout=30)
    if r.status_code not in (200, 201):
        why = x_error(r)
        item["status"] = "refused"; item["why"] = f"{r.status_code} {why}"[:200]; save(state_path, state)
        tell(f"X refused the reply ({r.status_code}): {why}. Check the account before posting more.", msg_id)
        sys.exit(f"X API error {r.status_code}: {why}")
    reply_id = r.json()["data"]["id"]
    item.update({"status": "posted", "reply_id": reply_id, "posted": now()})
    save(state_path, state)
    url = f"https://x.com/{HANDLE}/status/{reply_id}"
    print("replied:", url)
    tell(f"Replied: {url}", msg_id)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "draft":
        draft(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "send":
        send(sys.argv[2])
    elif cmd == "post":
        post(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] else None)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
