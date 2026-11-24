# The @truecfb reply bot

Status: **built in draft mode, 23 Nov 2026 (plan approved by Dan the same day). Off until its secrets are added**; see "Turning it on" at the end. Posting stays off until the GitHub variable `REPLIES_LIVE` is `true`. **24 Nov 2026 (Dan's call): the model now writes the reply** from a fact sheet of the engine's numbers and the README's rules, and code checks every number before Dan sees it; the fixed templates are the fallback. Grok is the default model.

When someone tags @truecfb (usually under another account's post, asking it to weigh in), a model reads the question, then writes the reply from the engine's numbers. Code checks that every number in the reply is one the engine published. It starts in draft mode: each draft goes to Telegram, and nothing posts until Dan taps.

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
- **Pick (24 Nov 2026): Grok.** Dan's Anthropic account is a work account and he wants this project's spend kept on the X / xAI side. Grok 4.3 is the default; the model test compares it with Grok 4.7 (and Claude, if a key is ever added) on the same sample mentions, for cents. The provider is chosen automatically: Grok when `XAI_API_KEY` is set, unless `REPLY_PROVIDER` says otherwise.
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
  3. model reads: tweet text ─► {intent, teams, season}   (no numbers)
  4. engine: fact sheet of every number for it (site/*.json, game_impact.py)
  5. model writes the reply from the fact sheet + the README's rules
     code checks it: every number on the sheet or in the rules, brand
     and X rules, no predictions, ≤280. Fails ─► one rewrite ─► template
  6. Telegram draft: who asked, their text, the parent post, the reply,
     the template version beside it   [Post reply] [Skip]
  7. commit data/bot/replies.json (handled ids, newest id)
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
- **Later:** X's Activity API pushes mention events to a webhook (wider reply and mention coverage, changelog 19 Nov 2026). The Worker could take those instead of polling. Not needed at this volume.

### What the model does and what the engine does

| Model (two calls, structured output) | Engine and code |
|---|---|
| **Reads** the mention and the parent post: `intent` from a fixed list, `teams` (names from the 138-team list only), optional `season`, `conference`, or `skip` with a reason | Every number: rank, Team Rating, Game Rating and its parts, Matchup Rating, Conference Rating, record, gaps and changes (`reply_facts.sheet`) |
| **Writes** the reply from the fact sheet, with the README's rules word for word as its knowledge of v1.0 (`reply_facts.primer`, read from the README on every run, so it always knows the version the engine runs) | **Checks** the reply (`reply_writer.problems`): every number must be written on the sheet or in the rules, sign included; brand and X rules; no prediction wording. One rewrite, then the fixed template |
| Never calculates: the sheet already has each Game Rating split into its parts (result, venue, opponent's bonus, postseason, the 0 to 100 limit) and every gap the reply might need | Splits each Game Rating the way the site's How it works page does, from the engine's published settings and margin curve; the split matches every published Game Rating of every season to rounding (`tests/test_reply_writer.py`) |

What the check cannot catch: a number used for the wrong thing (calling a Game Rating the Team Rating, or quoting a real 8-point margin as "8 points better"), and wording that predicts without the usual words. Dan reads every draft; the template version sits under it for comparison.

### Intents and templates (the fallback)

The templates write the reply when the model's reply fails the checks twice, when the model declines, errors or is turned off (`REPLY_WRITER=template`), and they appear under every model reply in the draft. `{…}` slots are filled by the engine.

| Intent | Example ask | Reply template |
|---|---|---|
| `team` | "where's Utah in this?" | `Utah: #{rank} in TrueCFB v1.0, Team Rating {rating} ({record}).` + last game line |
| `compare` | "Utah or BYU?" | One line per team (rank, Team Rating, record); if they played this season: `{winner} won {score}: Game Ratings {a} and {b}.` |
| `game` | tagged under a game result | The existing result text for that game (`game_impact`), without hashtags |
| `top` | "who's #1?" | `TrueCFB v1.0 top 5: 1 {team} {rating} · 2 …` |
| `conference` | "is the Big 12 better than the ACC?" | Conference Rating and rank for each |
| `how` | "how does this work?" | Fixed text, no numbers: results only, open formula, How it works page on the TrueCFB site (no link) |
| `predict` | "who wins Saturday?" | `TrueCFB rates results, not predictions.` + the `compare` lines |
| `skip` | abusive, off topic, unclear | No draft; one line in Telegram ("skipped @handle: off topic") so Dan can see what was left out |

Rules for every reply, model-written or template, enforced in code like `game_impact.post_text`:
- **TrueCFB** spelling, **v1.0**, **Rating** (never "score" for a TrueCFB number; "score" only for points, as in 28-20).
- One decimal on ratings; signed changes with a real minus sign (−); "NR" for unranked.
- Describes, never predicts; no hype, no emoji; fan terms.
- No links, no hashtags, no @mentions in the text. `exclude_reply_user_ids` keeps the other account in the thread from being mentioned automatically.
- 2020 numbers carry "(2020 is flagged unreliable)".
- ≤280 weighted characters; lines drop in a set order to fit.

### Telegram draft

Same bot and chat as the result posts. The message shows what they asked, the post above, a link to the mention (the handle is on X; looking it up through the API costs $0.010), what the model understood and why, the drafted reply (and who wrote it: the model, or the template and why), what the reply rests on, the template version, and any model reply the checks turned down. Buttons: **Post reply** (only while `REPLIES_LIVE` is `true`) and **Skip**, as `rpost:<id>` / `rskip:<id>` taps beside the result posts' `post:` / `skip:`. Tap behavior is the same as today: buttons come off first, so a double tap can't post twice.

### The pieces

| File | What |
|---|---|
| `src/reply_facts.py` | The fact sheet (every number a reply may use, from the engine's files), each Game Rating split into its parts, the README primer, and the number check |
| `src/reply_writer.py` | The writer: prompt, the checks, one rewrite, the template fallback |
| `src/reply_templates.py` | The fixed template replies (the fallback), from `site/data.json`, `history.json`, `sched_*.json` and `data/bot/drafts.json`; `check()` holds the wording rules |
| `src/reply_model.py` | The model calls: fixed JSON shapes; the reading step's team and conference names only from the engine's lists. Grok when `XAI_API_KEY` is set, Claude with `REPLY_PROVIDER=claude` |
| `src/reply_bot.py` | `draft` (read mentions, filter, model reads, model writes, checks, save), `send` (Telegram), `post` (one approved reply) |
| `src/reply_eval.py`, `data/bot/reply_samples.json` | 64 made-up mentions (including how-it-works and why-is-X-ranked-there questions, and a prompt injection) to compare models on reading and writing |
| `tests/test_reply_templates.py`, `tests/test_reply_writer.py` | Every template intent on every season; the Game Rating split against every published game; the number and wording checks; the rewrite and fallback with a stand-in model |
| `.github/workflows/reply-draft.yml` | Started by the Worker; drafts and sends to Telegram |
| `.github/workflows/post-reply.yml` | Started by a "Post reply" tap; posts only while `REPLIES_LIVE` is `true` |
| `.github/workflows/reply-eval.yml` | "Reply bot: try the model", by hand |
| `worker/index.js` | `pollMentions()` (only runs when `X_BEARER_TOKEN` and `X_USER_ID` are set) and the `rpost:` / `rskip:` taps |
| `data/bot/replies.json`, `data/bot/optout.json`, `site/replies.json` | What was handled (ids, what the bot understood, the reply, what happened; never the text people wrote), opt-outs as hashes, and the newest handled id for the Worker |
| `requirements-reply.txt` | `anthropic`, for the reply jobs only (Grok is called with `requests`) |

Run the tests with `python tests/test_reply_templates.py` and `python tests/test_reply_writer.py` (no keys needed).

### Cost per reply

| | Posted reply | Skipped draft |
|---|---|---|
| Mention read: the Worker's check (app-only token) plus the draft job's read (own account) | $0.006 | $0.006 |
| Parent post read (when there is one) | $0.005 | $0.005 |
| Model: read + write (Grok 4.3; a rewrite adds ≈$0.003) | ≈$0.005 | ≈$0.005 |
| Reply post ("summoned"; $0.015 if X bills it as a plain post) | $0.010 | none |
| **Total** | **≈$0.026** | **≈$0.016** |

The Worker only checks whether there is anything new (up to 5 posts); the draft job then reads them with the account's own keys at $0.001 each. Putting the write keys on the Worker would save $0.005 a mention; not worth it. At 100 replies a week, about $2.60 a week. GitHub Actions minutes are free on a public repo.

### Risks

1. **X approval, unclear.** Help Center says approval is required; developer docs say it isn't. Mitigation: draft mode first; ask X before going live.
2. **Account limits.** Replies outside the "summoned" rule return 403, and a forum thread reports accounts getting temporarily limited after such errors. Mitigation: only reply to the mention itself, check before posting, stop on the first 403.
3. **Mentioning people who didn't opt in.** A reply in someone else's thread can auto-mention the original poster. Mitigation: `exclude_reply_user_ids`, no handles in text.
4. **Prompt injection and trolling.** The model's words now reach the draft. Mitigations: posts are passed as data and the writer is told to skip anything that tells it what to say (it falls back to the template); no number can get past the check unless the engine published it; Dan taps every reply.
5. **Wrong team.** "Miami", "USC", "the U", nicknames. Mitigation: names only from the 138-team list, `skip` when unsure, the draft shows the detected teams.
6. **Pile-ups.** A popular post could bring dozens of tags. Mitigation: at most one reply per user per thread; cap drafts per hour; X spend limit.
7. **Predictions.** TrueCFB describes, never predicts. The writer is told so, the check rejects common prediction wording ("will beat", "favored", "odds"), and the `predict` template says so plainly. Wording that predicts without those words is on Dan's review.
8. **Bowl games.** Until the final 2026 CFP ranking is added on selection day (6 Dec), bowl results don't count. A question about a bowl game gets the two teams side by side instead (the templates only use games the engine has counted).
9. **Token expiry.** `GITHUB_DISPATCH_TOKEN` expires about Nov 2027; the reply bot depends on it too.
10. **A wrong explanation of the formula in public.** The writer learns v1.0 from the README's own text, not a summary, and the model test includes how-it-works questions to read before going live.

## Turning it on

1. **Model key:** sign in at console.x.ai with @truecfb's X account, add credits (or link the X developer account for bonus credits), create an API key, and save it as the GitHub secret `XAI_API_KEY` (`gh secret set XAI_API_KEY` asks for it).
2. **Try the model:** Actions → "Reply bot: try the model" → Run. The run summary shows, per model, how many of the 64 samples it read right, the reply it wrote for each (or why the template was used), what each reply rests on, and the cost. To use something other than Grok 4.3, set the GitHub variable `REPLY_MODEL` (and `REPLY_PROVIDER` for Claude).
3. **X read token and id:** in the X developer console (app `truecfb-bot`), copy the app's Bearer Token into the Cloudflare secret `X_BEARER_TOKEN`. Run Actions → "Reply drafts" once by hand: its log prints @truecfb's user id. Save it as the GitHub variable `X_USER_ID` and the Cloudflare variable `X_USER_ID`. The Worker starts checking mentions on its next run.
4. **Drafts arrive in Telegram** with a Skip button only ("draft mode: posting is off"). Skipped mentions are listed in one message per run.
5. **Before going live:** update the bio (automated account, tag it for a TrueCFB answer, reply "stop" to opt out, a link to Dan's account) and send X the approval request (section 1).
6. **Go live:** set the GitHub variable `REPLIES_LIVE` to `true`. New drafts get a "Post reply" button.

To pause: delete `REPLIES_LIVE` (stops posting) or the Cloudflare `X_BEARER_TOKEN` (stops checking mentions).
