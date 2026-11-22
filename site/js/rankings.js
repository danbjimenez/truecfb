/* TrueCFB: the rankings page. */
(() => {
  const {$, load, loadRank, esc, day, bonus, pollCell, teamLink, readHash, writeHash} = TC;
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
