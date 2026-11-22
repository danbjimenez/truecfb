/* TrueCFB: the Game Rating chart on the How it works page. */
(() => {
  const {$, load, bonus} = TC;
  let D = null, venue = 0;

  function gameRating(m, win, opp){
    const S = D.settings, f = D.F[Math.min(m, D.F.length - 1)], w = S.win[0] + (S.win[1] - S.win[0]) * f;
    return Math.max(0, Math.min(100, (win ? w : 100 - w) + venue * S.venue + S.b * (opp - 50)));
  }
  function renderCurve(){
    const opp = +$("opp").value;
    $("opp-v").textContent = opp; $("opp-b").textContent = bonus(D, opp);
    const L = 34, R = 388, T = 12, Bm = 222, X = m => L + (m - 1) / 48 * (R - L), Y = v => Bm - v / 100 * (Bm - T);
    let s = "";
    [0, 25, 50, 75, 100].forEach(v => { s += '<line class="grid" x1="' + L + '" x2="' + R + '" y1="' + Y(v) + '" y2="' + Y(v) + '"/><text class="axis" x="' + (L - 8) + '" y="' + (Y(v) + 4) + '" text-anchor="end">' + v + "</text>"; });
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

  load().then(d => {
    D = d; renderCurve();
    $("opp").addEventListener("input", renderCurve);
    document.querySelectorAll("#ven button").forEach(b => b.addEventListener("click", () => {
      venue = +b.dataset.v;
      document.querySelectorAll("#ven button").forEach(x => x.setAttribute("aria-pressed", x === b));
      renderCurve();
    }));
  }).catch(() => { $("quick").innerHTML = '<p class="note">The chart data did not load. Reload the page to try again.</p>'; });
})();
