# TrueCFB: working notes for Claude

TrueCFB is Dan Jimenez's open-source college football ranking: every FBS team rated on results alone, with a public, deterministic formula (2026.2, 27 Nov 2026; versions are year.release, and 2026.1 was released as v1.0 on 21 Nov 2026). Live at truecfb.com, posts as @truecfb on X. This repo is the whole project: formula, site, data jobs and the X bot.

Read before changing things:
- `README.md`: the rules, exact definitions, anchor games, how to run it.
- `docs/DESIGN.md`: goals, why each setting has its value, rejected ideas, future-version ideas.
- `docs/BRAND.md`: naming, wording and visual rules (the site, the cards, the posts).
- `docs/X-BOT.md`: how the X bot runs, accounts, secrets, X's rules.

## Rules that never bend

- **The formula is fixed at 2026.2.** No change to a rule or a number without a new version, recorded in the README's version history, with every season re-run. Display, data plumbing and site work are not formula changes, but must leave every published number unchanged; check that before calling it done.
- **Write the name TrueCFB** (never all capitals) and the version as **2026.2** (year.release, no "v"; code reads it from `engine.VERSION`).
- **Rating, never score.** Game Rating (one team, one game), Team Rating, Conference Rating, Matchup Rating (the pot two teams split). "Score" means points on the scoreboard only.
- **Blind to the jersey:** nothing but results goes into a rating. No mascots; team logos only beside team names on the result card (Dan, 27 Nov 2026); team colors only as each team's line on the Top 25 chart and the CFP comparison card. Blue = higher, orange = lower; never red/green as a verdict (the better/worse standard is in `docs/BRAND.md`).
- **Every number in a post or card comes from the engine.** Result posts and cards use fixed templates. Replies (since 24 Nov 2026, Dan's call) are written by a model that looks up the engine's published numbers (any college football question since 25 Nov), and code rejects any reply with a number those lookups did not return. No model ever decides a number.
- 2020 is a throwaway year: flagged unreliable, never special-cased.

## Map

| Path | What |
|---|---|
| `src/engine.py` | The formula (the only place ratings are computed) |
| `src/build_games.py`, `src/fetch_data.py`, `src/fill_live_finals.py` | Game data: public files, plus same-day finals from the CFBD API |
| `src/run_all.py` | Re-runs every season 2014 to now and writes the site's data files |
| `src/build_pages.py`, `src/templates/team.html` | Called by `run_all.py`: team pages (`site/team/<slug>.html`), the parts of `index.html` and `team.html` between `<!--gen:...-->` markers, `rankings.json`, `llms.txt`, `sitemap.xml` |
| `src/fetch_polls.py`, `src/fetch_colors.py` | AP/CFP polls and team colors (display only) |
| `src/game_impact.py` | What one game changed; post text |
| `src/card.py` | The 1200 × 675 result card |
| `src/cfp_card.py` | The weekly "TrueCFB vs the CFP ranking" card and post |
| `src/bot_drafts.py`, `src/bot_post.py` | X bot: drafts to Telegram, posting |
| `src/reply_bot.py`, `reply_agent.py`, `reply_facts.py`, `reply_book.py`, `reply_whatif.py`, `reply_model.py` | Reply bot (`docs/REPLY-BOT.md`): the model (Grok by default) answers any college football question, looking up the engine's numbers as it needs them (what-ifs re-run the engine from `site/whatif.json`); code checks every number |
| `site/` | The static site (Cloudflare serves it); `site/live.json` = finals the bot has handled |
| `worker/index.js` | Cloudflare Worker: scoreboard check, Telegram hook, X's push of mentions (`/hooks/x`; set up with `src/x_push.py`) |
| `.github/workflows/` | `refresh.yml` (3×/week + daily in Dec/Jan), `game-final.yml`, `post-to-x.yml`, `reply-draft.yml`, `post-reply.yml`, `reply-eval.yml`, `x-push.yml`, `telegram-setup.yml`, `release.yml` |
| `data/` | Polls, CFP finals, team colors, team hashtags, bot drafts and posted log (downloaded game files are not committed) |

## Running locally

```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/fetch_data.py data/schedules data/espn
python src/build_games.py data/schedules data/espn data/games.csv data/latest_poll.json
python src/run_all.py data/games.csv src data/latest_poll.json site data/cfp_final.json data/polls
python src/game_impact.py data/games.csv src 2026 --text      # latest game day's posts
```

A full re-run takes about 15 seconds. After changing anything in `src/`, re-run and confirm the site's data files are unchanged (`git diff --stat site/`) unless a change was intended. Team pages and the generated parts of `index.html` and `team.html` are rewritten on every run: edit `src/templates/team.html` or `src/build_pages.py`, not the output.

Known local difference: on an Apple Silicon Mac, the week-1 order of teams tied at exactly 25.0 (teams new to FBS) can differ from what the GitHub jobs publish, because `sort_values("rating")` uses numpy's default sort, which does not keep ties in a fixed order across CPUs. Ratings are identical. Only `rank_{year}.json` week 1, `sched_{year}.json` `start` and `history.json` show it; anything else in the diff is real.

## How we work

- Branch, open a PR, and merge when Dan says "merge". Cloudflare deploys `main` automatically (branch previews build too).
- The jobs commit to `main` on their own (ratings, drafts, posted log). Pull before starting work.
- Dan prefers short, scannable answers and honest assessments over reassurance.

## Open work

- **Selection day, Sun 6 Dec 2026:** add the final 2026 CFP ranking to `data/cfp_final.json` (key `"2026"`, 25 names in order, spelled as in `data/polls/2026.json`). The date is already in `run_all.py`; that one entry switches 2026 to count bowl and playoff games. Until then the current season counts regular-season games only.
- **Reply bot:** live since 26 Nov 2026 (`REPLIES_LIVE` on; every reply still needs Dan's Post reply tap). Dan chose not to file X's written-approval request (X's 17 Nov developer docs say none is needed). Next: push mentions to the Worker (X Activity API) instead of polling.
- **Security settings (Dan, from the 23 Nov 2026 review):** in GitHub, an `x-bot` environment limited to `main` holding the four `X_*` secrets (then add `environment: x-bot` to post-to-x.yml), a ruleset on `main` blocking force-push and deletion, GitHub-owned actions only with SHA pinning required, email privacy, Dependabot alerts on. In Cloudflare, a WAF rule allowing `/hooks/telegram` only from Telegram's IP ranges (`149.154.160.0/20`, `91.108.4.0/22`).
- **Site content from the agent** (later): beyond X posts, Dan wants the agent to write content for the site and keep the data fresh. Setup stays Claude + Cloudflare + GitHub Actions; self-hosting on a Mac mini was considered and dropped.
- **Preseason tie order:** fix the unstable sort above (`kind="stable"` or a name tiebreak) so local runs match the jobs. It changes the published order of tied teams once, so it needs Dan's OK.
- **Hashtags:** review the flagged teams in `data/team_hashtags.json`.
- **"Predict" page** (later epic): enter future results and see how the rankings would change.
- **Design system:** add the site's header band, nav and footer as components.
- `GITHUB_DISPATCH_TOKEN` (Cloudflare) expires about Nov 2027.
