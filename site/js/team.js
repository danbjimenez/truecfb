/* TrueCFB: one team's page. */
(() => {
  const {$, slug, load, loadSched, loadHistory, esc, day, bonus, matchup, moveChip, teamLink, teamHref, readHash, ordinal} = TC;
  let D = null;
  const got = {};   // seasons whose game files have arrived, for the chart's data labels

  function resultText(g){
    return (g[3] > g[4] ? "W " : "L ") + g[3] + "-" + g[4] + (g[5] ? " OT" : "");
  }
  function where(g){
    return g[2] === "H" ? "vs " : g[2] === "A" ? "at " : "vs (N) ";
  }

  // Where a team's first rating of a season came from.
  function startNote(t, y, rating){
    if(D.history[t] && D.history[t][String(+y - 1)]) return "Last season's final Team Rating";
    // The first season shown starts from the season before it, which is run only to set this number.
    const first = Object.keys(D.seasons).sort()[0];
    return y === first && rating !== D.settings.fcs ? "The final " + (+y - 1) + " Team Rating" : "A team new to FBS starts at " + D.settings.fcs;
  }

  // Team Rating History: one point for every snapshot of every season.
  function drawHistory(t, y){
    const box = $("t-chart");
    loadHistory().then(H => {
      if($("team").value !== t || $("season").value !== y) return;
      const mine = H.teams[t] || {}, pick = (flat, odd) => flat ? flat.filter((_, i) => i % 2 === odd) : null;
      let top = 100;
      const seasons = Object.keys(D.seasons).sort().map(k => {
        const values = pick(mine[k], 0);
        if(values) top = Math.max(top, Math.max.apply(null, values));
        return {year: k, points: D.seasons[k], values, ranks: pick(mine[k], 1)};
      });
      TC.historyChart(box, {
        label: "Team Rating History for " + t, seasons, selected: y,
        domain: [0, Math.ceil(top / 10) * 10], ticks: [0, 25, 50, 75, 100],
        onPick: k => { $("season").value = k; render(); },
        tip: (p, again) => {
          const s = seasons.find(x => x.year === p.year);
          const head = '<div class="hc-h">' + p.year + " \u00b7 " + esc(p.label.replace(/ \(.*\)$/, "")) + '</div><div class="hc-v"><b>' + p.v.toFixed(1) + "</b>" +
            (p.i ? moveChip(p.v, s.values[p.i - 1]) : "") + '<span class="hc-k">Team Rating \u00b7 #' + s.ranks[p.i] + "</span></div>";
          if(p.i === 0) return head + '<div class="hc-s">' + esc(startNote(t, p.year, p.v)) + "</div>";
          const all = got[p.year];
          if(!all){
            loadSched(p.year).then(a => { got[p.year] = a; }).catch(() => { got[p.year] = {failed: true}; }).then(again);
            return head + '<div class="hc-s">Loading the game\u2026</div>';
          }
          if(all.failed) return head + '<div class="hc-s">The game did not load.</div>';
          const games = ((all.games || {})[t] || []).filter(g => g[13] === p.id), rating = D.ratings[p.year][t][0];
          if(!games.length) return head + '<div class="hc-s">' + (p.id === "final" ? "No bowl or playoff game" : p.id === "post" ? "No bowl or playoff game yet" : p.id === "reg" ? "No new game" : "No game this week") + "</div>";
          return head + games.map(g => '<div class="hc-g"><div>' + resultText(g) + " " + where(g) + esc(g[1]) + '</div><div class="hc-s">' + day(g[0]) +
            " \u00b7 Game Rating " + g[6].toFixed(1) + " \u00b7 Matchup Rating " + matchup(D, rating, g) + "</div></div>").join("");
        }
      });
    }).catch(() => {
      if($("team").value === t && $("season").value === y) box.innerHTML = '<p class="note">The history did not load. Reload the page to try again.</p>';
    });
  }

  function render(){
    const t = $("team").value, y = $("season").value, info = D.ratings[y][t];
    const cur = D.current, isCurrent = y === cur.season;
    document.title = t + " · TrueCFB";
    $("t-name").textContent = t;
    history.replaceState(null, "", teamHref(t, isCurrent ? null : y));   // /team/utah, or /team/utah#season=2019

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

    drawHistory(t, y);

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
    // The page arrives with this team's latest season already written in (src/build_pages.py); keep it on screen until the file loads.
    const sch = $("t-sched"), built = sch.dataset.built === t + "|" + y;
    delete sch.dataset.built;
    if(!built){
      $("t-tiles").innerHTML = "";
      sch.innerHTML = '<tr><td colspan="4">Loading the games…</td></tr>';
    }
    loadSched(y).then(all => {
      if($("team").value !== t || $("season").value !== y) return;
      got[y] = all;
      const games = (all.games || {})[t] || [], start = (all.start || {})[t];
      const move = moveChip;   // how far the Team Rating moved from the row above
      let prev = start ? start[0] : null;
      const first = start ? '<tr><td>Start of season<span class="sub2">' +
        esc(startNote(t, y, start[0])) +
        '</span></td><td></td><td></td><td class="rt">' + start[0].toFixed(1) + '<span class="sub2">#' + start[1] + "</span></td></tr>" : "";
      const rows = games.map(g => {
        const pot = matchup(D, info[0], g);
        const post = g[9] ? " \u00b7 " + (g[9] === 15 ? "playoff" : "bowl") + " +" + (g[9] + (g[3] > g[4] ? g[10] : 0)) : "";
        const opp = g[8] ? esc(g[1]) + ' <span class="rec">FCS</span>' : teamLink(g[1], isCurrent ? null : y);
        const after = g[11] == null ? "" : g[11].toFixed(1) + '<span class="sub2">' + move(g[11], prev) + (g[12] ? " #" + g[12] : "") + "</span>";
        if(g[11] != null) prev = g[11];
        return "<tr><td>" + where(g) + opp + '<span class="sub2"><span>' + day(g[0]) + " \u00b7 bonus " + bonus(D, g[7]) + " \u00b7</span> <span>Matchup Rating " + pot + post +
          "</span></span></td><td>" + resultText(g) + "</td><td>" + g[6].toFixed(1) + '</td><td class="rt">' + after + "</td></tr>";
      }).join("");
      $("t-sched").innerHTML = first + (rows || '<tr><td colspan="4">No games played yet this season.</td></tr>');

      const tiles = [[bonus(D, info[0]), "Bonus: what " + t + " is worth to anyone who plays it"]];
      if(games.length){
        const best = games.reduce((a, b) => b[6] > a[6] ? b : a), low = games.reduce((a, b) => b[6] < a[6] ? b : a);
        const avgOpp = games.reduce((s, g) => s + g[7], 0) / games.length;
        tiles.push([best[6].toFixed(0), "Best Game Rating: " + resultText(best) + " " + where(best) + best[1]]);
        tiles.push([low[6].toFixed(0), "Lowest Game Rating: " + resultText(low) + " " + where(low) + low[1]]);
        tiles.push([avgOpp.toFixed(0), "Average opponent Team Rating (an average team is 50)"]);
      }
      $("t-tiles").innerHTML = tiles.map(q => "<div><b>" + esc(q[0]) + "</b><span>" + esc(q[1]) + "</span></div>").join("");
    }).catch(() => {
      if($("team").value === t && $("season").value === y)
        $("t-sched").innerHTML = '<tr><td colspan="4">The games did not load. Pick the team again to retry.</td></tr>';
    });
  }

  // The team comes from the address (/team/utah); the season from "#season=2019", else the current one,
  // or the team's last FBS season if it is not in FBS now.
  function pickFromAddress(){
    const h = readHash(), ys = Object.keys(D.seasons);
    const bySlug = {};
    Object.keys(D.history).forEach(x => { bySlug[slug(x)] = x; });
    const t = bySlug[decodeURIComponent(location.pathname.replace(/\/+$/, "").split("/").pop())] ||
      (h.team && D.history[h.team] ? h.team : null) || document.body.dataset.team;
    if(t && D.history[t]) $("team").value = t;
    const mine = ys.filter(y => D.ratings[y][$("team").value]).sort();
    $("season").value = h.season && ys.includes(h.season) ? h.season
      : D.ratings[D.current.season][$("team").value] || !mine.length ? D.current.season : mine[mine.length - 1];
  }

  load().then(d => {
    D = d;
    const ys = Object.keys(D.seasons).sort().reverse();
    $("season").innerHTML = ys.map(y => "<option>" + y + "</option>").join("");
    $("season").value = D.current.season;
    const teams = Object.keys(D.history).sort((a, b) => a.localeCompare(b));
    $("team").innerHTML = teams.map(t => '<option value="' + esc(t) + '">' + esc(t) + "</option>").join("");
    // With no team in the link, open on the current #1.
    const cr = D.ratings[D.current.season], top = Object.keys(cr).find(t => cr[t][1] === 1);
    if(top) $("team").value = top;
    pickFromAddress(); render();
    $("team").addEventListener("change", render);
    $("season").addEventListener("change", render);
    window.addEventListener("hashchange", () => { pickFromAddress(); render(); window.scrollTo(0, 0); });
  }).catch(() => {
    $("t-missing").hidden = false;
    $("t-missing").textContent = "The team data did not load. Reload the page to try again.";
    $("t-body").hidden = true;
  });
})();
