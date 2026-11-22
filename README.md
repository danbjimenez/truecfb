# TrueCFB

Every FBS team rated on results alone. Every game counts. Open source formula.

- Site: [truecfb.com](https://truecfb.com)
- Formula: v1.0, frozen 21 November 2026
- Covers every FBS season from 2014 to now

TrueCFB measures the season that was played. It does not predict games. It knows nothing about a team except its results: no reputation, no recruiting rankings, no preseason poll.

## The rules

1. Every game has a **Matchup Rating**: 100 plus both teams' bonuses. Two average teams make a 100. The two best teams make about 155. That is the pot the two teams split.
2. The winner's share starts at 75 and the loser's at 25.
3. Margin moves it up to 5 points either way: a 1-point win is 70, a blowout win is 80. An overtime game counts as a 1-point margin.
4. Add 3 on the road, subtract 3 at home, nothing at a neutral site.
5. Add your opponent's **bonus**, win or lose. The bonus is how far the opponent is rated above or below 50. An FCS opponent counts as a 25, so its bonus is −25.
6. Keep the result between 0 and 100. That is the team's **Game Rating**. A **Team Rating** is the average of its Game Ratings.
7. Postseason games are worth more, and their Game Ratings can go above 100. A regular bowl adds 10 for both teams. A playoff game adds 15 for both teams, and the winner adds 10 more in the first round, 20 in a quarterfinal, 30 in a semifinal and 40 in the final.

A **Conference Rating** is the plain average of its members' Team Ratings. It is published, not used as an input.

### How a season runs

- **Start.** A team starts at last season's final rating, after all bowl and playoff games. Think of it as six placeholder games at that rating.
- **Each game.** Each real game replaces one placeholder. After six games the placeholders are gone and the Team Rating is the plain average of this season's Game Ratings. Weeks 1 to 6 are provisional. A team new to FBS starts at 25.
- **Re-rating.** Bonuses update as results come in, so an old game is worth more if that opponent keeps winning. A team's rating can move in a week it does not play.
- **Postseason.** Every bowl and playoff game counts like any other game, plus the extra points in rule 7.
- **Tiebreak.** At season's end only: if two neighbors are within 1 point and the lower one won their game (with no split), they swap.

### Worked example

Utah, 2026. Home win 66-14 over Idaho (FCS): 75 + 5 − 3 − 25 = 52. Home win 28-20 over BYU, rated 68.7 at the time: 73.6 for an 8-point win, −2.9 at home, +18.7 for BYU's bonus = 89.4.

## Exact definitions

| Item | Value |
|---|---|
| Win, before adjustments | 70 + 10 × F(m) |
| Loss, before adjustments | 30 − 10 × F(m) |
| F(m) | Share of all FBS-vs-FBS games in 2014 to 2025 (9,085 games) decided by fewer than m points, plus half of those decided by exactly m. Overtime games use m = 1. |
| Venue | 2.86 (road +, home −, neutral 0) |
| Opponent bonus | opponent's rating − 50 |
| FCS opponent rating | 25 |
| Game Rating limits | 0 to 100, applied before postseason points |
| Regular bowl | +10 to both teams |
| Playoff game | +15 to both teams |
| Playoff winner, by round | +10 before the quarterfinals, +20 quarterfinal, +30 semifinal, +40 final |
| Carryover | Last season's final rating stands in for each of the first 6 games not yet played; a team new to FBS starts at 25 |
| Head-to-head window | 1.0 rating point, neighbors only, end of season only |
| Starting point for the calculation | Every team at 50 |

- F(m), selected values: 1 pt 3.7%, 3 pts 14.0%, 7 pts 30.7%, 14 pts 50.6%, 21 pts 67.4%, 28 pts 80.6%, 35 pts 89.7%, 42 pts 94.9%.
- Venue is measured, not chosen: it is the average edge of home teams in conference games on this scale (home teams won 55.5% of 6,131 conference games).
- Opponent ratings come from the same calculation. Start every team at 50 and repeat until nothing moves. Starting at 50 is part of the rule.
- Only FBS teams are rated.

## Anchor games

| Game | Game Rating |
|---|---|
| Typical win over an average team, neutral site | 75 |
| Beat the best team on the road by a lot | 100 |
| Beat the worst team at home by 1 | 36 |
| Typical loss to an average team | 25 |
| Lose to the best team on the road by 1 | 61 |
| Lose to the worst team at home by a lot | 0 |

## How it compares with the committee

Regular-season final TrueCFB ranking against the final College Football Playoff ranking.

| Season | Avg gap (spots) | CFP 25 in TrueCFB 25 | TrueCFB top 4 | CFP top 4 |
|---|---|---|---|---|
| 2014 | 2.9 | 24 | Oregon, Alabama, Florida State, Ohio State | Alabama, Oregon, Florida State, Ohio State |
| 2015 | 2.7 | 23 | Alabama, Michigan State, Clemson, Oklahoma | Clemson, Alabama, Michigan State, Oklahoma |
| 2016 | 3.4 | 21 | Alabama, Ohio State, Washington, Clemson | Alabama, Clemson, Ohio State, Washington |
| 2017 | 3.5 | 22 | Clemson, Georgia, Ohio State, Wisconsin | Clemson, Oklahoma, Georgia, Alabama |
| 2018 | 2.9 | 22 | Alabama, Clemson, Notre Dame, Georgia | Alabama, Clemson, Notre Dame, Oklahoma |
| 2019 | 3.7 | 23 | Ohio State, LSU, Clemson, Oklahoma | LSU, Ohio State, Clemson, Oklahoma |
| 2020 (unreliable) | 9.3 | 17 | Alabama, Ohio State, USC, Cincinnati | Alabama, Clemson, Ohio State, Notre Dame |
| 2021 | 3.0 | 21 | Michigan, Georgia, Alabama, Ohio State | Alabama, Michigan, Georgia, Cincinnati |
| 2022 | 2.1 | 23 | Georgia, TCU, Michigan, Ohio State | Georgia, Michigan, TCU, Ohio State |
| 2023 | 2.6 | 22 | Michigan, Washington, Texas, Ohio State | Michigan, Washington, Texas, Alabama |
| 2024 | 3.3 | 22 | Oregon, Notre Dame, Ohio State, Georgia | Oregon, Georgia, Texas, Penn State |
| 2025 | 2.9 | 23 | Indiana, Ohio State, Georgia, Texas Tech | Indiana, Ohio State, Georgia, Texas Tech |

- The same four teams as the committee in 6 of 12 seasons. The average gap is 3.0 spots without 2020.
- After the postseason, the champion finishes 1st in every season. The runner-up finishes 2nd in all but one (in 2019, 13-0 Ohio State stays ahead of Clemson).

A gap from the committee is not an error in either direction. It is only a measure of how far the two differ.

## Known limits

- **2020 is unreliable.** Most conferences played only themselves, so nothing ties one conference's level to another's. In five late-season snapshots the ratings depend on the starting point. The formula is not adjusted for that season.
- **A blowout of a weak team can lower a top team's rating.** A Team Rating is an average. A home blowout of an FCS team earns a Game Rating of about 52, and a top team's average is in the mid-70s. The game takes nothing away; it earns less than the team's usual game.
- **Year-end ratings run high.** Postseason points pass through opponents' bonuses, so ratings drift up by about 8 points for a typical top-40 team during the postseason.
- **The playoff field is chosen by the committee,** so playoff points go to teams the committee picked.
- **Poll comparison has gaps.** Weekly poll ranks come from that week's games, so a ranked team on a bye is missing that week. Final AP polls, after the bowls, are not in the data.
- **Overtime flags are missing for some older games** (2013, 2015, 2016, 2018 and 2022). Those games use the actual margin.

## Version policy

The rules and numbers are fixed like a rulebook. They are not tuned to playoff results and not re-fit each year. Any change is a new version, with every season re-run so ratings stay comparable across years.

| Version | Date | Change |
|---|---|---|
| v1.0 | 21 Nov 2026 | First public version. The rules above, frozen. |

Before the public release the formula went through two drafts, numbered 1.0 and 1.1 while it was being built. Older commits use those numbers. The first draft set the opponent bonus at 0.9 × (rating − 50). The second set it at the full value, and that second draft is what was released as v1.0.

## Run it yourself

You need Python 3.10 or later.

```
pip install -r requirements.txt
python src/fetch_data.py data/schedules data/espn
python src/build_games.py data/schedules data/espn data/games.csv data/latest_poll.json
python src/run_all.py data/games.csv src data/latest_poll.json site data/cfp_final.json data/polls
```

The last step rewrites the data files in `site/`. Open `site/index.html` through any local web server to see the result.

The weekly AP and CFP rankings shown beside the TrueCFB ranking are saved in `data/polls/`, so the commands above work as they are. To refresh those files yourself, get a free key from [CollegeFootballData.com](https://collegefootballdata.com/key) and run `CFBD_API_KEY=your-key python src/fetch_polls.py data/polls` before the last step. The polls are only shown for comparison. They are never an input to a rating.

| Path | What it is |
|---|---|
| `src/engine.py` | The formula. Every rule and number above is in this one file. |
| `src/fetch_data.py` | Downloads the public game files. |
| `src/fetch_polls.py` | Saves the weekly AP and CFP rankings (needs a free CollegeFootballData key). |
| `src/build_games.py` | Merges them into one games table and notes how complete each week of the current season is. |
| `src/run_all.py` | Runs every season and writes the site's data files: `data.json`, `rank_{year}.json`, `sched_{year}.json` and `history.json`. |
| `data/cfp_final.json` | Final CFP rankings, 2014 to 2025. |
| `data/polls/` | Weekly AP and CFP rankings by season, as saved by `fetch_polls.py`. |
| `site/` | The website: the Rankings, Teams, Conferences, How it works and About pages, their styles and scripts, and the data files the pipeline writes. |
| `.github/workflows/refresh.yml` | The scheduled job that refreshes the numbers. |
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
