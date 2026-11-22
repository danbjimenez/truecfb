/* TrueCFB: the conferences page. */
(() => {
  const {$, load, esc, day, teamLink, readHash, writeHash, ordinal} = TC;
  const INDEP = "FBS Independents";
  let D = null;

  const clamp = v => Math.max(0, Math.min(100, v));
  // c = [name, number of teams, rating, non-conference wins, non-conference losses]
  const confsOf = y => D.conf[y].filter(c => c[0] !== INDEP);

  function fillConfs(keep){
    const y = $("season").value, names = D.conf[y].map(c => c[0]);
    $("conf").innerHTML = names.map(n => '<option value="' + esc(n) + '">' + esc(n) + "</option>").join("");
    $("conf").value = keep && names.includes(keep) ? keep : names[0];
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

    // The conference's rating in every season it existed under this name.
    const years = Object.keys(D.conf).sort().filter(k => D.conf[k].some(c => c[0] === name));
    $("c-hist").innerHTML = years.map(k => {
      const c = D.conf[k].find(x => x[0] === name), list = D.conf[k].filter(x => x[0] !== INDEP), rk = list.findIndex(x => x[0] === name);
      return '<div class="hrow"><span class="yr">' + k + '</span><span class="bar"><i style="width:' + clamp(c[2]) + '%"></i></span><span class="val">' +
        c[2].toFixed(1) + (rk >= 0 ? "<small>#" + (rk + 1) + "</small>" : "") + "</span></div>";
    }).join("");
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
