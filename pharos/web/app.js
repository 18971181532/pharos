/* Pharos dashboard — vanilla JS, zero dependencies, Canvas 2D charts. */
"use strict";

const PALETTE = ["#58a6ff", "#3fb950", "#bc8cff", "#d29922", "#39c5cf",
                 "#f85149", "#f0883e", "#7ee787", "#79c0ff", "#d2a8ff",
                 "#56d4dd", "#e3b341", "#ff7b72", "#a5d6ff"];

const state = { stats: null };

/* ---------------- helpers ---------------- */
async function api(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function setupCanvas(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const w = rect.width || canvas.width;
  const h = rect.height || canvas.height;
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  return { ctx, w, h };
}

function fmtSize(bytes) {
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (bytes >= 1024 && i < units.length - 1) { bytes /= 1024; i++; }
  return bytes.toFixed(i === 0 ? 0 : 1) + units[i];
}

function escapeHtml(s) {
  return s.replace(/[&<>"]/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function highlight(snippet) {
  // The engine wraps matches in [[ ... ]]
  return escapeHtml(snippet)
    .replace(/\[\[(.+?)\]\]/g, '<mark>$1</mark>');
}

/* ---------------- tabs ---------------- */
document.querySelectorAll(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
    tab.classList.add("active");
    document.getElementById("tab-" + tab.dataset.tab).classList.add("active");
    if (tab.dataset.tab === "overview") renderOverview();
    if (tab.dataset.tab === "terms") renderTermCloud();
    if (tab.dataset.tab === "languages") renderLanguages();
  });
});

/* ---------------- search ---------------- */
async function doSearch(query) {
  const meta = document.getElementById("result-meta");
  const corr = document.getElementById("correction");
  const box = document.getElementById("results");
  meta.textContent = "Searching…";
  corr.classList.add("hidden");
  box.innerHTML = "";
  if (!query.trim()) { meta.textContent = "Enter a query to search the index."; return; }

  const data = await api("/api/search?q=" + encodeURIComponent(query) + "&limit=60");
  meta.textContent = `${data.total} matches in ${data.took_ms} ms`;

  if (data.corrected_query) {
    corr.classList.remove("hidden");
    corr.innerHTML = `No results — did you mean: <a>${escapeHtml(data.corrected_query)}</a>`;
    corr.querySelector("a").addEventListener("click", () => {
      document.getElementById("search-input").value = data.corrected_query;
      doSearch(data.corrected_query);
    });
  }

  box.innerHTML = data.hits.map(h => `
    <div class="result" data-path="${escapeHtml(h.path)}">
      <div class="result-head">
        <span class="result-path">${escapeHtml(h.path)}</span>
        <span class="result-score">score ${h.score.toFixed(2)}</span>
      </div>
      <div class="result-meta-line">
        <span class="lang-badge">${escapeHtml(h.language)}</span>
        ${fmtSize(h.size)} · ${h.matched_terms.slice(0, 6).map(escapeHtml).join(", ")}
      </div>
      ${h.snippets.map(s => `<div class="snippet">${highlight(s)}</div>`).join("")}
    </div>`).join("");

  box.querySelectorAll(".result").forEach(el => {
    el.addEventListener("click", () => openFile(el.dataset.path));
  });
}

async function openFile(path) {
  try {
    const data = await api("/api/file?path=" + encodeURIComponent(path));
    document.getElementById("modal-title").textContent = data.path;
    document.getElementById("modal-body").textContent = data.content;
    document.getElementById("file-modal").classList.remove("hidden");
  } catch (e) { /* ignore */ }
}
document.getElementById("modal-close").addEventListener("click", () =>
  document.getElementById("file-modal").classList.add("hidden"));
document.getElementById("file-modal").addEventListener("click", e => {
  if (e.target.id === "file-modal") e.target.classList.add("hidden");
});

document.getElementById("search-btn").addEventListener("click", () =>
  doSearch(document.getElementById("search-input").value));
document.getElementById("search-input").addEventListener("keydown", e => {
  if (e.key === "Enter") doSearch(e.target.value);
});
document.getElementById("refresh-btn").addEventListener("click", async () => {
  const btn = document.getElementById("refresh-btn");
  btn.textContent = "…";
  await api("/api/refresh");
  state.stats = await api("/api/stats");
  btn.textContent = "↻";
  renderOverview();
});

/* ---------------- overview ---------------- */
function barChart(canvas, items, opts = {}) {
  const { ctx, w, h } = setupCanvas(canvas);
  if (!items.length) return;
  const padL = opts.padL || 150, padB = 30, padT = 10, padR = 30;
  const max = Math.max(...items.map(d => d[1])) || 1;
  const rowH = (h - padT - padB) / items.length;
  const barW = w - padL - padR;
  ctx.font = "12px monospace";
  items.forEach((d, i) => {
    const y = padT + i * rowH;
    const bw = (d[1] / max) * barW;
    ctx.fillStyle = PALETTE[i % PALETTE.length];
    ctx.fillRect(padL, y + 4, Math.max(bw, 2), rowH - 8);
    ctx.fillStyle = "#9aa7b4";
    ctx.textAlign = "right";
    ctx.fillText(d[0].slice(0, 22), padL - 10, y + rowH / 2 + 4);
    ctx.fillStyle = "#e6edf3";
    ctx.textAlign = "left";
    ctx.fillText(String(d[1]), padL + bw + 6, y + rowH / 2 + 4);
  });
}

function donut(canvas, items) {
  const { ctx, w, h } = setupCanvas(canvas);
  const cx = w / 2, cy = h / 2, r = Math.min(w, h) / 2 - 30;
  const total = items.reduce((s, d) => s + d[1], 0) || 1;
  let angle = -Math.PI / 2;
  items.forEach((d, i) => {
    const slice = (d[1] / total) * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, r, angle, angle + slice);
    ctx.closePath();
    ctx.fillStyle = PALETTE[i % PALETTE.length];
    ctx.fill();
    angle += slice;
  });
  ctx.fillStyle = "#161b22";
  ctx.beginPath();
  ctx.arc(cx, cy, r * 0.58, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#e6edf3";
  ctx.font = "bold 26px sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(String(total), cx, cy + 2);
  ctx.fillStyle = "#6e7d8c";
  ctx.font = "12px sans-serif";
  ctx.fillText(opts_label(items), cx, cy + 22);

  // legend
  ctx.font = "12px monospace";
  ctx.textAlign = "left";
  items.slice(0, 8).forEach((d, i) => {
    const ly = 20 + i * 18;
    ctx.fillStyle = PALETTE[i % PALETTE.length];
    ctx.fillRect(10, ly - 9, 10, 10);
    ctx.fillStyle = "#9aa7b4";
    ctx.fillText(`${d[0]} (${d[1]})`, 26, ly);
  });
}
function opts_label(items) {
  if (items.length > 8) return "languages";
  return "files";
}

async function renderOverview() {
  if (!state.stats) state.stats = await api("/api/stats");
  const s = state.stats;
  const cards = [
    ["Documents", s.document_count, "accent"],
    ["Tokens", s.token_count.toLocaleString(), "green"],
    ["Unique Terms", s.unique_terms.toLocaleString(), "purple"],
    ["Languages", Object.keys(s.languages).length, ""],
    ["Index Size", fmtSize(s.total_size), ""],
    ["Index Time", s.index_time.toFixed(2) + "s", ""],
  ];
  document.getElementById("stats-cards").innerHTML = cards.map(c =>
    `<div class="card"><div class="card-label">${c[0]}</div>
     <div class="card-value ${c[2]}">${c[1]}</div></div>`).join("");

  barChart(document.getElementById("terms-canvas"), s.top_terms.slice(0, 15));
  const langItems = Object.entries(s.languages).slice(0, 12);
  donut(document.getElementById("lang-canvas"), langItems);
}

/* ---------------- term cloud ---------------- */
async function renderTermCloud() {
  const data = await api("/api/terms?n=120");
  const max = Math.max(...data.terms.map(t => t[1])) || 1;
  const min = Math.min(...data.terms.map(t => t[1]));
  const cloud = document.getElementById("term-cloud");
  cloud.innerHTML = data.terms.map(([term, df]) => {
    const t = (df - min) / ((max - min) || 1);
    const size = 12 + t * 22;
    const color = PALETTE[Math.floor(t * (PALETTE.length - 1))];
    return `<span title="${df} files" style="font-size:${size.toFixed(1)}px;color:${color}">${escapeHtml(term)}</span>`;
  }).join("");
  cloud.querySelectorAll("span").forEach(el =>
    el.addEventListener("click", () => {
      document.getElementById("search-input").value = el.textContent;
      document.querySelector('.tab[data-tab="results"]').click();
      doSearch(el.textContent);
    }));
}

/* ---------------- languages ---------------- */
async function renderLanguages() {
  if (!state.stats) state.stats = await api("/api/stats");
  const items = Object.entries(state.stats.languages);
  barChart(document.getElementById("lang-bar-canvas"), items, { padL: 140 });
  const tbody = document.querySelector("#ext-table tbody");
  tbody.innerHTML = Object.entries(state.stats.extensions)
    .map(([ext, n]) => `<tr><td>.${escapeHtml(ext)}</td><td>${n}</td></tr>`).join("");
}

/* ---------------- init ---------------- */
renderOverview();
