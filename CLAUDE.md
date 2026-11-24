# TrueCFB: working notes for Claude

TrueCFB is Dan Jimenez's open-source college football ranking: every FBS team rated on results alone, with a public, deterministic formula (v1.0, frozen 21 Nov 2026). Live at truecfb.com, posts as @truecfb on X. This repo is the whole project: formula, site, data jobs and the X bot.

Read before changing things:
- `README.md`: the rules, exact definitions, anchor games, how to run it.
- `docs/DESIGN.md`: goals, why each setting has its value, rejected ideas, future-version ideas.
- `docs/BRAND.md`: naming, wording and visual rules (the site, the cards, the posts).
- `docs/X-BOT.md`: how the X bot runs, accounts, secrets, X's rules.

## Rules that never bend

- **The formula is frozen at v1.0.** No change to a rule or a number without a new version, recorded in the README's version history, with every season re-run. Display, data plumbing and site work are not formula changes, but must leave every published number unchanged; check that before calling it done.
- **Write the name TrueCFB** (never all capitals) and the version **v1.0**.
- **Rating, never score.** Game Rating (one team, one game), Team Rating, Conference Rating, Matchup Rating (the pot two teams split). "Score" means points on the scoreboard only.
- **Blind to the jersey:** no team logos, mascots or team colors, except each team's line on the Top 25 chart. Blue = higher, orange = lower; never red/green as a verdict.
- **Every number in a post or card comes from the engine.** The X bot uses fixed templates; no model writes numbers.
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
| `src/bot_drafts.py`, `src/bot_post.py` | X bot: drafts to Telegram, posting |
| `site/` | The static site (Cloudflare serves it); `site/live.json` = finals the bot has handled |
| `worker/index.js` | Cloudflare Worker: scoreboard check + Telegram hook |
| `.github/workflows/` | `refresh.yml` (3×/week + daily in Dec/Jan), `game-final.yml`, `post-to-x.yml`, `telegram-setup.yml`, `release.yml` |
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

## How we work

- Branch, open a PR, and merge when Dan says "merge". Cloudflare deploys `main` automatically (branch previews build too).
- The jobs commit to `main` on their own (ratings, drafts, posted log). Pull before starting work.
- Dan prefers short, scannable answers and honest assessments over reassurance.

## Open work

- **Before the 2026 bowls:** add the 2026 selection date and the final 2026 CFP ranking to `run_all.py` and `data/cfp_final.json`. Until then the current season counts regular-season games only, and bowl games will not move ratings.
- **Reply bot:** when someone tags @truecfb, a model reads the question and the engine supplies every number; start in draft mode (Telegram). Check X's current rules on AI replies first (see `docs/X-BOT.md`).
- **Hashtags:** review the flagged teams in `data/team_hashtags.json`.
- **"Predict" page** (later epic): enter future results and see how the rankings would change.
- **Design system:** add the site's header band, nav and footer as components.
- `GITHUB_DISPATCH_TOKEN` (Cloudflare) expires about Nov 2027.
