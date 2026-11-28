# The @truecfb reply bot

Status: **live since 26 Nov 2026** (`REPLIES_LIVE` is `true`; every reply still waits for Dan's "Post reply" tap). Dan chose not to file X's written-approval request (section 1). **24 Nov 2026 (Dan's call): the model writes the reply**, and code checks every number before Dan sees it. **25 Nov 2026 (Dan's call): any college football question**, not a fixed list of question types: the model looks up the engine's numbers it needs (rankings, a team's season, two teams, conferences, the CFP and AP beside TrueCFB, the season's best and worst Game Ratings) and answers from them. Grok 4.7 is the default model.

When someone tags @truecfb (usually under another account's post, asking it to weigh in), a model works out what TrueCFB's numbers say about it, looking them up as it goes, and writes the reply. Code checks that every number in the reply is one a lookup returned for that question. It starts in draft mode: each draft goes to Telegram, and nothing posts until Dan taps.

## 1. X's rules (checked 23 Nov 2026)

| Question | Answer | Source |
|---|---|---|
| Do AI reply bots need X's written approval? | **The sources disagree.** The Help Center automation rules ("Updated April 2026", read 23 Nov) still say any AI reply bot "requires prior written and explicit approval from X". The developer docs dropped that on 17 Nov 2026 (docs PR #553, merged): "No written approval needed—must follow all automation rules." The changelog entry for that change (PR #554) is still an unmerged draft. | [Automation rules](https://help.x.com/en/rules-and-policies/x-automation), [Developer Guidelines](https://docs.x.com/developer-guidelines), [docs PR #553](https://github.com/xdevplatform/docs/pull/553), [PR #554](https://github.com/xdevplatform/docs/pull/554) |
| When can the API post a reply? | Self-serve apps (pay-per-use included), since 23 Feb 2026: only when "the original post's author has explicitly summoned the replying account by @mentioning them or quoting one of their posts." | [Manage Posts](https://docs.x.com/x-api/posts/manage-tweets/introduction), [changelog, 23 Feb 2026](https://docs.x.com/changelog) |
| What does that mean for us? | We can reply **to the post that tags us** (its author summoned us). We cannot reply to the post above it (the other account's post) unless that author tagged us too. | same |
| Other reply rules | The user must opt in first (a mention that asks for a response counts). One automated reply per interaction. A clear way to opt out, honored promptly. No replies triggered by keyword searches. Filter sensitive content. Check the post still exists before replying. The account needs the Automated label (already on), a bio that says it is automated, and a link to a human-run account. | [Automation rules](https://help.x.com/en/rules-and-policies/x-automation), [Developer Guidelines](https://docs.x.com/developer-guidelines) |

**Recommendation:** build in draft mode now (drafts only read from X, so no approval question arises). Before the first live reply, file an approval request through the developer portal anyway. It costs nothing and covers us while the Help Center still says approval is required. A forum thread reports X staff saying human-reviewed AI replies still need approval; another reports the opposite. Neither is official.

### What reading costs (pay-per-use)

From [X's pricing page](https://docs.x.com/x-api/getting-started/pricing) (no date on the page):

| Item | Price |
|---|---|
| Our own mentions (`GET /2/users/:id/mentions`, user-context auth) | $0.001 per post returned ("owned read") |
| Any other post read (the parent post; mentions read with an app-only token) | $0.005 per post |
| User read | $0.010 per user |
| Post: Create | $0.015 |
| Post: Create (summoned) | $0.010. X doesn't define "summoned"; most likely a reply to a post that tagged us. |
| Post with a link | $0.200, so **replies never carry a link** (not even a bare "truecfb.com", which X turns into a link) |

The same resource read twice in one UTC day is billed once. Reads are billed per post returned, so an empty mentions check should cost nothing; check the usage page in the first week to confirm. Cap: 3 million post reads a month. A spend limit can be set in the console.

## 2. Grok or Claude?

The model never decides a number (section 3), but since 24 Nov it writes the reply's words, so its writing and how well it keeps to the rules now matter. Reading the question (`{what's being asked, which teams}`) is easy for any current model; the model test (`reply_eval.py`) shows both steps side by side.

| | Grok (xAI API) | Claude (Anthropic API) |
|---|---|---|
| Cost per question (read ≈1,500 tokens in; write ≈4,200 in, of which ≈2,900 cached, plus the reply) | Grok 4.3: ≈$0.005. Grok 4.7: ≈$0.009 | Haiku 5.5: ≈$0.0005. Sonnet 5.5: ≈$0.01 |
| Structured output (a fixed JSON shape, team names from a list of 138) | Yes | Yes (`strict` schemas with an enum) |
| Where it runs | GitHub Actions, key in GitHub secrets | Same |
| X-native extras | `x_search` can read threads ($5 per 1,000 posts). Not needed: we get the parent post from the X API, and we want the model to see only the tweet, not go looking for outside numbers. | None needed |
| New account and bill | Yes (xAI) | Yes (Anthropic API billing is separate from a Claude subscription) |

Prices: [xAI models page](https://docs.x.ai/docs/models) (read 23 Nov 2026); Anthropic's model price table as of 3 Nov 2026.

- **"Grok powers it" can't mean @grok answers with TrueCFB numbers.** @grok is xAI's own account, and we can't feed it the engine. The way to get Grok quoting TrueCFB is the separate open item "Readable by Grok and search engines" (`rankings.json`, `llms.txt`, a page per team).
- Using Grok gives no known edge with X's rules or approval.
- **Pick (24 Nov 2026): Grok.** Dan's Anthropic account is a work account and he wants this project's spend kept on the X / xAI side. Grok 4.7 is the default since the model test of 24 Nov 2026 (64 samples): it read 62 right against Grok 4.3's 59, and all 55 of its replies passed the checks on the first try, with none of the false claims 4.3 made, for about $0.009 a question against $0.004. The model test can still compare models (and Claude, if a key is ever added) on the same sample mentions, for cents. The provider is chosen automatically: Grok when `XAI_API_KEY` is set, unless `REPLY_PROVIDER` says otherwise.
- **Billing:** the xAI API account (console.x.ai) is separate from the X developer account and bills separately, prepaid by default. Sign up with @truecfb's X account to keep it apart from work accounts. Linking the xAI team to the X developer account earns xAI credits (up to 20% back) on X API credit purchases ([X API pricing](https://docs.x.com/x-api/getting-started/pricing), [xAI billing](https://docs.x.ai/console/billing)).

## 3. Plan

### Flow

```
X mention ─► Worker cron (every 5 min in game windows, 15 otherwise)
              GET /2/users/:id/mentions?since_id=…   (read-only app token)
              new ids? ─► dispatch reply-draft.yml
                              │
reply-draft.yml (Actions) ◄───┘
  1. fetch the mention + the post it replies to or quotes
  2. skip filters: opted out, already handled, sensitive, our own posts
  3. model: reads the post, calls lookups (engine files, site/*.json),
     as many as it needs, then calls reply (or skip)
  4. code checks the reply: every number in this question's lookups or
     the rules, brand and X rules, no predictions, ≤280.
     Fails ─► one rewrite ─► still failing: no draft
  5. Telegram draft: what they asked, the post above, the reply, what it
     rests on, what was looked up   [Post reply] [Skip]
  6. commit data/bot/replies.json (handled ids, newest id)
                              │
Dan taps Post reply ─► Worker /hooks/telegram ─► post-reply.yml
  re-check: post still exists, not replied before, not opted out
  POST /2/tweets  reply.in_reply_to_tweet_id = mention
                  reply.exclude_reply_user_ids = everyone but the asker
  record in data/bot/replies.json, link back in Telegram
```

### Picking up mentions: Worker cron, not an Actions cron

- **Worker** (recommended): it already wakes every 5 minutes, is on time, and starts a GitHub job only when there is something new. It gets a new **read-only** secret, `X_BEARER_TOKEN` (app-only). It still never holds the X write keys and never computes a rating. The newest handled id comes from `site/replies.json`, the same pattern as `site/live.json`; Actions also checks `data/bot/replies.json`, so a duplicate dispatch does nothing.
- **Actions cron**: GitHub delays scheduled runs by 5 to 30 minutes and runs a ~40-second job even when there is nothing to do. Not worth it.
- **Push (26 Nov 2026, Dan's call):** X's Activity API pushes each mention (`post.mention.create`) to `https://truecfb.com/hooks/x` the moment it happens, and the Worker starts the draft job, so the wait is the job and the model (a minute or two), not the next check. The Worker answers X's ownership check and verifies every push with the app's OAuth 2.0 client secret (`X_CLIENT_SECRET`, a Cloudflare secret; it cannot post on its own). X pushes posts that type @truecfb but not replies under @truecfb's own posts (found 28 Nov 2026), so with push on the Worker still checks the mentions every 5 minutes; that also covers X turning the webhook off after failed checks. An empty check costs nothing. Cost: X bills each pushed event (its price table does not list mentions yet; likely about $0.005, the same as reading the mention). Set up with Actions → "Reply bot: set up push" (`src/x_push.py`), steps below.

### What the model does and what the engine does

| Model (Grok 4.7 by default; tool calls) | Engine and code |
|---|---|
| **Reads** the post and the post above it, decides what TrueCFB's numbers can say about it, and **looks them up** (`reply_facts.LOOKUPS`): `rankings`, `team` (a season game by game, each Game Rating split into its parts), `matchup` (two teams, the gap, their game), `conference`, `polls` (the CFP ranking or AP poll beside TrueCFB's ranking at the same point, and the biggest differences), `games` (a season's highest or lowest Game Ratings, in wins, losses or all games), `upcoming` (games not yet played, from the public schedule file the ratings jobs read, with kickoff times), `stakes` (the picture around a cut: each team's next game and what a win or loss would do to its rank), `what_if` (one game not yet played, a close and a two-score result each way, the margin a win needs to move up, and help from losses by the teams just above: the engine re-run with that game added, so every what-if number is engine output; `src/reply_whatif.py`, from `site/whatif.json`). The `team` lookup also gives the team's games still to play and its conference record; `conference` gives every member's record in games between members | Every number, from the engine's files only (`reply_book.Book`): rank, Team Rating, Game Rating and its parts, Matchup Rating, Conference Rating, record, the CFP and AP ranks the engine published beside its own (`site/rank_*.json`), gaps and changes |
| **Writes** the reply, with the README's rules word for word as its knowledge of the rules (`reply_facts.primer`, read from the README on every run). May use general football knowledge in words; may not add a number of its own | **Checks** the reply (`reply_agent.problems`): every number must be written in something a lookup returned for this question, or in the rules, sign included; brand and X rules; no prediction wording. One rewrite, then no draft (Telegram shows the attempt and why) |
| Never calculates: the lookups already split each Game Rating into its parts (result, opponent's strength, margin, venue, postseason, the 0 to 100 limit) and give every gap | Splits each Game Rating the way the site's How it works page does, from the engine's published settings and margin curve; the split matches every published Game Rating of every season to rounding (`tests/test_reply_bot.py`) |

What the check cannot catch: a number used for the wrong thing (calling a Game Rating the Team Rating, or quoting a real 8-point margin as "8 points better"), a claim made from general knowledge in words, and wording that predicts without the usual words. Dan reads every draft, with what the model looked up and what it says the reply rests on.

**Games not yet played and the voice (26 Nov 2026, Dan's call):** a reply to "what are the implications for tonight's Texas Tech game?" read like a stat line and didn't know who Tech was playing. Dan wants an analyst's answer: what's at stake in the conference race, what a win or a loss would do to the rating and the rank. So the bot can now see the schedule, conference records, what-ifs and the photos in the two posts (a mention under a graphic of five 9-2 teams asked about what the graphic showed), and the prompt asks for conversational sentences with two or three numbers at most. A what-if is not a prediction: it never says who will win.

**Playoff questions (28 Nov 2026, Dan's call):** asked "what does BYU need to do to get into the CFP?", the bot opened with "TrueCFB rates results, not predictions, so it cannot say…", a bummer way to engage. Now `what_if` also gives how big a win it takes to move up (every margin from 1 to 40, where margin stops counting) and which losses by the three teams just above would move the team further (the engine re-run with both games added), and the prompt asks for an analyst's answer: where the team stands in TrueCFB and with the committee, what's in its hands, what help it needs. It still never says what the committee will do.

Tuned with the model test the same day (four rounds, about $0.80): `what_if` also takes an exact `margin` ("what if they win by 30"), re-runs a game already played with its result changed ("what if Texas had beaten Florida"), gives the smallest win that passes a team above once that team loses, says when a game is not on the schedule, and for a team with no game left lists which losses above it would move it up. A `stakes` lookup gives the picture around a cut in one call: each team's committee rank, next game, and rank after a close win, a 40-point win and a close loss.

`site/whatif.json` holds the newest season's engine inputs unrounded (`run_all.py` writes it), and a what-if first re-runs the season without the extra game and must reproduce the published ratings and ranks exactly, or it gives nothing.

**Why lookups instead of fixed question types (25 Nov 2026):** the first live test, "where does the CFP committee diverge the most from your rankings, and why?", fit none of the eight types and got no draft. Adding a type for each new kind of question doesn't scale; giving the model lookups does, and the number check works the same on whatever it looked up. The fixed templates went with the types.

Rules for every reply, enforced in code like `game_impact.post_text`:
- **TrueCFB** spelling, the current version (**2026.2**, from `engine.VERSION`), **Rating** (never "score" for a TrueCFB number; "score" only for points, as in 28-20).
- One decimal on ratings; signed changes with a real minus sign (−); "NR" for unranked.
- Describes, never predicts; no hype, no emoji; fan terms.
- No links, no hashtags, no @mentions in the text. `exclude_reply_user_ids` keeps the other account in the thread from being mentioned automatically.
- 2020 numbers carry "(2020 is flagged unreliable)".
- ≤280 weighted characters; lines drop in a set order to fit.

### Telegram draft

Same bot and chat as the result posts. The message shows what they asked, the post above, a link to the mention (the handle is on X; looking it up through the API costs $0.010), the drafted reply and the model that wrote it, what the reply rests on, and what it looked up. A mention whose reply failed the checks twice gets its own message with the model's attempt and why, and no buttons; mentions the model chose to skip are listed in one message per run, with its reason. Buttons: **Post reply** (only while `REPLIES_LIVE` is `true`) and **Skip**, as `rpost:<id>` / `rskip:<id>` taps beside the result posts' `post:` / `skip:`. Tap behavior is the same as today: buttons come off first, so a double tap can't post twice.

### One answer shape (28 Nov 2026, Dan's call)

A perfect analyst for every question isn't possible; showing the math is. Every reply is "here is what TrueCFB's numbers say about your question", in two or three sentences: (1) the TrueCFB answer in words, (2) the math behind it: the one or two results or numbers that drive it, (3) what's next when it helps. Replies never say what TrueCFB can't do, doesn't rate or won't predict: "best QB?" gets "on results alone, Georgia is the team to beat, and here is why". `reply_agent.DISCLAIMS` rejects disclaimer wording ("TrueCFB doesn't…", "can't say", "not predictions") and the model rewrites once, like any other failed check.

**Which part of the formula decides it.** A Team Rating is the average of its Game Ratings, and each Game Rating adds win/loss (70 or 30), opponent strength, margin and venue, so a Team Rating splits exactly into those four averages, and the gap between two teams into four part gaps. The `team` lookup gives the split; `matchup` gives both splits, the part gaps, the part that puts one team ahead and the parts that pull the other way. The prompt asks the model to name the deciding part in fan terms: "the extra win", "a tougher schedule", "bigger wins". Example: Texas Tech is 1.2 above BYU because its record (+3.9) and margins (+1.2) outweigh BYU's tougher schedule (−3.7).

### Answering a post Dan picks (28 Nov 2026)

When Dan sees a post @truecfb should answer, he shares its link with the Telegram bot; any words after the link are his note on what to cover ("focus on the playoff angle"). The Worker (Dan's chat only) starts "Reply drafts" with that post id, and the draft arrives like any other.
- **Quote post or reply.** X allows API replies only to posts that tag @truecfb, so a picked post that doesn't is drafted as a **quote post** ("Post as quote" button): it shows on @truecfb's timeline above their post, and the model is told to write it to stand on its own. A picked post that does tag @truecfb gets a normal reply ("Post reply").
- **Or send it yourself as a reply.** Every picked draft also has a **Reply on X (you send it)** button: X's web intent link (`x.com/intent/post?in_reply_to=<id>&text=...`), which opens X's reply box under the post with the draft filled in. Dan taps Post himself, logged in as @truecfb, so it can go under a post that doesn't tag @truecfb (X has no API for saved drafts). It is not recorded as posted in `replies.json`. Make sure the X app or browser is on the @truecfb account.
- The same checks as a mention: the author's opt-out, posts marked sensitive, every number checked against the engine. Not drafted twice, and never @truecfb's own posts.
- A picked post is not a mention: it does not move the Worker's record of the newest mention handled.
- Each quote post is approved by Dan, like every reply; X's automation rules still apply (no bulk or keyword-driven posting).

### The pieces

| File | What |
|---|---|
| `src/reply_agent.py` | The prompt, the loop (lookups, then `reply`), the checks and the one rewrite |
| `src/reply_facts.py` | The lookups the model can call (every number from the engine's files), each Game Rating split into its parts, the README primer, and the number check |
| `src/reply_book.py` | The engine's files, read once (`site/data.json`, `history.json`, `sched_*.json`, `rank_*.json`, `data/bot/drafts.json`), and the public schedule file for games not yet played; `check()` holds the wording rules |
| `src/reply_whatif.py`, `site/whatif.json` | What-ifs: the frozen engine re-run on the newest season with one made-up result added; the file is the season's unrounded engine inputs, written by `run_all.py` |
| `src/reply_model.py` | The conversation with the model, with tool calls, for Grok (xAI) and Claude. Grok when `XAI_API_KEY` is set, Claude with `REPLY_PROVIDER=claude` |
| `src/reply_bot.py` | `draft` (read mentions, filter, the model answers, save), `send` (Telegram), `post` (one approved reply) |
| `src/reply_eval.py`, `data/bot/reply_samples.json` | 83 made-up mentions, each marked reply, skip or either (how-it-works, why-is-X-ranked-there, the CFP, best losses, games not yet played, a player question, prompt injections), to try a model on |
| `tests/test_reply_bot.py` | Every lookup on every season; the Game Rating split against every published game; the number and wording checks; the loop, the rewrite and skips with a stand-in model |
| `.github/workflows/reply-draft.yml` | Started by the Worker; drafts and sends to Telegram |
| `.github/workflows/post-reply.yml` | Started by a "Post reply" tap; posts only while `REPLIES_LIVE` is `true` |
| `.github/workflows/reply-eval.yml` | "Reply bot: try the model", by hand |
| `worker/index.js` | `/hooks/x` (X's push of mentions, with `X_CLIENT_SECRET`), `pollMentions()` (the backup check; only runs when `X_BEARER_TOKEN` and `X_USER_ID` are set) and the `rpost:` / `rskip:` taps |
| `src/x_push.py`, `.github/workflows/x-push.yml`, `tests/test_worker_xhook.mjs` | Register the webhook and the mention subscription with X; the Worker hook's signing checked against Node's HMAC (`node tests/test_worker_xhook.mjs`) |
| `data/bot/replies.json`, `data/bot/optout.json`, `site/replies.json` | What was handled (ids, which lookups were used, the reply, what happened; never the text people wrote), opt-outs as hashes, and the newest handled id for the Worker |
| `requirements-reply.txt` | `anthropic`, for the reply jobs only (Grok is called with `requests`) |

Run the tests with `python tests/test_reply_bot.py` (no keys needed). Try one question by hand with `python src/reply_agent.py "<post>"` (needs `XAI_API_KEY`).

### Cost per reply

| | Posted reply | Skipped draft |
|---|---|---|
| Mention read: the Worker's check (app-only token) plus the draft job's read (own account) | $0.006 | $0.006 |
| Parent post read (when there is one) | $0.005 | $0.005 |
| Model: lookups and the reply (Grok 4.7, 2 to 3 turns; 78-question test, 25 Nov 2026) | ≈$0.014 | ≈$0.014 |
| Reply post ("summoned"; $0.015 if X bills it as a plain post) | $0.010 | none |
| **Total** | **≈$0.035** | **≈$0.025** |

The Worker only checks whether there is anything new (up to 5 posts); the draft job then reads them with the account's own keys at $0.001 each. Putting the write keys on the Worker would save $0.005 a mention; not worth it. At 100 replies a week, about $3.50 a week. GitHub Actions minutes are free on a public repo.

### Risks

1. **X approval, unclear.** Help Center says approval is required; developer docs say it isn't. Mitigation: draft mode first; ask X before going live.
2. **Account limits.** Replies outside the "summoned" rule return 403, and a forum thread reports accounts getting temporarily limited after such errors. Mitigation: only reply to the mention itself, check before posting, stop on the first 403.
3. **Mentioning people who didn't opt in.** A reply in someone else's thread can auto-mention the original poster. Mitigation: `exclude_reply_user_ids`, no handles in text.
4. **Prompt injection and trolling.** The model's words now reach the draft. Mitigations: posts are passed as data and the model is told to skip anything that tells it what to say; the lookups only read the engine's files, and their fields only take team, conference, season and poll names; no number can get past the check unless a lookup returned it; Dan taps every reply.
5. **Wrong team.** "Miami", "USC", "the U", nicknames. Mitigation: the lookups only take names from the team list (anything else gets the closest names back), the model is told to skip when a name could mean two teams, and the draft shows what it looked up.
6. **Pile-ups.** A popular post could bring dozens of tags. Mitigation: at most one reply per user per thread; cap drafts per hour; X spend limit.
7. **Predictions.** TrueCFB describes, never predicts. The model is told so, and the check rejects common prediction wording ("will beat", "favored", "odds"). Wording that predicts without those words is on Dan's review.
8. **Bowl games.** Until the final 2026 CFP ranking is added on selection day (6 Dec), bowl results don't count. The lookups only hold games the engine has counted, so a question about a bowl game gets the two teams side by side, not that game.
9. **Token expiry.** `GITHUB_DISPATCH_TOKEN` expires about Nov 2027; the reply bot depends on it too.
10. **A wrong explanation of the formula in public.** The writer learns the rules from the README's own text, not a summary, and the model test includes how-it-works questions to read before going live.

## Turning it on

1. **Model key:** sign in at console.x.ai with @truecfb's X account, add credits (or link the X developer account for bonus credits), create an API key, and save it as the GitHub secret `XAI_API_KEY` (`gh secret set XAI_API_KEY` asks for it).
2. **Try the model:** Actions → "Reply bot: try the model" → Run. It runs the 13 samples marked core by default (about $0.15 with Grok 4.7); set `set` to `all` for all 83 (about $1), or use `from` and `limit` to rerun a few. The run summary shows, per model, how many it answered or skipped as expected, the reply it wrote for each (or why there is none), what it looked up, what each reply rests on, and the cost. To use something other than Grok 4.7, set the GitHub variable `REPLY_MODEL` (and `REPLY_PROVIDER` for Claude).
3. **X read token and id:** in the X developer console (app `truecfb-bot`), copy the app's Bearer Token into the Cloudflare secret `X_BEARER_TOKEN`. Run Actions → "Reply drafts" once by hand: its log prints @truecfb's user id. Save it as the GitHub variable `X_USER_ID` and the Cloudflare variable `X_USER_ID`. The Worker starts checking mentions on its next run.
4. **Drafts arrive in Telegram** with a Skip button only ("draft mode: posting is off"). Skipped mentions are listed in one message per run.
5. **Before going live:** update the bio (automated account, tag it for a TrueCFB answer, reply "stop" to opt out, a link to Dan's account) and send X the approval request (section 1).
6. **Go live:** set the GitHub variable `REPLIES_LIVE` to `true`. New drafts get a "Post reply" button.

### Push (mentions arrive the moment they happen)

1. **X console** (console.x.com) → app `truecfb-bot` → **User authentication settings** → set up OAuth 2.0 (type: Web App or Automated App; callback URL `https://truecfb.com/`; website `https://truecfb.com`). Save, then copy the **OAuth 2.0 Client Secret** (shown once). This does not change the posting keys.
2. **Cloudflare** → Workers & Pages → `truecfb` → Settings → Variables and Secrets → add a **Secret** `X_CLIENT_SECRET` with that value → Deploy.
3. **GitHub** → Actions → "Reply bot: set up push" → Run with `setup`. It registers the webhook (X checks it right away) and subscribes it to mentions of @truecfb as @truecfb. If X refuses the subscription with these keys, it says so: X may want a one-time OAuth 2.0 sign-in by @truecfb instead.
4. Tag @truecfb: a draft should reach Telegram in a minute or two. `status` shows what is registered; `remove` undoes it (the backup check keeps working).

To pause: delete `REPLIES_LIVE` (stops posting) or the Cloudflare `X_BEARER_TOKEN` (stops the backup check); "Reply bot: set up push" → `remove` stops the push.
