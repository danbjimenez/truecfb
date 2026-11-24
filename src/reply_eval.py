"""TrueCFB reply bot: try the model step on the sample mentions in data/bot/reply_samples.json and
report how often it reads them right, what the reply would be, and what it costs.

  reply_eval.py <site_dir> <samples.json> <provider[:model]> [<provider[:model]> ...]
  e.g. reply_eval.py site data/bot/reply_samples.json claude claude:claude-haiku-5-5 grok

Needs ANTHROPIC_API_KEY for claude and XAI_API_KEY for grok (run it from the "Reply bot: try the
model" job, which has them). A provider whose key is missing is left out. Writes a table to the job
summary when GITHUB_STEP_SUMMARY is set.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reply_model as M  # noqa: E402
import reply_templates as R  # noqa: E402

# US dollars per million tokens: input, cached input, output (Anthropic and xAI price pages, Nov 2026)
PRICES = {"claude-sonnet-5-5": (2.00, 0.10, 10.00), "claude-haiku-5-5": (0.10, 0.01, 0.50),
          "claude-opus-5-5": (4.00, 0.20, 20.00), "grok-4.3": (1.25, 0.20, 2.50), "grok-4.7": (2.00, 0.50, 6.00)}
KEYS = {"claude": "ANTHROPIC_API_KEY", "grok": "XAI_API_KEY"}


def cost(info):
    p = PRICES.get(info["model"])
    if not p:
        return None
    fresh = max(info["in"] - info["cached"], 0)
    return (fresh * p[0] + info["cached"] * p[1] + info["out"] * p[2]) / 1e6


def judge(s, got):
    want_teams = set(s.get("teams", [])); want_confs = set(s.get("conferences", []))
    want_season = None if s.get("season", "current") == "current" else int(s["season"])
    ok_intent = got["intent"] == s["intent"]
    ok_names = s["intent"] == "skip" or (set(got["teams"]) == want_teams and set(got["conferences"]) == want_confs)
    ok_season = s["intent"] == "skip" or got["season"] == want_season
    return ok_intent and ok_names and ok_season


def run(book, samples, provider, model):
    teams = sorted({t for y in book.seasons for t in book.teams(y)})
    confs = sorted({c for y in book.seasons for c in book.conferences(y)})
    rows, right, spent = [], 0, 0.0
    for s in samples:
        try:
            got, info = M.read(s["post"], s.get("above", ""), teams, confs, book.seasons, book.current, provider, model)
        except Exception as err:
            rows.append((s, None, f"error: {err}", None)); continue
        ok = judge(s, got); right += ok
        c = cost(info); spent += c or 0
        try:
            text = R.reply(book, got["intent"], got["teams"], got["conferences"], got["season"])
        except R.Unanswerable as why:
            text = f"(no draft: {why})"
        rows.append((s, got, text, ok))
    return rows, right, spent, model


def main():
    site_dir, samples_path, wanted = sys.argv[1], sys.argv[2], sys.argv[3:]
    book = R.Book(site_dir, os.path.join(os.path.dirname(samples_path)))
    samples = json.load(open(samples_path))["samples"]
    out = []
    for w in wanted:
        provider, _, model = w.partition(":")
        model = model or M.DEFAULT_MODEL[provider]
        if not os.environ.get(KEYS[provider]):
            print(f"skipping {w}: {KEYS[provider]} not set")
            continue
        rows, right, spent, model = run(book, samples, provider, model)
        out.append(f"## {provider} · {model}: {right} of {len(samples)} read right · ${spent:.4f} in all "
                   f"(${spent / max(len(samples), 1):.5f} a mention)\n")
        out.append("| ok | post | post above | read as | reply |\n|---|---|---|---|---|")
        for s, got, text, ok in rows:
            read_as = "-" if got is None else f"{got['intent']} {', '.join(got['teams'] + got['conferences'])} {got['season'] or ''}".strip()
            cell = lambda x: str(x).replace("|", "/").replace("\n", "<br>")
            out.append(f"| {'yes' if ok else '**no**'} | {cell(s['post'])} | {cell(s.get('above', ''))} | {cell(read_as)} | {cell(text)} |")
        out.append("")
    report = "\n".join(out) or "No provider had its key set."
    print(report)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(report + "\n")


if __name__ == "__main__":
    main()
