"""TrueCFB: save the weekly AP and CFP rankings, so the site can show how far TrueCFB is from each.
Usage: fetch_polls.py <polls_dir> [first_year] [last_year]

Source: the CollegeFootballData.com API (GET /rankings). It needs a free API key in the environment
variable CFBD_API_KEY. With no key the script does nothing and the pipeline still runs: the poll
columns on the site are simply empty for any season that has no saved file.

One file per season, <polls_dir>/<year>.json:
  {"season": 2025,
   "regular":    {"1": {"ap": [[1, "Texas"], ...]}, ..., "10": {"ap": [...], "cfp": [...]}},
   "postseason": {"1": {"ap": [...]}}}
A regular-season week's polls are the ones published going into that week, so week 1 is the
preseason poll. The postseason entry is the final AP poll, after the bowls and the playoff.

A finished season is fetched once. The last year is fetched again on every run.
"""
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.collegefootballdata.com/rankings"


def poll_key(name):
    """Which column a poll belongs to, or None for polls the site does not show (Coaches, FCS, ...)."""
    n = name.strip().lower()
    if n in ("ap top 25", "ap"):
        return "ap"
    if n == "cfp" or ("playoff" in n and "fcs" not in n):
        return "cfp"
    return None


def get(key, year, season_type, tries=3):
    url = API + "?" + urllib.parse.urlencode({"year": year, "seasonType": season_type})
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + key, "Accept": "application/json"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            if err.code in (401, 403, 429) or attempt == tries - 1:   # bad key or out of calls: do not retry
                raise
        except Exception:
            if attempt == tries - 1:
                raise
        time.sleep(5 * (attempt + 1))


def tidy(entries, seen):
    """API response -> {week: {"ap": [[rank, school], ...], "cfp": [...]}}."""
    out = {}
    for e in entries:
        polls = {}
        for p in e.get("polls", []):
            seen.add(p.get("poll", ""))
            k = poll_key(p.get("poll", ""))
            if k is None:
                continue
            ranks = sorted(((int(x["rank"]), x["school"]) for x in p.get("ranks", []) if x.get("rank") is not None),
                           key=lambda t: (t[0], t[1]))
            if ranks:
                polls[k] = [[rk, school] for rk, school in ranks]
        if polls:
            out[str(int(e["week"]))] = polls
    return {w: out[w] for w in sorted(out, key=int)}


def main():
    folder = sys.argv[1]
    first = int(sys.argv[2]) if len(sys.argv) > 2 else 2014
    last = int(sys.argv[3]) if len(sys.argv) > 3 else 2026
    key = os.environ.get("CFBD_API_KEY", "").strip()
    if not key:
        print("No CFBD_API_KEY set: skipping the AP and CFP rankings. Saved files, if any, are still used.")
        return
    os.makedirs(folder, exist_ok=True)
    calls, seen = 0, set()
    month = datetime.datetime.now(datetime.timezone.utc).month
    for y in range(first, last + 1):
        path = os.path.join(folder, f"{y}.json")
        old = json.load(open(path)) if os.path.exists(path) else None
        if y < last and old and old.get("regular") and old.get("postseason"):
            continue   # a finished season, already saved
        try:
            new = {"season": y, "regular": tidy(get(key, y, "regular"), seen)}
            calls += 1
            # The final AP poll comes out in January, after the title game.
            if y < last or month in (1, 2):
                new["postseason"] = tidy(get(key, y, "postseason"), seen)
                calls += 1
            else:
                new["postseason"] = (old or {}).get("postseason", {})
        except Exception as err:   # keep the pipeline running on whatever is already saved
            print(f"::warning::Could not fetch rankings for {y}: {err}. Keeping the saved file, if there is one.")
            if isinstance(err, urllib.error.HTTPError) and err.code in (401, 403, 429):
                break
            continue
        if old and not new["regular"] and old.get("regular"):
            print(f"::warning::The API returned no regular-season polls for {y}; keeping the saved file.")
            continue
        with open(path, "w", encoding="utf-8") as f:
            json.dump(new, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        weeks = new["regular"]
        cfp_weeks = [w for w in weeks if "cfp" in weeks[w]]
        print(f"{y}: {len(weeks)} regular-season weeks, AP in {sum('ap' in weeks[w] for w in weeks)}, "
              f"CFP in {len(cfp_weeks)} (weeks {', '.join(cfp_weeks) or 'none'}), "
              f"final AP poll {'saved' if new['postseason'] else 'not yet'}")
    print("API calls used:", calls, "| poll names seen:", sorted(n for n in seen if n))


if __name__ == "__main__":
    main()
