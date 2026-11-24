/* TrueCFB: helpers shared by every page. */
const TC = (() => {
  const $ = id => document.getElementById(id);
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  let dataPromise = null;
  const sched = {}, ranks = {};
  let historyPromise = null;

  // The whole data file, fetched once per page.
  function load(){
    if(!dataPromise) dataPromise = fetch("/data.json").then(r => { if(!r.ok) throw new Error(r.status); return r.json(); });
    return dataPromise;
  }
  // One season's schedules, fetched when first needed.
  function loadSched(y){
    if(!sched[y]) sched[y] = fetch("/sched_" + y + ".json").then(r => { if(!r.ok) throw new Error(r.status); return r.json(); })
      .catch(e => { delete sched[y]; throw e; });
    return sched[y];
  }
  // One season's rankings at every point in the season, fetched when first needed.
  function loadRank(y){
    if(!ranks[y]) ranks[y] = fetch("/rank_" + y + ".json").then(r => { if(!r.ok) throw new Error(r.status); return r.json(); })
      .catch(e => { delete ranks[y]; throw e; });
    return ranks[y];
  }
  // Every team's and conference's rating and rank at every point of every season, fetched when first needed.
  function loadHistory(){
    if(!historyPromise) historyPromise = fetch("/history.json").then(r => { if(!r.ok) throw new Error(r.status); return r.json(); })
      .catch(e => { historyPromise = null; throw e; });
    return historyPromise;
  }
  const esc = s => String(s).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  // "2026-11-21" -> "21 Nov 2026"; "11-21" -> "21 Nov"
  function day(s){
    if(!s) return "";
    const p = s.split("-").map(Number);
    return p.length === 3 ? p[2] + " " + MONTHS[p[1] - 1] + " " + p[0] : p[1] + " " + MONTHS[p[0] - 1];
  }
  // Signed whole number with a real minus sign: +28, −25, 0
  function signed(n){
    const v = Math.round(n);
    return (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v);
  }
  const bonus = (D, rating) => signed(D.settings.b * (rating - 50));
  // The Matchup Rating: the pot the two teams split. g is one line of a team's schedule.
  const matchup = (D, teamRating, g) => Math.round(100 + D.settings.b * (teamRating - 50) + D.settings.b * (g[7] - 50) + 2 * g[9] + g[10]);
  // A chip for how far a rating moved: +1.3, −1.3, =
  function moveChip(now, before){
    if(now == null || before == null) return "";
    const d = Math.round((now - before) * 10) / 10, cls = d > 0 ? "up" : d < 0 ? "down" : "same";
    return '<span class="gap ' + cls + '">' + (d > 0 ? "+" + d.toFixed(1) : d < 0 ? "−" + (-d).toFixed(1) : "=") + "</span>";
  }
  // A poll's rank for a team, with a chip for how far TrueCFB is from it.
  function pollCell(ours, theirs){
    if(!theirs) return '<span class="nr">NR</span>';
    const d = theirs - ours, cls = d > 0 ? "up" : d < 0 ? "down" : "same";
    return '<span class="pr">' + theirs + '</span><span class="gap ' + cls + '">' + (d > 0 ? "+" + d : d < 0 ? "−" + (-d) : "=") + "</span>";
  }
  // A team's page address: "Texas A&M" -> "texas-am", "Hawai'i" -> "hawaii". Same as slug() in src/build_pages.py.
  const slug = team => String(team).normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
    .replace(/['&]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  function teamHref(team, season){
    return "/team/" + slug(team) + (season ? "#season=" + encodeURIComponent(season) : "");
  }
  const teamLink = (team, season) => '<a class="tm" href="' + teamHref(team, season) + '">' + esc(team) + "</a>";
  // Read and write "#a=1&b=2" so a view can be shared as a link.
  function readHash(){
    const out = {};
    new URLSearchParams(location.hash.replace(/^#/, "")).forEach((v, k) => { out[k] = v; });
    return out;
  }
  function writeHash(obj){
    const q = Object.keys(obj).filter(k => obj[k] != null && obj[k] !== "")
      .map(k => k + "=" + encodeURIComponent(obj[k])).join("&");
    history.replaceState(null, "", q ? "#" + q : location.pathname + location.search);
  }
  const ordinal = n => n + (n % 100 >= 11 && n % 100 <= 13 ? "th" : ["th", "st", "nd", "rd"][n % 10] || "th");
  return {$, slug, load, loadSched, loadRank, loadHistory, esc, day, signed, bonus, matchup, moveChip, pollCell, teamHref, teamLink, readHash, writeHash, ordinal};
})();
