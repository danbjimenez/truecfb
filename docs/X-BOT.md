# The @truecfb X bot

Live since 23 Nov 2026. After every FBS final, Dan gets a draft in Telegram: the result card plus a short post, with **Post to X** and **Skip** buttons. Nothing is posted without his tap. The site's numbers also update after every game.

**No AI in the loop.** The engine does the math, a fixed template writes the post, and the card is drawn from the same numbers. About $0.02 per post in X fees (post $0.015 + alt text $0.005).

## The post

```
FINAL: Tennessee 27, LSU 13
Matchup Rating 135
Tennessee #8 → #7 · LSU #18 → #21
#GoVols #GeauxTigers
```

No links (a link raises the X fee to $0.20) and no account mentions (X's automation rules do not allow automated mentions of accounts that did not opt in), so teams get hashtags instead. The card holds the detail; the long text version (`game_impact.post_text`) is the image's alt text.

## How it runs

1. **Cloudflare Worker** (`worker/index.js`, the same `truecfb` Worker that serves the site; `wrangler.jsonc`)
   - Cron every 5 minutes. Inside the game window (noon to 4am US Eastern) it checks the CollegeFootballData live scoreboard: every run on Saturdays, every third run on other days. About 2,600 calls a month, within the 5,000 on CFBD Tier 1.
   - New finals not in `site/live.json` start `game-final.yml` on GitHub.
   - `POST /hooks/telegram` takes Dan's button taps: checks the secret header (first 40 hex of SHA-256 of the bot token) and Dan's chat id, removes the buttons, and starts `post-to-x.yml`. Skip just marks the draft.
   - The Worker never holds the X keys and never computes a rating.
2. **`.github/workflows/game-final.yml`**: downloads data, adds same-day finals from the CFBD API (`src/fill_live_finals.py`), re-runs every season (`run_all.py`), drafts posts for new finals (`src/bot_drafts.py` → `game_impact.py`, `card.py`), commits site numbers and `data/bot/drafts.json`, then sends the drafts to Telegram. Shares the `site-data` queue with the scheduled refresh.
3. **`.github/workflows/post-to-x.yml`**: redraws the same card from the saved result, uploads it (X v2 media upload with OAuth 1.0a; falls back to v1.1), sets the alt text, posts, records it in `data/bot/posted.json`, and replies in Telegram with the link. A game is never posted twice.
4. **`.github/workflows/telegram-setup.yml`**: one-time setup. Without a chat id it messages the chat id to whoever wrote to the bot (inside Telegram, not the public logs); with one, it registers the webhook.

From final whistle to draft: about 5 to 10 minutes.

## Accounts and secrets

- X developer app `truecfb-bot` under @truecfb: pay-per-use credits, OAuth 1.0a Read and write. The account carries X's automated label.
- CollegeFootballData Patreon Tier 1 ($1/mo) on the same email as the API key (live scoreboard).
- Telegram bot `truecfb_bot`.
- **GitHub secrets:** `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_SECRET`, `CFBD_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
- **Cloudflare secrets** (Production only): `CFBD_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GITHUB_DISPATCH_TOKEN` (fine-grained token `truecfb-worker-dispatch`: this repo only, Actions read/write; **expires in about a year**, then the Worker cannot start jobs).

## Hashtags

`data/team_hashtags.json`: one tag per FBS team (138). A fan rallying cry where it is well established and points to one team (91); otherwise the plain team name. Built from general knowledge plus a couple of published lists, not checked team by team. Worth a look: South Carolina, Clemson, NC State, South Florida, Washington, Rutgers. Tags never affect a rating; PRs welcome.

## X rules this is built around

- Automated informational posts are allowed; automated mentions of accounts that did not opt in are not.
- Self-serve API replies are only accepted when the author tagged or quoted @truecfb (since 23 Feb 2026).
- AI reply bots: as of 23 Nov 2026 the Help Center automation rules still require X's prior written approval, while the developer docs dropped that on 17 Nov 2026. See `docs/REPLY-BOT.md` for the reply bot plan.
