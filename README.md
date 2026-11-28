# TrueCFB

Every FBS team rated on results alone. Every game counts. Open source formula.

- Site: [truecfb.com](https://truecfb.com)
- Formula: 2026.2, 27 November 2026 (versions are numbered year.release; 2026.1 was released as v1.0 on 21 November 2026)
- Covers every FBS season from 2014 to now

TrueCFB measures the season that was played. It does not predict games. It knows nothing about a team except its results: no reputation, no recruiting rankings, no preseason poll.

## The rules

1. A win starts at 70 and a loss at 30.
2. Add your opponent's **strength**, win or lose. Strength is how far a team is rated above or below 50: its Team Rating minus 50. An FCS opponent counts as a 25, so its strength is −25.
3. Add 1 point for every 4 points you win by, up to a 40-point margin (+10). A loss takes off the same: 1 point for every 4 points you lose by, down to −10. A 14-point win adds 3.5. Overtime games count by their final score.
4. Add 3 on the road, subtract 3 at home, nothing at a neutral site.
5. Keep the result between 0 and 100. That is the team's **Game Rating**. A **Team Rating** is the average of its Game Ratings.
6. Postseason games are worth more, and their Game Ratings can go above 100. A regular bowl adds 10 for both teams. A playoff game adds 15 for both teams, and the winner adds 10 more in the first round, 20 in a quarterfinal, 30 in a semifinal and 40 in the final.
7. Every game has a **Matchup Rating**: 100 plus both teams' strengths, which is the same as the two Team Ratings added together. Two average teams make a 100. The two best teams make about 155. It is the pot the two teams split: rules 1, 3 and 4 divide the 100 between the winner and the loser, and each team takes the other team's strength.

In short: **Game Rating = win 70 (or loss 30) + opponent's strength + margin + venue**, kept between 0 and 100.

A **Conference Rating** is the plain average of its members' Team Ratings. It is published, not used as an input.

### How a season runs

- **Start.** A team starts at last season's final rating, after all bowl and playoff games. Think of it as six placeholder games at that rating.
- **Each game.** Each real game replaces one placeholder. After six games the placeholders are gone and the Team Rating is the plain average of this season's Game Ratings. Weeks 1 to 6 are provisional. A team new to FBS starts at 25.
- **Re-rating.** Strengths update as results come in, so an old game is worth more if that opponent keeps winning. A team's rating can move in a week it does not play.
- **Postseason.** Every bowl and playoff game counts like any other game, plus the extra points in rule 6.
- **Solving it.** A team's rating depends on its opponents' ratings, and theirs depend on its rating. So start every team at 50, rate every game, average, and repeat with the new ratings until no rating moves.
- **Tiebreak.** In the two end-of-season rankings only (regular season final and season final): if two neighbors are within 1 point and the lower one beat the higher one, without also losing to it, they swap.

### Worked example

Utah, 2026. Home win 66-14 over Idaho (FCS): 70 − 25 + 10 − 3 = 52. Home win 28-20 over BYU, rated 67.1 through week 12: 70 for the win, +17.1 for BYU's strength, +2 for an 8-point margin, −3 at home = 86.1 (the parts are rounded). That number moves whenever BYU's rating does.

### The postseason, round by round

A bowl or playoff game is rated like any other game first, kept between 0 and 100. Then the postseason points are added on top.

| Game | Both teams | Winner adds | Most a win can earn |
|---|---|---|---|
| Regular bowl | +10 | none | 110 |
| Playoff, first round | +15 | +10 | 125 |
| Playoff, quarterfinal | +15 | +20 | 135 |
| Playoff, semifinal | +15 | +30 | 145 |
| Playoff, final | +15 | +40 | 155 |

- Every playoff game pays both teams 15 for playing it, win or lose.
- Each round pays its winner more than the last. A team earns the winner's points for every round it wins.
- The loser of a round still gets its 15 for that game and keeps everything from the rounds it won.
- A bye is not a game, so it earns nothing.
- The points go into the average like any Game Rating. A playoff win is one more game in that average, at 125 to 155.
- Conference championship games are regular-season games and get no extra points.
- From 2014 to 2023 the playoff was a semifinal and a final, at the same values. Any round before the quarterfinals uses the first-round value.

Example, the 2025 season: Indiana went from 78.8 before the playoff to 98.0 after three wins worth 135, 145 and 155. Miami went from 69.4 to 89.3 with wins worth 125, 135 and 145 and a loss in the final worth 90.5.

## Exact definitions

| Item | Value |
|---|---|
| Win, before adjustments | 70 + min(m, 40) ÷ 4 |
| Loss, before adjustments | 30 − min(m, 40) ÷ 4 |
| m | The final score margin, overtime included |
| Venue | 3 (road +, home −, neutral 0) |
| Opponent strength | opponent's rating − 50 |
| FCS opponent rating | 25 |
| Game Rating limits | 0 to 100, applied before postseason points |
| Regular bowl | +10 to both teams |
| Playoff game | +15 to both teams |
| Playoff winner, by round | +10 before the quarterfinals, +20 quarterfinal, +30 semifinal, +40 final |
| Carryover | Last season's final rating stands in for each of the first 6 games not yet played; a team new to FBS starts at 25 |
| Head-to-head window | 1.0 rating point, neighbors only, end of season only |
| Starting point for the calculation | Every team at 50 |

- Margin, selected values for a win: 1 pt 70.25, 7 pts 71.75, 14 pts 73.5, 21 pts 75.25, 28 pts 77, 40 pts or more 80. A loss is 100 minus the same number.
- Venue is the measured edge of home teams in conference games on this scale, 2.75, rounded to 3 (home teams won 55.5% of 6,131 conference games).
- Opponent ratings come from the same calculation. Start every team at 50 and repeat until nothing moves. Starting at 50 is part of the rule.
- Only FBS teams are rated.

## Anchor games

| Game | Game Rating |
|---|---|
| Typical win over an average team (by 14), neutral site | 73.5 |
| Beat the best team on the road by a lot | 100 |
| Beat the worst team at home by 1 | 35 |
| Typical loss to an average team (by 14) | 26.5 |
| Lose to the best team on the road by 1 | 59 |
| Lose to the worst team at home by a lot | 0 |

## How it compares with the committee

Regular-season final TrueCFB ranking against the final College Football Playoff ranking.

| Season | Avg gap (spots) | CFP 25 in TrueCFB 25 | TrueCFB top 4 | CFP top 4 |
|---|---|---|---|---|
| 2014 | 2.9 | 24 | Oregon, Alabama, Florida State, Ohio State | Alabama, Oregon, Florida State, Ohio State |
| 2015 | 2.8 | 23 | Alabama, Oklahoma, Michigan State, Clemson | Clemson, Alabama, Michigan State, Oklahoma |
| 2016 | 3.1 | 21 | Alabama, Ohio State, Washington, Clemson | Alabama, Clemson, Ohio State, Washington |
| 2017 | 3.4 | 23 | Clemson, Georgia, Ohio State, Wisconsin | Clemson, Oklahoma, Georgia, Alabama |
| 2018 | 3.2 | 22 | Alabama, Clemson, Notre Dame, Georgia | Alabama, Clemson, Notre Dame, Oklahoma |
| 2019 | 3.6 | 23 | Ohio State, LSU, Clemson, Oklahoma | LSU, Ohio State, Clemson, Oklahoma |
| 2020 (unreliable) | 9.0 | 17 | Alabama, Ohio State, USC, Oregon | Alabama, Clemson, Ohio State, Notre Dame |
| 2021 | 2.9 | 21 | Michigan, Georgia, Alabama, Ohio State | Alabama, Michigan, Georgia, Cincinnati |
| 2022 | 2.3 | 23 | Georgia, TCU, Michigan, Ohio State | Georgia, Michigan, TCU, Ohio State |
| 2023 | 2.6 | 23 | Michigan, Washington, Texas, Ohio State | Michigan, Washington, Texas, Alabama |
| 2024 | 3.4 | 22 | Oregon, Notre Dame, Ohio State, Georgia | Oregon, Georgia, Texas, Penn State |
| 2025 | 2.9 | 23 | Indiana, Ohio State, Texas Tech, Georgia | Indiana, Ohio State, Georgia, Texas Tech |

- The same four teams as the committee in 6 of 12 seasons. The average gap is 3.0 spots without 2020.
- After the postseason, the champion finishes 1st in every season. The runner-up finishes 2nd in all but one (in 2019, 13-1 Ohio State stays ahead of Clemson).

A gap from the committee is not an error in either direction. It is only a measure of how far the two differ.

## Known limits

- **2020 is unreliable.** Most conferences played only themselves, so nothing ties one conference's level to another's. In five late-season snapshots the ratings depend on the starting point. The formula is not adjusted for that season.
- **A blowout of a weak team can lower a top team's rating.** A Team Rating is an average. A home blowout of an FCS team earns a Game Rating of about 52, and a top team's average is in the mid-70s. The game takes nothing away; it earns less than the team's usual game.
- **Year-end ratings run high.** Postseason points pass through opponents' strengths, so ratings drift up by about 8 points for a typical top-40 team during the postseason.
- **The playoff field is chosen by the committee,** so playoff points go to teams the committee picked.
- **Poll comparison has gaps.** Weekly poll ranks come from that week's games, so a ranked team on a bye is missing that week. Final AP polls, after the bowls, are not in the data.
- **Overtime flags are missing for some older games** (2013, 2015, 2016, 2018 and 2022). Since 2026.2 the flag only adds "(OT)" to the score; every game counts by its final score.

## Version policy

The rules and numbers are fixed like a rulebook. They are not tuned to playoff results and not re-fit each year. Any change is a new version, with every season re-run so ratings stay comparable across years. Versions are numbered year.release: the year a version came out, then its number within that year.

| Version | Date | Change |
|---|---|---|
| 2026.1 | 21 Nov 2026 | First public version (released as v1.0). |
| 2026.2 | 27 Nov 2026 | Margin is 1 point for every 4 points of final margin, up to 40 (2026.1 used the share of 2014 to 2025 games decided by fewer points, which gave a similar curve). Overtime games count by their final score (2026.1 counted them as a 1-point margin). Venue is 3 (2026.1 used the measured 2.86; on the new scale it measures 2.75). The opponent's "bonus" is renamed strength. Every season re-run. |

Before the public release the formula went through two drafts, numbered 1.0 and 1.1 while it was being built. Older commits use those numbers; they are not releases. The first draft set the opponent's strength (then called the bonus) at 0.9 × (rating − 50). The second set it at the full value, and that second draft is what was released as v1.0 (now called 2026.1).

## Run it yourself

You need Python 3.10 or later.

```
pip install -r requirements.txt
python src/fetch_data.py data/schedules data/espn
python src/build_games.py data/schedules data/espn data/games.csv data/latest_poll.json
python src/run_all.py data/games.csv src data/latest_poll.json site data/cfp_final.json data/polls
```

The last step rewrites the data files in `site/`. Open `site/index.html` through any local web server to see the result.

To see what a single game changed, run `game_impact.py` after `build_games.py`:

```
python src/game_impact.py data/games.csv src 2026 --text                # every game on the latest game day
python src/game_impact.py data/games.csv src 2025 --game 401769076      # one game, by its id
```

For each game it prints the Matchup Rating, each team's Game Rating, how each Team Rating and rank moved, and the ripple: which of the two teams' past opponents gained or lost the most because of the result. "Before" and "after" differ by that one game only, with every other final through the end of its day counted in both. Add `--out impact.json` to save the full detail.

The weekly AP and CFP rankings shown beside the TrueCFB ranking are saved in `data/polls/`, so the commands above work as they are. To refresh those files yourself, get a free key from [CollegeFootballData.com](https://collegefootballdata.com/key) and run `CFBD_API_KEY=your-key python src/fetch_polls.py data/polls` before the last step. The polls are only shown for comparison. They are never an input to a rating.

| Path | What it is |
|---|---|
| `src/engine.py` | The formula. Every rule and number above is in this one file. |
| `src/fetch_data.py` | Downloads the public game files. |
| `src/fetch_polls.py` | Saves the weekly AP and CFP rankings (needs a free CollegeFootballData key). |
| `src/build_games.py` | Merges them into one games table and notes how complete each week of the current season is. |
| `src/run_all.py` | Runs every season and writes the site's data files: `data.json`, `rank_{year}.json`, `sched_{year}.json` and `history.json`. |
| `src/build_pages.py`, `src/templates/` | Runs at the end of `run_all.py`. From those data files it writes the parts of the site that work without JavaScript: a page per team (`/team/utah`), the top 25 on the Rankings page, the team index, `rankings.json` (the current ranking for anyone to use), `llms.txt` (a summary for AI assistants) and `sitemap.xml`. It computes no rating. |
| `src/game_impact.py` | What one game changed: Matchup Rating, Game Ratings, Team Rating and rank moves, and the ripple to past opponents. Also writes the post for X from a fixed template, so every number in a post comes from the engine. |
| `src/fill_live_finals.py` | Adds same-day finals from the CollegeFootballData API that the public files do not have yet (needs a key). |
| `src/bot_drafts.py`, `src/bot_post.py` | The X bot: drafts a post for each new final, sends it to Telegram for approval, and posts an approved draft as @truecfb. |
| `src/card.py`, `assets/fonts/` | Draws the 1200 × 675 result card for each post, in the TrueCFB brand, from the same numbers as the post. |
| `worker/index.js` | The small Cloudflare script beside the site: checks the live scoreboard during game windows and handles the Telegram buttons. |
| `src/fetch_colors.py` | Saves each team's main color to `data/team_colors.json`. Colors only color the lines of the Top 25 chart. They are never an input to a rating. |
| `data/cfp_final.json` | Final CFP rankings, 2014 to 2025. |
| `data/team_hashtags.json` | One hashtag per FBS team, added to each result post. Edit freely: tags never affect a rating. |
| `data/polls/` | Weekly AP and CFP rankings by season, as saved by `fetch_polls.py`. |
| `site/` | The website: the Rankings, Teams, Conferences, How it works and About pages, their styles and scripts, and the data files the pipeline writes. |
| `.github/workflows/refresh.yml` | The scheduled job that refreshes the numbers. |
| `.github/workflows/game-final.yml`, `post-to-x.yml`, `telegram-setup.yml` | The X bot's jobs: re-run and draft after a final, post an approved draft, and connect Telegram. |
| `wrangler.jsonc` | Tells Cloudflare to serve `site/` as the website. |

The words used throughout: a **Game Rating** is what one team earns for one game, a **Team Rating** is the average of a team's Game Ratings, a **Conference Rating** is the average of its members' Team Ratings, and a **Matchup Rating** is the pot two teams split. "Score" always means the points on the scoreboard.

## Data

- Game results: [CollegeFootballData.com](https://collegefootballdata.com), through the `sportsdataverse/cfbfastR-data` files on GitHub.
- Overtime flags, poll ranks at game time, some bowl and playoff games, and same-day finals: ESPN, through the `sportsdataverse/cfbfastR-cfb-raw` files on GitHub.
- Weekly AP and CFP rankings: the CollegeFootballData.com API.
- Final CFP rankings, as a check: Wikipedia season ranking pages, cross-checked against the ranks shown on bowl games.

TrueCFB is not affiliated with the College Football Playoff, the Associated Press, ESPN or any school or conference.

## Contributing

Fixes and improvements are welcome. Changes to the formula start as an issue and ship only as a new version. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

The code is released under the [MIT License](LICENSE). The license covers the code. It does not cover the TrueCFB name.
