"""TrueCFB reply bot: try the model on the sample mentions in data/bot/reply_samples.json and report,
for each, whether it answered or skipped as expected, the reply it wrote (or why there is none), what
it looked up, and what it cost.

  reply_eval.py <site_dir> <samples.json> <provider[:model]> [<provider[:model]> ...]
  e.g. reply_eval.py site data/bot/reply_samples.json grok grok:grok-4.3 claude

Needs XAI_API_KEY for grok and ANTHROPIC_API_KEY for claude (run it from the "Reply bot: try the
model" job, which has them). A provider whose key is missing is left out. Writes a table to the job
summary when GITHUB_STEP_SUMMARY is set. Each run costs money: by default only the samples marked core
(SAMPLE_SET=all for every one); SAMPLE_FROM=n starts at the nth, SAMPLE_LIMIT=n stops after n.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reply_agent as A  # noqa: E402
import reply_book as R  # noqa: E402
import reply_model as M  # noqa: E402

# US dollars per million tokens: input, cached input, output (Anthropic and xAI price pages, Nov 2026)
PRICES = {"claude-sonnet-5-5": (2.00, 0.10, 10.00), "claude-haiku-5-5": (0.10, 0.01, 0.50),
          "claude-opus-5-5": (4.00, 0.20, 20.00), "grok-4.3": (1.25, 0.20, 2.50), "grok-4.7": (2.00, 0.50, 6.00)}
KEYS = {"claude": "ANTHROPIC_API_KEY", "grok": "XAI_API_KEY"}
WORKERS = 3            # questions in flight at once (the API key allows 60 requests a minute)
OUTCOMES = ["replied", "skipped", "checks failed", "error"]


def cost(model, u):
    p = PRICES.get(model)
    if not p:
        return 0.0
    fresh = max(u["in"] - u["cached"], 0)
    return (fresh * p[0] + u["cached"] * p[1] + u["out"] * p[2]) / 1e6


def outcome(res):
    if res["status"] == "drafted":
        return "replied"
    if res["status"] == "declined":
        return "skipped"
    return "error" if any(p.startswith("model error") for p in res["problems"]) else "checks failed"


def as_expected(expect, got):
    return expect == "either" or (expect == "reply" and got == "replied") or (expect == "skip" and got == "skipped")


def one(book, s, provider, model):
    t0 = time.monotonic()
    res = A.answer(book, s["post"], s.get("above", ""), provider=provider, model=model)
    got = outcome(res)
    if got == "replied":
        text, why = res["reply"], res["note"]
    elif got == "skipped":
        text, why = "(skipped)", res["note"]
    else:
        text = "(no draft)"
        why = "; ".join(res["problems"]) + (f" (model wrote: {res['rejected']})" if res["rejected"] else "")
    return {"s": s, "got": got, "ok": as_expected(s.get("expect", "reply"), got), "text": text, "why": why,
            "lookups": ", ".join(res["lookups"]) or "-", "turns": len(res["usage"]),
            "dollars": sum(cost(res["by"] or model, u) for u in res["usage"]),
            "seconds": round(time.monotonic() - t0, 1)}


def run(book, samples, provider, model):
    from concurrent.futures import ThreadPoolExecutor
    rows = [None] * len(samples)
    with ThreadPoolExecutor(WORKERS) as pool:
        futures = [pool.submit(one, book, s, provider, model) for s in samples]
        for i, f in enumerate(futures):
            rows[i] = r = f.result()
            print(f"[{model} {i + 1}/{len(samples)}] {r['got']}{'' if r['ok'] else ' (NOT AS EXPECTED)'} · "
                  f"{r['turns']} turns, {r['seconds']} s · {r['s']['post'][:60]!r} -> {r['text'][:160]!r}", flush=True)
    return rows


def section(provider, model, rows):
    n = len(rows)
    tally = {k: sum(r["got"] == k for r in rows) for k in OUTCOMES}
    spent = sum(r["dollars"] for r in rows)
    secs = sorted(r["seconds"] for r in rows)
    turns = sorted(r["turns"] for r in rows)
    mid = lambda xs: xs[len(xs) // 2] if xs else 0
    out = [f"## {provider} · {model}: {sum(r['ok'] for r in rows)} of {n} as expected · ${spent:.4f} in all "
           f"(${spent / max(n, 1):.4f} a mention) · {mid(secs)} s a question (median), {secs[-1] if secs else 0} s slowest · "
           f"{mid(turns)} model turns (median), {turns[-1] if turns else 0} most\n",
           " · ".join(f"{k}: {v}" for k, v in tally.items()) + "\n",
           "| as expected | post | post above | expected | reply | based on / why | looked up |\n|---|---|---|---|---|---|---|"]
    cell = lambda x: str(x).replace("|", "/").replace("\n", "<br>")
    for r in rows:
        out.append(f"| {'yes' if r['ok'] else '**no**'} | {cell(r['s']['post'])} | {cell(r['s'].get('above', ''))} | "
                   f"{r['s'].get('expect', 'reply')} | {cell(r['text'])} | {cell(r['why'])} | {cell(r['lookups'])} |")
    return "\n".join(out) + "\n"


def main():
    site_dir, samples_path, wanted = sys.argv[1], sys.argv[2], sys.argv[3:]
    book = R.Book(site_dir, os.path.dirname(samples_path))
    samples = json.load(open(samples_path))["samples"]
    # Each run costs real money (about $0.012 a sample with Grok 4.7): the core set by default.
    if os.environ.get("SAMPLE_SET", "core") != "all":
        samples = [x for x in samples if x.get("core")]
    if os.environ.get("SAMPLE_FROM", "").isdigit():
        samples = samples[int(os.environ["SAMPLE_FROM"]) - 1:]
    if os.environ.get("SAMPLE_LIMIT", "").isdigit():
        samples = samples[:int(os.environ["SAMPLE_LIMIT"])]
    done = 0
    for w in wanted:
        provider, _, model = w.partition(":")
        model = model or M.DEFAULT_MODEL[provider]
        if not os.environ.get(KEYS[provider]):
            print(f"skipping {w}: {KEYS[provider]} not set")
            continue
        report = section(provider, model, run(book, samples, provider, model))
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
