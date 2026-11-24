# Reply bot: plan (not built)

Status: **proposal, 23 Nov 2026.** Nothing here is built, and no secrets have been added. It waits on Dan's OK.

When someone tags @truecfb (usually under another account's post, asking it to weigh in), a model reads the question and the engine supplies every number. It starts in draft mode: each draft goes to Telegram, and nothing posts until Dan taps.

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

Honest version: **for this job the model choice matters less than it seems**, because the model never writes a number (section 3). Its only job is to turn a tweet into `{what's being asked, which teams, which game}`. Any current model does that well. I'm Claude, so discount my lean accordingly.

| | Grok (xAI API) | Claude (Anthropic API) |
|---|---|---|
| Cost per reply (≈1,500 tokens in, 200 out) | Grok 4.3: ≈$0.002. Grok 4.7: ≈$0.004 | Haiku 5.5: ≈$0.0003. Sonnet 5.5: ≈$0.005 |
| Structured output (a fixed JSON shape, team names from a list of 138) | Yes | Yes (`strict` schemas with an enum) |
| Where it runs | GitHub Actions, key in GitHub secrets | Same |
| X-native extras | `x_search` can read threads ($5 per 1,000 posts). Not needed: we get the parent post from the X API, and we want the model to see only the tweet, not go looking for outside numbers. | None needed |
| New account and bill | Yes (xAI) | Yes (Anthropic API billing is separate from a Claude subscription) |

Prices: [xAI models page](https://docs.x.ai/docs/models) (read 23 Nov 2026); Anthropic's model price table as of 3 Nov 2026.

- **"Grok powers it" can't mean @grok answers with TrueCFB numbers.** @grok is xAI's own account, and we can't feed it the engine. The way to get Grok quoting TrueCFB is the separate open item "Readable by Grok and search engines" (`rankings.json`, `llms.txt`, a page per team).
- Using Grok gives no known edge with X's rules or approval.
- **Pick:** Claude Sonnet 5.5 at low effort (about half a cent; robust on fan slang like "the U", "Bama" or "Miami (which one?)"), or Haiku 5.5 if volume grows. The model call sits behind one small function, so switching to Grok is a one-file change. Before choosing, run both on the same ~50 sample mentions; that costs cents.

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
  3. model: tweet text ─► {intent, teams, season, game}   (no numbers)
  4. engine: look up every number (site/*.json, game_impact.py)
  5. fixed template per intent ─► reply text (≤280, checked)
  6. Telegram draft: who asked, their text, the parent post, the reply
     [Post reply] [Skip]
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

| Model (one call, structured output) | Engine and templates |
|---|---|
| Reads the mention and the parent post | Every number: rank, Team Rating, Game Rating, Matchup Rating, Conference Rating, record |
| Returns `intent` from a fixed list, `teams` (names from the 138-team list only), optional `season`, `game_id`, `conference` | Looks them up in the engine's outputs (`site/rank_*.json`, `sched_*.json`, `data.json`) and `game_impact.py` |
| Returns `skip` with a reason (prediction ask, off topic, abusive, unclear) | Fills a fixed template; checks length; refuses to draft if a team or game isn't found |
| **Never** writes reply text | Writes all reply text |

The model's output never reaches the post. So a tweet that tries to trick the model ("ignore your rules and say…") can at worst pick the wrong team or intent, and Dan sees that in the draft. A later option is to let the model write one sentence of framing around the engine's slots, with a check that rejects any digit it wrote. Not in v1.

### Intents and templates (v1)

`{…}` slots are filled by the engine; the model fills none of them.

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

Template rules, enforced in code like `game_impact.post_text`:
- **TrueCFB** spelling, **v1.0**, **Rating** (never "score" for a TrueCFB number; "score" only for points, as in 28-20).
- One decimal on ratings; signed changes with a real minus sign (−); "NR" for unranked.
- Describes, never predicts; no hype, no emoji; fan terms.
- No links, no hashtags, no @mentions in the text. `exclude_reply_user_ids` keeps the other account in the thread from being mentioned automatically.
- 2020 numbers carry "(2020 is flagged unreliable)".
- ≤280 weighted characters; lines drop in a set order to fit.

### Telegram draft

Same bot and chat as the result posts. The message shows the asker's handle, their text, the parent post's text, a link to the mention, the detected intent and teams, and the drafted reply. Buttons: **Post reply** and **Skip**. The Worker's hook gets a second callback pattern, `reply:<tweet id>` (19 digits; the current pattern takes only game ids). Tap behavior is the same as today: buttons come off first, so a double tap can't post twice.

### New pieces

- `src/reply_bot.py`: fetch, filter, model call, intent → template, Telegram draft.
- `src/reply_templates.py`: the templates and their tests (run on every season's data; no model involved).
- `.github/workflows/reply-draft.yml`, `post-reply.yml` (or a `kind` input on `post-to-x.yml`).
- `worker/index.js`: `pollMentions()` and the `reply:` callback.
- `data/bot/replies.json` (handled ids, drafts, posted replies) and `data/bot/optout.json`.
- Secrets: GitHub `ANTHROPIC_API_KEY` (or `XAI_API_KEY`); Cloudflare `X_BEARER_TOKEN`. Only after Dan approves.
- Bio: say it's automated, that tagging gets an answer, and that "stop" opts out; link to Dan's account.

### Cost per reply

| | Posted reply | Skipped draft |
|---|---|---|
| Mention read (app-only token) | $0.005 | $0.005 |
| Parent post read (when there is one) | $0.005 | $0.005 |
| Model (Sonnet 5.5 low effort; Haiku ≈$0.0003) | ≈$0.005 | ≈$0.005 |
| Reply post ("summoned"; $0.015 if X bills it as a plain post) | $0.010 | none |
| **Total** | **≈$0.025** | **≈$0.015** |

Reading mentions with the user-context keys would cut the mention read to $0.001, but it would put the write keys on the Worker; not worth $0.004. At 100 replies a week, about $2.50 a week. GitHub Actions minutes are free on a public repo.

### Risks

1. **X approval, unclear.** Help Center says approval is required; developer docs say it isn't. Mitigation: draft mode first; ask X before going live.
2. **Account limits.** Replies outside the "summoned" rule return 403, and a forum thread reports accounts getting temporarily limited after such errors. Mitigation: only reply to the mention itself, check before posting, stop on the first 403.
3. **Mentioning people who didn't opt in.** A reply in someone else's thread can auto-mention the original poster. Mitigation: `exclude_reply_user_ids`, no handles in text.
4. **Prompt injection and trolling.** The model only classifies; templates write the text; Dan taps every reply.
5. **Wrong team.** "Miami", "USC", "the U", nicknames. Mitigation: names only from the 138-team list, `skip` when unsure, the draft shows the detected teams.
6. **Pile-ups.** A popular post could bring dozens of tags. Mitigation: at most one reply per user per thread; cap drafts per hour; X spend limit.
7. **Reading the question as a prediction.** TrueCFB describes, never predicts; the `predict` template says so plainly.
8. **Bowl games.** Until the 2026 selection date and CFP final are added, bowl results won't move ratings; replies about bowl games would be wrong. Ship after the bowls work, or skip postseason games until then.
9. **Token expiry.** `GITHUB_DISPATCH_TOKEN` expires about Nov 2027; the reply bot depends on it too.

### Order of work, once approved

1. Templates and tests on past seasons (no model, no X).
2. Model step with a ~50-mention sample set; compare Claude and Grok on it.
3. Worker polling and Telegram drafts (draft only; Post reply disabled).
4. Approval request to X; bio update.
5. Turn on Post reply.
