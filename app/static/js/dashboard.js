let currentPage = 1;
let charts = {};
let editMode = false;
let currentLayout = { order: [], hidden: [] };
let originalLayout = null;

const BLOCK_TITLES = {
  summary: "金额卡",
  daily: "每日用量",
  models_endpoints: "模型 / 接口分布",
  heatmap_weekly: "7×24 周热力图",
  heatmap_year: "一年热力图",
  records: "原始数据",
};

function fmt(n) { return "¥" + Number(n || 0).toFixed(2); }
function fmtInt(n) { return Number(n || 0).toLocaleString("zh-CN"); }

function destroyCharts() {
  Object.values(charts).forEach(c => c.dispose());
  charts = {};
}

function renderDailyChart(daily) {
  const el = document.getElementById("daily-chart");
  charts.daily = echarts.init(el);
  charts.daily.setOption({
    tooltip: {
      trigger: "axis",
      formatter: (params) => {
        const day = params[0].axisValue;
        const dayData = daily.find(d => d.day === day) || {};
        let html = `<b>${day}</b><br>`;
        params.forEach(p => {
          if (p.seriesName === "估算价值") {
            html += `${p.marker}${p.seriesName}: ¥${Number(p.data || 0).toFixed(4)}<br>`;
          } else {
            html += `${p.marker}${p.seriesName}: ${fmtInt(p.data || 0)}<br>`;
          }
        });
        html += `<span style="color:#999">缓存命中率: ${(dayData.cache_hit_rate || 0).toFixed(2)}%</span>`;
        return html;
      },
    },
    legend: { data: ["输入", "输出", "缓存读取", "缓存创建"] },
    grid: { left: 60, right: 60, top: 40, bottom: 40 },
    xAxis: { type: "category", data: daily.map(d => d.day) },
    yAxis: [
      { type: "value", name: "Tokens" },
      { type: "value", name: "¥", position: "right" },
    ],
    series: [
      { name: "输入", type: "bar", stack: "t", data: daily.map(d => d.input_tokens), itemStyle: { color: "#52c41a" } },
      { name: "输出", type: "bar", stack: "t", data: daily.map(d => d.output_tokens), itemStyle: { color: "#fa8c16" } },
      { name: "缓存读取", type: "bar", stack: "t", data: daily.map(d => d.cache_read_tokens), itemStyle: { color: "#13c2c2" } },
      { name: "缓存创建", type: "bar", stack: "t", data: daily.map(d => d.cache_create_tokens), itemStyle: { color: "#722ed1" } },
      { name: "估算价值", type: "line", yAxisIndex: 1, data: daily.map(d => d.estimated_cost), itemStyle: { color: "#1677ff" } },
    ],
  });
}

function renderPie(elId, data, nameField) {
  const el = document.getElementById(elId);
  charts[elId] = echarts.init(el);
  charts[elId].setOption({
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    series: [{
      type: "pie", radius: ["40%", "70%"],
      data: data.map(d => ({ name: d[nameField], value: d.tokens })),
    }],
  });
}

function renderHeatmap(cells) {
  const el = document.getElementById("heatmap");
  charts.heatmap = echarts.init(el);
  const hours = Array.from({ length: 24 }, (_, i) => i + ":00");
  const dows = ["日", "一", "二", "三", "四", "五", "六"];
  const data = cells.map(c => [c.hour, c.dow, c.tokens]);
  charts.heatmap.setOption({
    tooltip: { position: "top", formatter: p => `${dows[p.data[1]]} ${p.data[0]}:00<br>${fmtInt(p.data[2])} tokens` },
    grid: { left: 50, right: 20, top: 20, bottom: 40 },
    xAxis: { type: "category", data: hours, splitArea: { show: true } },
    yAxis: { type: "category", data: dows, splitArea: { show: true } },
    visualMap: { min: 0, max: Math.max(1, ...cells.map(c => c.tokens)), calculable: true, orient: "horizontal", left: "center", bottom: 0 },
    series: [{ type: "heatmap", data, label: { show: false } }],
  });
}

function renderYearHeatmap(yr) {
  const el = document.getElementById("year-heatmap");
  if (charts.year) { charts.year.dispose(); delete charts.year; }
  el.innerHTML = "";

  if (!yr || !yr.cells || !yr.cells.length) return;

  const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const dayLabels = ["Mon", "Wed", "Fri"];
  const startD = new Date(yr.range[0] + "T00:00:00");
  const endD = new Date(yr.range[1] + "T00:00:00");

  const monthLabelsEl = document.createElement("div");
  monthLabelsEl.className = "yh-months";
  let cur = new Date(startD);
  while (cur <= endD) {
    if (cur.getDate() === 1 || cur.getTime() === startD.getTime()) {
      const span = document.createElement("span");
      span.textContent = monthNames[cur.getMonth()];
      monthLabelsEl.appendChild(span);
    } else {
      monthLabelsEl.appendChild(document.createElement("span"));
    }
    cur.setDate(cur.getDate() + 1);
    if (monthLabelsEl.children.length >= 12) break;
  }
  while (monthLabelsEl.children.length < 12) {
    monthLabelsEl.appendChild(document.createElement("span"));
  }
  el.appendChild(monthLabelsEl);

  const dayLabelsEl = document.createElement("div");
  dayLabelsEl.className = "yh-day-labels";
  for (let i = 0; i < 7; i++) {
    const span = document.createElement("span");
    if (i === 1 || i === 3 || i === 5) span.textContent = dayLabels[(i - 1) / 2];
    dayLabelsEl.appendChild(span);
  }
  el.appendChild(dayLabelsEl);

  const monthStart = startD.getMonth() + 1;
  const grid = document.createElement("div");
  grid.className = "yh-grid";

  yr.cells.forEach(c => {
    const cell = document.createElement("div");
    cell.className = `yh-cell yh-lv${c.level}`;
    cell.style.gridColumn = (c.month - monthStart + 1 + (c.month < monthStart ? 12 : 0)).toString();
    cell.style.gridRow = (c.dow + 1).toString();
    cell.dataset.date = c.date;
    cell.title = `${c.date}: ${fmtInt(c.tokens)} tokens`;
    grid.appendChild(cell);
  });

  el.appendChild(grid);

  const legend = document.createElement("div");
  legend.className = "yh-legend";
  const learn = document.createElement("a");
  learn.textContent = "Learn how we count contributions";
  learn.onclick = (e) => { e.preventDefault(); toast("缓存命中等级: 0=无, 1=25%分位, 2=50%分位, 3=75%分位, 4=最高", "success"); };
  legend.appendChild(learn);
  const scale = document.createElement("div");
  scale.className = "yh-scale";
  const less = document.createElement("span");
  less.textContent = "Less";
  scale.appendChild(less);
  for (let i = 0; i < 5; i++) {
    const sample = document.createElement("span");
    sample.className = `yh-cell yh-lv${i}`;
    scale.appendChild(sample);
  }
  const more = document.createElement("span");
  more.textContent = "More";
  scale.appendChild(more);
  legend.appendChild(scale);
  el.appendChild(legend);
}

async function loadDashboard() {
  destroyCharts();
  const r = await fetch("/api/dashboard");
  if (!r.ok) { toast("加载失败: " + r.status, "error"); return; }
  const d = await r.json();
  const s = d.summary;

  document.getElementById("actual-cost").textContent = fmt(s.actual_cost);
  document.getElementById("estimated-cost").textContent = fmt(s.estimated_cost);
  document.getElementById("cache-hit-rate").textContent = (s.cache_hit_rate || 0).toFixed(2) + "%";
  document.getElementById("mode-badge").textContent = d.billing_mode;
  document.getElementById("time-range").textContent =
    s.earliest ? `${s.earliest} ~ ${s.latest}` : "暂无数据";

  if (d.billing_mode === "token_plan" && !currentLayout.hidden.includes("summary")) {
    const saving = (s.estimated_cost || 0) - (s.actual_cost || 0);
    document.getElementById("saving-banner").style.display = "block";
    document.getElementById("saving-amount").textContent = fmt(saving);
  } else {
    document.getElementById("saving-banner").style.display = "none";
  }

  if (!currentLayout.hidden.includes("daily")) renderDailyChart(d.daily);
  if (!currentLayout.hidden.includes("models_endpoints")) {
    renderPie("model-pie", d.by_model, "model");
    renderPie("endpoint-pie", d.by_endpoint, "endpoint");
  }
  if (!currentLayout.hidden.includes("heatmap_weekly")) renderHeatmap(d.heatmap);
  if (!currentLayout.hidden.includes("heatmap_year")) renderYearHeatmap(d.year_heatmap);

  if (!currentLayout.hidden.includes("records")) {
    await loadFilterOptions();
    await loadRecords();
  }
}

async function loadFilterOptions() {
  const r = await fetch("/api/dashboard");
  const d = await r.json();
  const m = document.getElementById("filter-model");
  d.by_model.forEach(x => {
    if (![...m.options].some(o => o.value === x.model)) {
      const o = document.createElement("option");
      o.value = x.model; o.textContent = x.model;
      m.appendChild(o);
    }
  });
  const ep = document.getElementById("filter-endpoint");
  d.by_endpoint.forEach(x => {
    if (![...ep.options].some(o => o.value === x.endpoint)) {
      const o = document.createElement("option");
      o.value = x.endpoint; o.textContent = x.endpoint;
      ep.appendChild(o);
    }
  });
}

async function loadRecords() {
  const params = new URLSearchParams({
    page: currentPage, size: 50,
    model: document.getElementById("filter-model").value,
    endpoint: document.getElementById("filter-endpoint").value,
    date_from: document.getElementById("filter-from").value,
    date_to: document.getElementById("filter-to").value,
  });
  const r = await fetch("/api/records?" + params);
  const d = await r.json();
  const tbody = document.querySelector("#records-table tbody");
  tbody.innerHTML = "";
  d.rows.forEach(row => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.bucket_start}</td>
      <td>${row.model}</td>
      <td>${row.endpoint}</td>
      <td>${fmtInt(row.input_tokens)}</td>
      <td>${fmtInt(row.output_tokens)}</td>
      <td>${fmtInt(row.total_tokens)}</td>
      <td>${fmt(row.cost)}</td>`;
    tbody.appendChild(tr);
  });
  const totalPages = Math.max(1, Math.ceil(d.total / d.size));
  document.getElementById("page-info").textContent = `${d.page}/${totalPages} (共 ${d.total} 条)`;
}

function prevPage() { if (currentPage > 1) { currentPage--; loadRecords(); } }
function nextPage() { currentPage++; loadRecords(); }

function applyLayout() {
  const container = document.querySelector(".container");
  const blocks = currentLayout.order.map(name => document.querySelector(`[data-block="${name}"]`)).filter(Boolean);
  blocks.forEach(b => container.appendChild(b));
  currentLayout.hidden.forEach(name => {
    const el = document.querySelector(`[data-block="${name}"]`);
    if (el) el.style.display = "none";
  });
  currentLayout.order.filter(n => !currentLayout.hidden.includes(n)).forEach(name => {
    const el = document.querySelector(`[data-block="${name}"]`);
    if (el) el.style.display = "";
  });
}

function refreshBlockVisuals() {
  destroyCharts();
  loadDashboard();
}

function toggleEditMode() {
  if (editMode) return;
  editMode = true;
  originalLayout = JSON.parse(JSON.stringify(currentLayout));
  document.querySelectorAll(".block-toolbar").forEach(b => b.style.display = "");
  document.getElementById("btn-edit").style.display = "none";
  document.getElementById("btn-save-layout").style.display = "";
  document.getElementById("btn-cancel-layout").style.display = "";
  document.getElementById("edit-hint").style.display = "";
  document.querySelectorAll(".block-hide-btn").forEach(btn => {
    btn.textContent = currentLayout.hidden.includes(btn.closest("[data-block]").dataset.block) ? "🚫" : "👁";
  });
}

function cancelEdit() {
  if (!editMode) return;
  currentLayout = originalLayout;
  editMode = false;
  document.querySelectorAll(".block-toolbar").forEach(b => b.style.display = "none");
  document.getElementById("btn-edit").style.display = "";
  document.getElementById("btn-save-layout").style.display = "none";
  document.getElementById("btn-cancel-layout").style.display = "none";
  document.getElementById("edit-hint").style.display = "none";
  applyLayout();
  refreshBlockVisuals();
}

async function saveLayout() {
  if (!editMode) return;
  await fetch("/api/layout", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(currentLayout),
  });
  toast("布局已保存", "success");
  editMode = false;
  document.querySelectorAll(".block-toolbar").forEach(b => b.style.display = "none");
  document.getElementById("btn-edit").style.display = "";
  document.getElementById("btn-save-layout").style.display = "none";
  document.getElementById("btn-cancel-layout").style.display = "none";
  document.getElementById("edit-hint").style.display = "none";
}

function moveBlock(name, dir) {
  const order = currentLayout.order.slice();
  const i = order.indexOf(name);
  const j = i + dir;
  if (j < 0 || j >= order.length) return;
  [order[i], order[j]] = [order[j], order[i]];
  currentLayout.order = order;
  applyLayout();
}

function toggleBlock(name) {
  const idx = currentLayout.hidden.indexOf(name);
  if (idx >= 0) currentLayout.hidden.splice(idx, 1);
  else currentLayout.hidden.push(name);
  applyLayout();
  refreshBlockVisuals();
  if (editMode) {
    document.querySelectorAll(".block-hide-btn").forEach(btn => {
      const n = btn.closest("[data-block]").dataset.block;
      btn.textContent = currentLayout.hidden.includes(n) ? "🚫" : "👁";
    });
  }
}

async function init() {
  const r = await fetch("/api/layout");
  currentLayout = await r.json();
  applyLayout();
  loadDashboard();
}

window.addEventListener("resize", () => {
  Object.values(charts).forEach(c => c.resize());
});

init();
