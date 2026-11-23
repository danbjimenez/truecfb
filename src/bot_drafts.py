"""TrueCFB X bot: draft a post for every new final and send the drafts to Telegram for approval.

  draft:  bot_drafts.py draft <games.csv> <src_dir> <season> <bot_dir> <site_dir> [game ids, comma-separated]
          Finds finals not handled yet (the ids given, plus any of the season's games from the last two
          game days), runs game_impact for each, saves the drafts in <bot_dir>/drafts.json, and lists
          handled games in <site_dir>/live.json, which the Cloudflare Worker reads so it stops asking.
          Writes the ids of the new drafts to <bot_dir>/new.txt for the send step.
  send:   TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... bot_drafts.py send <bot_dir>
          Sends each new draft to Telegram as its result card (card.py) with the short post as the
          caption and Post and Skip buttons. Run it after the drafts are committed, because the post
          step reads drafts.json from the repo.

Every number in a draft comes from the engine through game_impact.py. Nothing here changes a rating.
"""
import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine as E  # noqa: E402
import game_impact as GI  # noqa: E402
import card as CARD  # noqa: E402

KEEP_DRAFTS = 400        # drafts kept in drafts.json (about five Saturdays)


def load(path, default):
    return json.load(open(path)) if os.path.exists(path) else default


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")


def draft(games_csv, src_dir, season, bot_dir, site_dir, given):
    live_path = os.path.join(site_dir, "live.json")
    live = load(live_path, {"season": season, "handled": []})
    if int(live.get("season", season)) != season:
        live = {"season": season, "handled": []}
    handled = set(int(x) for x in live["handled"])

    g = E.load_games(games_csv)
    s = g[g.season == season]
    days = sorted(s.day.unique())[-2:]
    candidates = set(int(x) for x in s[s.day.isin(days)].game_id) | (given & set(int(x) for x in s.game_id))
    new = sorted(candidates - handled)
    missing = sorted(given - set(int(x) for x in s.game_id))
    if missing:
        print("final on the scoreboard but not in the games table yet:", missing)

    drafts = load(os.path.join(bot_dir, "drafts.json"), {})
    made = []
    if new:
        F = E.margin_curve(g); V = E.home_edge(g, F)
        prior = GI.prior_for(g, F, V, season)
        teams = GI.season_teams(s)
        for gid in new:
            row = s[s.game_id == gid].iloc[0]
            res = GI.impact(s[s.day <= row.day], gid, F, V, prior, teams)
            text = GI.short_post(res)
            # The card is drawn again from "impact" when it is posted, so the same image goes out.
            drafts[str(gid)] = {"post": text, "length": GI.weighted_length(text), "alt": GI.post_text(res),
                                "day": res["day"], "matchup_rating": res["matchup_rating"],
                                "teams": [t["team"] for t in res["teams"]], "impact": res,
                                "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
            made.append(gid)
            print(f"--- draft {gid} ({drafts[str(gid)]['length']} of {GI.MAX_POST})\n{text}\n")
    # Keep the newest drafts only.
    if len(drafts) > KEEP_DRAFTS:
        drafts = dict(sorted(drafts.items(), key=lambda kv: kv[1]["created"])[-KEEP_DRAFTS:])
    save(os.path.join(bot_dir, "drafts.json"), drafts)
    live["handled"] = sorted(handled | set(new))
    live["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    save(live_path, live)
    with open(os.path.join(bot_dir, "new.txt"), "w") as f:
        f.write("\n".join(str(x) for x in made))
    print(f"new drafts: {len(made)} | handled this season: {len(live['handled'])}")


def send_card(gid, d):
    """One draft to Telegram: the card as a photo, the short post as the caption, and the buttons."""
    import io
    import requests
    png = io.BytesIO()
    CARD.render(d["impact"]).save(png, format="PNG", optimize=True)
    caption = f"{d['post']}\n\n[{d['length']}/280 \u00b7 game {gid}]"
    buttons = {"inline_keyboard": [[{"text": "Post to X", "callback_data": f"post:{gid}"},
                                    {"text": "Skip", "callback_data": f"skip:{gid}"}]]}
    r = requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendPhoto",
                      data={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "caption": caption,
                            "reply_markup": json.dumps(buttons)},
                      files={"photo": (f"{gid}.png", png.getvalue(), "image/png")}, timeout=60)
    r.raise_for_status()


def send(bot_dir):
    path = os.path.join(bot_dir, "new.txt")
    ids = [x for x in open(path).read().split() if x] if os.path.exists(path) else []
    if not ids:
        print("nothing to send")
        return
    if not (os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID")):
        print("::warning::TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is not set: drafts saved but not sent")
        return
    drafts = load(os.path.join(bot_dir, "drafts.json"), {})
    failed = 0
    for gid in ids:
        d = drafts.get(gid)
        if not d:
            continue
        try:
            send_card(gid, d)
        except Exception as err:  # keep going; one bad send should not block the rest
            failed += 1
            print(f"::warning::could not send draft {gid} to Telegram: {err}")
    print(f"sent {len(ids) - failed} of {len(ids)} drafts to Telegram")


def main():
    cmd = sys.argv[1]
    if cmd == "draft":
        games_csv, src_dir, season, bot_dir, site_dir = sys.argv[2:7]
        given = set(int(x) for x in (sys.argv[7] if len(sys.argv) > 7 else "").replace(" ", "").split(",") if x)
        draft(games_csv, src_dir, int(season), bot_dir, site_dir, given)
    elif cmd == "send":
        send(sys.argv[2])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
