(() => {
  "use strict";

  const S = { win: "3M", period: "m1", tab: "overview", data: null, built: null };
  const QKEYS = ["growth", "riskon", "riskoff", "value"];
  const QNAME = { growth: "Growth", riskon: "Risk ON", riskoff: "Risk OFF", value: "Value", quality: "Quality", tie: "Tie" };
  const qcol = (k) => (k === "tie" ? "var(--ink-3)" : `var(--q-${k})`);
  const leadKeys = (A) => (A.leader === "tie" ? A.tied : [A.leader]);
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
    par_up: [1.6, 2.6, 2.4, 3.4], par_down: [2.2, 3.2, 1.4, 2.4], flat: [2.0, 3.0, 2.05, 3.05],
  };
  function curveIcon(k, x, y, color) {
    const w = 58, h = 34, [os, ol, ns, nl] = CURVES[k];
    const col = color || `var(--q-${k})`;
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
      <path d="${path(ns, nl)}" fill="none" stroke="${col}" stroke-width="2.2"/></g>`;
  }
  const iconSVG = (k, color) => `<svg class="ci" width="62" height="38" viewBox="0 0 62 38" aria-hidden="true">${curveIcon(k, 0, 2, color)}</svg>`;

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
    const lead = W.assets.leader, hl = leadKeys(W.assets);
    let g = "";
    const corners = { growth: [-1, 1], riskon: [1, 1], riskoff: [-1, -1], value: [1, -1] };
    for (const k of QKEYS) {
      const [sx, sy] = corners[k];
      g += `<rect x="${sx < 0 ? C - H : C}" y="${sy > 0 ? C - H : C}" width="${H}" height="${H}" fill="var(--q-${k})" fill-opacity="${hl.includes(k) ? 0.14 : 0.05}"/>`;
    }
    g += `<rect x="${C - H}" y="${C - H}" width="${2 * H}" height="${2 * H}" fill="none" stroke="var(--line)"/>`;
    // axes with arrowheads
    g += `<defs><marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="var(--ink)"/></marker></defs>`;
    g += `<line x1="${C - H + 2}" y1="${C}" x2="${C + H - 2}" y2="${C}" stroke="var(--ink)" stroke-width="1.6" marker-start="url(#ah)" marker-end="url(#ah)"/>`;
    g += `<line x1="${C}" y1="${C + H - 2}" x2="${C}" y2="${C - H + 2}" stroke="var(--ink)" stroke-width="1.6" marker-start="url(#ah)" marker-end="url(#ah)"/>`;
    const lab = (x, y, txt, rot, col) => `<text x="${x}" y="${y}" text-anchor="middle" font-family="var(--f-display)" font-weight="800" font-size="11.5" letter-spacing="1.2" style="font-stretch:112%" fill="${col}" ${rot ? `transform="rotate(${rot} ${x} ${y})"` : ""}>${txt}</text>`;
    g += lab(C, C - H - 14, "EASIER FED  +", 0, "var(--up)");
    g += lab(C, C + H + 24, "TIGHTER FED  −", 0, "var(--down)");
    g += lab(C - H - 16, C, "−  WEAKER MACRO", -90, "var(--down)");
    g += lab(C + H + 16, C, "STRONGER MACRO  +", 90, "var(--up)");
    // quality center
    const [qx0, qy0] = P(-0.2, 0.2), [qx1, qy1] = P(0.2, -0.2);
    g += `<rect x="${qx0}" y="${qy0}" width="${qx1 - qx0}" height="${qy1 - qy0}" fill="var(--q-quality)" fill-opacity=".06" stroke="var(--q-quality)" stroke-dasharray="4 3" rx="3"/>`;
    g += `<text x="${C}" y="${qy0 - 5}" text-anchor="middle" font-family="var(--f-display)" font-weight="800" font-size="10" letter-spacing="1" fill="var(--q-quality)">QUALITY</text>`;
    // quadrant tapes
    const L = C - H + 10, R = C + H - 10, T = C - H + 10, B = C + H - 10;
    g += tapeSVG("growth", "Growth", L, T) + tapeSVG("riskon", "Risk ON", R, T, "end");
    g += tapeSVG("riskoff", "Risk OFF", L, B - 25) + tapeSVG("value", "Value", R, B - 25, "end");
    // trail: previous 12 weeks
    const tr = (W.trail || []).slice(-13);
    const pts = tr.map((p) => [P(p.ax, p.ay), p]);
    if (pts.length > 1) g += `<polyline points="${pts.map(([q]) => q.join(",")).join(" ")}" fill="none" stroke="var(--ink-2)" stroke-opacity=".5" stroke-dasharray="3 3"/>`;
    pts.slice(0, -1).forEach(([[x, y], p], i) => {
      const o = (0.2 + (0.6 * i) / pts.length).toFixed(2);
      g += `<rect x="${x - 3.5}" y="${y - 3.5}" width="7" height="7" transform="rotate(45 ${x} ${y})" fill="${qcol(p.asset_quad)}" fill-opacity="${o}" stroke="var(--surface)" stroke-width="1"><title>Week of ${fmtDate(p.date)}: ${QNAME[p.asset_quad]}</title></rect>`;
    });
    const [ax, ay] = P(W.assets.x, W.assets.y);
    g += `<rect class="cur-dot" x="${ax - 8}" y="${ay - 8}" width="16" height="16" transform="rotate(45 ${ax} ${ay})" fill="${qcol(lead)}" stroke="var(--ink)" stroke-width="2.4"><title>Now: ${lead === "tie" ? "tie between " + hl.map((k) => QNAME[k]).join(" and ") : QNAME[lead]}</title></rect>`;
    const right = ax < C + H - 70;
    g += `<text x="${ax + (right ? 15 : -15)}" y="${ay + 4.5}" text-anchor="${right ? "start" : "end"}" font-family="var(--f-display)" font-weight="800" font-size="13" fill="var(--ink)" paint-order="stroke" stroke="var(--surface)" stroke-width="4" stroke-linejoin="round">Now</text>`;
    return `<svg viewBox="0 0 520 520" role="img" aria-label="${esc(`Regime map. The ${S.win === "1M" ? "1-month" : "3-month"} checklist points to ${lead === "tie" ? "a tie between " + hl.map((k) => QNAME[k]).join(" and ") : QNAME[lead]}.`)}">${g}</svg>`;
  }

  // --------------------------------------------------------- overview ---
  function segWin() {
    return `<div class="seg" role="group" aria-label="Look-back window">${["3M", "1M"].map((w) =>
      `<button type="button" data-win="${w}" aria-pressed="${S.win === w}" title="${w === "1M" ? "Changes every ~2 weeks; no forward value in the backtest" : "The tested look-back"}">${w === "1M" ? "1 month · noisy" : "3 months"}</button>`).join("")}</div>`;
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
    const hl = leadKeys(W.assets);
    return qs.map((q) => row(q, hl.includes(q.key))).join("") + row(W.quality, false);
  }

  function sigRow(s, qk) {
    const ex = { up: "▲", down: "▼", flat: "▶", flat_down: "▶▼" }[s.expect];
    const st = { match: "✓", against: "✗", neutral: "–", na: "·", context: "i" }[s.status];
    const ar = { up: "▲", down: "▼", flat: "▶" }[s.actual] || "";
    let val = "no data", vcls = "flat";
    if (s.status !== "na") {
      const dp = s.unit === "bp" ? 0 : 1;
      const unit = s.unit === "%" ? "%" : s.unit === "bp" ? "bp" : s.unit === "σ" ? "σ" : "%";
      val = `${signed(s.value, dp, unit)} ${ar}`;
      vcls = s.actual === "flat" ? "flat" : dir(s.z);
    }
    const word = { match: "Confirms", against: "Contradicts", neutral: "No clear move", na: "No data", context: "Context, not scored" }[s.status];
    let zs = s.status !== "na" && s.status !== "context" ? ` Move size: ${signed(s.z, 1)}σ versus a normal ${S.win === "1M" ? "month" : "3 months"}${s.date ? `, data to ${fmtDate(s.date)}` : ""}.` : "";
    if (s.status === "context") {
      const [y, m] = (s.date || "").split("-").map(Number);
      const when = /quarterly/i.test(s.measure || "") && y ? `Q${Math.floor((m - 1) / 3) + 1} ${y}` : fmtDate(s.date, true);
      zs = ` Latest data: ${when}. Shown for context and not scored: it is revised and published late, so the backtest could not use it.`;
    }
    return `<details class="sig"><summary title="${word}"><span class="st ${s.status}" aria-label="${word}">${st}</span>
      <span class="lab">${esc(s.label)}</span><span class="exp" style="color:var(--q-${qk})" aria-label="expected ${s.expect}">${ex}</span>
      <span class="val ${vcls}">${val}</span></summary>
      <div class="more"><b>${esc(s.measure)}</b>. ${esc(s.why)}${zs} <b>${word}.</b></div></details>`;
  }

  function quadCards(W) {
    return [...W.quadrants, W.quality].map((q) => `<div class="qcard">
      <div class="qcard-h"><span class="tape t-${q.key}">${q.name}</span>
        <span class="cnt">${q.match}/${q.n} ✓ ${q.against} ✗</span></div>
      <p class="qcard-blurb"><span class="claim">Your chart:</span> ${esc(q.blurb)}</p>
      <div>${q.signals.map((s) => sigRow(s, q.key)).join("")}</div></div>`).join("");
  }

  function historyStrip(W, alert) {
    const tr = W.trail || [];
    if (!tr.length) return "";
    const cols = `104px repeat(${tr.length}, minmax(9px, 1fr))`;
    const mo = tr.map((p) => Number(p.date.slice(5, 7)));
    const firstChange = mo.findIndex((m) => m !== mo[0]);
    const months = mo.map((m, i) => {
      const show = i === 0 ? firstChange === -1 || firstChange >= 3 : m !== mo[i - 1];
      return `<span class="mon">${show ? MON[m - 1] : ""}</span>`;
    }).join("");
    const hist = alert.hist || [];
    const prov = hist.length && hist[hist.length - 1].provisional;
    const a = tr.map((p, i) => `<span class="cell bg-${p.asset_quad}${prov && i === tr.length - 1 ? " prov" : ""}" title="Week of ${fmtDate(p.date)}: ${QNAME[p.asset_quad]}${prov && i === tr.length - 1 ? " (this week so far)" : ""}"></span>`).join("");
    const al = hist.map((p) => `<span class="cell ${p.on ? "bg-alert" : "bg-none"}${p.provisional ? " prov" : ""}" title="Week of ${fmtDate(p.date)}: ${p.on ? "Risk OFF alert on" : p.tie ? "tie, no alert" : "clear"}${p.provisional ? " (provisional until Friday's close)" : ""}"></span>`).join("");
    return `<div class="hist"><div class="hist-grid" style="grid-template-columns:${cols}">
      <span class="lab">Best fit (${S.win})</span>${a}<span class="lab">Risk OFF alert</span>${al}<span class="lab"></span>${months}</div></div>
      <div class="hist-legend">${QKEYS.map((k) => `<span><i class="sw bg-${k}"></i>${QNAME[k]}</span>`).join("")}<span><i class="sw bg-tie"></i>Tie</span><span><i class="sw bg-alert"></i>Alert on (3-month)</span>${prov ? `<span><i class="sw bg-none prov"></i>This week: provisional until Friday's close</span>` : ""}</div>`;
  }

  function alertChart(hist) {
    const W = 600, H = 96, pl = 30, pr = 8, pt = 8, pb = 8;
    const n = hist.length;
    if (n < 2) return "";
    const X = (i) => pl + (i / (n - 1)) * (W - pl - pr);
    const Y = (v) => pt + (1 - (v + 1) / 2) * (H - pt - pb);
    const bw = (W - pl - pr) / (n - 1);
    let g = "";
    hist.forEach((p, i) => { if (p.on) g += `<rect x="${X(i) - bw / 2}" y="${pt}" width="${bw}" height="${H - pt - pb}" fill="var(--q-riskoff)" fill-opacity="${p.provisional ? ".06" : ".14"}"${p.provisional ? ' stroke="var(--q-riskoff)" stroke-opacity=".5" stroke-dasharray="2 2"' : ""}/>`; });
    for (const v of [-1, 0, 1]) {
      g += `<line x1="${pl}" x2="${W - pr}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--line)" ${v === 0 ? "" : 'stroke-dasharray="2 3"'}/>`;
      g += `<text x="${pl - 5}" y="${Y(v) + 3.5}" text-anchor="end" font-size="10" font-family="var(--f-mono)" fill="var(--ink-3)">${v > 0 ? "+1" : v < 0 ? "−1" : "0"}</text>`;
    }
    const line = (k) => hist.map((p, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(p[k]).toFixed(1)}`).join("");
    g += `<path d="${line("lead_net")}" fill="none" stroke="var(--ink-3)" stroke-width="1.5" stroke-dasharray="4 3"/>`;
    g += `<path d="${line("net")}" fill="none" stroke="var(--q-riskoff)" stroke-width="2.2"/>`;
    const pv = hist[n - 1].provisional;
    g += `<circle cx="${X(n - 1)}" cy="${Y(hist[n - 1].net)}" r="${pv ? 4 : 3.5}" fill="${pv ? "var(--surface)" : "var(--q-riskoff)"}" stroke="var(--q-riskoff)" stroke-width="2"><title>${pv ? "This week so far (provisional)" : "Latest close"}</title></circle>`;
    return `<svg class="alert-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Risk OFF score over the past year against the leading quadrant's score">${g}</svg>`;
  }

  function fridayOf(d) {
    const t = new Date(d + "T12:00:00Z");
    t.setUTCDate(t.getUTCDate() + (5 - t.getUTCDay()));
    return t.toISOString().slice(0, 10);
  }

  function actionBox(A, mode) {
    const helped = (A.overlay || []).filter((r) => r.helped_both_halves);
    const notHelped = (A.overlay || []).filter((r) => !r.helped_both_halves);
    const park = A.parking || [];
    const cls = (v) => (v > 0.5 ? "up" : v < -0.5 ? "down" : "flat");
    const title = { on: "What historically helped while the alert was on", prov: "If it confirms at Friday's close: what historically helped", off: "What historically helped when the alert was on" }[mode];
    return `<details class="action" ${mode === "on" ? "open" : ""}>
      <summary>${title}</summary>
      <div class="action-body">
        <p>Move <b>stocks and high-yield bonds</b> into <b>T-bills or short Treasuries</b> at the next day's close, and move back at the next day's close after the first Friday the alert is clear.</p>
        <div class="action-cols">
          <div>
            <h3>In both halves of the backtest this improved</h3>
            <div class="tbl-wrap"><table class="mini">
              <thead><tr><th>Holding</th><th>Sharpe</th><th>Worst drop</th></tr></thead>
              <tbody>${helped.map((r) => `<tr><td>${esc(r.name)} <span class="tk">${esc(r.t)}</span></td><td>${num(r.sharpe_before, 2)} → <b>${num(r.sharpe_after, 2)}</b></td><td>${num(r.dd_before, 0)}% → ${num(r.dd_after, 0)}%</td></tr>`).join("")}</tbody>
            </table></div>
            ${notHelped.length ? `<p class="fine">Did not reliably help: ${notHelped.map((r) => esc(r.name)).join(", ")}.</p>` : ""}
          </div>
          <div>
            <h3>Where the money sat best (return a year while on)</h3>
            <div class="tbl-wrap"><table class="mini">
              <thead><tr><th>Park in</th><th>2008–16</th><th>2017–26</th></tr></thead>
              <tbody>${park.map((r) => `<tr><td>${esc(r.name)}</td><td class="${cls(r["2008-16"])}">${signed(r["2008-16"], 1, "%")}</td><td class="${cls(r["2017-26"])}">${signed(r["2017-26"], 1, "%")}</td></tr>`).join("")}</tbody>
            </table></div>
            <p class="fine">Only cash, short Treasuries and the dollar were positive in both halves. Staples and utilities still lost money; long bonds and gold flipped sign between the halves.</p>
          </div>
        </div>
        <p class="fine">Historical test results, not personal advice. Taxes are not modelled: selling in a taxable account can realise gains.</p>
      </div>
    </details>`;
  }

  function recent(list) {
    if (!list || !list.length) return "";
    const one = (e) => `${MON[Number(e.start.slice(5, 7)) - 1]} ${e.start.slice(0, 4)} (${e.weeks} wk, S&P ${signed(e.spx, 1, "%")})`;
    return ` Last ${list.length === 1 ? "alert" : list.length}: ${list.map(one).join(", ")}.`;
  }

  function streakOf(trail, key) {
    let n = 0;
    for (let i = trail.length - 1; i >= 0 && trail[i].asset_quad === key; i--) n++;
    return n;
  }

  function alertPanel(A, W3) {
    const t = A.track;
    const P = A.provisional;
    const decide = P ? fmtDate(fridayOf(P.date)) : "";
    const L = W3.assets, hl = leadKeys(L);
    const led = L.leader === "tie" ? 0 : streakOf(W3.trail || [], L.leader);
    const regime = hl.map((k) => `<span class="tape lg t-${k}">${QNAME[k]}</span>`).join(`<span class="vs">=</span>`);
    const regimeNote = L.leader === "tie" ? "tied on the 3-month checklist" :
      `best fit on the 3-month checklist${led > 1 ? `, ${led} weeks running` : ""}${P ? " (this week so far)" : ""}`;
    let head;
    if (A.on) {
      head = `<div class="alert-banner" role="status"><span>Risk OFF alert · On</span>
        <small>since the week of ${fmtDate(A.since)} · ${A.weeks} week${A.weeks === 1 ? "" : "s"} · confirmed at Friday's close</small></div>`;
    } else {
      const provOn = P && P.on;
      head = `<div class="alert-head">
        <div class="regime-now">${regime}<span class="when">${regimeNote}</span></div>
        <span class="state ${provOn ? "prov" : "off"}">Risk OFF alert: ${provOn ? "provisional" : "clear"}</span>
        <span class="when">${provOn ? "officially clear as of" : "as of"} the close on ${fmtDate(A.official_date)}${A.last_on ? ` · last alert: week of ${fmtDate(A.last_on)}` : ""}</span>
      </div>`;
    }
    let prov = "";
    if (P) {
      if (P.tie) prov = `<b>This week so far: Risk OFF is tied for first.</b> A tie is not a call. Friday's close (${decide}) decides.`;
      else if (P.on && !A.on) prov = `<b>Provisional: turning on this week.</b> Risk OFF leads on the latest data. It becomes official only if it still leads at Friday's close (${decide}). Don't act on it before then.`;
      else if (!P.on && A.on) prov = `<b>Provisional: clearing this week.</b> Risk OFF no longer leads on the latest data. It clears officially only if that holds at Friday's close (${decide}).`;
      else if (P.on) prov = `This week so far: still on. Friday's close (${decide}) confirms.`;
    }
    const move = ok(A.net_4w) ? ` (4 weeks ago ${signed(A.net_4w, 2)})` : "";
    const now = P ? "On the latest data, " : "At the close, ";
    let gauge;
    if (A.tied && A.tied.includes("riskoff")) gauge = `${now}Risk OFF scores <b>${signed(A.net, 2)}</b>${move}, tied for first with ${A.tied.filter((k) => k !== "riskoff").map((k) => QNAME[k]).join(" and ")}.`;
    else if (A.lead === "riskoff") gauge = `${now}Risk OFF leads the 3-month checklist with a score of <b>${signed(A.net, 2)}</b>${move}.`;
    else gauge = `${now}Risk OFF scores <b>${signed(A.net, 2)}</b>${move} and ranks ${["", "1st", "2nd", "3rd", "4th"][A.rank]} of 4. ${QNAME[A.lead]} leads at ${signed(A.lead_net, 2)}, so the gap to an alert is <b>${num(A.gap, 2)}</b>.`;
    const boxMode = A.on ? "on" : P && P.on ? "prov" : "off";
    const cls = A.on ? "is-on" : P && P.on ? "is-prov" : "is-clear";
    const edge = A.on || (P && P.on) ? "" : ` style="border-left-color:${qcol(L.leader)}"`;
    return `<div class="panel alert ${cls}"${edge}>
      ${head}
      ${prov ? `<p class="prov-note">${prov}</p>` : ""}
      <div class="alert-grid">
        <div class="alert-gauge">
          <p>${gauge}</p>
          ${alertChart(A.hist || [])}
          <div class="alert-key"><span><i class="ln riskoff"></i>Risk OFF score</span><span><i class="ln lead"></i>Leading quadrant's score</span><span><i class="sw bg-alert-soft"></i>Alert on</span></div>
        </div>
        <div class="alert-track">
          <div class="stats">
            <div><b class="down">${signed(t.spx_next3m, 1)}%</b><span>S&P a year, 3 months after an alert (average ${signed(t.spx_avg3m, 1)}%)</span></div>
            <div><b>${t.episodes}</b><span>alerts, ${t.share_of_weeks}% of weeks, usually ${t.median_weeks || 3} weeks long</span></div>
            <div><b class="up">${num(t.cash_cagr, 1)}%</b><span>a year in cash during alerts (buy &amp; hold ${num(t.bh_cagr, 1)}%)</span></div>
            <div><b>${num(t.cash_sharpe, 2)}</b><span>Sharpe ratio (buy &amp; hold ${num(t.bh_sharpe, 2)})</span></div>
          </div>
          ${ok(t.false_alarms) ? `<p class="fine"><b>${t.false_alarms} of ${t.episodes} alerts were false alarms:</b> the S&P rose while you were out, by ${signed(t.false_cost, 1)}% on average. The other ${t.real_alerts} avoided an average move of ${signed(t.real_saved, 1)}%. The edge comes from that imbalance.${recent(t.recent)}</p>` : ""}
          <p class="fine">Fires when Risk OFF leads the 3-month checklist at a Friday close, the one call with a tested edge; the backtest acted at the next day's close. Market signals only (EPS and LEI are revised and published late). Backtest ${esc(t.period)}, after trading costs, before taxes. It missed ${esc(t.missed)}.</p>
        </div>
      </div>
      ${actionBox(A, boxMode)}
    </div>`;
  }

  function ratesPanel(reg) {
    const c = reg.curve_context;
    if (!c) return "";
    const iconKey = c.clear ? c.quad : c.parallel ? ((c.d2 + c.d10) > 0 ? "par_up" : "par_down") : "flat";
    const trendTxt = c.trend ? `the S&P is ${num(Math.abs(c.trend_pct), 1)}% ${c.trend === "up" ? "above" : "below"} its 200-day average` : "";
    const after = ok(c.next3m) ? `Since 1990, weeks like this were followed by <b>${signed(c.next3m, 1)}%</b> a year for the S&P over the next 3 months (${c.weeks} weeks), against ${signed(reg.curve_avg, 1)}% on average.` : "";
    const rows = reg.curve_table.map((r) => {
      const cur = c.clear && r.quad === c.quad;
      const cell = (k) => {
        const [v, n] = r[k], hit = cur && c.trend === k;
        return `<td class="${hit ? "hit" : ""}"><span class="${dir(v - reg.curve_avg)}">${signed(v, 1)}%</span><span class="n">${n} wks</span></td>`;
      };
      return `<tr class="${cur ? "cur" : ""}"><td><div class="shape">${iconSVG(r.quad)}<span>${esc(r.name)}${r.quad === "riskon" ? `<em>good cuts vs bad cuts</em>` : ""}<span class="tape t-${r.quad} narrow-only">${esc(r.chart_label)}</span></span></div></td>
        <td><span class="tape t-${r.quad}">${esc(r.chart_label)}</span></td>
        <td class="${dir(r.during)}">${signed(r.during, 1)}%</td>${cell("up")}${cell("down")}</tr>`;
    }).join("");
    return `<div class="panel rates">
      <div class="panel-h"><h2>Yield curve</h2><span class="sub">Context, not a signal: on its own it had no timing value over 36 years</span></div>
      <div class="rates-now">${iconSVG(iconKey, "var(--ink)")}
        <div><p><b>${esc(c.shape)}</b> over the past 3 months: 2-year ${signed(c.d2, 0, "bp")}, 10-year ${signed(c.d10, 0, "bp")}${trendTxt ? `; ${trendTxt}` : ""}. ${esc(c.note)}</p>
        <p>${after}</p></div></div>
      <div class="tbl-wrap"><table class="rates-tbl">
        <thead><tr><th>Curve shape, 3 months</th><th>Your chart calls it</th><th>S&amp;P while it forms</th><th>Next 3M, S&amp;P above 200-day</th><th>Next 3M, below 200-day</th></tr></thead>
        <tbody>${rows}</tbody></table></div>
      <p class="fine">S&amp;P 500 total return, annualized, weekly samples 1990–2026. The 200-day average splits easing into good cuts (stocks holding up) and bad cuts (cutting into weakness): the same bull steepener was followed by ${signed(reg.curve_table[0].up[0], 1)}% versus ${signed(reg.curve_table[0].down[0], 1)}% a year.</p>
    </div>`;
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
    const W = regime.windows[S.win] || regime.windows["3M"];
    const lead = W.assets.leader, hl = leadKeys(W.assets);
    const fol = (regime.follow || {})[hl.length === 1 ? hl[0] : ""] || null;
    const edge = S.win === "3M" && hl.length === 1 && fol ? (fol.tested_edge ? `<span class="pill edge">tested signal</span>` : `<span class="pill noedge">description only</span>`) : "";
    const margin = lead === "tie" ? `<span class="pill tie">tie</span>` : `<span class="pill gap">ahead by ${num(W.assets.margin, 2)}</span>`;
    $("#overview").innerHTML = `
      ${regime.alert ? alertPanel(regime.alert, regime.windows["3M"]) : ""}
      <div class="ov-top">
        <div class="panel map-wrap">
          <div class="panel-h"><h2>Regime map</h2><span class="sub">${S.win === "1M" ? "Past month (noisy)" : "Past 3 months"} · data to ${fmtDate(regime.asof, true)}</span></div>
          ${mapSVG(regime, W)}
          <div class="map-legend">
            <span><svg width="16" height="16" aria-hidden="true"><rect x="4" y="4" width="8" height="8" transform="rotate(45 8 8)" fill="${qcol(lead)}" stroke="var(--ink)" stroke-width="2"/></svg>Now</span>
            <span class="muted">Faded marks: previous 12 weeks</span>
          </div>
          <p class="map-note">Placed by the four checklist scores below: up when Growth and Risk ON beat Risk OFF and Value, right when Risk ON and Value beat Growth and Risk OFF.</p>
        </div>
        <div class="panel read">
          <div class="panel-h" style="justify-content:space-between"><h2>The read</h2>${segWin()}</div>
          <div class="verdict">${hl.map((k) => `<span class="tape lg t-${k}">${QNAME[k]}</span>`).join(`<span class="vs">=</span>`)}${margin}${edge}</div>
          <div class="scores">${scoreRows(W)}</div>
          ${W.story.paras.map((p) => `<p>${md(p)}</p>`).join("")}
          ${W.story.backdrop.length ? `<ul class="backdrop">${W.story.backdrop.map((b) => `<li>${md(b)}</li>`).join("")}</ul>` : ""}
        </div>
      </div>
      ${ratesPanel(regime)}
      <div class="panel"><div class="panel-h"><h2>Key numbers</h2><span class="sub">Rates lag one business day</span></div>${tiles()}</div>
      <div class="panel"><div class="panel-h"><h2>Signal checklist</h2><span class="sub">Every ▲ ▼ ▶ from your chart, checked against the market over the ${S.win === "1M" ? "past month" : "past 3 months"}. Tap a row for what it measures.</span></div>
        <div class="checks">${quadCards(W)}</div></div>
      <div class="panel"><div class="panel-h"><h2>Regime history</h2><span class="sub">Each week over the past year</span></div>${historyStrip(W, regime.alert || {})}</div>`;
    // on narrow screens start the strip at the latest week
    document.querySelectorAll("#overview .hist").forEach((h) => { h.scrollLeft = h.scrollWidth; });
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

  function periodLabel(r) {  // FRED dates monthly/quarterly data on the first day of the period
    const [y, m] = r.date.split("-").map(Number);
    if (r.freq === "quarterly") return `Q${Math.floor((m - 1) / 3) + 1} ${y}`;
    if (r.freq === "monthly") return `${MON[m - 1]} ${y}`;
    return fmtDate(r.date, true);
  }

  function macroRow(r) {
    const rate = (r.unit === "%" || r.unit === "pp") && r.freq === "daily";
    const alt = r.alt ? ` · ${r.alt.label} ${num(r.alt.value, r.dp)}${r.alt.unit === "%" ? "%" : r.alt.unit}` : "";
    const status = r.status ? `<span class="chip ${r.status}">${r.status}</span>` : `<span></span>`;
    const col = r.good ? `var(--${goodCls((sparkPts(r).slice(-1)[0] ?? 0) - (sparkPts(r)[0] ?? 0), r.good)})` : "var(--q-value)";
    return `<div class="mrow"><button type="button" aria-expanded="false" data-id="${esc(r.id)}">
        <span class="mname"><span class="nm">${esc(r.name)}</span><span class="meta">${r.freq} · ${periodLabel(r)}${alt}</span></span>
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
      if (!S.data && d.regime && d.regime.default_window) S.win = d.regime.default_window;
      S.data = d;
      $("#empty").hidden = true;
      const first = !S.built;
      S.built = d.meta.built;
      renderAll();
      // the tab name in the URL is also a section id; don't let the browser jump past the header
      if (first) window.scrollTo(0, 0);
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
