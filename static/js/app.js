let dataset = null;
let facts   = null;
let story   = "";
let chart   = null;

const els = {
  sourceLabel:  document.getElementById("source-label"),
  sourceNotes:  document.getElementById("source-notes"),
  sourceLink:   document.getElementById("source-link"),
  uploadForm:   document.getElementById("upload-form"),
  csvFile:      document.getElementById("csv-file"),
  startYear:    document.getElementById("start-year"),
  endYear:      document.getElementById("end-year"),
  location:     document.getElementById("location"),
  tone:         document.getElementById("tone"),
  length:       document.getElementById("length"),
  analyzeBtn:   document.getElementById("analyze-btn"),
  status:       document.getElementById("status-pill"),
  story:        document.getElementById("story-output"),
  facts:        document.getElementById("facts-list"),
  history:      document.getElementById("history"),
  chartTitle:   document.getElementById("chart-title"),
  chartSubtitle:document.getElementById("chart-subtitle"),
  downloadFacts:document.getElementById("download-facts"),
  downloadStory:document.getElementById("download-story"),
};

/* ── Status pill ──────────────────────────────────────────────── */
function setStatus(text, busy = false) {
  els.status.textContent = text;
  els.status.classList.toggle("busy", busy);
}

/* ── Fetch helper ─────────────────────────────────────────────── */
async function fetchJSON(url, options) {
  const res  = await fetch(url, options);
  const data = await res.json();
  if (!res.ok || data.error) throw new Error(data.error || "Request failed");
  return data;
}

/* ── Chart ────────────────────────────────────────────────────── */
function renderChart(series, trend) {
  const ctx = document.getElementById("climate-chart").getContext("2d");
  if (chart) chart.destroy();

  // Ocean-dark palette
  const tealAlpha = "rgba(0,212,180,";
  const redAlpha  = "rgba(232,113,74,";

  chart = new Chart(ctx, {
    type: "line",
    data: {
      labels: series.map(p => p.year),
      datasets: [
        {
          label: dataset?.meta?.value_label || "Value",
          data:  series.map(p => p.value),
          borderColor:     tealAlpha + "0.9)",
          backgroundColor: tealAlpha + "0.06)",
          pointRadius: 0,
          borderWidth: 2,
          fill: true,
          tension: 0.2,
        },
        {
          label: "Trend",
          data:  trend ? trend.map(p => p.value) : [],
          borderColor: redAlpha + "0.75)",
          borderDash:  [6, 5],
          pointRadius: 0,
          borderWidth: 1.8,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          labels: {
            boxWidth: 12,
            font: { size: 11, family: "'DM Mono', monospace" },
            color: "#8394b0",
          },
        },
        tooltip: {
          backgroundColor: "rgba(13,18,32,0.92)",
          borderColor:     "rgba(30,45,69,0.8)",
          borderWidth: 1,
          titleColor: "#e2e9f4",
          bodyColor:  "#8394b0",
          callbacks: {
            label: item => `${item.dataset.label}: ${Number(item.raw).toFixed(3)}`,
          },
        },
      },
      scales: {
        x: {
          ticks: { maxTicksLimit: 10, color: "#3f506a", font: { size: 11 } },
          grid:  { display: false },
          border:{ color: "#1e2d45" },
        },
        y: {
          ticks: { color: "#3f506a", font: { size: 11 } },
          grid:  { color: "rgba(30,45,69,0.6)" },
          border:{ color: "#1e2d45" },
        },
      },
    },
  });
}

/* ── Dataset ──────────────────────────────────────────────────── */
function setDataset(next) {
  dataset = next;
  facts   = null;
  story   = "";
  const meta = dataset.meta;

  els.sourceLabel.textContent   = meta.label;
  els.sourceNotes.textContent   = meta.notes || "No notes supplied.";
  els.sourceLink.href           = meta.citation_url || "#";
  els.sourceLink.style.display  = meta.citation_url ? "inline" : "none";

  els.startYear.min   = dataset.min_year;
  els.startYear.max   = dataset.max_year;
  els.endYear.min     = dataset.min_year;
  els.endYear.max     = dataset.max_year;
  els.startYear.value = dataset.min_year;
  els.endYear.value   = dataset.max_year;

  els.chartTitle.textContent    = meta.label;
  els.chartSubtitle.textContent = `${dataset.min_year}–${dataset.max_year} · ${meta.source}`;

  renderChart(dataset.series, null);
  renderEmptyFacts();
  els.story.textContent = "Facts load automatically. Click Weave narrative when you are ready.";
  els.story.classList.remove("has-content");
  els.downloadFacts.disabled = true;
  els.downloadStory.disabled = true;
  refreshFacts();
}

/* ── Facts rendering ──────────────────────────────────────────── */
function renderFacts(f) {
  const unit = f.dataset.unit;
  document.getElementById("stat-shift").textContent = `${f.net_change} ${unit}`;
  document.getElementById("stat-trend").textContent = `${f.trend_per_decade} ${unit}`;
  document.getElementById("stat-peak").textContent  = `${f.peak.value} (${f.peak.year})`;
  document.getElementById("stat-r2").textContent    = `${Math.round(f.r2 * 100)}%`;

  const rows = [
    ["Dataset",     f.dataset.label],
    ["Location",    f.location],
    ["Timeframe",   `${f.start_year} to ${f.end_year} (${f.points} pts)`],
    ["Start",       `${f.start_value} ${unit}`],
    ["End",         `${f.end_value} ${unit}`],
    ["Net change",  `${f.net_change} ${unit}`],
    ["Trend",       `${f.trend_per_year} ${unit}/yr (${f.trend_per_decade}/decade)`],
    ["Peak",        `${f.peak.value} ${unit} in ${f.peak.year}`],
    ["Trough",      `${f.trough.value} ${unit} in ${f.trough.year}`],
    ["Volatility",  `${f.volatility}`],
    ["Source",      f.dataset.source],
  ];
  els.facts.innerHTML = rows.map(([k, v]) =>
    `<dt>${escapeHTML(k)}</dt><dd>${escapeHTML(v)}</dd>`
  ).join("");
}

function renderEmptyFacts() {
  ["stat-shift","stat-trend","stat-peak","stat-r2"].forEach(id => {
    document.getElementById(id).textContent = "—";
  });
  els.facts.innerHTML = "<dt>Status</dt><dd>Waiting for analysis.</dd>";
}

function escapeHTML(v) {
  return String(v)
    .replaceAll("&","&amp;").replaceAll("<","&lt;")
    .replaceAll(">","&gt;").replaceAll('"',"&quot;");
}

/* ── Analyze ──────────────────────────────────────────────────── */
async function analyze() {
  if (!dataset) return;
  const start = Number(els.startYear.value);
  const end   = Number(els.endYear.value);
  if (start >= end) { alert("Start year must be before end year."); return; }

  setStatus("Weaving…", true);
  els.analyzeBtn.disabled = true;
  els.story.textContent = "";
  els.story.classList.remove("has-content");

  try {
    const data = await fetchJSON("/api/analyze", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        series:     dataset.series,
        meta:       dataset.meta,
        start_year: start,
        end_year:   end,
        location:   els.location.value,
        tone:       els.tone.value,
        length:     els.length.value,
      }),
    });

    facts = data.facts;
    story = data.story;
    renderFacts(facts);
    renderChart(facts.series, facts.trend);

    // Typewriter effect
    els.story.textContent = "";
    els.story.classList.add("has-content");
    await typewrite(els.story, story);

    els.downloadFacts.disabled = false;
    els.downloadStory.disabled = false;
    setStatus(`Run #${data.run_id}`);
    loadHistory();
  } catch (err) {
    alert(err.message);
    setStatus("Error");
  } finally {
    els.analyzeBtn.disabled = false;
  }
}

/* ── Typewriter ───────────────────────────────────────────────── */
async function typewrite(el, text, speed = 12) {
  el.innerHTML = "";
  const cursor = document.createElement("span");
  cursor.className = "cursor";
  el.appendChild(cursor);

  for (let i = 0; i < text.length; i++) {
    const t = document.createTextNode(text[i]);
    el.insertBefore(t, cursor);
    if (i % 4 === 0) await new Promise(r => setTimeout(r, speed));
  }
  cursor.remove();
}

/* ── Refresh facts (on range/location change) ─────────────────── */
async function refreshFacts() {
  if (!dataset) return;
  const start = Number(els.startYear.value);
  const end   = Number(els.endYear.value);
  if (!start || !end || start >= end) return;

  setStatus("Updating…", true);
  try {
    const data = await fetchJSON("/api/facts", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        series:     dataset.series,
        meta:       dataset.meta,
        start_year: start,
        end_year:   end,
        location:   els.location.value,
      }),
    });
    facts = data.facts;
    renderFacts(facts);
    renderChart(facts.series, facts.trend);
    els.downloadFacts.disabled = false;
    setStatus("Facts ready");
  } catch { setStatus("Error"); }
}

/* ── Default data load ────────────────────────────────────────── */
async function loadDefault() {
  setStatus("Loading…", true);
  const data = await fetchJSON("/api/default-data");
  setDataset(data);
  setStatus("Ready");
}

/* ── CSV upload ───────────────────────────────────────────────── */
async function uploadCSV(event) {
  event.preventDefault();
  if (!els.csvFile.files.length) { alert("Choose a CSV file first."); return; }
  const form = new FormData();
  form.append("file", els.csvFile.files[0]);
  form.append("dataset_label", document.getElementById("dataset-label").value);
  form.append("unit",          document.getElementById("dataset-unit").value);
  setStatus("Parsing…", true);
  try {
    const data = await fetchJSON("/api/upload", { method: "POST", body: form });
    setDataset(data);
    setStatus("CSV loaded");
  } catch (err) {
    alert(err.message);
    setStatus("Error");
  }
}

/* ── History ──────────────────────────────────────────────────── */
async function loadHistory() {
  try {
    const rows = await fetchJSON("/api/history");
    if (!rows.length) {
      els.history.innerHTML = '<span class="muted">No runs yet.</span>';
      return;
    }
    els.history.innerHTML = rows.map(r =>
      `<div class="history-item">
        <strong>${escapeHTML(r.dataset_label)}</strong><br>
        ${escapeHTML(r.location)} · ${r.start_year}–${r.end_year}
      </div>`
    ).join("");
  } catch {
    els.history.innerHTML = '<span class="muted">History unavailable.</span>';
  }
}

/* ── Download ─────────────────────────────────────────────────── */
function download(filename, text, mime = "text/plain") {
  const blob = new Blob([text], { type: mime });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  a.remove(); URL.revokeObjectURL(url);
}

/* ── Events ───────────────────────────────────────────────────── */
document.querySelectorAll(".segment").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".segment").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    const uploadMode = btn.dataset.source === "upload";
    els.uploadForm.classList.toggle("hidden", !uploadMode);
    if (!uploadMode) loadDefault();
  });
});

document.getElementById("upload-form").addEventListener("submit", uploadCSV);
els.analyzeBtn.addEventListener("click", analyze);
els.startYear.addEventListener("change", refreshFacts);
els.endYear.addEventListener("change", refreshFacts);
els.location.addEventListener("change", refreshFacts);

els.downloadFacts.addEventListener("click", () => {
  if (facts) download("tidetales-fact-pack.json", JSON.stringify(facts, null, 2), "application/json");
});
els.downloadStory.addEventListener("click", () => {
  if (story) download("tidetales-story.txt", story);
});

/* ── Boot ─────────────────────────────────────────────────────── */
loadDefault().then(loadHistory).catch(err => {
  setStatus("Error");
  alert(err.message);
});
