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
  - One exception: on the Rankings page's "Top 25 through the season" chart, each team's line is in its main color (from `data/team_colors.json`). Names stay in the text color. Colors are never an input to a rating.
- **Blue means higher than the comparison, orange means lower.** Never red or green as a verdict.
- Text runs the full width of its panel or column (no 65-character cap).

## Result card (X posts)

1200 × 675, drawn by `src/card.py`: green header band with the score and the Matchup Rating, one panel per team (Game Rating, Team Rating before → after with the change, rank before → after), the ripple to past opponents, and the wordmark, tagline and truecfb.com in the footer.
