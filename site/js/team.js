/* TrueCFB: one team's page. */
(() => {
  const {$, load, loadSched, esc, day, signed, bonus, teamLink, readHash, writeHash, ordinal} = TC;
  let D = null;

  const clamp = v => Math.max(0, Math.min(100, v));
  function resultText(g){
    return (g[3] > g[4] ? "W " : "L ") + g[3] + "-" + g[4] + (g[5] ? " OT" : "");
  }
  function where(g){
    return g[2] === "H" ? "vs " : g[2] === "A" ? "at " : "vs (N) ";
  }

  function render(){
    const t = $("team").value, y = $("season").value, info = D.ratings[y][t];
    const cur = D.current, isCurrent = y === cur.season;
    document.title = t + " · TrueCFB";
    $("t-name").textContent = t;
    writeHash({team: t, season: isCurrent ? null : y});

    if(!info){
      $("t-status").textContent = y + " season";
      $("t-missing").hidden = false;
      $("t-missing").textContent = t + " was not an FBS team in " + y + ". Pick another season.";
      $("t-body").hidden = true;
      return;
    }
    $("t-missing").hidden = true; $("t-body").hidden = false;

    const conf = (D.team_conf[y] || {})[t];
    $("t-status").textContent = y + " season" + (conf ? " · " + conf : "") + " · " + info[2] + "-" + info[3];

    // Readouts
    const nTeams = Object.keys(D.ratings[y]).length;
    $("t-rating").textContent = info[0].toFixed(1);
    $("t-rating-l").textContent = "TrueCFB Team Rating, " + (!isCurrent ? "at season's end after bowls and playoff"
      : cur.complete ? cur.now_label.toLowerCase() + (cur.now_through ? " (" + day(cur.now_through) + ")" : "")
      : "with this week still being played");
    $("t-rank").textContent = "#" + info[1];
    $("t-rank-l").textContent = "of " + nTeams + " FBS teams";
    $("t-carry").hidden = info[2] + info[3] >= D.settings.carry;

    // History
    const h = D.history[t] || {};
    $("t-hist").innerHTML = Object.keys(h).sort().map(k =>
      '<div class="hrow"><span class="yr">' + k + '</span><span class="bar"><i style="width:' + clamp(h[k][0]) + '%"></i></span><span class="val">' +
      h[k][0].toFixed(1) + "<small>#" + h[k][1] + "</small></span></div>").join("");

    // Conference table
    if(conf){
      const INDEP = "FBS Independents", all = D.conf[y], self = all.find(c => c[0] === conf);
      const rows = all.filter(c => c[0] !== INDEP), ci = rows.findIndex(c => c[0] === conf);
      const members = Object.keys(D.team_conf[y]).filter(x => D.team_conf[y][x] === conf && D.ratings[y][x])
        .sort((a, b) => D.ratings[y][a][1] - D.ratings[y][b][1]);
      $("t-conf-box").hidden = false;
      $("t-conf-title").textContent = conf;
      $("t-conf-note").textContent = ci >= 0
        ? "TrueCFB Conference Rating " + rows[ci][2].toFixed(1) + ", " + ordinal(ci + 1) + " of " + rows.length + " conferences. It is the plain average of these teams' ratings."
        : self ? "Independents are not a conference. The plain average of these teams' ratings is " + self[2].toFixed(1) + "." : "";
      $("t-conf").innerHTML = members.map((m, i) => {
        const r = D.ratings[y][m];
        return '<tr><td class="rk">' + (i + 1) + "</td><td>" + (m === t ? esc(m) : teamLink(m, isCurrent ? null : y)) +
          '<span class="rec">' + r[2] + "-" + r[3] + '</span></td><td class="rt">' + r[0].toFixed(1) + "</td><td>" + r[1] + "</td></tr>";
      }).join("");
    } else $("t-conf-box").hidden = true;

    // Schedule and tiles need this season's game file.
    $("t-tiles").innerHTML = "";
    $("t-sched").innerHTML = '<tr><td colspan="4">Loading the games…</td></tr>';
    loadSched(y).then(all => {
      if($("team").value !== t || $("season").value !== y) return;
      const games = all[t] || [];
      $("t-sched").innerHTML = games.length ? games.map(g => {
        const d = g[6] - info[0], cls = d > 0.05 ? "up" : d < -0.05 ? "down" : "same";
        const pot = Math.round(100 + D.settings.b * (info[0] - 50) + D.settings.b * (g[7] - 50) + 2 * g[9] + g[10]);
        const post = g[9] ? " · " + (g[9] === 15 ? "playoff" : "bowl") + " +" + (g[9] + (g[3] > g[4] ? g[10] : 0)) : "";
        const opp = g[8] ? esc(g[1]) + ' <span class="rec">FCS</span>' : teamLink(g[1], isCurrent ? null : y);
        return "<tr><td>" + where(g) + opp + '<span class="sub2">' + day(g[0]) + " · Game Rating " + pot + " · bonus " + bonus(D, g[7]) + post +
          "</span></td><td>" + resultText(g) + '</td><td class="rt">' + g[6].toFixed(1) + '</td><td><span class="gap ' + cls + '">' +
          (d > 0.05 ? "+" : d < -0.05 ? "−" : "") + Math.abs(d).toFixed(1) + "</span></td></tr>";
      }).join("") : '<tr><td colspan="4">No games played yet this season.</td></tr>';

      const tiles = [[bonus(D, info[0]), "Bonus: what " + t + " is worth to anyone who plays it"]];
      if(games.length){
        const best = games.reduce((a, b) => b[6] > a[6] ? b : a), low = games.reduce((a, b) => b[6] < a[6] ? b : a);
        const avgOpp = games.reduce((s, g) => s + g[7], 0) / games.length;
        tiles.push([best[6].toFixed(0), "Best game: " + resultText(best) + " " + where(best) + best[1]]);
        tiles.push([low[6].toFixed(0), "Lowest game: " + resultText(low) + " " + where(low) + low[1]]);
        tiles.push([avgOpp.toFixed(0), "Average opponent rating (an average team is 50)"]);
      }
      $("t-tiles").innerHTML = tiles.map(q => "<div><b>" + esc(q[0]) + "</b><span>" + esc(q[1]) + "</span></div>").join("");
    }).catch(() => {
      if($("team").value === t && $("season").value === y)
        $("t-sched").innerHTML = '<tr><td colspan="4">The games did not load. Pick the team again to retry.</td></tr>';
    });
  }

  function pickFromHash(){
    const h = readHash(), ys = Object.keys(D.seasons);
    $("season").value = h.season && ys.includes(h.season) ? h.season : D.current.season;
    if(h.team && D.history[h.team]) $("team").value = h.team;
  }

  load().then(d => {
    D = d;
    const ys = Object.keys(D.seasons).sort().reverse();
    $("season").innerHTML = ys.map(y => "<option>" + y + "</option>").join("");
    $("season").value = D.current.season;
    const teams = Object.keys(D.history).sort((a, b) => a.localeCompare(b));
    $("team").innerHTML = teams.map(t => '<option value="' + esc(t) + '">' + esc(t) + "</option>").join("");
    // With no team in the link, open on the current #1.
    const cs = D.seasons[D.current.season], top = (cs.find(s => s.id === D.current.default) || cs[cs.length - 1]).rows[0][1];
    $("team").value = top;
    pickFromHash(); render();
    $("team").addEventListener("change", render);
    $("season").addEventListener("change", render);
    window.addEventListener("hashchange", () => { pickFromHash(); render(); window.scrollTo(0, 0); });
  }).catch(() => {
    $("t-missing").hidden = false;
    $("t-missing").textContent = "The team data did not load. Reload the page to try again.";
    $("t-body").hidden = true;
  });
})();
