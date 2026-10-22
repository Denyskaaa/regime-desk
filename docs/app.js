(() => {
  "use strict";

  const S = { win: "1M", period: "m1", tab: "overview", data: null, built: null };
  const QKEYS = ["growth", "riskon", "riskoff", "value"];
  const QNAME = { growth: "Growth", riskon: "Risk ON", riskoff: "Risk OFF", value: "Value", quality: "Quality" };
  const PERIODS = [["d1", "1D"], ["w1", "1W"], ["m1", "1M"], ["m3", "3M"], ["ytd", "YTD"], ["y1", "1Y"]];
  const MINUS = "−";
  const $ = (s, el = document) => el.querySelector(s);

  // ------------------------------------------------------------ format ---
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const ok = (v) => v !== null && v !== undefined && isFinite(v);
  const fixed = (v, dp) => Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: dp, maximumFractionDigits: dp });
  function num(v, dp = 2) {
    if (!ok(v)) return "–";
    const s = fixed(v, dp);
    return (v < 0 && Number(s.replace(/,/g, "")) !== 0 ? MINUS : "") + s;
  }
  function signed(v, dp = 1, unit = "") {
    if (!ok(v)) return "–";
    const s = fixed(v, dp);
    if (Number(s.replace(/,/g, "")) === 0) return s + unit;
    return (v > 0 ? "+" : MINUS) + s + unit;
  }
  const dir = (v) => (!ok(v) || v === 0 ? "flat" : v > 0 ? "up" : "down");
  function goodCls(v, good, dp = 2) {
    if (!ok(v) || Number(v.toFixed(dp)) === 0 || !good) return "flat";
    return (v > 0) === (good === "up") ? "up" : "down";
  }
  function priceDp(t, v) {
    if (/=X$/.test(t)) return Math.abs(v) >= 20 ? 2 : 4;
    const a = Math.abs(v);
    return a >= 10000 ? 0 : a >= 10 ? 2 : 3;
  }
  const md = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  function fmtDate(d, withYear) {
    if (!d) return "";
    const [y, m, day] = d.split("-").map(Number);
    const yr = withYear || y !== new Date().getFullYear() ? `, ${y}` : "";
    return `${MON[m - 1]} ${day}${yr}`;
  }
  function ago(iso) {
    const min = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
    if (min < 1) return "just now";
    if (min < 60) return `${min} min ago`;
    const h = Math.round(min / 60);
    if (h < 48) return `${h} h ago`;
    return `${Math.round(h / 24)} days ago`;
  }

  // ------------------------------------------------------------ charts ---
  function spark(vals, w = 112, h = 28, color) {
    const v = (vals || []).filter(ok);
    if (v.length < 2) return "";
    const lo = Math.min(...v), hi = Math.max(...v), rng = hi - lo || 1;
    const pts = v.map((y, i) => [(i / (v.length - 1)) * (w - 4) + 2, h - 3 - ((y - lo) / rng) * (h - 6)]);
    const c = color || `var(--${dir(v[v.length - 1] - v[0])})`;
    const line = pts.map((p) => p.map((n) => n.toFixed(1)).join(",")).join(" ");
    const area = `2,${h} ${line} ${(w - 2).toFixed(1)},${h}`;
    const [ex, ey] = pts[pts.length - 1];
    return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true" preserveAspectRatio="none">
      <polygon points="${area}" fill="${c}" fill-opacity=".09"/>
      <polyline points="${line}" fill="none" stroke="${c}" stroke-width="1.5" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>
      <circle cx="${ex.toFixed(1)}" cy="${ey.toFixed(1)}" r="2.4" fill="${c}"/></svg>`;
  }

  function niceTicks(lo, hi, n = 4) {
    const span = hi - lo || 1;
    const step0 = span / n, mag = Math.pow(10, Math.floor(Math.log10(step0)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= n) || 10 * mag;
    const out = [];
    for (let t = Math.ceil(lo / step) * step; t <= hi + 1e-9; t += step) out.push(+t.toFixed(10));
    return out;
  }

  function lineChart(el, pts, opts) {
    const W = Math.max(280, Math.round(el.clientWidth || 800)), H = 190, pl = 46, pr = 14, pt = 10, pb = 24;
    const t = pts.map((p) => Date.parse(p[0])), y = pts.map((p) => p[1]);
    let lo = Math.min(...y), hi = Math.max(...y);
    const pad = (hi - lo) * 0.08 || 1; lo -= pad; hi += pad;
    const t0 = t[0], t1 = t[t.length - 1];
    const X = (v) => pl + ((v - t0) / (t1 - t0 || 1)) * (W - pl - pr);
    const Y = (v) => pt + (1 - (v - lo) / (hi - lo)) * (H - pt - pb);
    let g = "";
    for (const tk of niceTicks(lo, hi)) {
      g += `<line x1="${pl}" x2="${W - pr}" y1="${Y(tk)}" y2="${Y(tk)}" stroke="var(--line)" stroke-width="1"/>`;
      g += `<text x="${pl - 6}" y="${Y(tk) + 4}" text-anchor="end" font-size="11" font-family="var(--f-mono)" fill="var(--ink-3)">${num(tk, Math.abs(tk) < 10 && tk % 1 ? 1 : 0)}</text>`;
    }
    if (lo < 0 && hi > 0) g += `<line x1="${pl}" x2="${W - pr}" y1="${Y(0)}" y2="${Y(0)}" stroke="var(--ink-3)" stroke-width="1"/>`;
    const y0 = new Date(t0).getUTCFullYear(), y1 = new Date(t1).getUTCFullYear();
    for (let yr = y0 + 1; yr <= y1; yr++) {
      const x = X(Date.UTC(yr, 0, 1));
      g += `<line x1="${x}" x2="${x}" y1="${pt}" y2="${H - pb}" stroke="var(--line)" stroke-dasharray="2 3"/>`;
      g += `<text x="${x + 4}" y="${H - 7}" font-size="11" font-family="var(--f-mono)" fill="var(--ink-3)">${yr}</text>`;
    }
    const d = pts.map((p, i) => `${i ? "L" : "M"}${X(t[i]).toFixed(1)},${Y(y[i]).toFixed(1)}`).join("");
    const col = opts.color || "var(--q-value)";
    g += `<path d="${d}L${X(t1).toFixed(1)},${H - pb}L${X(t0).toFixed(1)},${H - pb}Z" fill="${col}" fill-opacity=".07"/>`;
    g += `<path d="${d}" fill="none" stroke="${col}" stroke-width="2" stroke-linejoin="round"/>`;
    g += `<circle cx="${X(t1)}" cy="${Y(y[y.length - 1])}" r="3.5" fill="${col}"/>`;
    g += `<g class="hover" visibility="hidden"><line y1="${pt}" y2="${H - pb}" stroke="var(--ink-2)" stroke-width="1"/><circle r="4" fill="var(--surface)" stroke="${col}" stroke-width="2"/></g>`;
    g += `<rect x="${pl}" y="${pt}" width="${W - pl - pr}" height="${H - pt - pb}" fill="transparent"/>`;
    el.innerHTML = `<div class="chart-read"></div><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(opts.label)} history">${g}</svg>`;
    const svg = $("svg", el), hov = $(".hover", svg), read = $(".chart-read", el);
    const last = pts[pts.length - 1];
    const show = (i) => (read.textContent = `${fmtDate(pts[i][0], true)}: ${num(pts[i][1], opts.dp)} ${opts.unit}`);
    show(pts.length - 1);
    svg.addEventListener("pointermove", (e) => {
      const r = svg.getBoundingClientRect();
      const x = ((e.clientX - r.left) / r.width) * W;
      const tv = t0 + ((x - pl) / (W - pl - pr)) * (t1 - t0);
      let i = 0, best = Infinity;
      t.forEach((tt, k) => { const dd = Math.abs(tt - tv); if (dd < best) { best = dd; i = k; } });
      hov.setAttribute("visibility", "visible");
      $("line", hov).setAttribute("x1", X(t[i])); $("line", hov).setAttribute("x2", X(t[i]));
      $("circle", hov).setAttribute("cx", X(t[i])); $("circle", hov).setAttribute("cy", Y(y[i]));
      show(i);
    });
    svg.addEventListener("pointerleave", () => { hov.setAttribute("visibility", "hidden"); show(pts.length - 1); });
    return last;
  }

  // ------------------------------------------------------- regime map ---
  const CURVES = { // [old short, old long, new short, new long] yields for the little curve icons
    growth: [2.0, 3.0, 1.7, 2.3], riskon: [2.0, 3.0, 1.0, 2.6],
    riskoff: [2.0, 3.0, 2.9, 3.3], value: [2.0, 3.0, 2.2, 3.9],
  };
  function curveIcon(k, x, y) {
    const w = 58, h = 34, [os, ol, ns, nl] = CURVES[k];
    const Yv = (v) => y + h - 4 - ((v - 0.8) / 3.3) * (h - 8);
    const path = (s, l) => {
      let d = "";
      for (let i = 0; i <= 12; i++) {
        const tt = i / 12, v = s + (l - s) * Math.sqrt(tt);
        d += `${i ? "L" : "M"}${(x + 6 + tt * (w - 10)).toFixed(1)},${Yv(v).toFixed(1)}`;
      }
      return d;
    };
    return `<g aria-hidden="true">
      <path d="M${x + 4},${y} V${y + h} H${x + w}" fill="none" stroke="var(--ink-3)" stroke-width="1.2"/>
      <path d="${path(os, ol)}" fill="none" stroke="var(--ink-3)" stroke-width="1.4" stroke-dasharray="3 2"/>
      <path d="${path(ns, nl)}" fill="none" stroke="var(--q-${k})" stroke-width="2.2"/></g>`;
  }

  function tapeSVG(k, label, x, y, anchor) {
    const w = label.length * 9.4 + 18, hh = 25;
    const rx = anchor === "end" ? x - w : x;
    return `<g><rect x="${rx}" y="${y}" width="${w}" height="${hh}" rx="2.5" fill="var(--tape-bg)"/>
      <text x="${rx + w / 2}" y="${y + 17.5}" text-anchor="middle" font-family="var(--f-display)" font-weight="800"
        font-size="15" style="font-stretch:112%" fill="var(--qb-${k})">${label}</text></g>`;
  }

  function mapSVG(reg, W) {
    const C = 260, H = 206, K = 0.9;
    const P = (x, y) => [C + x * H * K, C - y * H * K];
    const lead = W.assets.leader, curveQ = W.curve && W.curve.clear ? W.curve.quad : null;
    let g = "";
    const corners = { growth: [-1, 1], riskon: [1, 1], riskoff: [-1, -1], value: [1, -1] };
    for (const k of QKEYS) {
      const [sx, sy] = corners[k];
      g += `<rect x="${sx < 0 ? C - H : C}" y="${sy > 0 ? C - H : C}" width="${H}" height="${H}" fill="var(--q-${k})" fill-opacity="${k === lead ? 0.14 : 0.05}"/>`;
    }
    g += `<rect x="${C - H}" y="${C - H}" width="${2 * H}" height="${2 * H}" fill="none" stroke="var(--line)"/>`;
    // ticks in basis points
    const sc = W.scale || { x: 30, y: 30 };
    for (const f of [-1, -0.5, 0.5, 1]) {
      const [tx] = P(f, 0), [, ty] = P(0, f);
      g += `<line x1="${tx}" x2="${tx}" y1="${C - 4}" y2="${C + 4}" stroke="var(--ink-2)"/>`;
      g += `<line y1="${ty}" y2="${ty}" x1="${C - 4}" x2="${C + 4}" stroke="var(--ink-2)"/>`;
      if (Math.abs(f) === 1) {
        g += `<text x="${tx}" y="${C + 16}" text-anchor="middle" font-size="10" font-family="var(--f-mono)" fill="var(--ink-3)">${signed(f * sc.x, 0)}bp</text>`;
        g += `<text x="${C + 7}" y="${ty + 3.5}" font-size="10" font-family="var(--f-mono)" fill="var(--ink-3)">${signed(-f * sc.y, 0)}bp</text>`;
      }
    }
    // axes with arrowheads
    g += `<defs><marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="var(--ink)"/></marker></defs>`;
    g += `<line x1="${C - H + 2}" y1="${C}" x2="${C + H - 2}" y2="${C}" stroke="var(--ink)" stroke-width="1.6" marker-start="url(#ah)" marker-end="url(#ah)"/>`;
    g += `<line x1="${C}" y1="${C + H - 2}" x2="${C}" y2="${C - H + 2}" stroke="var(--ink)" stroke-width="1.6" marker-start="url(#ah)" marker-end="url(#ah)"/>`;
    // axis labels outside the plot
    const lab = (x, y, txt, rot, col) => `<text x="${x}" y="${y}" text-anchor="middle" font-family="var(--f-display)" font-weight="800" font-size="11.5" letter-spacing="1.2" style="font-stretch:112%" fill="${col}" ${rot ? `transform="rotate(${rot} ${x} ${y})"` : ""}>${txt}</text>`;
    g += lab(C, C - H - 14, "EASIER FED  +", 0, "var(--up)");
    g += lab(C, C + H + 24, "TIGHTER FED  −", 0, "var(--down)");
    g += lab(C - H - 16, C, "−  WEAKER MACRO", -90, "var(--down)");
    g += lab(C + H + 16, C, "STRONGER MACRO  +", 90, "var(--up)");
    // quality center
    const [qx0, qy0] = P(-0.2, 0.2), [qx1, qy1] = P(0.2, -0.2);
    g += `<rect x="${qx0}" y="${qy0}" width="${qx1 - qx0}" height="${qy1 - qy0}" fill="var(--q-quality)" fill-opacity=".06" stroke="var(--q-quality)" stroke-dasharray="4 3" rx="3"/>`;
    g += `<text x="${C}" y="${qy0 - 5}" text-anchor="middle" font-family="var(--f-display)" font-weight="800" font-size="10" letter-spacing="1" fill="var(--q-quality)">QUALITY</text>`;
    // tapes and curve icons
    const L = C - H + 10, R = C + H - 10, T = C - H + 10, B = C + H - 10;
    g += tapeSVG("growth", "Growth", L, T) + curveIcon("growth", L, T + 32);
    g += tapeSVG("riskon", "Risk ON", R, T, "end") + curveIcon("riskon", R - 58, T + 32);
    g += tapeSVG("riskoff", "Risk OFF", L, B - 25) + curveIcon("riskoff", L, B - 25 - 40);
    g += tapeSVG("value", "Value", R, B - 25, "end") + curveIcon("value", R - 58, B - 25 - 40);
    const cap = (x, y, txt, anchor) => `<text x="${x}" y="${y}" text-anchor="${anchor}" font-size="10" font-family="var(--f-mono)" fill="var(--ink-3)">${txt}</text>`;
    g += cap(L + 62, T + 52, "bull flattener", "start") + cap(R - 62, T + 52, "bull steepener", "end");
    g += cap(L + 62, B - 44, "bear flattener", "start") + cap(R - 62, B - 44, "bear steepener", "end");

    // trails (last 13 weeks)
    const tr = (W.trail || []).slice(-13);
    const cpts = tr.filter((p) => ok(p.cx)).map((p) => [P(p.cx, p.cy), p]);
    const apts = tr.map((p) => [P(p.ax, p.ay), p]);
    if (apts.length > 1) g += `<polyline points="${apts.map(([q]) => q.join(",")).join(" ")}" fill="none" stroke="var(--ink-2)" stroke-opacity=".45" stroke-dasharray="3 3"/>`;
    if (cpts.length > 1) g += `<polyline points="${cpts.map(([q]) => q.join(",")).join(" ")}" fill="none" stroke="var(--ink)" stroke-opacity=".35" stroke-width="1.4"/>`;
    apts.slice(0, -1).forEach(([[x, y], p], i) => {
      const o = (0.2 + (0.6 * i) / apts.length).toFixed(2);
      g += `<rect x="${x - 3}" y="${y - 3}" width="6" height="6" transform="rotate(45 ${x} ${y})" fill="var(--surface)" stroke="var(--ink-2)" stroke-opacity="${o}"><title>Assets, week of ${fmtDate(p.date)}: ${QNAME[p.asset_quad]}</title></rect>`;
    });
    cpts.slice(0, -1).forEach(([[x, y], p], i) => {
      const o = (0.18 + (0.6 * i) / cpts.length).toFixed(2);
      g += `<circle cx="${x}" cy="${y}" r="3.2" fill="var(--ink)" fill-opacity="${o}"><title>Curve, week of ${fmtDate(p.date)}</title></circle>`;
    });
    // current positions
    const [axx, ayy] = P(W.assets.x, W.assets.y);
    g += `<rect x="${axx - 7}" y="${ayy - 7}" width="14" height="14" transform="rotate(45 ${axx} ${ayy})" fill="var(--surface)" stroke="var(--ink)" stroke-width="2.4"><title>Cross-asset checklist: ${QNAME[lead]}</title></rect>`;
    let cxx = null, cyy = null;
    if (W.curve) {
      [cxx, cyy] = P(W.curve.x, W.curve.y);
      g += `<circle cx="${cxx}" cy="${cyy}" r="8" fill="var(--ink)" stroke="var(--surface)" stroke-width="2.5"><title>Yield curve: ${esc(W.curve.name)}</title></circle>`;
    }
    const near = cxx !== null && Math.hypot(cxx - axx, cyy - ayy) < 34;
    const tag = (x, y, txt, dy) => {
      const right = x < C + H - 70;
      return `<text x="${x + (right ? 13 : -13)}" y="${y + dy}" text-anchor="${right ? "start" : "end"}" font-family="var(--f-display)" font-weight="700" font-size="12.5" fill="var(--ink)" paint-order="stroke" stroke="var(--surface)" stroke-width="4" stroke-linejoin="round">${txt}</text>`;
    };
    if (cxx !== null) g += tag(cxx, cyy, "Curve", near ? -10 : 4);
    g += tag(axx, ayy, "Assets", near ? 16 : 4);
    const aria = `Regime map. Assets point to ${QNAME[lead]}${curveQ ? `; the yield curve points to ${QNAME[curveQ]}` : ""}.`;
    return `<svg viewBox="0 0 520 520" role="img" aria-label="${esc(aria)}">${g}</svg>`;
  }

  // --------------------------------------------------------- overview ---
  function segWin() {
    return `<div class="seg" role="group" aria-label="Look-back window">${["1M", "3M"].map((w) =>
      `<button type="button" data-win="${w}" aria-pressed="${S.win === w}">${w === "1M" ? "1 month" : "3 months"}</button>`).join("")}</div>`;
  }

  function scoreRows(W) {
    const qs = [...W.quadrants].sort((a, b) => b.net - a.net || b.match - a.match);
    const row = (q, isLead) => {
      const n = q.n || 1, pct = (v) => ((v / n) * 100).toFixed(1);
      return `<div class="score${isLead ? " lead" : ""}"><span class="tape t-${q.key}">${q.name}</span>
        <div class="bar" role="img" aria-label="${q.match} of ${q.n} confirm, ${q.against} against">
          <i style="width:${pct(q.match)}%;background:var(--q-${q.key})"></i><i class="n" style="width:${pct(q.neutral)}%"></i>
          <i style="width:${pct(q.against)}%;background:repeating-linear-gradient(135deg,var(--ink-3) 0 2px,transparent 2px 5px)"></i></div>
        <span class="cnt" title="${q.match} confirm, ${q.against} against">${q.match}/${q.n} ✓ ${q.against} ✗</span></div>`;
    };
    return qs.map((q) => row(q, q.key === W.assets.leader)).join("") + row(W.quality, false);
  }

  function sigRow(s, qk) {
    const ex = { up: "▲", down: "▼", flat: "▶", flat_down: "▶▼" }[s.expect];
    const st = { match: "✓", against: "✗", neutral: "–", na: "·" }[s.status];
    const ar = { up: "▲", down: "▼", flat: "▶" }[s.actual] || "";
    let val = "no data", vcls = "flat";
    if (s.status !== "na") {
      const dp = s.unit === "bp" ? 0 : 1;
      const unit = s.unit === "%" ? "%" : s.unit === "bp" ? "bp" : s.unit === "σ" ? "σ" : "%";
      val = `${signed(s.value, dp, unit)} ${ar}`;
      vcls = s.actual === "flat" ? "flat" : dir(s.z);
    }
    const word = { match: "Confirms", against: "Contradicts", neutral: "No clear move", na: "No data" }[s.status];
    const zs = s.status !== "na" ? ` Move size: ${signed(s.z, 1)}σ versus a normal ${S.win === "1M" ? "month" : "3 months"}${s.date ? `, data to ${fmtDate(s.date)}` : ""}.` : "";
    return `<details class="sig"><summary title="${word}"><span class="st ${s.status}" aria-label="${word}">${st}</span>
      <span class="lab">${esc(s.label)}</span><span class="exp" style="color:var(--q-${qk})" aria-label="expected ${s.expect}">${ex}</span>
      <span class="val ${vcls}">${val}</span></summary>
      <div class="more"><b>${esc(s.measure)}</b>. ${esc(s.why)}${zs} <b>${word}.</b></div></details>`;
  }

  function quadCards(W) {
    return [...W.quadrants, W.quality].map((q) => `<div class="qcard">
      <div class="qcard-h"><span class="tape t-${q.key}">${q.name}</span><span class="sub">${esc(q.curve)}</span>
        <span class="cnt">${q.match}/${q.n} ✓</span></div>
      <p class="qcard-blurb">${esc(q.blurb)}</p>
      <div>${q.signals.map((s) => sigRow(s, q.key)).join("")}</div></div>`).join("");
  }

  function historyStrip(W) {
    const tr = W.trail || [];
    if (!tr.length) return "";
    const cols = `64px repeat(${tr.length}, minmax(9px, 1fr))`;
    const mo = tr.map((p) => Number(p.date.slice(5, 7)));
    const firstChange = mo.findIndex((m) => m !== mo[0]);
    const months = mo.map((m, i) => {
      const show = i === 0 ? firstChange === -1 || firstChange >= 3 : m !== mo[i - 1];
      return `<span class="mon">${show ? MON[m - 1] : ""}</span>`;
    }).join("");
    const a = tr.map((p) => `<span class="cell bg-${p.asset_quad}" title="Week of ${fmtDate(p.date)}: ${QNAME[p.asset_quad]}"></span>`).join("");
    const c = tr.map((p) => `<span class="cell bg-${p.curve_quad || "none"}" title="Week of ${fmtDate(p.date)}: ${p.curve_quad ? QNAME[p.curve_quad] : "no clear curve move"}"></span>`).join("");
    return `<div class="hist"><div class="hist-grid" style="grid-template-columns:${cols}">
      <span class="lab">Assets</span>${a}<span class="lab">Curve</span>${c}<span></span>${months}</div></div>
      <div class="hist-legend">${QKEYS.map((k) => `<span><i class="sw bg-${k}"></i>${QNAME[k]}</span>`).join("")}<span><i class="sw bg-none"></i>No clear call</span></div>`;
  }

  function tiles() {
    const { macro, market } = S.data;
    const rows = {};
    macro.groups.forEach((g) => g.rows.forEach((r) => (rows[r.id] = r)));
    const mk = {};
    market.groups.forEach((g) => g.items.forEach((i) => (mk[i.t] = i)));
    const spec = [["DFF", "Fed funds"], ["DGS2", "2Y Treasury"], ["DGS10", "10Y Treasury"], ["T10Y2Y", "10Y − 2Y"],
      ["PCEPILFE", "Core PCE"], ["CPIAUCSL", "CPI"], ["UNRATE", "Unemployment"], ["ICSA", "Jobless claims"],
      ["GDPNOW", "GDPNow"], ["BAMLH0A0HYM2", "HY spread"], ["^VIX", "VIX"], ["DX-Y.NYB", "Dollar index"]];
    return `<div class="tiles">${spec.map(([id, label]) => {
      if (rows[id]) {
        const r = rows[id];
        const rate = (r.unit === "%" || r.unit === "pp") && r.freq === "daily";
        const v = `${num(r.last, r.dp)}<span class="muted" style="font-size:12px"> ${esc(r.unit)}</span>`;
        const c = rate ? `${signed(r.chg * 100, 0, "bp")} ${r.chg_label}` : `${signed(r.chg, r.dp)} ${r.chg_label}`;
        const cc = rate ? dir(Math.round(r.chg * 100)) : goodCls(r.chg, r.good, r.dp);
        return `<div class="tile"><div class="k">${label}</div><div class="v">${v}</div><div class="c ${cc}">${c}</div></div>`;
      }
      if (mk[id]) {
        const i = mk[id];
        return `<div class="tile"><div class="k">${label}</div><div class="v">${num(i.last, 2)}</div><div class="c ${dir(i.chg.d1)}">${signed(i.chg.d1, 2, "%")} today</div></div>`;
      }
      return "";
    }).join("")}</div>`;
  }

  function renderOverview() {
    const { regime } = S.data;
    const W = regime.windows[S.win];
    const lead = W.assets.leader, conf = W.story.confidence;
    $("#overview").innerHTML = `
      <div class="ov-top">
        <div class="panel map-wrap">
          <div class="panel-h"><h2>Regime map</h2><span class="sub">${S.win === "1M" ? "Past month" : "Past 3 months"} · data to ${fmtDate(regime.asof, true)}</span></div>
          ${mapSVG(regime, W)}
          <div class="map-legend">
            <span><svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="5.5" fill="var(--ink)"/></svg>Yield curve (2Y and 10Y moves)</span>
            <span><svg width="14" height="14" aria-hidden="true"><rect x="3" y="3" width="8" height="8" transform="rotate(45 7 7)" fill="var(--surface)" stroke="var(--ink)" stroke-width="2"/></svg>Cross-asset checklist</span>
            <span class="muted">Faded marks: previous 12 weeks</span>
          </div>
          <p class="map-note">Up = yields falling on average (the market pricing an easier Fed). Right = the 10Y−2Y slope steepening. The edge of the map is a ${S.win === "1M" ? "1-month" : "3-month"} move as large as the biggest 5% of the past five years.</p>
        </div>
        <div class="panel read">
          <div class="panel-h" style="justify-content:space-between"><h2>The read</h2>${segWin()}</div>
          <div class="verdict"><span class="tape lg t-${lead}">${QNAME[lead]}</span><span class="pill ${conf}">${conf} confidence</span></div>
          <div class="scores">${scoreRows(W)}</div>
          ${W.story.paras.map((p) => `<p>${md(p)}</p>`).join("")}
          <ul class="backdrop">${W.story.backdrop.map((b) => `<li>${md(b)}</li>`).join("")}</ul>
        </div>
      </div>
      <div class="panel"><div class="panel-h"><h2>Key numbers</h2><span class="sub">Rates lag one business day</span></div>${tiles()}</div>
      <div class="panel"><div class="panel-h"><h2>Signal checklist</h2><span class="sub">Every ▲ ▼ ▶ from your chart, checked against the market over the ${S.win === "1M" ? "past month" : "past 3 months"}. Tap a row for what it measures.</span></div>
        <div class="checks">${quadCards(W)}</div></div>
      <div class="panel"><div class="panel-h"><h2>Regime history</h2><span class="sub">Best fit each week over the past year, ${S.win === "1M" ? "1-month" : "3-month"} look-back</span></div>${historyStrip(W)}</div>`;
  }

  // ---------------------------------------------------------- markets ---
  function segPeriod() {
    return `<div class="seg" role="group" aria-label="Period">${PERIODS.map(([k, l]) =>
      `<button type="button" data-period="${k}" aria-pressed="${S.period === k}">${l}</button>`).join("")}</div>`;
  }

  function heatmap(group) {
    const vals = group.items.map((i) => i.chg[S.period]).filter(ok);
    const mx = Math.max(1, ...vals.map(Math.abs));
    const items = [...group.items].sort((a, b) => (b.chg[S.period] ?? -1e9) - (a.chg[S.period] ?? -1e9));
    return `<div class="heat">${items.map((i) => {
      const v = i.chg[S.period];
      const pct = ok(v) ? Math.round(8 + (Math.min(Math.abs(v) / mx, 1)) * 50) : 0;
      const bg = ok(v) && v !== 0 ? `color-mix(in srgb, var(--${v > 0 ? "up" : "down"}) ${pct}%, var(--surface))` : "var(--surface-2)";
      return `<div class="h" style="background:${bg}"><div><div class="n">${esc(i.name)}</div><div class="t">${esc(i.t)}</div></div><div class="p">${signed(v, 1, "%")}</div></div>`;
    }).join("")}</div>`;
  }

  function groupTable(g) {
    const isY = g.items.every((i) => i.kind === "yield");
    const head = PERIODS.map(([k, l]) => `<th class="${k === S.period ? "sel" : ""}">${l}</th>`).join("");
    const rows = g.items.map((i) => {
      const y = i.kind === "yield";
      const last = y ? `${num(i.last, 2)}%` : num(i.last, priceDp(i.t, i.last));
      const cells = PERIODS.map(([k]) => {
        const v = i.chg[k];
        return `<td class="${dir(v)}${k === S.period ? " sel" : ""}">${y ? signed(v, 0) : signed(v, 1, "%")}</td>`;
      }).join("");
      const pos = ok(i.range52) ? Math.max(0, Math.min(1, i.range52)) : null;
      const rng = pos === null ? "" : `<span class="rng" title="52-week range ${num(i.lo52, 2)} – ${num(i.hi52, 2)}"><i style="left:calc(${(pos * 100).toFixed(1)}% - 1.5px)"></i></span>`;
      return `<tr><td>${esc(i.name)}<span class="tk">${esc(i.t)}${i.src === "FRED" ? " · prior close" : ""}</span></td>
        <td>${last}</td>${cells}<td>${spark(i.spark, 96, 26)}</td><td>${rng}</td></tr>`;
    }).join("");
    return `<div class="panel"><div class="panel-h"><h2>${esc(g.name)}</h2>${isY || g.name === "Rates" ? `<span class="sub">Moves in basis points</span>` : ""}</div>
      <div class="tbl-wrap"><table class="mk"><thead><tr><th>Name</th><th>Last</th>${head}<th>3M</th><th>52W range</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
  }

  function renderMarkets() {
    const m = S.data.market;
    const sectors = m.groups.find((g) => g.name === "Sectors");
    const lbl = PERIODS.find((p) => p[0] === S.period)[1];
    const asof = m.groups[0]?.items[0]?.date;
    $("#markets").innerHTML = `
      <div class="panel">
        <div class="panel-h mk-bar"><h2>Sector heat map</h2><span class="sub">${lbl} move · prices to ${fmtDate(asof, true)}</span><span style="margin-left:auto">${segPeriod()}</span></div>
        ${sectors ? heatmap(sectors) : ""}
      </div>
      <div class="mk-groups">${m.groups.map(groupTable).join("")}</div>`;
  }

  // ------------------------------------------------------------ macro ---
  const slug = (s) => s.toLowerCase().replace(/[^a-z]+/g, "-").replace(/^-|-$/g, "");
  function sparkPts(r) {
    const n = { monthly: 36, weekly: 104, daily: 104, quarterly: 20 }[r.freq] || 36;
    return r.hist.slice(-n).map((p) => p[1]);
  }
  function unitLabel(u) { return u === "% y/y" || u === "% m/m" || u === "% ann." ? u : u; }

  function macroRow(r) {
    const rate = (r.unit === "%" || r.unit === "pp") && r.freq === "daily";
    const alt = r.alt ? ` · ${r.alt.label} ${num(r.alt.value, r.dp)}${r.alt.unit === "%" ? "%" : r.alt.unit}` : "";
    const status = r.status ? `<span class="chip ${r.status}">${r.status}</span>` : `<span></span>`;
    const col = r.good ? `var(--${goodCls((sparkPts(r).slice(-1)[0] ?? 0) - (sparkPts(r)[0] ?? 0), r.good)})` : "var(--q-value)";
    return `<div class="mrow"><button type="button" aria-expanded="false" data-id="${esc(r.id)}">
        <span class="mname"><span class="nm">${esc(r.name)}</span><span class="meta">${r.freq} · ${fmtDate(r.date, true)}${alt}</span></span>
        <span class="mval">${num(r.last, r.dp)}<span class="u">${esc(unitLabel(r.unit))}</span></span>
        <span class="mchg ${rate ? dir(Math.round(r.chg * 100)) : goodCls(r.chg, r.good, r.dp)}">${rate ? signed(r.chg * 100, 0, "bp") : signed(r.chg, r.dp)}<span class="l">${esc(r.chg_label)}</span></span>
        ${status}
        <span class="spark">${spark(sparkPts(r), 120, 30, col)}</span>
      </button><div class="detail" hidden></div></div>`;
  }

  function renderMacro() {
    const groups = S.data.macro.groups;
    $("#macro").innerHTML = `
      <div class="panel"><div class="panel-h"><h2>US macro</h2><span class="sub">Grouped like your slide. Trend compares the latest readings with the ones before. Tap any row for five years of history.</span></div>
        <nav class="jump" aria-label="Jump to group">${groups.map((g) => `<a href="#g-${slug(g.name)}" data-jump="g-${slug(g.name)}">${esc(g.name)}</a>`).join("")}</nav></div>
      ${groups.map((g) => `<div class="panel" id="g-${slug(g.name)}"><div class="panel-h"><h2>${esc(g.name)}</h2><span class="sub">${esc(g.sub)}</span></div>
        <div>${g.rows.map(macroRow).join("")}</div>
        ${g.not_free && g.not_free.length ? `<p class="notfree">Not in free data: ${esc(g.not_free.join(", "))}.</p>` : ""}</div>`).join("")}`;
  }

  function toggleRow(btn) {
    const det = btn.nextElementSibling;
    const open = btn.getAttribute("aria-expanded") === "true";
    btn.setAttribute("aria-expanded", String(!open));
    det.hidden = open;
    if (!open && !det.dataset.done) {
      const id = btn.dataset.id;
      let row = null;
      S.data.macro.groups.forEach((g) => g.rows.forEach((r) => { if (r.id === id) row = r; }));
      if (!row) return;
      det.innerHTML = `${row.note ? `<p class="note">${esc(row.note)}</p>` : ""}<div class="chart"></div>`;
      lineChart($(".chart", det), row.hist, { unit: row.unit, dp: row.dp, label: row.name });
      det.dataset.done = "1";
    }
  }

  // ------------------------------------------------------------ shell ---
  function renderFresh() {
    const m = S.data.meta;
    const hrs = (Date.now() - new Date(m.built).getTime()) / 3.6e6;
    $("#live-dot").classList.toggle("stale", hrs > 6);
    $("#fresh-text").textContent = `Updated ${ago(m.built)}`;
    $("#fresh").title = `Built ${new Date(m.built).toLocaleString()}. Markets to ${m.market_asof}.`;
    $("#sample-banner").hidden = !m.sample;
  }

  function setTab(tab, push) {
    if (!["overview", "markets", "macro"].includes(tab)) tab = "overview";
    S.tab = tab;
    document.querySelectorAll(".tab").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === tab)));
    ["overview", "markets", "macro"].forEach((id) => ($("#" + id).hidden = id !== tab));
    if (push) { try { history.replaceState(null, "", "#" + tab); } catch (e) { /* sandboxed */ } }
  }

  function renderAll() {
    renderFresh();
    renderOverview();
    renderMarkets();
    renderMacro();
    setTab(S.tab);
  }

  async function getJSON(n) {
    const r = await fetch(`data/${n}.json?t=${Date.now()}`, { cache: "no-store" });
    if (!r.ok) throw new Error(`${n}: ${r.status}`);
    return r.json();
  }

  async function load() {
    try {
      let d = window.__RD_DATA__;
      if (!d) {
        const [meta, market, macro, regime] = await Promise.all(["meta", "market", "macro", "regime"].map(getJSON));
        d = { meta, market, macro, regime };
      }
      S.data = d; S.built = d.meta.built;
      $("#empty").hidden = true;
      renderAll();
    } catch (e) {
      $("#empty").hidden = false;
      ["overview", "markets", "macro"].forEach((id) => ($("#" + id).hidden = true));
      $("#fresh-text").textContent = "No data yet";
    }
  }

  document.addEventListener("click", (e) => {
    const t = e.target.closest("[data-tab],[data-win],[data-period],.mrow > button,[data-jump],#theme-btn");
    if (!t) return;
    if (t.dataset.tab) { setTab(t.dataset.tab, true); window.scrollTo({ top: 0 }); }
    else if (t.dataset.win) { S.win = t.dataset.win; renderOverview(); }
    else if (t.dataset.period) { S.period = t.dataset.period; renderMarkets(); }
    else if (t.dataset.jump) {
      e.preventDefault();
      const el = document.getElementById(t.dataset.jump);
      if (el) el.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    }
    else if (t.id === "theme-btn") {
      const root = document.documentElement;
      const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
      root.dataset.theme = dark ? "light" : "dark";
      try { localStorage.setItem("rd-theme", root.dataset.theme); } catch (err) { /* storage blocked */ }
    }
    else toggleRow(t);
  });

  S.tab = (location.hash || "#overview").slice(1);
  window.addEventListener("hashchange", () => setTab(location.hash.slice(1)));
  load();
  // pick up new data without a manual reload
  setInterval(async () => {
    if (window.__RD_DATA__) return;
    try {
      const m = await getJSON("meta");
      if (m.built !== S.built) load(); else if (S.data) renderFresh();
    } catch (e) { /* offline */ }
  }, 5 * 60 * 1000);
})();
