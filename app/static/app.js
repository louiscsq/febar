// Banksia NOC topology app: plain JS over the JSON API (no build step).
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const COLORS = {down: "#e5484d", degraded: "#f08c2e", impacted: "#e8c547", alarm: "#9b8afb", ok: "#3fb27f"};
const fmtTs = (t) => t ? new Date(t).toISOString().replace("T", " ").slice(0, 19) + " UTC" : "n/a";
const num = (v, d = 0) => (v === null || v === undefined) ? "n/a" : Number(v).toLocaleString(undefined, {maximumFractionDigits: d});
let state = {region: null, incident: null, conversation: null, map: null, mapLayer: null};

async function api(path, opts = {}) {
  const r = await fetch(path, {headers: {"Content-Type": "application/json"}, ...opts});
  const body = await r.json().catch(() => ({error: r.statusText}));
  if (!r.ok) throw new Error(body.error || r.statusText);
  return body;
}

async function init() {
  const me = await api("/api/me");
  $("#who").textContent = `${me.user || "local"} · regions: ${me.regions.join(", ") || "none"}`;
  const sel = $("#region");
  sel.innerHTML = me.regions.map((r) => `<option>${esc(r)}</option>`).join("");
  sel.onchange = () => selectRegion(sel.value);
  document.querySelectorAll(".tabs button").forEach((b) => b.onclick = () => showTab(b.dataset.tab));
  $("#genie-form").onsubmit = askGenie;
  $("#genie-new").onclick = () => { state.conversation = null; $("#genie-out").innerHTML = ""; };
  loadKpis();
  if (me.regions.length) selectRegion(me.regions.includes("NSW") ? "NSW" : me.regions[0]);
  else $("#incident-list").innerHTML = `<p class="muted">You are not in any NOC region group.</p>`;
}

function showTab(t) {
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === t));
  document.querySelectorAll(".pane").forEach((p) => p.classList.toggle("active", p.id === t));
  if (t === "map" && state.map) setTimeout(() => state.map.invalidateSize(), 50);
}

async function loadKpis() {
  try {
    const k = await api("/api/kpis");
    const tiles = k.operational.map((r) => `<div class="kpi"><b>${num(r.mttd_s, 0)} s</b><span>${esc(r.region_code)} MTTD · ${num(r.pct_detected_within_5min, 0)} % ≤ 5 min · ${r.n_open_incidents} open</span></div>`);
    const sc = k.scorecard;
    tiles.push(sc && sc.available
      ? `<div class="kpi"><b>${num(sc.impact_within_5min_pct, 1)} %</b><span>scored: faults detected ≤ 5 min (median ${num(sc.impact_median_ttd_s, 0)} s, evaluation)</span></div>`
      : `<div class="kpi"><b>n/a</b><span>scored KPI: national NOC only</span></div>`);
    $("#kpis").innerHTML = tiles.join("");
  } catch (e) { $("#kpis").innerHTML = `<span class="err">KPIs: ${esc(e.message)}</span>`; }
}

async function selectRegion(region) {
  state.region = region; state.incident = null;
  $("#detail").innerHTML = `<p class="muted">Select an incident.</p>`;
  await loadIncidentList();
  renderTopology(await api(`/api/regions/${encodeURIComponent(region)}/topology`));
}

async function loadIncidentList() {
  const region = state.region;
  const {incidents} = await api(`/api/incidents?region=${encodeURIComponent(region)}`);
  $("#inc-count").textContent = incidents.length;
  $("#incident-list").innerHTML = incidents.map((i) => `
    <div class="inc${i.incident_id === state.incident ? " sel" : ""}" data-id="${esc(i.incident_id)}">
      <div class="el">${esc(i.suspect_1_id)} <span class="tag">${esc(i.suspect_1_type)}</span></div>
      <div>${esc(i.fault_hypothesis || "")} · ${num(i.n_impacted_cells)} cells · ~${num(i.est_affected_subscribers)} subs</div>
      <div class="id">${esc(i.incident_id)} · ${fmtTs(i.detected_ts)} <span class="tag ${esc(i.sms_decision)}">SMS ${esc(i.sms_decision)}</span></div>
    </div>`).join("") || `<p class="muted">No open incidents in ${esc(region)}.</p>`;
  document.querySelectorAll(".inc").forEach((d) => d.onclick = () => selectIncident(d.dataset.id));
}

async function selectIncident(id) {
  state.incident = id;
  document.querySelectorAll(".inc").forEach((d) => d.classList.toggle("sel", d.dataset.id === id));
  $("#detail").innerHTML = `<p class="muted">Loading ${esc(id)}…</p>`;
  const [inc, topo] = await Promise.all([api(`/api/incidents/${encodeURIComponent(id)}`),
    api(`/api/regions/${encodeURIComponent(state.region)}/topology?incident_id=${encodeURIComponent(id)}`)]);
  renderTopology(topo);
  renderIncident(inc);
}

function renderTopology(t) {
  const g = t.graph, svg = $("#topo-svg");
  $("#topo-title").textContent = g.view === "incident"
    ? `incident ${t.incident_id}: path from core to suspects` : `${t.region} overview: ${t.n_elements} elements (healthy ones collapsed)`;
  const W = Math.max(svg.parentElement.clientWidth - 10, 600), rowH = 78, H = (g.max_depth + 1) * rowH + 40;
  const leaves = g.nodes.filter((n) => !g.edges.some((e) => e.source === n.id)).length;
  const width = Math.max(W, leaves * 112);
  svg.setAttribute("viewBox", `0 0 ${width} ${H}`); svg.style.height = H + "px"; svg.style.width = width + "px";
  const pos = {}; g.nodes.forEach((n) => pos[n.id] = [30 + n.x * (width - 60), 24 + n.depth * rowH]);
  const onPath = new Set(g.path || []);
  let out = g.edges.map((e) => {
    const [x1, y1] = pos[e.source], [x2, y2] = pos[e.target];
    const hot = onPath.has(e.source) && (onPath.has(e.target) || (g.pinpoint === e.target));
    return `<path d="M${x1},${y1} C${x1},${(y1 + y2) / 2} ${x2},${(y1 + y2) / 2} ${x2},${y2}" fill="none" stroke="${hot ? "#ff3b6b" : "#33485c"}" stroke-width="${hot ? 3 : 1.2}"/>`;
  }).join("");
  out += g.nodes.map((n) => {
    const [x, y] = pos[n.id];
    if (n.kind === "collapsed") return `<g><rect x="${x - 22}" y="${y - 9}" width="44" height="18" rx="9" fill="#24364a"/><text x="${x}" y="${y + 4}" text-anchor="middle">+${n.count}</text></g>`;
    const r = n.highlight === "pinpoint" ? 11 : n.highlight === "suspect" ? 9 : 7;
    const ring = n.highlight === "pinpoint" ? `<circle cx="${x}" cy="${y}" r="${r + 6}" fill="none" stroke="#ff3b6b" stroke-width="3"><animate attributeName="r" values="${r + 4};${r + 9};${r + 4}" dur="1.6s" repeatCount="indefinite"/></circle>`
      : n.highlight === "suspect" ? `<circle cx="${x}" cy="${y}" r="${r + 4}" fill="none" stroke="#ffb020" stroke-width="2.5"/>` : "";
    const short = n.element_type === "CELL" ? n.id.split("-").pop() : n.id;  // cells: sector (4G1), site is the parent
    const label = n.suspect_rank ? `#${n.suspect_rank} ${n.id} (${num(n.suspect_score, 2)})` : short;
    return `<g><title>${esc(n.name)} · ${esc(n.element_type)} · ${esc(n.state)}${n.rca_score != null ? " · score " + num(n.rca_score, 2) : ""}</title>${ring}
      <circle cx="${x}" cy="${y}" r="${r}" fill="${COLORS[n.state] || COLORS.ok}" stroke="#0f1720"/>
      <text x="${x}" y="${y + r + 12}" text-anchor="middle" class="${n.highlight ? "" : "lbl-muted"}">${esc(label)}</text></g>`;
  }).join("");
  svg.innerHTML = out;
  renderMap(t);
}

function renderMap(t) {
  if (!window.L) { $("#map").innerHTML = `<p class="muted">Map library not reachable.</p>`; return; }
  if (!state.map) {
    state.map = L.map("map", {preferCanvas: true});
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {maxZoom: 18, attribution: "© OpenStreetMap"}).addTo(state.map);
  }
  if (state.mapLayer) state.mapLayer.remove();
  const layer = L.layerGroup(), focus = [];
  [...t.map].sort((a, b) => (a.suspect_rank ? 1 : 0) - (b.suspect_rank ? 1 : 0)).forEach((p) => {
    const sus = p.suspect_rank, big = sus === 1 ? 12 : sus ? 9 : (p.element_type === "SITE" ? 4 : 6);
    const m = L.circleMarker([p.lat, p.lon], {radius: big, color: sus === 1 ? "#ff3b6b" : sus ? "#ffb020" : "#0f1720",
      weight: sus ? 3 : 1, fillColor: COLORS[p.state] || COLORS.ok, fillOpacity: 0.9});
    m.bindTooltip(`${esc(p.name)}<br>${esc(p.element_type)} · ${esc(p.state)}${sus ? " · suspect #" + sus : ""}`);
    m.addTo(layer); if (sus) focus.push([p.lat, p.lon]);
  });
  layer.addTo(state.map); state.mapLayer = layer;
  const pts = focus.length ? focus : t.map.map((p) => [p.lat, p.lon]);
  if (pts.length) state.map.fitBounds(L.latLngBounds(pts).pad(focus.length ? 2.5 : 0.05), {maxZoom: 13});
}

function renderIncident(d) {
  const det = d.detection || {}, pin = d.pinpoint || {}, sms = d.sms || {};
  const path = (d.path_from_core || []).map((p) => `${esc(p.element_id)} <span class="tag">${esc(p.state)}</span>`).join(" → ");
  $("#detail").innerHTML = `
    <h2>${esc(d.incident_id)} <span class="tag">${esc(d.region_code)}</span></h2>
    <div class="pin-box"><div class="muted small">Failing element (ranker suspect #1)</div>
      <div class="big">${esc(pin.element_id)} · ${esc(pin.name || "")}</div>
      <div>${esc(pin.element_type)} · state ${esc(pin.state)} · score ${num(pin.score, 2)} · ${num(pin.n_impacted_cells)} / ${num(pin.n_desc_cells)} cells impacted</div>
      <div class="path">${path}</div></div>
    <h3>Detection</h3><div class="kv">
      <div>first anomaly</div><div>${fmtTs(det.first_impact_signal_ts)}</div>
      <div>detected (impact)</div><div>${fmtTs(det.first_detection_ts)}</div>
      <div>time to detect</div><div><b>${num(det.time_to_detect_s, 0)} s</b> ${det.detected_within_5min ? "✓ within 5 min" : det.available ? "✗ over 5 min" : ""}</div>
      <div>incident opened</div><div>${fmtTs(d.detected_ts)} (ranker v${esc(d.model_version)})</div></div>
    <h3>Impact (counts only)</h3><div class="kv">
      <div>impacted cells</div><div>${num(d.impact.impacted_cells)}</div><div>impacted sites</div><div>${num(d.impact.impacted_sites)}</div>
      <div>est. affected subscribers</div><div>${num(d.impact.est_affected_subscribers)}</div></div>
    <h3>Top-3 suspects (RCA ranker)</h3><table><tr><th>#</th><th>element</th><th>type</th><th>score</th><th>state</th></tr>
      ${d.suspects.map((s) => `<tr><td>${s.rank}</td><td>${esc(s.element_id)}</td><td>${esc(s.element_type)}</td><td>${num(s.score, 3)}</td><td>${esc(s.state || "")}</td></tr>`).join("")}</table>
    <h3>Gen AI root-cause summary <span class="tag">${esc(d.ai.confidence || "")}</span>${d.ai.agrees_with_ranker ? "" : ' <span class="tag rejected">differs from ranker</span>'}</h3>
      <div><b>${esc(d.ai.likely_root_cause || "")}</b> · ${esc(d.ai.fault_hypothesis || "")}</div><p>${esc(d.ai.summary || "No summary yet.")}</p>
      <ol>${(d.ai.next_steps || []).map((s) => `<li>${esc(typeof s === "string" ? s : JSON.stringify(s))}</li>`).join("")}</ol>
    <h3>Customer SMS draft <span id="sms-tag" class="tag ${esc(sms.decision)}">${esc(sms.decision)}</span></h3>
      <div class="sms">${esc(sms.text || "No draft.")}</div>
      <div class="muted small">${esc(sms.note)}${sms.reviewed_by ? ` Last decision by ${esc(sms.reviewed_by)} at ${fmtTs(sms.reviewed_at)}.` : ""}</div>
      ${sms.text ? `<p><input id="sms-note" placeholder="note (optional)" style="width:100%"></p>
      <button class="approve" id="sms-approve">Approve draft</button> <button class="reject" id="sms-reject">Reject draft</button>
      <div id="sms-msg" class="small"></div><div id="sms-history"></div>` : ""}`;
  if (sms.text) {
    $("#sms-approve").onclick = () => review(d, "approve");
    $("#sms-reject").onclick = () => review(d, "reject");
    loadReviews(d.incident_id);
  }
}

async function review(d, decision) {
  const btns = [$("#sms-approve"), $("#sms-reject")]; btns.forEach((b) => b.disabled = true);
  try {
    const r = await api(`/api/incidents/${encodeURIComponent(d.incident_id)}/sms-review`, {method: "POST",
      body: JSON.stringify({decision, summary_id: d.sms.summary_id, note: $("#sms-note").value || null})});
    $("#sms-tag").className = `tag ${r.decision}`; $("#sms-tag").textContent = r.decision;
    $("#sms-msg").innerHTML = `Recorded <b>${esc(r.decision)}</b> by ${esc(r.reviewed_by)} at ${fmtTs(r.reviewed_at)} (not sent).`;
    loadReviews(d.incident_id);
    loadIncidentList();
  } catch (e) { $("#sms-msg").innerHTML = `<span class="err">${esc(e.message)}</span>`; }
  btns.forEach((b) => b.disabled = false);
}

async function loadReviews(id) {
  const {reviews} = await api(`/api/incidents/${encodeURIComponent(id)}/sms-reviews`);
  $("#sms-history").innerHTML = reviews.length ? `<h3>Review history (Lakebase)</h3><table><tr><th>when</th><th>decision</th><th>by</th><th>note</th></tr>${
    reviews.map((r) => `<tr><td>${fmtTs(r.reviewed_at)}</td><td>${esc(r.decision)}</td><td>${esc(r.reviewed_by)}</td><td>${esc(r.note || "")}</td></tr>`).join("")}</table>` : "";
}

async function askGenie(ev) {
  ev.preventDefault();
  const q = $("#genie-q").value.trim(); if (!q) return;
  const box = document.createElement("div"); box.className = "genie-ans";
  box.innerHTML = `<b>${esc(q)}</b><div class="muted">Genie is thinking…</div>`;
  $("#genie-out").prepend(box);
  try {
    const a = await api("/api/genie/ask", {method: "POST", body: JSON.stringify({question: q, conversation_id: state.conversation})});
    state.conversation = a.conversation_id;
    const table = a.columns.length ? `<table><tr>${a.columns.map((c) => `<th>${esc(c)}</th>`).join("")}</tr>${
      a.rows.slice(0, 50).map((r) => `<tr>${r.map((v) => `<td>${esc(v)}</td>`).join("")}</tr>`).join("")}</table>
      <div class="muted small">${a.row_count} row(s)</div>` : "";
    box.innerHTML = `<b>${esc(q)}</b><p>${esc((a.text || []).join(" ") || a.description || "")}</p>${table}
      ${a.sql ? `<details><summary class="muted small">generated SQL</summary><pre>${esc(a.sql)}</pre></details>` : ""}
      ${a.error ? `<div class="err">${esc(a.error)}</div>` : ""}`;
  } catch (e) { box.innerHTML = `<b>${esc(q)}</b><div class="err">${esc(e.message)}</div>`; }
}

init().catch((e) => { document.body.insertAdjacentHTML("afterbegin", `<div class="err">${esc(e.message)}</div>`); });
