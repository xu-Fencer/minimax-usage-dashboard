let currentPage = 1;
let charts = {};

function fmt(n) {
  return "¥" + Number(n || 0).toFixed(2);
}
function fmtInt(n) {
  return Number(n || 0).toLocaleString("zh-CN");
}

function destroyCharts() {
  Object.values(charts).forEach(c => c.dispose());
  charts = {};
}

function renderDailyChart(daily) {
  const el = document.getElementById("daily-cost-line");
  charts.daily = echarts.init(el);
  charts.daily.setOption({
    tooltip: { trigger: "axis" },
    legend: { data: ["输入", "输出", "估算价值"] },
    grid: { left: 60, right: 60, top: 40, bottom: 40 },
    xAxis: { type: "category", data: daily.map(d => d.day) },
    yAxis: [
      { type: "value", name: "Tokens" },
      { type: "value", name: "¥", position: "right" },
    ],
    series: [
      { name: "输入", type: "bar", stack: "t", data: daily.map(d => d.input_tokens), itemStyle: { color: "#52c41a" } },
      { name: "输出", type: "bar", stack: "t", data: daily.map(d => d.output_tokens), itemStyle: { color: "#fa8c16" } },
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

async function loadDashboard() {
  destroyCharts();
  const r = await fetch("/api/dashboard");
  if (!r.ok) { toast("加载失败: " + r.status, "error"); return; }
  const d = await r.json();
  const s = d.summary;

  document.getElementById("actual-cost").textContent = fmt(s.actual_cost);
  document.getElementById("estimated-cost").textContent = fmt(s.estimated_cost);
  document.getElementById("mode-badge").textContent = d.billing_mode;
  document.getElementById("time-range").textContent =
    s.earliest ? `${s.earliest} ~ ${s.latest}` : "暂无数据";

  if (d.billing_mode === "token_plan") {
    const saving = (s.estimated_cost || 0) - (s.actual_cost || 0);
    document.getElementById("saving-banner").style.display = "block";
    document.getElementById("saving-amount").textContent = fmt(saving);
  }

  renderDailyChart(d.daily);
  renderPie("model-pie", d.by_model, "model");
  renderPie("endpoint-pie", d.by_endpoint, "endpoint");
  renderHeatmap(d.heatmap);

  await loadFilterOptions();
  await loadRecords();
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

window.addEventListener("resize", () => {
  Object.values(charts).forEach(c => c.resize());
});
loadDashboard();
