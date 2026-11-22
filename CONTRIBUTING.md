# Contributing to TrueCFB

Thanks for looking. TrueCFB is an open formula, so the code is here to be read, checked and improved.

## What is welcome

- **Bug fixes** in the pipeline or the site.
- **Data fixes.** A wrong score, a missing game, a wrong overtime flag. Say where the correct value comes from.
- **Site improvements.** Clearer pages, better accessibility, faster loading.
- **Clearer writing** in the README or on the About page.

## Changes to the formula

TrueCFB v1.0 is frozen. The rules and numbers in `src/engine.py` are fixed like a rulebook, so a pull request that changes one will not be merged as a fix.

If you think a rule should change:

1. Open an issue first. Describe the rule, why it should change, and what it does to the rankings.
2. Show before and after numbers for at least the three most recent seasons.
3. If the change is accepted, it ships as a new version, with every season re-run.

The maintainer decides what becomes a new version. The formula is not tuned to match a poll, the committee or playoff results.

## Before you open a pull request

- **Run it.** The README has the four commands under "Run it yourself".
- **Say whether any rating changes.** If your change touches `src/`, run the pipeline before and after and compare the files in `site/`. A change that is not meant to move a rating should leave every rating the same.
- **Do not edit the data files by hand.** `site/data.json`, `site/history.json`, `site/rank_*.json` and `site/sched_*.json` are written by the pipeline. A scheduled job rewrites them every two hours, so leave them out of your pull request unless they are the point of it.
- **Do not commit downloads.** Everything under `data/schedules/` and `data/espn/` is fetched on each run.

## Site changes

The site follows the TrueCFB brand rules:

- **Blind to the jersey.** No team colors, logos, helmets or mascots. Every team is plain text.
- **The name is TrueCFB.** Capital T, lowercase r, u, e, capital CFB. Never in all capitals, including inside a heading.
- **Rating, not score.** TrueCFB's numbers are a Game Rating, a Team Rating, a Conference Rating or a Matchup Rating. "Score" only ever means the points on the scoreboard.
- **Blue means higher than the comparison and orange means lower.** Never red or green as a verdict.
- **Both themes.** Check the page in light and dark.
- **Phone first.** Check it at phone width. A wide table scrolls inside its frame; the page does not.

## License

By contributing, you agree that your contribution is released under the [MIT License](LICENSE).
