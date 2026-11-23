# TrueCFB v1.0: why it works the way it does

The rules and numbers are in the [README](../README.md). This file keeps the reasoning: the goals, why each setting has the value it has, what was tried and dropped, and what the postseason points do. TrueCFB was designed by Dan Jimenez with Claude in November 2026, and v1.0 was frozen on 21 November 2026.

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

- **Win 75 / loss 25 with margin ±5** is Dan's own description of the scale ("beat the best team by a ton is 100, lose to the worst by a lot is 0"). Margin is the smallest input.
- **Opponent bonus at full value.** The first draft used 0.9 × (rating − 50), which guarantees one answer in every possible season. Full value was chosen for release: one less thing to explain ("you just add your opponent's bonus"), and non-conference results reach conference mates at full strength. The cost is 2020 (see below).
- **Venue at 2.86** is measured, not chosen: the average edge of home teams in conference games on this scale (home teams won 55.5% of 6,131 conference games, 2014 to 2025). A larger value would turn venue into a bonus for playing on the road and raise the cost of hosting a small program.
- **FCS at 25** (the data implies 16 to 21). Set higher on purpose to soften the cost of scheduling a small program. At full bonus value this number also helps hold the whole scale in place.
- **Six-game fade-out** kept over a fresh start: starting everyone at 50 leaves the ranking far from the poll for the first month. The regular-season final ranking is the same either way.
- **Playoff points above the 100 limit:** a playoff win is already near 100, so points kept under the limit would only help the loser. The winner's points grow by round so that advancing always pays more.
- **Bowl points (+10):** with none, a bowl is a coin flip a top team can avoid.
- **The Matchup Rating** (100 plus both bonuses) replaced a "0.9 × (opponent's rating − 50)" explanation that was too hard for fans. Without the 0–100 limit or postseason points, the two teams' Game Ratings add up to it exactly: margin and venue only move points from one side to the other.

## Why a blowout of a weak team lowers a top team's rating

A Team Rating is an average. A home blowout of an FCS team earns a Game Rating of about 52; a top team's average is in the mid-70s. The game did not take anything away; it earned less than the team's usual game. If a team played that opponent every week its rating would settle at about 52, and it could instead have scheduled a tougher team and risked a loss. This is the flip side of rewarding harder schedules.

Measured effect (average Game Rating minus the team's own Team Rating, 11 seasons without 2020): for a top-25 team, an FCS game is about −15 and a weak FBS game about −9. About 7 in 10 top-25 teams play an FCS game, so it largely cancels in the order. It also ripples: when a top team's rating dips after a cupcake win, its earlier opponents dip slightly too.

## One answer, and 2020

- Opponent ratings come from the same calculation: start every team at 50 and repeat until nothing moves. Starting at 50 is part of the rule.
- In every season except 2020, starting anywhere gives the same ratings (checked on all 191 non-2020 snapshots, from starts of 5, 50 and 95). The level is held in place by FCS games, the 0 to 100 limits and the carried-over placeholders.
- 2020: in five late-season snapshots the ratings depend on the starting point (by up to 14.5 points), because conference-only schedules left nothing tying one conference's level to another's. That season is marked unreliable and left out of summary figures. Bonus at 0.9 remains the fallback if a future season is cut into isolated groups.

## What the postseason points do (11 seasons, 2020 left out)

- The champion finishes 1st in every season. The runner-up finishes 2nd in all but one (in 2019, 13-0 Ohio State stays ahead of Clemson).
- Playoff teams are ordered by how far they advanced in 95% of pairings.
- Ranking spots for top-25 teams, on average: a bowl win gains about 2.4, a bowl loss costs about 4.7, no postseason game costs about 3 (only two cases), a close loss in a first playoff game costs about 1.3, and a first-game loss by 15 or more about 2.6.
- No team that plays a postseason game ends with a lower rating than it had before, because every team's rating drifts up over the postseason, by about 8 points for a typical top-40 team. The postseason points pass through opponents' bonuses at full value.
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
| More margin, less bonus (to make cupcake blowouts harmless) | Blowing out weak teams becomes the best way to raise a rating |
| First FCS win not counted | Special rule for one kind of opponent |
| Lowest-scoring win not counted | Every game should count |
| Bigger win shrinks a weak opponent's penalty | Never reaches zero; rewards running up the score on weak teams |
| Explicit scheduling or conference-loyalty bonuses | Need conference membership as an input; less blind, easier to game |
| Fresh start each season (no carryover) | A month of noise; the six-game fade-out was kept |
| Postseason games counting with no extra points | Teams that reach the playoff and lose finish below where they ended the regular season |
| Postseason games that can only help (losses never count) | Breaks "every game counts" |
| Flat playoff points kept under the 100 limit | The limit absorbs the winner's points, so the champion is not always 1st |
| Bonus at 0.9 (the first draft) | Replaced before release for a simpler rule |

## Ideas for a future version (not in v1.0)

Any of these would be a new version, with every season re-run.

1. Year-end ratings run about 8 points above in-season ratings because postseason points pass through opponents' bonuses. Tested fix: postseason points count only for the team that earned them. Same order (champion 1st in all 11 seasons, bracket order 95%), drift under 1 point, champions averaging about 87.
2. Whether a first-round playoff loss should cost no ranking spots at all (today about 1 to 3).
3. Whether to stretch the scale for display so the best regular-season teams read in the 90s.

## Naming history

- Named TrueCFB on 22 Nov 2026. Considered and dropped: OpenFPI (ESPN's FPI is a predictive metric), OpenRank (crowded), OpenCFB (an existing project at opencfb.com), RealCFB (domain taken), BasedCFB, BlindCFB (too easy to joke about). The [prefix]CFB pattern carries across the family.
- Before release the formula went through two drafts numbered 1.0 and 1.1. Draft 1.0 had the opponent bonus at 0.9; draft 1.1 had it at full value and was released as v1.0. Older commits and notes use the draft numbers.
- "Game Rating" first meant the pot two teams split; it was renamed Matchup Rating, and Game Rating now means what one team earns for one game.
