# TrueCFB brand rules

The full design system (colors, type, components, wordmark files) lives in a Claude artifact; the site's tokens and component styles are in `site/css/site.css`, and the fonts are in `site/fonts/` (TTF copies for the result card in `assets/fonts/`).

## Words

- **The name is always written TrueCFB**: capital T, lowercase "rue", capital CFB. Everywhere: titles, headings, labels, navigation, body text, posts and cards. Never all capitals, even inside a heading that is otherwise uppercase by style (the stylesheet's `.nm` class keeps the name's capitals).
- **The version is written v1.0** in copy, code and docs.
- **Every TrueCFB number is a rating, never a score.** "Score" only means points on the scoreboard (28-20).
  - **Game Rating**: what one team earns for one game, 0 to 100 (above 100 in the postseason).
  - **Team Rating**: the average of a team's Game Ratings.
  - **Conference Rating**: the plain average of its members' Team Ratings.
  - **Matchup Rating**: the pot the two teams in a game split, 100 plus both teams' bonuses.
- **Tagline:** "Unbiased, Deterministic, Open Source Rankings". "Deterministic" is kept on purpose, for the analytics audience.
- **Site description line:** "Every FBS team rated on results alone. Every game counts. Open source formula."
- **Chart titles:** "Team Rating History", "Conference Rating History".
- **Voice:** fan terms; describes, never predicts; no hype, no emoji.

## Numbers

- One decimal on ratings. Signed changes, bonuses and gaps, with a real minus sign (−) in images and on the site.
- "NR" for not ranked. Tabular figures.

## Look

- Barlow Condensed (display) and IBM Plex Sans (body). Field green (#1f6b45) header band; light theme by default.
- **Blind to the jersey, visually:** no team logos, helmets or mascots anywhere; team names are plain text and bars are the same green.
  - Two exceptions, both charts where a line follows a team: the Rankings page's "Top 25 through the season" chart, and the lines on the CFP comparison card. Each team's line is in its main color (from `data/team_colors.json`), darkened to at least 3:1 against the background. Names stay in the text color. Colors are never an input to a rating.
- **Blue means higher than the comparison, orange means lower.** Never red or green as a verdict.
- Text runs the full width of its panel or column (no 65-character cap).

## Result card (X posts)

1200 × 675, drawn by `src/card.py`: green header band with the score and the Matchup Rating, one panel per team (Game Rating, Team Rating before → after with the change, rank before → after), the ripple to past opponents, and the wordmark, tagline and truecfb.com in the footer.

## CFP comparison card (X posts)

2400 × 1350 (the 1200 × 675 layout at 2×), drawn by `src/cfp_card.py` each week the committee publishes a ranking.
- **TrueCFB is the base, on the left:** rank, team, Team Rating, record. The committee is on the right, titled "CFP committee": rank, team, and, right-aligned in its own column headed "vs TrueCFB" (mirroring Team Rating), how many spots higher (+, blue) or lower (−, orange) the committee has the team than TrueCFB, in brackets.
- A smooth line joins each team, in the team's main color. Every line is the same width (no bold); the top 12 are in full color on a shaded panel, the rest faded.
- Teams on only one list start or end at a note under that list ("Outside top 25", "Not ranked by CFP").
- No key: the brackets and lines explain themselves. Footer as on the result card: wordmark, tagline, truecfb.com.
- "TrueCFB" without the version on the card and in the post.
