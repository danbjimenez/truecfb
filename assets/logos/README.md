# Team logos for the result card

One PNG per FBS team, named by the team's site slug (the same as its page on truecfb.com: `iowa.png`,
`texas-am.png`, `san-jose-state.png`), square, transparent background. `src/card.py` draws a team's
logo beside its name in the scoreboard and in the Matchup Rating row. A team with no file here gets a
plain monogram circle instead, so the card always draws.

Logos are display only (Dan's call, 27 Nov 2026): nothing about a team but its results ever goes into
a rating. School logos are their schools' trademarks, shown to identify the teams.

The 138 files here (every FBS team in the 2025 and 2026 games) came from ESPN's logo images
(`a.espncdn.com/i/teamlogos/ncaa/500/<ESPN team id>.png`, the ids in `data/games.csv`) on 27 Nov 2026,
trimmed to the logo and resized to 256 × 256. A team new to FBS needs its file added the same way.
FCS teams have none and get the monogram.
