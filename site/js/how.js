/* TrueCFB: the How it works page. The one-game calculator, the worked example and the playoff run. */
(() => {
  const {$, load, loadSched, loadRank, esc, day, bonus, moveChip, teamLink} = TC;
  let D = null, venue = 0, kind = "reg";

  // Bowl and playoff points, added after the 0 to 100 limit.
  function extra(win){
    const P = D.settings.post;
    return kind === "reg" ? 0 : kind === "bowl" ? P.bowl : P.playoff + (win ? P.win[kind] : 0);
  }
  function gameRating(m, win, opp){
    const S = D.settings, f = D.F[Math.min(m, D.F.length - 1)], w = S.win[0] + (S.win[1] - S.win[0]) * f;
    return Math.max(0, Math.min(100, (win ? w : 100 - w) + venue * S.venue + S.b * (opp - 50))) + extra(win);
  }
  function renderCurve(){
    const opp = +$("opp").value, top = kind === "reg" ? 100 : 160, ticks = kind === "reg" ? [0, 25, 50, 75, 100] : [0, 40, 80, 120, 160];
    $("opp-v").textContent = opp; $("opp-b").textContent = bonus(D, opp);
    const L = 34, R = 388, T = 12, Bm = 222, X = m => L + (m - 1) / 48 * (R - L), Y = v => Bm - v / top * (Bm - T);
    let s = "";
    ticks.forEach(v => { s += '<line class="grid" x1="' + L + '" x2="' + R + '" y1="' + Y(v) + '" y2="' + Y(v) + '"/><text class="axis" x="' + (L - 8) + '" y="' + (Y(v) + 4) + '" text-anchor="end">' + v + "</text>"; });
    [1, 7, 14, 21, 28, 35, 42, 49].forEach(m => { s += '<text class="axis" x="' + X(m) + '" y="' + (Bm + 18) + '" text-anchor="middle">' + m + "</text>"; });
    s += '<text class="axis" x="' + ((L + R) / 2) + '" y="' + (Bm + 36) + '" text-anchor="middle">Final margin (points)</text>';
    const pts = win => Array.from({length: 49}, (_, i) => X(i + 1).toFixed(1) + "," + Y(gameRating(i + 1, win, opp)).toFixed(1)).join(" ");
    const yw = Y(gameRating(49, true, opp)), yl = Y(gameRating(49, false, opp));
    s += '<polyline class="lw" points="' + pts(true) + '"/><polyline class="ll" points="' + pts(false) + '"/>';
    s += '<text class="tw" x="' + (R - 4) + '" y="' + (yw < 30 ? yw + 18 : yw - 8) + '" text-anchor="end">Winner</text><text class="tl" x="' + (R - 4) + '" y="' + (yl > 200 ? yl - 8 : yl + 18) + '" text-anchor="end">Loser</text>';
    $("curve").innerHTML = s;
    $("quick").innerHTML = [["Win by 21", gameRating(21, true, opp)], ["Win by 1", gameRating(1, true, opp)], ["Lose by 1", gameRating(1, false, opp)], ["Lose by 21", gameRating(21, false, opp)]]
      .map(q => "<div><b>" + q[1].toFixed(0) + "</b><span>" + q[0] + "</span></div>").join("");
  }

  // The worked example uses a real game, so its numbers follow the opponent's rating.
  function example(){
    loadSched("2026").then(all => {
      const g = ((all.games || {}).Utah || []).find(x => x[1] === "BYU" && x[3] === 28 && x[4] === 20);
      if(!g) return;
      const b = Math.round((g[7] - 50) * 10) / 10;
      $("ex-opp").textContent = g[7].toFixed(1);
      $("ex-bonus").textContent = (b < 0 ? "−" : "+") + Math.abs(b).toFixed(1);
      $("ex-gr").textContent = g[6].toFixed(1);
    }).catch(() => {});
  }

  // The latest finished playoff, game by game, for the champion and the runner-up.
  function playoffRun(){
    const P = D.settings.post, y = Object.keys(D.seasons).sort().reverse().find(k => D.seasons[k].some(p => p.id === "final"));
    if(!y) return;
    const names = {earlier: "First round", quarterfinal: "Quarterfinal", semifinal: "Semifinal", final: "Final"};
    const roundOf = g => names[Object.keys(P.win).find(k => P.win[k] === g[10])] || "Playoff";
    Promise.all([loadSched(y), loadRank(y)]).then(res => {
      const games = res[0].games || {}, isPlayoff = g => g[9] === P.playoff, isFinal = g => isPlayoff(g) && g[10] === P.win.final;
      const champ = Object.keys(games).find(t => games[t].some(g => isFinal(g) && g[3] > g[4]));
      if(!champ) return;
      const runner = games[champ].find(isFinal)[1], before = {};
      (res[1].reg || []).forEach(r => { before[r[1]] = r; });
      const run = t => games[t].filter(isPlayoff);
      const block = (t, what) => {
        const b = before[t];
        let prev = b ? b[2] : null;
        let h = '<tr><td colspan="4"><span class="lab">' + esc(t) + " · " + what + "</span></td></tr>" +
          (b ? '<tr><td>Before the playoff<span class="sub2">Regular season final</span></td><td></td><td></td><td class="rt">' + b[2].toFixed(1) + '<span class="sub2">#' + b[0] + "</span></td></tr>" : "");
        run(t).forEach(g => {
          const won = g[3] > g[4], field = g[6] - g[9] - (won ? g[10] : 0);
          h += "<tr><td>" + roundOf(g) + ": " + (g[2] === "A" ? "at " : "vs ") + esc(g[1]) + '<span class="sub2"><span>' + day(g[0]) + " ·</span> <span>" + field.toFixed(1) + " on the field</span> <span>+ " + g[9] +
            " for playing" + (won ? "</span> <span>+ " + g[10] + " for winning" : "") + "</span></span></td><td>" + (won ? "W " : "L ") + g[3] + "-" + g[4] + (g[5] ? " OT" : "") +
            "</td><td>" + g[6].toFixed(1) + '</td><td class="rt">' + g[11].toFixed(1) + '<span class="sub2">' + moveChip(g[11], prev) + " #" + g[12] + "</span></td></tr>";
          prev = g[11];
        });
        return h;
      };
      $("po-title").textContent = "The " + y + " season's playoff, game by game";
      $("po-note").textContent = champ + " played " + run(champ).length + " playoff games and " + runner + " played " + run(runner).length +
        ". Team Rating is the rating once that day's games were counted.";
      $("po-rows").innerHTML = block(champ, "champion") + block(runner, "runner-up");
      const lost = run(runner).find(isFinal), fin = t => D.ratings[y][t][0].toFixed(1);
      if(before[champ] && before[runner] && lost)
        $("po-after").textContent = champ + " went from " + before[champ][2].toFixed(1) + " before the playoff to " + fin(champ) + " after it, and " + runner + " from " +
          before[runner][2].toFixed(1) + " to " + fin(runner) + ". " + runner + "'s loss in the final still earned " + lost[6].toFixed(1) +
          ": the loser adds the winner's bonus, and no bonus is bigger than the champion's. Part of each rise also comes from opponents. Their bowl and playoff points raise their bonuses, which raises the value of having played them.";
      $("po-run").hidden = false;
    }).catch(() => {});
  }

  load().then(d => {
    D = d; renderCurve(); example(); playoffRun();
    $("opp").addEventListener("input", renderCurve);
    $("kind").addEventListener("change", () => { kind = $("kind").value; renderCurve(); });
    document.querySelectorAll("#ven button").forEach(b => b.addEventListener("click", () => {
      venue = +b.dataset.v;
      document.querySelectorAll("#ven button").forEach(x => x.setAttribute("aria-pressed", x === b));
      renderCurve();
    }));
  }).catch(() => { $("quick").innerHTML = '<p class="note">The chart data did not load. Reload the page to try again.</p>'; });
})();
