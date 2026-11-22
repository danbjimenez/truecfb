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

/* TC.rankChart(box, cfg): how a set of teams moved through the rankings, one line per team.
     box   the element to draw in (class "hc")
     cfg   label   what the chart shows, for screen readers
           points  [{id, label}], the points in the season from the first to the one picked on the page
           teams   [{name, color, href, ranks: [rank at each point]}], in rank order at the last point
           tip     (team index, point index) -> HTML for the data label
   A line is drawn in the team's colour, adjusted where needed so it shows against the panel.
   Names stay in the text colour, each at the end of its own line, so colour is never the only clue. */
TC.rankChart = (box, cfg) => {
  const {esc} = TC, n = cfg.points.length, OUT = 26.4;
  if(box._watch) box._watch.disconnect();
  if(box._scheme) box._scheme[0].removeEventListener("change", box._scheme[1]);
  box.innerHTML = '<div class="hc-plot rk" tabindex="0" role="group" aria-label="' + esc(cfg.label) +
    '. Use the up and down arrow keys to move between teams, and left and right to move through the weeks."></div><div class="hc-tip" role="status" aria-live="polite" hidden></div>';
  const plot = box.firstChild, tip = box.lastChild;
  let W = 0, H = 0, narrow = false, X = null, Y = null, mark = null, curT = -1, curI = -1, right = 0;

  const rgb = h => [1, 3, 5].map(k => parseInt(h.slice(k, k + 2), 16));
  const lum = c => { const v = c.map(x => { x /= 255; return x <= .03928 ? x / 12.92 : Math.pow((x + .055) / 1.055, 2.4); }); return .2126 * v[0] + .7152 * v[1] + .0722 * v[2]; };
  const contrast = (a, b) => (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
  // A navy line on a dark panel, or a yellow one on white, would vanish: step it toward the text side until it shows.
  function shown(hex, panel){
    let c = rgb(hex);
    const pl = lum(panel), to = pl < .5 ? 255 : 0;
    for(let k = 0; k < 14 && contrast(lum(c), pl) < 3; k++) c = c.map(v => Math.round(v + (to - v) * .15));
    return "rgb(" + c.join(",") + ")";
  }
  function short(p, i){
    const w = /week (\d+)/i.exec(p.label);
    return i === 0 && /pre/i.test(p.label) ? "Pre" : p.id === "reg" ? "Reg" : p.id === "final" ? "Final" : w ? w[1] : "Now";
  }

  function draw(){
    const width = Math.floor(box.clientWidth);
    if(!width || width === W) return;
    W = width; narrow = W < 560;
    box.classList.toggle("hc-narrow", narrow);
    const rowH = narrow ? 13 : 17, m = {l: 30, r: narrow ? 96 : 132, t: 6, b: 22}, pw = W - m.l - m.r;
    H = Math.round(m.t + (OUT + .5) * rowH + m.b); right = W - m.r;
    X = i => n > 1 ? m.l + 8 + i * (pw - 16) / (n - 1) : m.l + pw / 2;
    Y = r => m.t + (Math.min(r, OUT) - .5) * rowH;
    const n1 = v => v.toFixed(1);
    const raw = getComputedStyle(box).getPropertyValue("--panel").trim(), panel = /^#[0-9a-f]{6}$/i.test(raw) ? rgb(raw) : [255, 255, 255];

    let g = '<svg viewBox="0 0 ' + W + " " + H + '" width="' + W + '" height="' + H + '">';
    for(let r = 1; r <= 25; r++){
      g += '<text class="axis" x="' + (m.l - 6) + '" y="' + n1(Y(r) + 4) + '" text-anchor="end">' + r + "</text>";
      if(r % 5 === 0) g += '<line class="grid" x1="' + m.l + '" x2="' + right + '" y1="' + n1(m.t + r * rowH) + '" y2="' + n1(m.t + r * rowH) + '"/>';
    }
    g += '<text class="axis" x="' + (m.l - 6) + '" y="' + n1(Y(OUT) + 4) + '" text-anchor="end">26+</text>';
    const step = Math.max(1, Math.ceil(22 / (n > 1 ? (pw - 16) / (n - 1) : 22)));
    cfg.points.forEach((p, i) => {
      if((n - 1 - i) % step === 0) g += '<text class="axis" x="' + n1(X(i)) + '" y="' + (H - 6) + '" text-anchor="middle">' + short(p, i) + "</text>";
    });
    // The best-ranked team is drawn last, so it sits on top where lines cross.
    for(let k = cfg.teams.length - 1; k >= 0; k--){
      const t = cfg.teams[k], col = t.color ? shown(t.color, panel) : "";
      let d = "", pen = false;
      t.ranks.forEach((r, i) => { if(r == null){ pen = false; return; } d += (pen ? "L" : "M") + n1(X(i)) + " " + n1(Y(r)); pen = true; });
      const last = t.ranks[n - 1];
      g += '<path class="rk-line" data-t="' + k + '"' + (col ? ' stroke="' + col + '"' : "") + ' d="' + d + '"/>' +
        '<circle class="rk-end" data-t="' + k + '" r="3"' + (col ? ' fill="' + col + '"' : "") + ' cx="' + n1(X(n - 1)) + '" cy="' + n1(Y(last)) + '"/>' +
        '<a href="' + esc(t.href) + '"><text class="rk-name" data-t="' + k + '" x="' + (right + 8) + '" y="' + n1(Y(last) + 4) + '">' + esc(t.name) + "</text></a>";
    }
    g += '<circle class="rk-mark" r="5" style="display:none"/></svg>';
    plot.innerHTML = g;
    mark = plot.querySelector(".rk-mark");
    if(curT >= 0) show(curT, curI); else rest();
  }

  function show(k, i){
    if(!cfg.teams.length) return;
    k = Math.max(0, Math.min(cfg.teams.length - 1, k)); i = Math.max(0, Math.min(n - 1, i));
    const t = cfg.teams[k], r = t.ranks[i];
    if(r == null) return;
    plot.querySelectorAll(".on").forEach(e => e.classList.remove("on"));
    plot.querySelectorAll('[data-t="' + k + '"]').forEach(e => e.classList.add("on"));
    plot.classList.add("rk-dim");
    curT = k; curI = i;
    const line = plot.querySelector('.rk-line[data-t="' + k + '"]');
    mark.setAttribute("cx", X(i)); mark.setAttribute("cy", Y(r)); mark.setAttribute("fill", line.getAttribute("stroke") || "currentColor"); mark.style.display = "";
    tip.hidden = false;
    tip.innerHTML = cfg.tip(k, i);
    if(narrow){ tip.style.left = tip.style.top = ""; return; }
    const tw = tip.offsetWidth, th = tip.offsetHeight;
    let left = X(i) + 14;
    if(left + tw > right) left = X(i) - 14 - tw;
    tip.style.left = Math.max(0, left) + "px";
    tip.style.top = Math.max(0, Math.min(H - th, Y(r) - th / 2)) + "px";
  }
  // Nothing picked: every line at full strength. On a phone the label space stays, with a hint in it.
  function rest(){
    curT = curI = -1;
    plot.classList.remove("rk-dim");
    plot.querySelectorAll(".on").forEach(e => e.classList.remove("on"));
    if(mark) mark.style.display = "none";
    tip.style.left = tip.style.top = "";
    tip.hidden = !narrow;
    if(narrow) tip.innerHTML = '<div class="hc-s">Tap a line to follow one team. Tap a name to open its page.</div>';
  }
  // The nearest week under the pointer, then the team whose line is closest at that week.
  function pick(e){
    const b = plot.getBoundingClientRect(), x = (e.clientX - b.left) * W / b.width, y = (e.clientY - b.top) * W / b.width;
    let i = 0;
    for(let j = 1; j < n; j++) if(Math.abs(X(j) - x) < Math.abs(X(i) - x)) i = j;
    if(x > right) i = n - 1;
    let k = -1, best = 1e9;
    cfg.teams.forEach((t, j) => { const r = t.ranks[i]; if(r != null && Math.abs(Y(r) - y) < best){ best = Math.abs(Y(r) - y); k = j; } });
    if(k >= 0) show(k, i);
  }

  plot.addEventListener("pointermove", pick);
  plot.addEventListener("pointerdown", pick);
  plot.addEventListener("pointerleave", e => { if(e.pointerType === "mouse") rest(); });
  plot.addEventListener("keydown", e => {
    const move = {ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1]}[e.key];
    if(move){ e.preventDefault(); if(curT < 0) show(0, n - 1); else show(curT + move[0], curI + move[1]); }
    else if(e.key === "Escape") rest();
  });

  draw();
  if(window.ResizeObserver){ box._watch = new ResizeObserver(draw); box._watch.observe(box); }
  // Light and dark panels need different line adjustments, so redraw when the theme changes.
  if(window.matchMedia){
    const mq = matchMedia("(prefers-color-scheme: dark)"), again = () => { W = 0; draw(); };
    mq.addEventListener("change", again); box._scheme = [mq, again];
  }
};
