"""TrueCFB: save each FBS team's primary colour, used only to colour lines on the Top 25 chart.
Colours are never an input to a rating.
Usage: fetch_colors.py <games.csv> <out.json>

Source: the team list in sportsdataverse/cfbfastR-data (themes/logos.csv), the same project the game
files come from. The output is saved in the repo (data/team_colors.json), so this only needs running
when a team joins FBS or changes its colours."""
import sys, csv, io, json, urllib.request
import pandas as pd

URL = "https://raw.githubusercontent.com/sportsdataverse/cfbfastR-data/main/themes/logos.csv"
# Our team name -> the name the colour list uses, where they differ.
ALIAS = {"App State": "Appalachian State", "Massachusetts": "UMass", "Sam Houston": "Sam Houston State",
         "Southern Miss": "Southern Mississippi", "UConn": "Connecticut", "UL Monroe": "Louisiana Monroe",
         "UTSA": "UT San Antonio"}

games = pd.read_csv(sys.argv[1], low_memory=False)
teams = sorted(set(games.home[games.home_fbs]) | set(games.away[games.away_fbs]))
raw = urllib.request.urlopen(URL, timeout=60).read().decode("latin-1")
color = {}
for r in csv.DictReader(io.StringIO(raw)):
    c = (r.get("color") or "").strip().lower()
    if len(c) == 7 and c.startswith("#"):
        color.setdefault(r["school"], c)
out = {t: color[ALIAS.get(t, t)] for t in teams if ALIAS.get(t, t) in color}
missing = [t for t in teams if t not in out]
if missing:
    print("no colour found for:", missing)
json.dump(out, open(sys.argv[2], "w"), indent=0, sort_keys=True)
print(f"saved {len(out)} team colours to {sys.argv[2]}")
