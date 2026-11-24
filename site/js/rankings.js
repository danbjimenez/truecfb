/* TrueCFB: the rankings page. */
(() => {
  const {$, load, loadRank, esc, day, bonus, pollCell, teamLink, teamHref, readHash, writeHash} = TC;
  let D = null, showAll = false;

  const snapsOf = y => D.seasons[y];
  // Which point in the season the page opens on: the last fully completed week of the
  // current season, or the season-final ranking of a finished one.
  function defaultSnap(y){
    const snaps = snapsOf(y);
    const want = y === D.current.season ? D.current.default : "final";
    return (snaps.find(s => s.id === want) || snaps[snaps.length - 1]).id;
  }
  function fillSnaps(keep){
    const y = $("season").value, snaps = snapsOf(y);
    $("snap").innerHTML = snaps.map(s => '<option value="' + s.id + '">' + esc(s.label) + "</option>").join("");
    $("snap").value = keep && snaps.some(s => s.id === keep) ? keep : defaultSnap(y);
  }
  // r = [rank, team, rating, wins, losses, CFP rank, AP rank]
  function row(r, y, s, isCurrent){
    // A poll that was published shows a rank or NR; one that was not published leaves the cell empty.
    // Below the top 25, NR would be on almost every row, so only ranked teams are marked there.
    const cell = (has, theirs) => !has ? "" : theirs ? pollCell(r[0], theirs) : r[0] <= 25 ? '<span class="nr">NR</span>' : "";
    return '<tr><td class="rk">' + r[0] + "</td><td>" + teamLink(r[1], isCurrent ? null : y) + '<span class="rec">' + r[3] + "-" + r[4] +
      '</span></td><td class="rt">' + r[2].toFixed(1) + "</td><td>" + bonus(D, r[2]) + "</td><td>" + cell(s.cfp, r[5]) +
      "</td><td>" + cell(s.ap, r[6]) + "</td></tr>";
  }
  // The chart under the table: how this top 25 moved through the season, up to the point picked above.
  function drawTrack(all, y, id, isCurrent){
    const snaps = snapsOf(y), points = snaps.slice(0, snaps.findIndex(x => x.id === id) + 1), top = (all[id] || []).slice(0, 25);
    $("track-box").hidden = !top.length;
    if(!top.length) return;
    const at = points.map(p => { const m = {}; (all[p.id] || []).forEach(r => { m[r[1]] = r; }); return m; });
    const teams = top.map(r => ({name: r[1], color: (D.colors || {})[r[1]], href: teamHref(r[1], isCurrent ? null : y),
      ranks: at.map(m => m[r[1]] ? m[r[1]][0] : null)}));
    const last = points[points.length - 1].label.replace(/ \(.*\)$/, "");
    $("track-note").textContent = points.length < 2
      ? "This is the starting order. Pick a later point in the season above to see the lines."
      : "Each line is one team's TrueCFB rank at every point of the " + y + " season, from the preseason to " + last.charAt(0).toLowerCase() + last.slice(1) +
        ". The teams are the top 25 at that point. A line on the bottom row was outside the top 25 that week. Lines are in each team's main color. Point at a line, or tap it, to follow one team.";
    TC.rankChart($("track"), {
      label: "Top 25 through the " + y + " season", points, teams,
      tip: (k, i) => {
        const t = teams[k], r = at[i][t.name], before = i ? at[i - 1][t.name] : null;
        const d = before ? before[0] - r[0] : null, cls = d > 0 ? "up" : d < 0 ? "down" : "same";
        const chip = d == null ? "" : '<span class="gap ' + cls + '">' + (d > 0 ? "+" + d : d < 0 ? "\u2212" + (-d) : "=") + "</span>";
        return '<div class="hc-h">' + esc(points[i].label.replace(/ \(.*\)$/, "")) + '</div><div class="hc-g">' + teamLink(t.name, isCurrent ? null : y) + "</div>" +
          '<div class="hc-v"><b>#' + r[0] + "</b>" + chip + '<span class="hc-k">Team Rating ' + r[2].toFixed(1) + " \u00b7 " + r[3] + "-" + r[4] + "</span></div>";
      }
    });
  }

  function render(){
    const y = $("season").value, id = $("snap").value, s = snapsOf(y).find(x => x.id === id);
    const cur = D.current, isCurrent = y === cur.season;

    // Status line: what this ranking covers.
    let status = y + " season · " + s.label.replace(" (after bowls and playoff)", "");
    if(isCurrent && id === cur.default && cur.through) status += " · " + day(cur.through);
    else if(isCurrent && id === "now" && cur.now_through) status += " · " + day(cur.now_through);
    $("status").textContent = status;

    // A week that is still being played is not in the default view.
    const prog = $("progress-note");
    if(isCurrent && !cur.complete && id !== "now"){
      prog.hidden = false;
      prog.textContent = cur.now_label + ". This ranking stops at the last full week. Choose “" + cur.now_label + "” above to count the finals so far.";
    } else if(isCurrent && !cur.complete && id === "now"){
      prog.hidden = false;
      prog.textContent = "This week is still being played, so these ratings will move as games finish.";
    } else prog.hidden = true;
    $("season-note").hidden = y !== "2020";

    // Why a poll column is empty.
    const pn = $("poll-note");
    if(s.cfp && s.ap) pn.hidden = true;
    else {
      pn.hidden = false;
      pn.textContent = isCurrent && id === "now" && cur.complete
        ? "A poll is only compared once it includes these games. The AP poll comes out on Sunday and the CFP ranking on Tuesday."
        : id === "final" ? "After the bowls and the playoff, only the AP publishes a final poll."
        : id === "post" ? "Neither poll is published during the bowls and the playoff. The AP's final poll comes after the title game."
        : !s.cfp && !s.ap ? "No AP or CFP ranking is on file for this point in the season."
        : !s.cfp ? "The CFP committee had not published a ranking at this point in the season."
        : "No AP poll is on file for this point in the season.";
    }

    writeHash(isCurrent && id === cur.default && !showAll ? {} : {season: isCurrent ? null : y, view: isCurrent && id === cur.default ? null : id, show: showAll ? "all" : null});

    loadRank(y).then(all => {
      if($("season").value !== y || $("snap").value !== id) return;
      const rows = all[id] || [];
      $("rows").innerHTML = (showAll ? rows : rows.slice(0, 25)).map(r => row(r, y, s, isCurrent)).join("") ||
        '<tr><td colspan="6">No ranking for this point in the season.</td></tr>';
      drawTrack(all, y, id, isCurrent);
    }).catch(() => {
      $("rows").innerHTML = '<tr><td colspan="6">The ranking did not load. Reload the page to try again.</td></tr>';
    });
  }
  function setShow(all){
    showAll = all;
    document.querySelectorAll("#show button").forEach(b => b.setAttribute("aria-pressed", String((b.dataset.v === "all") === all)));
  }

  load().then(d => {
    D = d;
    const ys = Object.keys(D.seasons).sort().reverse(), h = readHash();
    $("season").innerHTML = ys.map(y => "<option>" + y + "</option>").join("");
    $("season").value = ys.includes(h.season) ? h.season : D.current.season;
    setShow(h.show === "all");
    fillSnaps(h.view); render();
    $("season").addEventListener("change", () => { fillSnaps(); render(); });
    $("snap").addEventListener("change", render);
    document.querySelectorAll("#show button").forEach(b => b.addEventListener("click", () => { setShow(b.dataset.v === "all"); render(); }));
  }).catch(() => {
    $("rows").innerHTML = '<tr><td colspan="6">The ranking data did not load. Reload the page to try again.</td></tr>';
  });
})();
