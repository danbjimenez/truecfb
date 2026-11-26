"""TrueCFB reply bot: what one made-up result would do to the ranking.

  WhatIf(site_dir) -> the newest season's engine inputs (site/whatif.json, written by run_all.py)
  WhatIf.scenarios(team, opponent, site, margins) -> for each result, every team's new Team Rating and rank

It runs the frozen v1.0 engine (engine.rate, engine.rank_with_h2h) on the season's published games with
one game added. Nothing here changes a rule or a number: it is the same calculation on a season that
has one more game in it. Before any what-if, the season is re-run without the extra game and must give
exactly the published ratings; if it does not (the file is older than the latest results), the lookup
says so and gives nothing.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine as E  # noqa: E402

MARGINS = (3, 17)      # a close result and a two-score one, each way


class OutOfDate(Exception):
    pass


class WhatIf:
    def __init__(self, site_dir, published=None):
        import numpy as np
        import pandas as pd
        path = os.path.join(site_dir, "whatif.json")
        if not os.path.exists(path):
            raise OutOfDate("no what-if data yet (site/whatif.json is written by the ratings jobs)")
        d = json.load(open(path))
        self.season, self.h2h, self.teams = d["season"], d["h2h"], d["teams"]
        self.F, self.v = np.array(d["F"]), d["venue"]
        self.prior = pd.Series(d["prior"])
        self.games = pd.DataFrame(d["games"], columns=d["columns"])
        self.base_table, self.base_rank = self.run(self.games)
        if published is not None:
            off = [t for t in self.teams if t in published and
                   (round(float(self.base_table.rating[t]), 1) != published[t][0] or self.base_rank[t] != published[t][1])]
            if off:
                raise OutOfDate(f"what-if data does not match the published ratings ({len(off)} teams differ); "
                                "it updates with the next ratings run")

    def run(self, games):
        table, _ = E.rate(games, self.F, self.v, prior=self.prior, teams=self.teams)
        order = E.rank_with_h2h(table, games)[0] if self.h2h else list(table.sort_values("rating", ascending=False).index)
        return table, {t: i + 1 for i, t in enumerate(order)}

    def with_game(self, team, opponent, site, margin):
        """The season with one more game: team vs opponent, margin from team's side (+ win, - loss).
        site: home, away or neutral, from team's side. opponent may be an FCS team (any name not in FBS)."""
        import pandas as pd
        home, away, m = (opponent, team, -margin) if site == "away" else (team, opponent, margin)
        row = {"season": self.season, "week": int(self.games.week.max()) + 1, "home": home, "away": away,
               "home_fbs": home in self.teams, "away_fbs": away in self.teams, "margin_home": int(m),
               "neutral": site == "neutral", "season_type": "regular", "note": None, "game_id": "what-if"}
        return self.run(pd.concat([self.games, pd.DataFrame([row])], ignore_index=True))

    def scenarios(self, team, opponent, site, margins=MARGINS):
        out = []
        for m in [x for x in margins] + [-x for x in margins]:
            table, rank = self.with_game(team, opponent, site, m)
            out.append({"margin": m, "table": table, "rank": rank})
        return out
