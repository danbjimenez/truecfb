# TrueCFB brand rules

The full design system (colors, type, components, wordmark files) lives in a Claude artifact; the site's tokens and component styles are in `site/css/site.css`, and the fonts are in `site/fonts/` (TTF copies for the result card in `assets/fonts/`).

## Words

- **The name is always written TrueCFB**: capital T, lowercase "rue", capital CFB. Everywhere: titles, headings, labels, navigation, body text, posts and cards. Never all capitals, even inside a heading that is otherwise uppercase by style (the stylesheet's `.nm` class keeps the name's capitals).
- **The version is written 2026.2**: year.release, no "v" (2026.1 was released as "v1.0"), in copy, code and docs.
- **Every TrueCFB number is a rating, never a score.** "Score" only means points on the scoreboard (28-20).
  - **Game Rating**: what one team earns for one game, 0 to 100 (above 100 in the postseason).
  - **Team Rating**: the average of a team's Game Ratings.
  - **Conference Rating**: the plain average of its members' Team Ratings.
  - **Matchup Rating**: the pot the two teams in a game split, 100 plus both teams' strengths.
  - **Strength**: how far a team is rated above or below 50 (Team Rating − 50); what it adds to an opponent's Game Rating, win or lose. Called the "bonus" before 27 Nov 2026 (Dan's call: "bonus" reads oddly when it is negative).
- **Tagline:** "Unbiased, Deterministic, Open Source Rankings". "Deterministic" is kept on purpose, for the analytics audience.
- **Site description line:** "Every FBS team rated on results alone. Every game counts. Open source formula."
- **Chart titles:** "Team Rating History", "Conference Rating History".
- **Voice:** fan terms; describes, never predicts; no hype, no emoji.

## Numbers

- One decimal on ratings. Signed changes, strengths and gaps, with a real minus sign (−) in images and on the site.
- "NR" for not ranked. Tabular figures.

## Look

- Barlow Condensed (display) and IBM Plex Sans (body). Field green (#1f6b45) header band; light theme by default.
- **Blind to the jersey, visually:** ratings never see the jersey, and the brand shows almost none of it. No helmets or mascots; team names are plain text and bars are the same green.
  - Logos appear in one place: beside each team's name on the result card (Dan, 27 Nov 2026), so fans can find their game in the feed.
  - Two exceptions, both charts where a line follows a team: the Rankings page's "Top 25 through the season" chart, and the lines on the CFP comparison card. Each team's line is in its main color (from `data/team_colors.json`), darkened to at least 3:1 against the background. Names stay in the text color. Colors are never an input to a rating.
- **Blue means higher than the comparison, orange means lower.** Never red or green as a verdict.
- **Better and worse, one standard** (also in the design system, "Better and worse"):
  - Color the number, never its label or the team name. `up` #1d5fa8 is higher or better, `down` #b0561a is lower or worse; equal is "=" in muted. For ranks a smaller number is higher.
  - Every change also carries a sign or an arrow (+1.2, −1.3, ▲3, ▼5); color is never the only signal.
  - **Change chip:** the signed change in a pill, text `up` on `up-tint` #e3ecf7 or `down` on `down-tint` #f6e9df, body font at 600.
  - **Compared value:** two numbers head to head (a game's two Game Ratings, a new rank) take `up`/`down` themselves, display font at 700.
  - **Before → after:** old value muted, muted arrow, new value in ink at 700; a change chip sits between the old value and the arrow (56.5 −1.3 → 55.2).
  - Display type stops at 700. Cards use the design system's share-card sizes (about 3× the site); nothing that must be read goes below 16px on a 1200 × 675 card.
- Text runs the full width of its panel or column (no 65-character cap).

## Result card (X posts)

1200 × 675, drawn by `src/card.py` from the game's `game_impact` result (designed 27 Nov 2026):
- **Scoreboard band** (field green): visitor on the left, home on the right, each with logo, name, record and score; the loser's score faded; FINAL (OT) and the date between.
- **Matchup Rating:** the two Team Ratings as a sum with small logos, "55.2 + 65.6 = 120.8", one decimal so it adds up, and its percentile among the season's FBS games. Postseason points are added as their own term.
- **Game Rating:** the two Game Ratings as compared values (higher blue, lower orange) with their percentile among the season's Game Ratings, a split bar, and under each team its sum in rule order: win or loss + opponent + margin + venue (+ postseason, and the 0 to 100 limit when it applied), each number over a small label.
- **Team Rating:** before, change chip, → after.
- **TrueCFB rank:** before → after, the new rank in blue or orange, with a ▲/▼ chip.
- Section labels sit in the center column, between the two teams; the visitor's numbers are flush left, the home team's flush right; 1px rules between sections; wordmark and truecfb.com in the footer.
- The ripple to past opponents is in the alt text, not on the card. An FCS team's column says it is not rated.

## CFP comparison card (X posts)

2400 × 1350 (the 1200 × 675 layout at 2×), drawn by `src/cfp_card.py` each week the committee publishes a ranking.
- **TrueCFB is the base, on the left:** rank, team, Team Rating, record. The committee is on the right, titled "CFP committee": rank, team, and, right-aligned in its own column headed "vs TrueCFB" (mirroring Team Rating), how many spots higher (+, blue) or lower (−, orange) the committee has the team than TrueCFB, in brackets.
- A smooth line joins each team, in the team's main color. Every line is the same width (no bold); the top 12 are in full color on a shaded panel, the rest faded.
- Teams on only one list start or end at a note under that list ("Outside top 25", "Not ranked by CFP").
- No key: the brackets and lines explain themselves. Footer as on the result card: wordmark, tagline, truecfb.com.
- "TrueCFB" without the version on the card and in the post.
