(async function () {
  const $ = (id) => document.getElementById(id);
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  // theme toggle
  $("theme").addEventListener("click", () => {
    const r = document.documentElement;
    const dark = r.dataset.theme ? r.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    r.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("pluma-theme", r.dataset.theme); } catch (e) {}
    redraw();
  });
  try { const t = localStorage.getItem("pluma-theme"); if (t) document.documentElement.dataset.theme = t; } catch (e) {}

  const [rows, meta] = await Promise.all([
    fetch("data/lookrock.json").then((r) => r.json()),
    fetch("data/meta.json").then((r) => r.json()),
  ]);
  const H = meta.headline;
  $("rho-ext").innerHTML = (() => { const [a, b] = H.camera_vs_site_extinction.spearman.toFixed(2).split("."); return `${a}<span class="dp">.</span>${b}`; })();
  $("rho-ext-note").textContent = `Rank match across ${H.camera_vs_site_extinction.n} daytime hours in November 2016.`;
  $("cat-within").textContent = Math.round(H.test.within_one_category * 100) + "%";
  $("cat-note").textContent = `Exact category ${Math.round(H.test.category_match * 100)}% of the time, ${H.test.n} hours, 19–29 Nov.`;

  const pts = rows.filter((r) => r.gate === "pass" && r.pred_pm25 != null && r.monitor_pm25 != null)
    .map((r) => ({ ...r, t: new Date(r.timestamp) }));
  pts.sort((a, b) => a.t - b.t);

  // distance map -> metres (NaN for sky)
  const dimg = new Image(); dimg.src = "data/distance.png"; await dimg.decode();
  const W = 1000, Hh = 520;
  const tmp = document.createElement("canvas"); tmp.width = W; tmp.height = Hh;
  const tctx = tmp.getContext("2d"); tctx.drawImage(dimg, 0, 0);
  const raw = tctx.getImageData(0, 0, W, Hh).data;
  const enc = meta.distance_encoding;
  const dist = new Float32Array(W * Hh);
  for (let i = 0; i < W * Hh; i++) {
    const v = raw[i * 4];
    dist[i] = v === 0 ? NaN : Math.pow(10, enc.log10_min + ((v - 1) / 254) * (enc.log10_max - enc.log10_min));
  }

  const sight = $("sight"), sctx = sight.getContext("2d");
  const out = sctx.createImageData(W, Hh);
  const hex = (h) => { h = h.replace("#", ""); return [0, 2, 4].map((k) => parseInt(h.slice(k, k + 2), 16)); };

  const LABELS = ["Happy Valley Ridge", "Rich Mtn", "Clingmans Dome"];
  const sightFrame = $("sight-frame");
  const labelEls = LABELS.map((name) => {
    const r = meta.ridges.find((x) => x.name === name);
    const el = document.createElement("div"); el.className = "ridge-label";
    const lift = name === "Clingmans Dome" ? 9 : 0;
    el.style.left = (r.x * 100) + "%"; el.style.top = (r.y * 100 - 1 - lift) + "%";
    sightFrame.appendChild(el); return { el, r };
  });

  const ptex = document.createElement("canvas"); ptex.width = W; ptex.height = Hh;
  const pctx = ptex.getContext("2d", { willReadFrequently: true });
  let lum = null;
  function readPhoto(img) {
    pctx.drawImage(img, 0, 200, 1000, 520, 0, 0, W, Hh);
    const px = pctx.getImageData(0, 0, W, Hh).data; lum = new Float32Array(W * Hh);
    for (let i = 0; i < W * Hh; i++) lum[i] = (0.2126 * px[i * 4] + 0.7152 * px[i * 4 + 1] + 0.0722 * px[i * 4 + 2]) / 255;
  }
  const STOPS = ["#0b0f17", "#1d2b4a", "#2f6f8f", "#5fc2b0", "#d9f2c4", "#fff8e8"].map(hex);
  const ramp = (t) => {
    const x = Math.min(Math.max(t, 0), 1) * (STOPS.length - 1), k = Math.min(Math.floor(x), STOPS.length - 2), f = x - k;
    const A = STOPS[k], B = STOPS[k + 1];
    return [A[0] + (B[0] - A[0]) * f, A[1] + (B[1] - A[1]) * f, A[2] + (B[2] - A[2]) * f];
  };
  function drawSight(beta) {
    const sky = STOPS[0], line = [255, 255, 255];
    const vr = 3.912 / beta;
    const d = out.data;
    for (let i = 0; i < W * Hh; i++) {
      const m = dist[i]; let c;
      if (Number.isNaN(m)) c = sky;
      else {
        c = ramp(Math.exp(-beta * m));
        const below = i + W < W * Hh ? dist[i + W] : NaN;
        if (!Number.isNaN(below) && (m - vr) * (below - vr) < 0 && (i % W) % 8 < 5) c = line; // visual-range line
      }
      d[i * 4] = c[0]; d[i * 4 + 1] = c[1]; d[i * 4 + 2] = c[2]; d[i * 4 + 3] = 255;
    }
    sctx.putImageData(out, 0, 0);
    for (const { el, r } of labelEls) {
      const pct = Math.exp(-beta * r.km * 1000) * 100;
      el.innerHTML = `${r.name.replace(" Ridge", "")} · ${r.miles} mi<span>${pct >= 1 ? Math.round(pct) : num(pct)}%</span>`;
    }
    $("vr-tag").textContent = `Visual range ${Math.round(vr / 1000)} km`;
  }

  const num = (v, d = 1) => { const [a, b] = v.toFixed(d).split("."); return b ? `${a}<span class="dp">.</span>${b}` : a; };
  const CAT = { "Good": "good", "Moderate": "moderate" };
  const catClass = (c) => CAT[c] || "bad";
  const fmtWhen = (t) => t.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "Etc/GMT+5" })
    .replace(",", "") + ", " + t.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Etc/GMT+5" });

  // ---------- timeline ----------
  const svg = $("tl"); const NS = "http://www.w3.org/2000/svg";
  const tMin = pts[0].t.getTime() - 6 * 3600e3, tMax = pts[pts.length - 1].t.getTime() + 30 * 3600e3;
  const yMax = Math.max(...pts.map((p) => Math.max(p.pred_pm25, p.monitor_pm25))) * 1.08;
  let idx = pts.findIndex((p) => p.file.includes("20161126_1200")); if (idx < 0) idx = 0;

  function el(tag, attrs, parent) { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); (parent || svg).appendChild(e); return e; }
  let geom;
  function drawTimeline() {
    svg.innerHTML = "";
    const w = svg.clientWidth, h = svg.clientHeight, pl = 34, pr = 92, pt = 14, pb = 24;
    const n = pts.length;
    const xi = (i) => pl + (i / (n - 1)) * (w - pl - pr);
    const x = (t) => xi(pts.findIndex((p) => p.t.getTime() === (t.getTime ? t.getTime() : t)));
    const y = (v) => h - pb - (v / yMax) * (h - pt - pb);
    geom = { x, xi, y, w, pl, pr };
    const ink3 = css("--ink-3"), rule = css("--rule"), accent = css("--accent"), ink2 = css("--ink-2");
    // category thresholds
    [[9, "Good", css("--strong")], [35.4, "Moderate", css("--promising")], [55.4, "Sensitive", css("--no")], [125.4, "Unhealthy", css("--no")]]
      .forEach(([v, name, col]) => {
        if (v > yMax) return;
        el("line", { x1: pl, x2: w - pr, y1: y(v), y2: y(v), stroke: rule, "stroke-dasharray": "3 4" });
        const tx = el("text", { x: w - pr + 6, y: y(v) + 4, fill: col, "font-size": 12, "font-weight": 500 }); tx.textContent = name;
      });
    // day ticks: one per day, at that day's first daytime hour
    const dayKey = (p) => p.timestamp.slice(0, 10);
    pts.forEach((p, i) => {
      if (i > 0 && dayKey(p) === dayKey(pts[i - 1])) return;
      el("line", { x1: xi(i), x2: xi(i), y1: h - pb, y2: h - pb + 4, stroke: css("--rule-strong") });
      if (i > 0) el("line", { x1: xi(i) - (xi(1) - xi(0)) / 2, x2: xi(i) - (xi(1) - xi(0)) / 2, y1: pt + 16, y2: h - pb, stroke: rule, "stroke-width": 1, opacity: 0.6 });
      const day = +p.timestamp.slice(8, 10);
      if (day % 2 === 0 || i === 0) {
        const tx = el("text", { x: xi(i) + 2, y: h - 6, fill: ink3, "font-size": 12 });
        tx.textContent = day + " Nov";
      }
    });
    [0, 50, 100, 150].filter((v) => v < yMax).forEach((v) => {
      const tx = el("text", { x: pl - 8, y: y(v) + 4, fill: ink3, "font-size": 12, "text-anchor": "end" }); tx.textContent = v;
    });
    // calibration split
    const firstTest = pts.findIndex((p) => p.split === "test");
    const sx = (xi(firstTest) + xi(firstTest - 1)) / 2;
    el("line", { x1: sx, x2: sx, y1: pt, y2: h - pb, stroke: css("--rule-strong") });
    const s1 = el("text", { x: sx - 8, y: pt + 10, fill: ink3, "font-size": 12, "text-anchor": "end" }); s1.textContent = "Calibration days";
    const s2 = el("text", { x: sx + 8, y: pt + 10, fill: accent, "font-size": 12, "font-weight": 600 }); s2.textContent = "Unseen days";
    // lines, broken at overnight gaps
    function series(key, color, width) {
      const dstr = pts.map((p, i) => (i ? "L" : "M") + xi(i) + " " + y(p[key])).join(" ");
      el("path", { d: dstr, fill: "none", stroke: color, "stroke-width": width, "stroke-linejoin": "round", "stroke-linecap": "round" });
    }
    series("monitor_pm25", ink2, 1.6);
    series("pred_pm25", accent, 2.2);
    // labels on the marks, at the 8 Nov smoke peak
    const peak = pts.reduce((a, b) => (b.monitor_pm25 > a.monitor_pm25 ? b : a));
    const pi = pts.indexOf(peak);
    const lm = el("text", { x: xi(pi) + 8, y: y(peak.monitor_pm25) + 4, fill: ink2, "font-size": 12, "font-weight": 600 }); lm.textContent = "Monitor";
    const lc = el("text", { x: xi(pi) + 10, y: y(peak.pred_pm25) + 18, fill: accent, "font-size": 12, "font-weight": 600 }); lc.textContent = "Camera";
    // cursor
    geom.cursor = el("line", { y1: pt, y2: h - pb, stroke: css("--ink"), "stroke-width": 1 });
    geom.dotM = el("circle", { r: 4.5, fill: ink2, stroke: css("--surface"), "stroke-width": 2 });
    geom.dotC = el("circle", { r: 4.5, fill: accent, stroke: css("--surface"), "stroke-width": 2 });
    moveCursor();
  }
  function moveCursor() {
    if (!geom) return;
    const p = pts[idx], cx = geom.xi(idx);
    geom.cursor.setAttribute("x1", cx); geom.cursor.setAttribute("x2", cx);
    geom.dotM.setAttribute("cx", cx); geom.dotM.setAttribute("cy", geom.y(p.monitor_pm25));
    geom.dotC.setAttribute("cx", cx); geom.dotC.setAttribute("cy", geom.y(p.pred_pm25));
    svg.setAttribute("aria-valuetext", fmtWhen(p.t));
  }
  function pick(evt) {
    const r = svg.getBoundingClientRect(); const px = evt.clientX - r.left;
    let best = 0, bd = Infinity;
    pts.forEach((p, i) => { const d = Math.abs(geom.xi(i) - px); if (d < bd) { bd = d; best = i; } });
    show(best);
  }
  let dragging = false;
  svg.addEventListener("pointerdown", (e) => { dragging = true; svg.setPointerCapture(e.pointerId); pick(e); stop(); });
  svg.addEventListener("pointermove", (e) => { if (dragging) pick(e); });
  svg.addEventListener("pointerup", () => { dragging = false; });
  svg.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight") { show(Math.min(idx + 1, pts.length - 1)); e.preventDefault(); }
    if (e.key === "ArrowLeft") { show(Math.max(idx - 1, 0)); e.preventDefault(); }
  });

  // ---------- show one hour ----------
  const photo = $("photo");
  function show(i) {
    idx = i; const p = pts[i];
    photo.src = "frames/" + p.file;
    const beta0 = p.cam_beta * 1e-6;

    [i + 1, i + 2].forEach((k) => { if (pts[k]) { const im = new Image(); im.src = "frames/" + pts[k].file; } });
    const beta = p.cam_beta * 1e-6;
    drawSight(beta);
    $("when").textContent = fmtWhen(p.t);
    const sp = $("split"); sp.textContent = p.split === "test" ? "Unseen day" : "Calibration day"; sp.className = "split" + (p.split === "test" ? " test" : "");
    $("cam").innerHTML = num(p.pred_pm25) + '<span class="unit">µg/m³</span>';
    $("mon").innerHTML = num(p.monitor_pm25) + '<span class="unit">µg/m³</span>';
    const cc = $("cam-cat"); cc.textContent = p.category; cc.className = "cat " + catClass(p.category);
    const mc = $("mon-cat"); mc.textContent = p.monitor_category; mc.className = "cat " + catClass(p.monitor_category);
    $("vis").innerHTML = Math.round(3.912 / beta / 1000) + '<span class="unit">km</span>';
    $("vis-site").textContent = p.site_beta ? `Park instrument: ${Math.round(3912 / p.site_beta)} km` : "Park instrument: no reading";
    moveCursor();
  }

  // ---------- play ----------
  let timer = null;
  const PLAY = '<polygon points="6 3 20 12 6 21 6 3"/>', PAUSE = '<rect x="14" y="4" width="4" height="16" rx="1"/><rect x="6" y="4" width="4" height="16" rx="1"/>';
  function stop() { clearInterval(timer); timer = null; $("play-ic").innerHTML = PLAY; $("play-tx").textContent = "Play"; }
  $("play").addEventListener("click", () => {
    if (timer) return stop();
    $("play-ic").innerHTML = PAUSE; $("play-tx").textContent = "Pause";
    timer = setInterval(() => show((idx + 1) % pts.length), 700);
  });
  $("prev").addEventListener("click", () => { stop(); show(Math.max(idx - 1, 0)); });
  $("next").addEventListener("click", () => { stop(); show(Math.min(idx + 1, pts.length - 1)); });



  // ---------- Arkansas map ----------
  {
    const M = await fetch("data/arkansas_map.json").then((r) => r.json());
    const svg = $("ark-map"), lons = M.outline.map((p) => p[0]), lats = M.outline.map((p) => p[1]);
    const k = Math.cos((35 * Math.PI) / 180), pad = 40, Wm = 900, Hm = 560;
    const x0 = Math.min(...lons), x1 = Math.max(...lons), y0 = Math.min(...lats), y1 = Math.max(...lats);
    const sc = Math.min((Wm - 2 * pad) / ((x1 - x0) * k), (Hm - 2 * pad) / (y1 - y0));
    const ox = (Wm - (x1 - x0) * k * sc) / 2, oy = (Hm - (y1 - y0) * sc) / 2;
    const P = (lon, lat) => [ox + (lon - x0) * k * sc, oy + (y1 - lat) * sc];
    const mk = (tag, at, txt) => { const e = document.createElementNS(NS, tag); for (const a in at) e.setAttribute(a, at[a]); if (txt) e.textContent = txt; svg.appendChild(e); return e; };
    const draw = () => {
      svg.innerHTML = "";
      mk("path", { d: "M" + M.outline.map((p) => P(...p).join(" ")).join(" L") + " Z", fill: css("--sunken"), stroke: css("--rule-strong"), "stroke-width": 1.2 });
      const tun = M.cameras.find((c) => c.key === "tunnel"), spr = M.monitors[0];
      const [ax, ay] = P(tun.lon, tun.lat), [bx, by] = P(spr.lon, spr.lat);
      mk("line", { x1: ax, y1: ay, x2: bx, y2: by, stroke: css("--accent"), "stroke-width": 2, "stroke-dasharray": "5 5" });
      mk("text", { x: (ax + bx) / 2 + 12, y: (ay + by) / 2 + 2, fill: css("--accent"), "font-size": 16, "font-weight": 650 }, `${Math.round(spr.km_from_tunnel)} km`);
      for (const m of M.monitors) {
        const [x, y] = P(m.lon, m.lat);
        mk("circle", { cx: x, cy: y, r: 5.5, fill: css("--ink-2"), stroke: css("--surface"), "stroke-width": 2 });
        const right = m.lon < -91.4 && m.name !== "Little Rock";
        const dy = m.name === "Little Rock" ? 14 : m.name === "North Little Rock" ? -4 : 4;
        mk("text", { x: x + (right ? 10 : -10), y: y + dy, fill: css("--ink-2"), "font-size": 13, "font-weight": 500, "text-anchor": right ? "start" : "end" }, m.name);
      }
      for (const c of M.cameras) {
        const [x, y] = P(c.lon, c.lat);
        mk("circle", { cx: x, cy: y, r: 8, fill: css("--sky"), stroke: css("--surface"), "stroke-width": 2.5 });
        const t = c.key === "tunnel" ? { x: x - 4, y: y + 30, a: "start" } : { x: x + 14, y: y + 5, a: "start" };
        mk("text", { x: t.x, y: t.y, fill: css("--ink"), "font-size": 14, "font-weight": 650, "text-anchor": t.a }, c.name.split(",")[0] + " camera");
      }
      mk("text", { x: Wm - 16, y: 30, fill: css("--ink-3"), "font-size": 13, "text-anchor": "end" }, `${M.monitors.length} PM2.5 monitors in the state`);
    };
    draw();
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", draw);
    $("theme").addEventListener("click", () => setTimeout(draw, 0));
  }
  // ---------- Arkansas viewer: predictions only, no ground truth ----------
  const ARK = await Promise.all(["tunnel", "edwards"].map((c) =>
    fetch(`arkansas/${c}/series.json`).then((r) => r.json()).then(async (m) => {
      const im = new Image(); im.src = `arkansas/${c}/distance.png`; await im.decode();
      const [w, hgt] = m.size; const cv = document.createElement("canvas"); cv.width = w; cv.height = hgt;
      const cx = cv.getContext("2d"); cx.drawImage(im, 0, 0); const px = cx.getImageData(0, 0, w, hgt).data;
      const e = m.distance_encoding, dd = new Float32Array(w * hgt);
      for (let i = 0; i < w * hgt; i++) { const v = px[i * 4]; dd[i] = v === 0 ? NaN : Math.pow(10, e.log10_min + ((v - 1) / 254) * (e.log10_max - e.log10_min)); }
      return { key: c, m, dist: dd };
    })));
  let cam = 0, fi = 0;
  const aCanvas = $("ark-sight"), aCtx = aCanvas.getContext("2d");
  const segHost = $("ark-cams");
  ARK.forEach((A, k) => {
    const b = document.createElement("button"); b.textContent = A.m.short; b.setAttribute("aria-pressed", k === 0);
    b.addEventListener("click", () => { cam = k; { const S = ARK[k].m.series; const li = [...S.keys()].reverse().find((i) => S[i].status === "reading"); fi = li ?? 0; } [...segHost.children].forEach((x, i) => x.setAttribute("aria-pressed", i === k)); arkShow(); });
    segHost.appendChild(b);
  });
  const fmtTaken = (s) => s ? new Date(s).toLocaleString("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "America/Chicago" }).replace(",", "") + " CST" : "Saved frame, time not recorded";

  function arkSight(A, beta) {
    const [w, hgt] = A.m.size; aCanvas.width = w; aCanvas.height = hgt;
    const img = aCtx.createImageData(w, hgt), d = img.data, vr = 3.912 / beta;
    for (let i = 0; i < w * hgt; i++) {
      const m = A.dist[i]; let c;
      if (Number.isNaN(m)) c = STOPS[0];
      else {
        c = ramp(Math.exp(-beta * m));
        const below = i + w < w * hgt ? A.dist[i + w] : NaN;
        if (!Number.isNaN(below) && (m - vr) * (below - vr) < 0 && (i % w) % 8 < 5) c = [255, 255, 255];
      }
      d[i * 4] = c[0]; d[i * 4 + 1] = c[1]; d[i * 4 + 2] = c[2]; d[i * 4 + 3] = 255;
    }
    aCtx.putImageData(img, 0, 0);
  }

  function arkTimeline() {
    const svg = $("ark-tl"); svg.innerHTML = "";
    const A = ARK[cam], S = A.m.series, n = S.length;
    const w = svg.clientWidth, hgt = svg.clientHeight, pl = 34, pr = 92, pt = 14, pb = 26;
    const xi = (i) => n === 1 ? (pl + w - pr) / 2 : pl + 30 + (i / (n - 1)) * (w - pl - pr - 60);
    const yMax = Math.max(12, ...S.map((e) => e.pm25 || 0)) * 1.25;
    const y = (v) => hgt - pb - (v / yMax) * (hgt - pt - pb);
    const mk = (tag, at) => { const e = document.createElementNS(NS, tag); for (const k in at) e.setAttribute(k, at[k]); svg.appendChild(e); return e; };
    [[9, "Good", css("--strong")], [35.4, "Moderate", css("--promising")], [55.4, "Sensitive", css("--no")]].forEach(([v, nm, col]) => {
      if (v > yMax) return;
      mk("line", { x1: pl, x2: w - pr, y1: y(v), y2: y(v), stroke: css("--rule"), "stroke-dasharray": "3 4" });
      mk("text", { x: w - pr + 6, y: y(v) + 4, fill: col, "font-size": 12, "font-weight": 500 }).textContent = nm;
    });
    [0, Math.round(yMax / 2)].forEach((v) => { mk("text", { x: pl - 8, y: y(v) + 4, fill: css("--ink-3"), "font-size": 12, "text-anchor": "end" }).textContent = v; });
    const good = S.map((e, i) => [e, i]).filter(([e]) => e.status === "reading");
    if (good.length > 1) mk("path", { d: good.map(([e, i], k) => (k ? "L" : "M") + xi(i) + " " + y(e.pm25)).join(" "), fill: "none", stroke: css("--accent"), "stroke-width": 2.2 });
    S.forEach((e, i) => {
      const t = e.taken ? new Date(e.taken).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "America/Chicago" }) : "Saved frame";
      mk("text", { x: xi(i), y: hgt - 6, fill: css("--ink-3"), "font-size": 12, "text-anchor": "middle" }).textContent = t;
      if (e.status === "reading") mk("circle", { cx: xi(i), cy: y(e.pm25), r: i === fi ? 6 : 4.5, fill: css("--accent"), stroke: css("--surface"), "stroke-width": 2 });
      else {
        mk("circle", { cx: xi(i), cy: y(0), r: i === fi ? 6 : 4.5, fill: css("--surface"), stroke: css("--weak"), "stroke-width": 1.6 });
        mk("text", { x: xi(i), y: y(0) - 12, fill: css("--weak"), "font-size": 12, "font-weight": 500, "text-anchor": "middle" }).textContent = "No reading";
      }
      if (i === fi) mk("line", { x1: xi(i), x2: xi(i), y1: pt, y2: hgt - pb, stroke: css("--ink"), "stroke-width": 1, opacity: 0.35 });
    });
    svg.onclick = (ev) => { const r = svg.getBoundingClientRect(); let best = 0, bd = 1e9; S.forEach((_, i) => { const d = Math.abs(xi(i) - (ev.clientX - r.left)); if (d < bd) { bd = d; best = i; } }); fi = best; arkShow(); };
    svg.onkeydown = (ev) => { if (ev.key === "ArrowRight") { fi = Math.min(fi + 1, n - 1); arkShow(); } if (ev.key === "ArrowLeft") { fi = Math.max(fi - 1, 0); arkShow(); } };
    const nr = S.filter((e) => e.status === "reading").length;
    $("ark-hint").textContent = `${n} frame${n === 1 ? "" : "s"} saved so far · ${nr} with a reading. Click a point to see that frame.`;
  }

  function arkShow() {
    const A = ARK[cam], m = A.m, e = m.series[fi];
    $("ark-photo").src = `arkansas/${A.key}/${e.file}`;
    $("ark-cap1").innerHTML = `<b>Camera frame</b> · ARDOT, ${m.camera.replace(/^ARDOT /, "")}`;
    $("ark-when").textContent = fmtTaken(e.taken);
    const reading = e.status === "reading";
    const dimg = $("ark-depth");
    if (reading) { dimg.hidden = true; aCanvas.hidden = false; arkSight(A, e.extinction_Mm * 1e-6); $("ark-tag").textContent = `Visual range ${Math.round(e.visual_range_km)} km`; }
    else { aCanvas.hidden = true; dimg.hidden = false; dimg.src = `arkansas/${A.key}/depth.jpg`; $("ark-tag").textContent = "No reading · distance only"; }
    $("ark-cap2").innerHTML = reading ? "<b>How far the camera can see</b> · predicted share of each ridge's light that gets through"
      : `<b>Distance from DA3</b> · bands at ${m.bands_km.map((k) => (k < 1 ? k.toFixed(1) : Math.round(k))).join(", ")} km, scaled by terrain ridges`;
    const pmEl = $("ark-pm"), catEl = $("ark-cat");
    if (reading) { pmEl.className = "big"; pmEl.innerHTML = num(e.pm25) + '<span class="unit">µg/m³</span>'; catEl.textContent = e.category; catEl.className = "cat " + catClass(e.category); }
    else { pmEl.className = "big none"; pmEl.textContent = "No reading"; catEl.textContent = "Declined by the model"; catEl.className = "cat weak"; }
    $("ark-vis").innerHTML = reading && e.visual_range_km ? Math.round(e.visual_range_km) + '<span class="unit">km</span>' : "—";
    $("ark-vis-note").textContent = reading ? "From the haze fit" : "Not estimated";
    $("ark-rh").innerHTML = Math.round(e.rh) + '<span class="unit">%</span>';
    $("ark-rh-src").textContent = e.rh_source;
    const why = $("ark-why");
    if (!reading) {
      const forced = e.pm25 != null ? ` If forced: <b>${e.category}, ${Math.round(e.pm25_range[0])}–${Math.round(e.pm25_range[1])} µg/m³</b>, not trusted.` : "";
      why.innerHTML = `<b>Why no reading:</b> ${e.reasons.join("; ")}.${forced} Nearest PM2.5 monitor: ${m.nearest_monitor.replace(/ \(.*\)/, "")}.`;
      why.hidden = false;
    } else { why.hidden = true; }
    arkTimeline();
    renderNow();
  }
  // latest reading per location
  const nowHost = $("ark-now");
  function renderNow() {
    nowHost.innerHTML = "";
    ARK.forEach((A, k) => {
      const S = A.m.series, li = [...S.keys()].reverse().find((i) => S[i].status === "reading");
      const e = li != null ? S[li] : S[S.length - 1];
      const row = document.createElement("div"); row.className = "now-row"; row.setAttribute("aria-current", k === cam);
      const val = li != null
        ? `<div><div class="val">${num(e.pm25)}<span class="unit">µg/m³</span></div><div class="cat ${catClass(e.category)}">${e.category}</div></div>`
        : `<div><div class="val none">No reading</div></div>`;
      row.innerHTML = `<img class="thumb" src="arkansas/${A.key}/${e.file}" alt="${A.m.short} camera frame">
        <div class="nm">${A.m.short}<small>${fmtTaken(e.taken)}</small></div>
        <div class="loc">${A.m.lat.toFixed(4)}, ${A.m.lon.toFixed(4)}<br>${A.m.elevation_ft.toLocaleString()} ft</div>
        ${val}
        <div class="rng">${li != null ? `Range ${Math.round(e.pm25_range[0])}–${Math.round(e.pm25_range[1])} µg/m³<br>Visibility ${Math.round(e.visual_range_km)} km` : ""}</div>`;
      row.addEventListener("click", () => { cam = k; fi = li != null ? li : 0; [...segHost.children].forEach((x, i) => x.setAttribute("aria-pressed", i === k)); arkShow(); });
      nowHost.appendChild(row);
    });
  }
  $("ark-prev").addEventListener("click", () => { fi = Math.max(fi - 1, 0); arkShow(); });
  $("ark-next").addEventListener("click", () => { fi = Math.min(fi + 1, ARK[cam].m.series.length - 1); arkShow(); });
  new ResizeObserver(() => arkTimeline()).observe($("ark-tl"));
  { const S = ARK[0].m.series; const li = [...S.keys()].reverse().find((i) => S[i].status === "reading"); fi = li ?? 0; }
  arkShow();

  function redraw() { drawTimeline(); show(idx); if (typeof arkShow === 'function') arkShow(); }
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", redraw);
  new ResizeObserver(() => drawTimeline()).observe(svg);
  redraw();
})();
