# TrueCFB 2026.2: why it works the way it does

The rules and numbers are in the [README](../README.md). This file keeps the reasoning: the goals, why each setting has the value it has, what was tried and dropped, and what the postseason points do. TrueCFB was designed by Dan Jimenez with Claude in November 2026, 2026.1 was released on 21 November 2026, and 2026.2 (the margin rule) on 27 November 2026.

## Goals

1. Blind to the team. Only results on the field count: no pedigree, reputation or talent.
2. Open: simple rules a casual fan can follow, and anyone can calculate and get the same ranking.
3. Measures the season that was played. It does not predict who would win a future game.
4. Winning matters most; who you beat and who you lose to matters next; how you win or lose (margin) matters least. Head-to-head is a tiebreaker only.
5. Cross-conference games should really matter: a non-conference win should lift the ratings of your conference mates as they play you.
6. Scheduling: reward harder schedules, but keep top teams willing to schedule small programs.
7. Every game counts. No dropped games and no special-case rules for particular opponents.
8. When the playoff is done, the final ranking should reflect how it turned out, with the champion on top. Regular bowls should count for something, so teams do not duck them.
9. 2020 is a throwaway year. The algorithm is not adjusted to handle it.

## Why these settings

- **Win 70 / loss 30, plus or minus 1 point for every 4 points of margin, up to 40 (2026.2).** Winning is the biggest input: a 1-point win is worth about 40 more than a 1-point loss. Margin is the smallest: at most 10. The rule a fan can do in their head replaced 2026.1's curve (the share of 2014 to 2025 games decided by fewer points), which gave almost the same numbers but needed a lookup table. See "The 2026.2 margin rule" below for the tests.
- **Overtime games count by their final score (2026.2).** 2026.1 counted them as a 1-point margin. Fans and every box score read the final score, and the effect is small (top 25 moves 0.15 spots on average).
- **Opponent strength at full value.** The first draft used 0.9 × (rating − 50), which guarantees one answer in every possible season. Full value was chosen for release: one less thing to explain ("you just add your opponent's strength"; it was called the bonus until 27 Nov 2026), and non-conference results reach conference mates at full strength. The cost is 2020 (see below).
- **Venue at 3 (2026.2).** The measured edge of home teams in conference games on this scale is 2.75 (home teams won 55.5% of 6,131 conference games, 2014 to 2025). It is rounded to 3 because a whole number is easier to explain; the rounding moves the top 25 by 0.1 spots on average, with the same top 4 in all 11 seasons. 2026.1 used the measured 2.86. A much larger value (4 moved the top 25 by 0.45 spots) would turn venue into a bonus for playing on the road and raise the cost of hosting a small program.
- **FCS at 25** (the data implies 16 to 21). Set higher on purpose to soften the cost of scheduling a small program. At full strength value this number also helps hold the whole scale in place.
- **Six-game fade-out** kept over a fresh start: starting everyone at 50 leaves the ranking far from the poll for the first month. The regular-season final ranking is the same either way.
- **Playoff points above the 100 limit:** a playoff win is already near 100, so points kept under the limit would only help the loser. The winner's points grow by round so that advancing always pays more.
- **Bowl points (+10):** with none, a bowl is a coin flip a top team can avoid.
- **The Matchup Rating** (100 plus both strengths, which equals the two Team Ratings added together) replaced a "0.9 × (opponent's rating − 50)" explanation that was too hard for fans. Without the 0–100 limit or postseason points, the two teams' Game Ratings add up to it exactly: margin and venue only move points from one side to the other.

## Why a blowout of a weak team lowers a top team's rating

A Team Rating is an average. A home blowout of an FCS team earns a Game Rating of about 52; a top team's average is in the mid-70s. The game did not take anything away; it earned less than the team's usual game. If a team played that opponent every week its rating would settle at about 52, and it could instead have scheduled a tougher team and risked a loss. This is the flip side of rewarding harder schedules.

Measured effect (average Game Rating minus the team's own Team Rating, 11 seasons without 2020): for a top-25 team, an FCS game is about −15 and a weak FBS game about −9. About 7 in 10 top-25 teams play an FCS game, so it largely cancels in the order. It also ripples: when a top team's rating dips after a cupcake win, its earlier opponents dip slightly too.

## One answer, and 2020

- Opponent ratings come from the same calculation: start every team at 50 and repeat until nothing moves. Starting at 50 is part of the rule.
- In every season except 2020, starting anywhere gives the same ratings (checked on all 191 non-2020 snapshots, from starts of 5, 50 and 95; re-checked for 2026.2 on 179 weekly and end-of-season snapshots). The level is held in place by FCS games, the 0 to 100 limits and the carried-over placeholders.
- 2020: in five late-season snapshots the ratings depend on the starting point (by up to 14.5 points), because conference-only schedules left nothing tying one conference's level to another's. That season is marked unreliable and left out of summary figures. Bonus at 0.9 remains the fallback if a future season is cut into isolated groups.

## What the postseason points do (11 seasons, 2020 left out)

- The champion finishes 1st in every season. The runner-up finishes 2nd in all but one (in 2019, 13-0 Ohio State stays ahead of Clemson).
- Playoff teams are ordered by how far they advanced in 95% of pairings.
- Ranking spots for top-25 teams, on average: a bowl win gains about 2.4, a bowl loss costs about 4.7, no postseason game costs about 3 (only two cases), a close loss in a first playoff game costs about 1.3, and a first-game loss by 15 or more about 2.6.
- No team that plays a postseason game ends with a lower rating than it had before, because every team's rating drifts up over the postseason, by about 8 points for a typical top-40 team. The postseason points pass through opponents' strengths at full value.
- Champions' season-final ratings run from 89 to 98, so year-end ratings sit higher than in-season ratings, and next season's preseason list is led by last year's playoff teams until the six games fade.
- Caveat: the playoff field is picked by the committee, so the playoff points go to teams the committee chose.

## Considered and rejected

| Idea | Why not |
|---|---|
| Blend of 70% raw Game Rating and 30% opponent rating | Squeezed all ratings into a 33 to 70 band so schedule barely counted |
| Opponent quality by rank (best = 100, worst = 0) | Different starting points gave different answers |
| Tuning weights to playoff results, or re-fitting each year | Turns it into a prediction model; tiny sample; breaks year-over-year comparison |
| Uncapped linear margin | A 77-0 win over a bad team becomes the best game of the year |
| Forcing ratings onto a bell curve | Erases the gaps between teams |
| Multiplying by the Matchup Rating (sum of both ratings) | A team's own rating inflates its own Game Ratings; top teams bunch at 97 to 99 |
| Multiplying by the opponent's rating only | The whole scale collapses |
| Larger venue value | Rewards where you play; raises the cost of hosting small programs |
| More margin, less opponent strength (to make cupcake blowouts harmless) | Blowing out weak teams becomes the best way to raise a rating |
| First FCS win not counted | Special rule for one kind of opponent |
| Lowest-scoring win not counted | Every game should count |
| Bigger win shrinks a weak opponent's penalty | Never reaches zero; rewards running up the score on weak teams |
| Explicit scheduling or conference-loyalty bonuses | Need conference membership as an input; less blind, easier to game |
| Fresh start each season (no carryover) | A month of noise; the six-game fade-out was kept |
| Postseason games counting with no extra points | Teams that reach the playoff and lose finish below where they ended the regular season |
| Postseason games that can only help (losses never count) | Breaks "every game counts" |
| Flat playoff points kept under the 100 limit | The limit absorbs the winner's points, so the champion is not always 1st |
| Opponent strength at 0.9 (the first draft) | Replaced before release for a simpler rule |
| Betting spreads to set the expected margin (considered for 2026.2) | Brings in reputation, injuries and market opinion, which a results-only rating leaves out; great teams get no credit when they win as expected; opponent strength counts twice (the spread and the bonus); lines differ by book and time and are not free to republish |
| Win 60 + 1 point per point of margin, up to 40 (considered for 2026.2) | Margin outweighs winning (a 1-point win is only 22 above a 1-point loss); a 40-point home win over an FCS team earns about 72, so cupcake blowouts pay; top 25 moves 3.5 spots from 2026.1 and matches the committee's top 4 in 1 of 11 seasons |
| A narrower (±3) or wider (±7.5) margin range | Both drift further from the committee than ±5; ignoring margin entirely is clearly worse |

## The 2026.2 margin rule

Dan asked for a margin rule that is simple to say and not arbitrary. Every rule below was run on every season from 2014 to 2025 with overtime games at their final score (2020 left out of the averages). These tests used the measured venue (2.75); rounding it to 3 changes the 2026.2 row by 0.1 spots or less. "Higher-ranked team won" is the share of regular-season games won by the team ranked higher in that season's regular-season final ranking.

| Rule (win; a loss mirrors it) | Top 25 moves vs 2026.1 | Gap from committee | Same top 4 as committee | Higher-ranked team won | Team Ratings vs a bell curve |
|---|---|---|---|---|---|
| 2026.1: 70 to 80 on the margin curve, OT as 1 point | – | 3.01 | 6 of 11 | 82.6% | 0.027 |
| **2026.2: 70 + 1 per 4 points, up to 40** | 0.46 spots | 3.00 | 6 of 11 | 82.6% | 0.025 |
| 70 + 1 per 3 points, up to 30 | 0.40 | 3.06 | 5 of 11 | 82.6% | 0.026 |
| 70 + 2 per touchdown, up to 35 | 0.37 | 3.01 | 6 of 11 | – | – |
| 65 + 1 per 2 points, up to 30 | 1.31 | 3.29 | 3 of 11 | 82.1% | 0.025 |
| 60 + 1 per point, up to 40 | 3.53 | 4.65 | 1 of 11 | 81.0% | 0.025 |
| No margin (75 / 25) | 1.47 | 3.56 | 4 of 11 | 82.7% | 0.022 |

- Team Ratings are close to a bell curve under every rule: symmetric, a little flatter than a bell curve (slightly fewer teams at the extremes), and the biggest gap from one is about 2.5% of teams. The margin rule barely changes that shape, so it could not decide the rule. The win/loss gap and the opponent bonus set the spread.
- Game Ratings form two overlapping humps (wins and losses) under any rule.
- "Higher-ranked team won" slightly favors rules with less margin (no margin scores highest), so it is a check, not a target. Matching the committee is a check too, never a goal.
- A 100 is still possible: the 80 caps the result part only; the opponent's strength comes on top. #1 beating #2 at a neutral site by 14 or more reaches 100.

## Ideas for a future version (not in 2026.2)

Any of these would be a new version, with every season re-run.

1. Year-end ratings run about 8 points above in-season ratings because postseason points pass through opponents' strengths. Tested fix: postseason points count only for the team that earned them. Same order (champion 1st in all 11 seasons, bracket order 95%), drift under 1 point, champions averaging about 87.
2. Whether a first-round playoff loss should cost no ranking spots at all (today about 1 to 3).
3. Whether to stretch the scale for display so the best regular-season teams read in the 90s.

## Naming history

- Versions are numbered year.release since 27 Nov 2026 (Dan's call, to track changes over the years): the first public version, released as v1.0, is 2026.1; the margin and venue change is 2026.2.

- Named TrueCFB on 22 Nov 2026. Considered and dropped: OpenFPI (ESPN's FPI is a predictive metric), OpenRank (crowded), OpenCFB (an existing project at opencfb.com), RealCFB (domain taken), BasedCFB, BlindCFB (too easy to joke about). The [prefix]CFB pattern carries across the family.
- The opponent's "bonus" was renamed **strength** on 27 Nov 2026 (Dan's call): "bonus" read oddly when it was negative, and "strength" works both for a team ("Georgia's strength +26") and inside a Game Rating ("+16.0 opponent strength"). The `bonus` key in rankings.json and in the code keeps its old name so nothing reading it breaks.
- Before release the formula went through two drafts numbered 1.0 and 1.1. Draft 1.0 had the opponent's strength (then the bonus) at 0.9; draft 1.1 had it at full value and was released as v1.0 (2026.1). Older commits and notes use the draft numbers; draft 1.1 is not the released 2026.2 (27 Nov 2026), which changed the margin rule.
- "Game Rating" first meant the pot two teams split; it was renamed Matchup Rating, and Game Rating now means what one team earns for one game.
