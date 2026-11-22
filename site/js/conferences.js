/* TrueCFB: the conferences page. */
(() => {
  const {$, load, loadHistory, esc, day, moveChip, teamLink, readHash, writeHash, ordinal} = TC;
  const INDEP = "FBS Independents";
  let D = null;

  // c = [name, number of teams, rating, non-conference wins, non-conference losses]
  const confsOf = y => D.conf[y].filter(c => c[0] !== INDEP);

  function fillConfs(keep){
    const y = $("season").value, names = D.conf[y].map(c => c[0]);
    $("conf").innerHTML = names.map(n => '<option value="' + esc(n) + '">' + esc(n) + "</option>").join("");
    $("conf").value = keep && names.includes(keep) ? keep : names[0];
  }
  // Conference Rating History: one point for every snapshot of every season, with the other
  // conferences as quiet grey lines behind it.
  function drawHistory(name, y){
    const box = $("c-chart");
    $("c-key").textContent = name;
    loadHistory().then(H => {
      if($("conf").value !== name || $("season").value !== y) return;
      const names = Object.keys(H.conf), pick = (flat, odd) => flat ? flat.filter((_, i) => i % 2 === odd) : null;
      let lo = 100, hi = 0;
      names.forEach(n => Object.keys(H.conf[n]).forEach(k => pick(H.conf[n][k], 0).forEach(v => { lo = Math.min(lo, v); hi = Math.max(hi, v); })));
      lo = Math.floor(lo / 10) * 10; hi = Math.ceil(hi / 10) * 10;
      const ticks = []; for(let v = lo; v <= hi; v += 10) ticks.push(v);
      const mine = H.conf[name] || {};
      const seasons = Object.keys(D.seasons).sort().map(k => ({year: k, points: D.seasons[k], values: pick(mine[k], 0), ranks: pick(mine[k], 1)}));
      TC.historyChart(box, {
        label: "Conference Rating History for " + name, seasons, selected: y, domain: [lo, hi], ticks,
        context: names.filter(n => n !== name && n !== INDEP).map(n => k => pick(H.conf[n][k], 0)),
        onPick: k => { $("season").value = k; fillConfs(name); render(); },
        tip: p => {
          const s = seasons.find(x => x.year === p.year), rk = s.ranks[p.i];
          const ranked = names.filter(n => n !== INDEP && H.conf[n][p.year]).length;
          const at = t => H.teams[t][p.year][2 * p.i], rankAt = t => H.teams[t][p.year][2 * p.i + 1];
          const members = Object.keys(D.team_conf[p.year]).filter(t => D.team_conf[p.year][t] === name && H.teams[t] && H.teams[t][p.year])
            .sort((a, b) => rankAt(a) - rankAt(b));
          const one = (lab, t) => "<div>" + lab + " " + esc(t) + " " + at(t).toFixed(1) + ' <span class="hc-s">#' + rankAt(t) + "</span></div>";
          return '<div class="hc-h">' + p.year + " \u00b7 " + esc(p.label.replace(/ \(.*\)$/, "")) + '</div><div class="hc-v"><b>' + p.v.toFixed(1) + "</b>" +
            (p.i ? moveChip(p.v, s.values[p.i - 1]) : "") + '<span class="hc-k">' +
            (rk ? "Conference Rating \u00b7 " + ordinal(rk) + " of " + ranked : "Average Team Rating \u00b7 not a conference") + "</span></div>" +
            (members.length ? '<div class="hc-g">' + one("Highest:", members[0]) + one("Lowest:", members[members.length - 1]) +
              '<div class="hc-s">' + members.length + " teams</div></div>" : "");
        }
      });
    }).catch(() => {
      if($("conf").value === name && $("season").value === y) box.innerHTML = '<p class="note">The history did not load. Reload the page to try again.</p>';
    });
  }

  function render(){
    const y = $("season").value, name = $("conf").value, cur = D.current, isCurrent = y === cur.season;
    const when = !isCurrent ? "at season's end" : cur.complete ? cur.now_label.toLowerCase() : "with this week still being played";
    $("c-status").textContent = y + " season · " + (isCurrent ? (cur.complete ? cur.now_label : "week in progress") + (cur.now_through ? " · " + day(cur.now_through) : "") : "season final");
    $("c-note").textContent = "Ratings " + when + ". Non-conf is the record against FBS teams from other conferences.";
    writeHash({season: isCurrent ? null : y, conf: name});

    // All conferences, best first. Independents are listed last without a rank.
    const ranked = confsOf(y), indep = D.conf[y].find(c => c[0] === INDEP);
    const line = (c, rk) => '<tr><td class="rk">' + rk + '</td><td><button type="button" class="link" data-conf="' + esc(c[0]) + '">' + esc(c[0]) +
      '</button><span class="rec">' + c[1] + ' teams</span></td><td class="rt">' + c[2].toFixed(1) + "</td><td>" + c[3] + "-" + c[4] + "</td></tr>";
    $("c-rows").innerHTML = ranked.map((c, i) => line(c, i + 1)).join("") + (indep ? line(indep, "–") : "");
    document.querySelectorAll("#c-rows button.link").forEach(b => b.addEventListener("click", () => {
      $("conf").value = b.dataset.conf; render();
      $("c-detail").scrollIntoView({block: "start"});
    }));

    // The selected conference's teams, best first.
    const self = D.conf[y].find(c => c[0] === name), ci = ranked.findIndex(c => c[0] === name);
    const members = Object.keys(D.team_conf[y]).filter(t => D.team_conf[y][t] === name && D.ratings[y][t])
      .sort((a, b) => D.ratings[y][a][1] - D.ratings[y][b][1]);
    $("c-name").textContent = name;
    $("c-detail-note").textContent = !self ? "" : name === INDEP
      ? "Independents are not a conference. The plain average of these teams' ratings is " + self[2].toFixed(1) + "."
      : "Conference Rating " + self[2].toFixed(1) + ", " + ordinal(ci + 1) + " of " + ranked.length + " conferences. " + self[3] + "-" + self[4] + " against FBS teams from other conferences.";
    $("c-teams").innerHTML = members.map((m, i) => {
      const r = D.ratings[y][m];
      return '<tr><td class="rk">' + (i + 1) + "</td><td>" + teamLink(m, isCurrent ? null : y) + '<span class="rec">' + r[2] + "-" + r[3] +
        '</span></td><td class="rt">' + r[0].toFixed(1) + "</td><td>" + r[1] + "</td></tr>";
    }).join("");

    drawHistory(name, y);
  }

  load().then(d => {
    D = d;
    const ys = Object.keys(D.conf).sort().reverse(), h = readHash();
    $("season").innerHTML = ys.map(y => "<option>" + y + "</option>").join("");
    $("season").value = ys.includes(h.season) ? h.season : D.current.season;
    fillConfs(h.conf); render();
    $("season").addEventListener("change", () => { fillConfs($("conf").value); render(); });
    $("conf").addEventListener("change", render);
  }).catch(() => {
    $("c-rows").innerHTML = '<tr><td colspan="4">The conference data did not load. Reload the page to try again.</td></tr>';
  });
})();
