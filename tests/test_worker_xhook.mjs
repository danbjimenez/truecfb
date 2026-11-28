// The Worker's /hooks/x helpers (X's push of mentions), checked against Node's own HMAC.
//   node tests/test_worker_xhook.mjs
import { createHmac } from "node:crypto";
const W = await import(new URL("../worker/index.js", import.meta.url));
const ref = (k, m) => "sha256=" + createHmac("sha256", k).update(m).digest("base64");
const a = await W.xSign("client-secret", "challenge_string");
if (a !== ref("client-secret", "challenge_string")) throw new Error("crc mismatch " + a);
const body = JSON.stringify({ data: { event_type: "post.mention.create", filter: { user_id: "99" },
  payload: { id: "123", author_id: "42", text: "@truecfb hi" } } });
if ((await W.xSign("s", body)) !== ref("s", body)) throw new Error("signature mismatch");
if (W.mentionFrom(JSON.parse(body), "99") !== "123") throw new Error("mention not found");
if (W.mentionFrom(JSON.parse(body), "98") !== null) throw new Error("other account's filter accepted");
const own = JSON.parse(body); own.data.payload.author_id = "99";
if (W.mentionFrom(own, "99") !== null) throw new Error("our own post accepted");
const like = JSON.parse(body); like.data.event_type = "like.create";
if (W.mentionFrom(like, "99") !== null) throw new Error("other event accepted");
if (W.mentionFrom({ event_type: "post.mention.create", filter: { user_id: "99" }, payload: { id: "7", author_id: "1" } }, "99") !== "7")
  throw new Error("unwrapped event not accepted");
const d = (iso) => new Date(iso);
if (!W.shouldCheckMentions(d("2026-11-26T10:30:00Z"), true) || !W.shouldCheckMentions(d("2026-11-26T10:05:00Z"), true))
  throw new Error("backup schedule: every run with push");
if (!W.shouldCheckMentions(d("2026-11-26T10:15:00Z"), false)) throw new Error("old schedule changed");
const link = W.postLink("https://x.com/BuildModeBen/status/2126535613541503182?s=20 focus on the playoff angle");
if (!link || link.id !== "2126535613541503182" || link.note !== "focus on the playoff angle") throw new Error("post link");
if (W.postLink("https://twitter.com/i/web/status/123")?.id !== "123" || W.postLink("no link") !== null
    || W.postLink("https://evil.com/x.com/a/status/1") !== null) throw new Error("post link forms");
console.log("worker x hook ok");
