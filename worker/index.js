// TrueCFB Worker: serves the site from site/ (as before), and runs the X bot's two always-on jobs.
//
// 1. Every few minutes during game windows: ask the CollegeFootballData live scoreboard which games
//    are final, compare with site/live.json (games already handled), and start the "Game finals" job
//    on GitHub for any new ones. That job re-runs the ratings and sends drafts to Telegram.
// 2. /hooks/telegram: when Dan taps "Post to X" or "Skip" on a draft, start the "Post to X" job on
//    GitHub (or mark it skipped). Only Dan's chat is accepted, and only with the bot's secret header.
//
// The Worker never holds the X keys and never computes a rating. Posting happens on GitHub,
// from the draft the engine wrote.
//
// Secrets (Cloudflare dashboard -> truecfb -> Settings -> Variables and Secrets):
//   CFBD_API_KEY, GITHUB_DISPATCH_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

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
    ctx.waitUntil(pollScoreboard(env, new Date(event.scheduledTime)));
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
    const m = /^(post|skip):(\d{1,12})$/.exec(cb.data || "");
    if (!m) return ok;
    const [, action, game] = m;
    const original = msg.text || "";
    if (action === "skip") {
      ctx.waitUntil(Promise.all([
        tg("answerCallbackQuery", { callback_query_id: cb.id, text: "Skipped" }),
        tg("editMessageText", { chat_id: chat, message_id: msg.message_id, text: `${original}\n\nSkipped` }),
      ]));
      return ok;
    }
    // Take the buttons off first, so a second tap cannot post twice.
    await tg("editMessageText", { chat_id: chat, message_id: msg.message_id, text: `${original}\n\nPosting...` });
    const started = await dispatch(env, "post-to-x.yml", { game, message_id: String(msg.message_id) });
    ctx.waitUntil(tg("answerCallbackQuery", {
      callback_query_id: cb.id,
      text: started ? "Posting to X..." : "Could not start the post job. Check GitHub Actions.",
    }));
    if (!started) {
      ctx.waitUntil(tg("editMessageText", {
        chat_id: chat, message_id: msg.message_id, text: `${original}\n\nNot posted: the post job did not start.`,
        reply_markup: { inline_keyboard: [[{ text: "Try again", callback_data: `post:${game}` }, { text: "Skip", callback_data: `skip:${game}` }]] },
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
