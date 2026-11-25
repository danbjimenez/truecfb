"""TrueCFB reply bot: try the model on the sample mentions in data/bot/reply_samples.json and report
how often it reads them right, the reply it writes for each (and whether that reply passed the checks or
fell back to the template), and what it costs.

  reply_eval.py <site_dir> <samples.json> <provider[:model]> [<provider[:model]> ...]
  e.g. reply_eval.py site data/bot/reply_samples.json grok grok:grok-4.3 claude

Needs XAI_API_KEY for grok and ANTHROPIC_API_KEY for claude (run it from the "Reply bot: try the
model" job, which has them). A provider whose key is missing is left out. Writes a table to the job
summary when GITHUB_STEP_SUMMARY is set.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reply_model as M  # noqa: E402
import reply_templates as R  # noqa: E402
import reply_writer as W  # noqa: E402

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


WORKERS = 3            # questions in flight at once (the API key allows 60 requests a minute)


def one(book, s, teams, confs, provider, model):
    """Read and write one sample. Returns (row, dollars spent, tally key, seconds per call)."""
    try:
        got, info = M.read(s["post"], s.get("above", ""), teams, confs, book.seasons, book.current, provider, model)
    except Exception as err:
        return (s, None, f"error: {str(err)[:200]}", None, ""), 0.0, "error", []
    ok = judge(s, got)
    spent, secs = cost(info) or 0, [info.get("seconds", 0)]
    try:
        c = W.compose(book, got, s["post"], s.get("above", ""), provider=provider, model=model)
    except R.Unanswerable as why:
        return (s, got, f"(no draft: {why})", ok, ""), spent, "no draft", secs
    spent += sum(cost(u) or 0 for u in c["usage"])
    secs += [u.get("seconds", 0) for u in c["usage"]]
    if c["by"] == "template":
        how = "template: " + "; ".join(c["problems"]) + (f" (model wrote: {c['rejected']})" if c.get("rejected") else "")
        key = "template"
    else:
        how, key = c["note"], ("first try" if len(c["usage"]) == 1 else "after a rewrite")
    return (s, got, c["reply"], ok, how), spent, key, secs


def run(book, samples, provider, model):
    from concurrent.futures import ThreadPoolExecutor
    teams = sorted({t for y in book.seasons for t in book.teams(y)})
    confs = sorted({c for y in book.seasons for c in book.conferences(y)})
    tally = {"first try": 0, "after a rewrite": 0, "template": 0, "no draft": 0, "error": 0}
    rows, right, spent, secs = [None] * len(samples), 0, 0.0, []
    with ThreadPoolExecutor(WORKERS) as pool:
        futures = [pool.submit(one, book, s, teams, confs, provider, model) for s in samples]
        for i, f in enumerate(futures):
            row, dollars, key, sec = f.result()
            rows[i] = row; spent += dollars; tally[key] += 1; secs += sec; right += bool(row[3])
            print(f"[{model} {i + 1}/{len(samples)}] {key} · read {'right' if row[3] else 'WRONG'} · "
                  f"{row[0]['post'][:60]!r} -> {str(row[2])[:160]!r}", flush=True)
    return rows, right, spent, model, tally, secs


def section(samples, provider, model, rows, right, spent, tally, secs):
    secs = sorted(x for x in secs if x)
    mid = secs[len(secs) // 2] if secs else 0
    out = [f"## {provider} · {model}: {right} of {len(samples)} read right · ${spent:.4f} in all "
           f"(${spent / max(len(samples), 1):.5f} a mention) · {mid:.1f} s a call (median), {secs[-1] if secs else 0:.1f} s slowest\n",
           "Model's reply used: " + f"{tally['first try']} on the first try, {tally['after a rewrite']} after a rewrite · "
           f"template instead: {tally['template']} · no draft: {tally['no draft']} · errors: {tally['error']}\n",
           "| read right | post | post above | read as | reply | based on / why not used |\n|---|---|---|---|---|---|"]
    cell = lambda x: str(x).replace("|", "/").replace("\n", "<br>")
    for s, got, text, ok, how in rows:
        read_as = "-" if got is None else f"{got['intent']} {', '.join(got['teams'] + got['conferences'])} {got['season'] or ''}".strip()
        out.append(f"| {'yes' if ok else '**no**'} | {cell(s['post'])} | {cell(s.get('above', ''))} | {cell(read_as)} | {cell(text)} | {cell(how)} |")
    return "\n".join(out) + "\n"


def main():
    site_dir, samples_path, wanted = sys.argv[1], sys.argv[2], sys.argv[3:]
    book = R.Book(site_dir, os.path.join(os.path.dirname(samples_path)))
    samples = json.load(open(samples_path))["samples"]
    if os.environ.get("SAMPLE_LIMIT", "").isdigit():
        samples = samples[:int(os.environ["SAMPLE_LIMIT"])]
    done = 0
    for w in wanted:
        provider, _, model = w.partition(":")
        model = model or M.DEFAULT_MODEL[provider]
        if not os.environ.get(KEYS[provider]):
            print(f"skipping {w}: {KEYS[provider]} not set")
            continue
        rows, right, spent, model, tally, secs = run(book, samples, provider, model)
        report = section(samples, provider, model, rows, right, spent, tally, secs)
        print(report, flush=True)
        # Written as each model finishes, so a run cut short still keeps what it finished.
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
                f.write(report + "\n")
        done += 1
    if not done:
        print("No provider had its key set.")


if __name__ == "__main__":
    main()
