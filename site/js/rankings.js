/* TrueCFB: the rankings page. */
(() => {
  const {$, load, esc, day, bonus, pollCell, teamLink, teamHref, readHash, writeHash} = TC;
  let D = null;

  const snapsOf = y => D.seasons[y];
  // Which point in the season a page opens on: the last fully completed week of the
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
  function row(r, y, withPoll){
    return '<tr><td class="rk">' + r[0] + "</td><td>" + teamLink(r[1], y) + '<span class="rec">' + r[3] + "-" + r[4] +
      '</span></td><td class="rt">' + r[2].toFixed(1) + "</td><td>" + bonus(D, r[2]) + "</td>" +
      (withPoll ? "<td>" + pollCell(r[0], r[5]) + "</td>" : "") + "</tr>";
  }
  function render(){
    const y = $("season").value, s = snapsOf(y).find(x => x.id === $("snap").value);
    const cur = D.current, isCurrent = y === cur.season, withPoll = !!s.n;
    const pollName = (!s.poll || s.poll === "Poll") ? "poll" : s.poll;

    // Status line: what this ranking covers.
    let status = y + " season · " + s.label.replace(" (after bowls and playoff)", "");
    if(isCurrent && s.id === cur.default && cur.through) status += " · " + day(cur.through);
    else if(isCurrent && s.id === "now" && cur.now_through) status += " · " + day(cur.now_through);
    $("status").textContent = status;

    // A week that is still being played is not in the default view.
    const prog = $("progress-note");
    if(isCurrent && !cur.complete && s.id !== "now"){
      prog.hidden = false;
      prog.textContent = cur.now_label + ". This ranking stops at the last full week. Choose “" + cur.now_label + "” above to count the finals so far.";
    } else if(isCurrent && !cur.complete && s.id === "now"){
      prog.hidden = false;
      prog.textContent = "This week is still being played, so these ratings will move as games finish.";
    } else prog.hidden = true;
    $("season-note").hidden = y !== "2020";

    $("rank-head").innerHTML = "<tr><th>#</th><th>Team</th><th>Rating</th><th>Bonus</th>" + (withPoll ? "<th>" + esc(s.poll || "Poll") + "</th>" : "") + "</tr>";
    $("rows").innerHTML = s.rows.map(r => row(r, y, withPoll)).join("");
    document.querySelectorAll(".poll-only").forEach(el => { el.hidden = !withPoll; });

    $("readouts").hidden = !withPoll;
    $("others-box").hidden = !withPoll;
    if(withPoll){
      $("r-in").textContent = s.rows.filter(r => r[5]).length + " of " + s.n;
      $("r-in-l").textContent = pollName + " teams are in the TrueCFB top 25";
      $("r-gap").textContent = s.gap.toFixed(1);
      $("r-gap-l").textContent = "average spots between the TrueCFB rank and the " + pollName + " rank";
      $("others").innerHTML = s.others.length
        ? '<div class="tablewrap"><table class="t-rank"><thead><tr><th>#</th><th>Team</th><th>Rating</th><th>Bonus</th><th>' + esc(s.poll || "Poll") + "</th></tr></thead><tbody>" +
          s.others.map(r => row(r, y, true)).join("") + "</tbody></table></div>"
        : '<p class="note">None. Every ' + esc(pollName) + " team is in the TrueCFB top 25.</p>";
    }
    writeHash(isCurrent && s.id === cur.default ? {} : {season: y, view: s.id});
  }
  function renderSeason(){
    const y = $("season").value, last = snapsOf(y)[snapsOf(y).length - 1];
    $("conf-note").textContent = "The plain average of every member's Team Rating, " +
      (last.id === "now" ? "from all games played so far." : "at season's end.") +
      " Non-conf is the record against FBS teams from other conferences.";
    $("conf").innerHTML = D.conf[y].map(c => "<tr><td>" + esc(c[0]) + '<span class="rec">' + c[1] + ' teams</span></td><td class="rt">' +
      c[2].toFixed(1) + "</td><td>" + c[3] + "-" + c[4] + "</td></tr>").join("");
    const teams = Object.keys(D.ratings[y]).sort((a, b) => a.localeCompare(b));
    $("jump").innerHTML = '<option value="">Choose a team</option>' +
      teams.map(t => '<option value="' + esc(t) + '">' + esc(t) + " (#" + D.ratings[y][t][1] + ")</option>").join("");
  }

  load().then(d => {
    D = d;
    const ys = Object.keys(D.seasons).sort().reverse(), h = readHash();
    $("season").innerHTML = ys.map(y => "<option>" + y + "</option>").join("");
    $("season").value = ys.includes(h.season) ? h.season : D.current.season;
    fillSnaps(h.view); renderSeason(); render();
    $("season").addEventListener("change", () => { fillSnaps(); renderSeason(); render(); });
    $("snap").addEventListener("change", render);
    $("jump").addEventListener("change", e => { if(e.target.value) location.href = teamHref(e.target.value, $("season").value); });
  }).catch(() => {
    $("rows").innerHTML = "<tr><td>The ranking data did not load. Reload the page to try again.</td></tr>";
  });
})();
