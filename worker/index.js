// TrueCFB Worker: serves the site from site/ (as before), and runs the X bot's two always-on jobs.
//
// 1. Every few minutes during game windows: ask the CollegeFootballData live scoreboard which games
//    are final, compare with site/live.json (games already handled), and start the "Game finals" job
//    on GitHub for any new ones. That job re-runs the ratings and sends drafts to Telegram.
// 2. /hooks/telegram: when Dan taps "Post to X" or "Skip" on a draft, start the "Post to X" job on
//    GitHub (or mark it skipped). Only Dan's chat is accepted, and only with the bot's secret header.
//
// 3. Reply bot (docs/REPLY-BOT.md): every few minutes, ask X whether anyone new has tagged @truecfb,
//    and if so start the "Reply drafts" job on GitHub. "Post reply" taps start "Post a reply".
//
// The Worker never holds the X write keys and never computes a rating. Posting happens on GitHub,
// from the draft the engine wrote. For the reply bot it holds only a read-only X token.
//
// Secrets (Cloudflare dashboard -> truecfb -> Settings -> Variables and Secrets):
//   CFBD_API_KEY, GITHUB_DISPATCH_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
//   X_BEARER_TOKEN (read-only app token) and X_USER_ID (@truecfb's numeric id): the reply bot stays
//   off until both are set.

const REPO = "danbjimenez/truecfb";
const SCOREBOARD = "https://api.collegefootballdata.com/scoreboard?classification=fbs";
const RECENT_HOURS = 14; // only finals that kicked off this recently count as new

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === "/hooks/telegram") {
      if (request.method !== "POST") return new Response("Not found", { status: 404 });
      return telegramHook(request, env, ctx);
    }
    return env.ASSETS.fetch(request);
  },

  async scheduled(event, env, ctx) {
    const now = new Date(event.scheduledTime);
    ctx.waitUntil(Promise.all([pollScoreboard(env, now), pollMentions(env, now)]));
  },
};

// ---------- 1. the scoreboard ----------

// Game windows, in UTC: noon to 4am US Eastern. Every 5 minutes on Saturdays (into early Sunday),
// every 15 minutes on other days. About 2,500 scoreboard calls a month, inside the 5,000 allowed.
export function shouldPoll(d) {
  const h = d.getUTCHours(), day = d.getUTCDay(), m = d.getUTCMinutes();
  const inWindow = h >= 16 || h < 9;
  if (!inWindow) return false;
  const saturday = (day === 6 && h >= 16) || (day === 0 && h < 9);
  return saturday || m % 15 < 5;
}

async function pollScoreboard(env, now) {
  if (!shouldPoll(now)) return;
  if (!env.CFBD_API_KEY || !env.GITHUB_DISPATCH_TOKEN) {
    console.log("bot: CFBD_API_KEY or GITHUB_DISPATCH_TOKEN not set; skipping");
    return;
  }
  const r = await fetch(SCOREBOARD, { headers: { Authorization: `Bearer ${env.CFBD_API_KEY}`, Accept: "application/json" } });
  if (!r.ok) {
    console.log(`bot: scoreboard returned ${r.status}`);
    return;
  }
  const games = await r.json();
  const cutoff = now.getTime() - RECENT_HOURS * 3600 * 1000;
  const finals = games
    .filter((g) => g.status === "completed" && Date.parse(g.startDate) >= cutoff)
    .map((g) => Number(g.id));
  if (!finals.length) return;

  const live = await env.ASSETS.fetch(new Request("https://truecfb.com/live.json"));
  const handled = new Set(live.ok ? ((await live.json()).handled || []).map(Number) : []);
  const fresh = finals.filter((id) => !handled.has(id));
  if (!fresh.length) return;

  const ok = await dispatch(env, "game-final.yml", { games: fresh.join(",") });
  console.log(`bot: ${fresh.length} new final(s) ${fresh.join(",")} -> game-final ${ok ? "started" : "FAILED"}`);
}

async function dispatch(env, workflow, inputs) {
  const r = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${workflow}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_DISPATCH_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "truecfb-worker",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ ref: "main", inputs }),
  });
  if (r.status !== 204) console.log(`bot: dispatch ${workflow} returned ${r.status} ${await r.text()}`);
  return r.status === 204;
}

// ---------- 3. mentions of @truecfb ----------

// Every run on Saturdays (and early Sunday), every third run (15 minutes) the rest of the week, all day.
export function shouldCheckMentions(d) {
  const h = d.getUTCHours(), day = d.getUTCDay(), m = d.getUTCMinutes();
  const saturday = (day === 6 && h >= 16) || (day === 0 && h < 9);
  return saturday || m % 15 < 5;
}

async function pollMentions(env, now) {
  if (!env.X_BEARER_TOKEN || !env.X_USER_ID || !env.GITHUB_DISPATCH_TOKEN) return; // reply bot not set up
  if (!shouldCheckMentions(now)) return;
  if (!/^\d{1,20}$/.test(String(env.X_USER_ID))) return;
  // The newest mention the draft job has handled; it writes site/replies.json after each run.
  const seen = await env.ASSETS.fetch(new Request("https://truecfb.com/replies.json"));
  const newest = seen.ok ? String((await seen.json()).newest || "") : "";
  const q = new URLSearchParams({ max_results: "5" });
  if (/^\d{1,20}$/.test(newest)) q.set("since_id", newest);
  else q.set("start_time", new Date(now.getTime() - 2 * 3600 * 1000).toISOString().replace(/\.\d+Z$/, "Z"));
  const r = await fetch(`https://api.x.com/2/users/${env.X_USER_ID}/mentions?${q}`, {
    headers: { Authorization: `Bearer ${env.X_BEARER_TOKEN}`, "User-Agent": "truecfb-worker" },
  });
  if (!r.ok) {
    console.log(`bot: mentions returned ${r.status}`);
    return;
  }
  const found = ((await r.json()).data || []).length;
  if (!found) return;
  const ok = await dispatch(env, "reply-draft.yml", { since_id: newest });
  console.log(`bot: new mention(s) -> reply-draft ${ok ? "started" : "FAILED"}`);
}

// ---------- 2. Telegram taps ----------

// The webhook secret is the first 40 hex characters of SHA-256(bot token); the setup job registers the
// same value with Telegram, so no extra secret is needed.
export async function webhookSecret(token) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(token));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 40);
}

async function telegramHook(request, env, ctx) {
  const ok = new Response("ok");
  if (!env.TELEGRAM_BOT_TOKEN || !env.TELEGRAM_CHAT_ID) return ok;
  const header = request.headers.get("X-Telegram-Bot-Api-Secret-Token") || "";
  if (header !== (await webhookSecret(env.TELEGRAM_BOT_TOKEN))) return new Response("Forbidden", { status: 403 });

  let update;
  try {
    update = await request.json();
  } catch {
    return ok;
  }
  const chat = String(env.TELEGRAM_CHAT_ID);
  const tg = (method, body) =>
    fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

  const cb = update.callback_query;
  if (cb) {
    const msg = cb.message || {};
    if (String(msg.chat?.id) !== chat || String(cb.from?.id) !== chat) return ok;
    // post/skip: a game's result post. rpost/rskip: a reply draft (the id of the post that tagged us).
    const m = /^(post|skip):(\d{1,12})$/.exec(cb.data || "") || /^(rpost|rskip):(\d{1,20})$/.exec(cb.data || "");
    if (!m) return ok;
    const [, action, game] = m;
    const isReply = action.startsWith("r");
    // Drafts arrive as a photo with a caption; older text drafts have plain text.
    const isPhoto = Array.isArray(msg.photo) && msg.photo.length > 0;
    const original = (isPhoto ? msg.caption : msg.text) || "";
    const setText = (text, extra = {}) =>
      tg(isPhoto ? "editMessageCaption" : "editMessageText",
        { chat_id: chat, message_id: msg.message_id, [isPhoto ? "caption" : "text"]: text, ...extra });
    if (action === "skip" || action === "rskip") {
      ctx.waitUntil(Promise.all([
        tg("answerCallbackQuery", { callback_query_id: cb.id, text: "Skipped" }),
        setText(`${original}\n\nSkipped`),
      ]));
      return ok;
    }
    // Take the buttons off first, so a second tap cannot post twice.
    await setText(`${original}\n\nPosting...`);
    const started = isReply
      ? await dispatch(env, "post-reply.yml", { mention: game, message_id: String(msg.message_id) })
      : await dispatch(env, "post-to-x.yml", { game, message_id: String(msg.message_id) });
    ctx.waitUntil(tg("answerCallbackQuery", {
      callback_query_id: cb.id,
      text: started ? "Posting to X..." : "Could not start the post job. Check GitHub Actions.",
    }));
    if (!started) {
      ctx.waitUntil(setText(`${original}\n\nNot posted: the post job did not start.`, {
        reply_markup: { inline_keyboard: [[{ text: "Try again", callback_data: `${isReply ? "rpost" : "post"}:${game}` },
                                           { text: "Skip", callback_data: `${isReply ? "rskip" : "skip"}:${game}` }]] },
      }));
    }
    return ok;
  }

  const message = update.message;
  if (message && String(message.chat?.id) === chat && message.text) {
    ctx.waitUntil(tg("sendMessage", { chat_id: chat, text: "TrueCFB drafts bot is running. Drafts arrive here after each final." }));
  }
  return ok;
}
