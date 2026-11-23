"""TrueCFB X bot: post one approved draft to X as @truecfb, then confirm in Telegram.

Usage: bot_post.py <bot_dir> <game_id> [telegram_message_id]
Needs X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET (OAuth 1.0a, the @truecfb account)
and, for the confirmation, TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.

The text posted is the draft saved in <bot_dir>/drafts.json, exactly as the engine wrote it; nothing
typed into Telegram can change it. A game that is already in <bot_dir>/posted.json is never posted again.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

import requests
from requests_oauthlib import OAuth1

HANDLE = "truecfb"


def load(path, default):
    return json.load(open(path)) if os.path.exists(path) else default


def tell(text, reply_to=None):
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return
    body = {"chat_id": chat, "text": text, "disable_web_page_preview": True}
    if reply_to:
        body["reply_parameters"] = {"message_id": int(reply_to), "allow_sending_without_reply": True}
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=30).read()
    except Exception as err:
        print(f"::warning::Telegram confirmation failed: {err}")


def main():
    bot_dir, gid = sys.argv[1], str(int(sys.argv[2]))
    msg_id = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else None
    drafts = load(os.path.join(bot_dir, "drafts.json"), {})
    posted_path = os.path.join(bot_dir, "posted.json")
    posted = load(posted_path, {})
    if gid in posted:
        tell(f"Already posted: https://x.com/{HANDLE}/status/{posted[gid]['post_id']}", msg_id)
        print("already posted; nothing to do")
        return
    d = drafts.get(gid)
    if not d:
        tell(f"No draft found for game {gid}. Nothing posted.", msg_id)
        sys.exit(f"no draft for game {gid}")

    auth = OAuth1(os.environ["X_API_KEY"], os.environ["X_API_SECRET"],
                  os.environ["X_ACCESS_TOKEN"], os.environ["X_ACCESS_SECRET"])
    r = requests.post("https://api.x.com/2/tweets", json={"text": d["post"]}, auth=auth, timeout=30)
    if r.status_code not in (200, 201):
        try:
            j = r.json(); why = f"{j.get('title', '')} {j.get('detail', '')}".strip() or r.text[:200]
        except ValueError:
            why = r.text[:200]
        tell(f"X refused the post for game {gid} ({r.status_code}): {why}", msg_id)
        sys.exit(f"X API error {r.status_code}: {why}")
    post_id = r.json()["data"]["id"]
    posted[gid] = {"post_id": post_id, "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    with open(posted_path, "w") as f:
        json.dump(posted, f, indent=1)
        f.write("\n")
    url = f"https://x.com/{HANDLE}/status/{post_id}"
    print("posted:", url)
    tell(f"Posted: {url}", msg_id)


if __name__ == "__main__":
    main()
