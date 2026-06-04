async function loadHistory() {
  const r = await fetch("/api/import-history");
  const items = await r.json();
  const tbody = document.querySelector("#history-table tbody");
  tbody.innerHTML = items.map(i => `
    <tr>
      <td>${i.imported_at}</td>
      <td>${i.filename}</td>
      <td>${i.inserted_rows}</td>
      <td>${i.skipped_rows}</td>
      <td>${i.error_rows}</td>
    </tr>`).join("");
}

async function loadStats() {
  const r = await fetch("/api/stats");
  const s = await r.json();
  const sizeKb = (s.db_size_bytes / 1024).toFixed(1);
  document.getElementById("stats").innerHTML = `
    <div>总行数: <strong>${s.total_buckets}</strong></div>
    <div>时间范围: ${s.earliest || "-"} ~ ${s.latest || "-"}</div>
    <div>数据库大小: ${sizeKb} KB</div>
  `;
}

async function loadSettings() {
  const r = await fetch("/api/settings");
  const s = await r.json();
  const radio = document.querySelector(`input[name=bm][value=${s.billing_mode}]`);
  if (radio) radio.checked = true;
  document.getElementById("current-mode").textContent = `当前: ${s.billing_mode}`;
  const themeSel = document.querySelector(".section select");
  if (themeSel) themeSel.value = s.theme;
}

async function saveSettings() {
  const v = document.querySelector("input[name=bm]:checked");
  if (!v) return;
  await fetch("/api/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ billing_mode: v.value }),
  });
  toast("已保存", "success");
  document.getElementById("current-mode").textContent = `当前: ${v.value}`;
}

async function loadPricing() {
  const r = await fetch("/api/pricing");
  const items = await r.json();
  const tbody = document.querySelector("#pricing-table tbody");
  tbody.innerHTML = items.map((p, i) => `
    <tr>
      <td>${p.model}</td>
      <td>${p.endpoint}</td>
      <td><input type="number" step="0.0001" data-i="${i}" data-k="input_price" value="${p.input_price}"></td>
      <td><input type="number" step="0.0001" data-i="${i}" data-k="output_price" value="${p.output_price}"></td>
      <td><input type="number" step="0.0001" data-i="${i}" data-k="cache_read_price" value="${p.cache_read_price}"></td>
      <td><input type="number" step="0.0001" data-i="${i}" data-k="cache_write_price" value="${p.cache_write_price}"></td>
    </tr>`).join("");
  window.__pricing = items;
}

async function syncPricing() {
  const r = await fetch("/api/pricing/sync", { method: "POST" });
  const d = await r.json();
  toast(`新增 ${d.added} 条`, "success");
  await loadPricing();
}

async function savePricing() {
  const items = window.__pricing || [];
  const updated = items.map((p, i) => {
    const out = { ...p };
    ["input_price", "output_price", "cache_read_price", "cache_write_price"].forEach(k => {
      const inp = document.querySelector(`input[data-i="${i}"][data-k="${k}"]`);
      if (inp) out[k] = parseFloat(inp.value || 0);
    });
    return out;
  });
  await fetch("/api/pricing", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updated),
  });
  toast("价格已保存", "success");
}

async function clearAll() {
  if (!confirm("确定清空所有用量数据？此操作不可恢复。")) return;
  if (!confirm("再次确认: 所有记录和导入历史都会删除")) return;
  const r = await fetch("/api/clear?confirm=yes", { method: "POST" });
  if (r.ok) { toast("已清空", "success"); loadHistory(); loadStats(); }
  else toast("清空失败", "error");
}

(async () => {
  await loadSettings();
  await loadHistory();
  await loadStats();
  await loadPricing();
})();
