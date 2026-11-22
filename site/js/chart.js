/* TrueCFB: the rating history chart on the team and conference pages.
   One line for the chosen team or conference, with one point for every snapshot of every season
   (preseason, after each week, regular season final, season final).

   TC.historyChart(box, cfg)
     box   the element to draw in (class "hc")
     cfg   label     what the chart shows, for screen readers
           seasons   [{year, points: [{id, label}], values: [rating, ...] or null}], oldest first
           context   optional list of functions year -> [rating, ...] or null, drawn as quiet grey lines
           selected  the season picked on the page; its band is shaded
           domain    [lowest, highest] rating on the scale
           ticks     ratings that get a gridline and a label
           tip       (point, again) -> HTML for the data label. point = {year, i, id, label, v}.
                     Call again() when data the label was waiting for has arrived.
           onPick    optional: called with a year when the reader picks that season */
TC.historyChart = (box, cfg) => {
  const {esc} = TC;
  if(box._watch) box._watch.disconnect();
  box.innerHTML = '<div class="hc-plot" tabindex="0" role="group" aria-label="' + esc(cfg.label) +
    '. Use the left and right arrow keys to move through the weeks."></div><div class="hc-tip" role="status" aria-live="polite" hidden></div>';
  const plot = box.firstChild, tip = box.lastChild;
  const slots = Math.max.apply(null, cfg.seasons.map(s => s.points.length));
  let pts = [], cur = -1, key = null, W = 0, H = 0, narrow = false, cross = null, dot = null, mouse = false;

  function draw(){
    const width = Math.floor(box.clientWidth);
    if(!width || width === W) return;
    W = width; narrow = W < 560; H = narrow ? 220 : 300;
    box.classList.toggle("hc-narrow", narrow);
    const m = {l: 30, r: 6, t: 10, b: 24}, pw = W - m.l - m.r, ph = H - m.t - m.b, band = pw / cfg.seasons.length;
    const lo = cfg.domain[0], hi = cfg.domain[1];
    const Y = v => m.t + ph * (1 - (v - lo) / (hi - lo));
    const X = (si, i) => m.l + si * band + (i + 0.5) * band / slots;
    const n1 = v => v.toFixed(1);

    pts = [];
    cfg.seasons.forEach((s, si) => s.points.forEach((p, i) => {
      const v = s.values ? s.values[i] : null;
      if(v != null) pts.push({year: s.year, i, id: p.id, label: p.label, v, x: X(si, i), y: Y(v)});
    }));
    // One path per series. A season the team or conference was not in leaves a gap.
    const path = valuesOf => {
      let d = "", pen = false;
      cfg.seasons.forEach((s, si) => {
        const vals = valuesOf(s);
        if(!vals){ pen = false; return; }
        s.points.forEach((p, i) => {
          if(vals[i] == null){ pen = false; return; }
          d += (pen ? "L" : "M") + n1(X(si, i)) + " " + n1(Y(vals[i]));
          pen = true;
        });
      });
      return d;
    };

    const sel = cfg.seasons.findIndex(s => s.year === cfg.selected), step = band < 22 ? 2 : 1;
    let g = '<svg viewBox="0 0 ' + W + " " + H + '" width="' + W + '" height="' + H + '" aria-hidden="true">';
    if(sel >= 0) g += '<rect class="hc-sel" x="' + n1(m.l + sel * band) + '" y="' + m.t + '" width="' + n1(band) + '" height="' + ph + '"/>';
    cfg.ticks.forEach(t => {
      g += '<line class="grid" x1="' + m.l + '" x2="' + (W - m.r) + '" y1="' + n1(Y(t)) + '" y2="' + n1(Y(t)) + '"/>' +
        '<text class="axis" x="' + (m.l - 6) + '" y="' + n1(Y(t) + 4) + '" text-anchor="end">' + t + "</text>";
    });
    cfg.seasons.forEach((s, si) => {
      if(si) g += '<line class="grid" x1="' + n1(m.l + si * band) + '" x2="' + n1(m.l + si * band) + '" y1="' + m.t + '" y2="' + (m.t + ph) + '"/>';
      if(si === sel || (step === 1 || (si % 2 === 0 && Math.abs(si - sel) !== 1)))
        g += '<text class="axis' + (si === sel ? " hc-on" : "") + '" x="' + n1(m.l + (si + 0.5) * band) + '" y="' + (H - 7) + '" text-anchor="middle">' +
          (band < 44 ? "’" + s.year.slice(2) : s.year) + "</text>";
    });
    (cfg.context || []).forEach(fn => { g += '<path class="hc-ctx" d="' + path(s => fn(s.year)) + '"/>'; });
    g += '<path class="hc-line" d="' + path(s => s.values) + '"/>' +
      '<line class="hc-cross" y1="' + m.t + '" y2="' + (m.t + ph) + '" style="display:none"/><circle class="hc-dot" r="4.5" style="display:none"/></svg>';
    plot.innerHTML = g;
    cross = plot.querySelector(".hc-cross"); dot = plot.querySelector(".hc-dot");

    // Keep the reader's place when the chart is redrawn at a new width. On a phone the label sits
    // under the chart and always shows a point, starting with the latest.
    const back = key ? pts.findIndex(p => p.year + "|" + p.id === key) : -1;
    if(back >= 0) show(back); else if(narrow) show(pts.length - 1); else hide();
  }

  function show(k){
    if(!pts.length) return;
    k = Math.max(0, Math.min(pts.length - 1, k));
    const p = pts[k];
    cur = k; key = p.year + "|" + p.id;
    cross.setAttribute("x1", p.x); cross.setAttribute("x2", p.x); cross.style.display = "";
    dot.setAttribute("cx", p.x); dot.setAttribute("cy", p.y); dot.style.display = "";
    tip.hidden = false;
    tip.innerHTML = cfg.tip(p, () => { if(key === p.year + "|" + p.id) show(cur); });
    if(cfg.onPick && narrow && p.year !== cfg.selected){
      const b = document.createElement("button");
      b.type = "button"; b.className = "link"; b.textContent = "Open the " + p.year + " season";
      b.addEventListener("click", () => cfg.onPick(p.year));
      tip.appendChild(b);
    }
    if(narrow){ tip.style.left = tip.style.top = ""; return; }
    // Beside the crosshair, on whichever side has room, level with the point.
    const tw = tip.offsetWidth, th = tip.offsetHeight;
    let left = p.x + 14;
    if(left + tw > W) left = p.x - 14 - tw;
    tip.style.left = Math.max(0, left) + "px";
    tip.style.top = Math.max(0, Math.min(H - th, p.y - th / 2)) + "px";
  }
  function hide(){
    if(narrow && pts.length) return show(pts.length - 1);
    cur = -1; key = null; tip.hidden = true;
    if(cross){ cross.style.display = "none"; dot.style.display = "none"; }
  }
  // The crosshair snaps to the nearest point, so the reader aims at a week, not at the line.
  function nearest(e){
    const r = plot.getBoundingClientRect(), x = (e.clientX - r.left) * W / r.width;
    let best = 0;
    for(let k = 1; k < pts.length; k++) if(Math.abs(pts[k].x - x) < Math.abs(pts[best].x - x)) best = k;
    return best;
  }

  plot.addEventListener("pointermove", e => { mouse = e.pointerType === "mouse"; if(pts.length) show(nearest(e)); });
  plot.addEventListener("pointerdown", e => { mouse = e.pointerType === "mouse"; if(pts.length) show(nearest(e)); });
  plot.addEventListener("pointerleave", e => { if(e.pointerType === "mouse") hide(); });
  plot.addEventListener("click", () => { if(mouse && cfg.onPick && cur >= 0 && pts[cur].year !== cfg.selected) cfg.onPick(pts[cur].year); });
  plot.addEventListener("keydown", e => {
    const to = {ArrowLeft: cur < 0 ? pts.length - 1 : cur - 1, ArrowRight: cur < 0 ? pts.length - 1 : cur + 1, Home: 0, End: pts.length - 1}[e.key];
    if(to != null){ e.preventDefault(); show(to); }
    else if(e.key === "Escape") hide();
    else if(e.key === "Enter" && cfg.onPick && cur >= 0 && pts[cur].year !== cfg.selected) cfg.onPick(pts[cur].year);
  });
  // On a phone the label stays put: it holds the button that opens a season.
  plot.addEventListener("blur", () => { if(!mouse && !narrow) hide(); });

  draw();
  if(window.ResizeObserver){ box._watch = new ResizeObserver(draw); box._watch.observe(box); }
};
