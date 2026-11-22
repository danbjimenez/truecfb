"""TrueCFB: download the public game files the pipeline reads.
Usage: fetch_data.py <schedules_dir> <espn_dir> [first_year] [last_year]

Sources (GitHub raw, both public):
  sportsdataverse/cfbfastR-data      schedules/csv/cfb_schedules_{year}.csv          (CollegeFootballData-derived)
  sportsdataverse/cfbfastR-cfb-raw   cfb/schedules/parquet/cfb_schedule_{year}.parquet   (ESPN)
"""
import os
import sys
import time
import urllib.request

CSV = "https://raw.githubusercontent.com/sportsdataverse/cfbfastR-data/main/schedules/csv/cfb_schedules_{y}.csv"
PARQUET = "https://raw.githubusercontent.com/sportsdataverse/cfbfastR-cfb-raw/main/cfb/schedules/parquet/cfb_schedule_{y}.parquet"


def fetch(url, path, tries=4):
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                body = r.read()
            if len(body) < 1000:
                raise ValueError(f"file is only {len(body)} bytes")
            with open(path + ".part", "wb") as f:
                f.write(body)
            os.replace(path + ".part", path)
            return len(body)
        except Exception as err:  # retry on any network or size problem
            if attempt == tries - 1:
                raise RuntimeError(f"could not download {url}: {err}")
            time.sleep(5 * (attempt + 1))


def main():
    sched_dir, espn_dir = sys.argv[1], sys.argv[2]
    first = int(sys.argv[3]) if len(sys.argv) > 3 else 2013
    last = int(sys.argv[4]) if len(sys.argv) > 4 else 2026
    os.makedirs(sched_dir, exist_ok=True)
    os.makedirs(espn_dir, exist_ok=True)
    for y in range(first, last + 1):
        a = fetch(CSV.format(y=y), os.path.join(sched_dir, f"cfb_schedules_{y}.csv"))
        b = fetch(PARQUET.format(y=y), os.path.join(espn_dir, f"cfb_schedule_{y}.parquet"))
        print(y, "results file", a, "bytes | ESPN file", b, "bytes")


if __name__ == "__main__":
    main()
