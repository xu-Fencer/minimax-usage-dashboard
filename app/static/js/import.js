(function () {
  const dz = document.getElementById("drop-zone");
  const fi = document.getElementById("file-input");
  const out = document.getElementById("import-result");

  function upload(file) {
    const fd = new FormData();
    fd.append("file", file);
    out.textContent = "上传中...";
    fetch("/api/import", { method: "POST", body: fd })
      .then(r => r.ok ? r.json() : r.json().then(e => Promise.reject(e)))
      .then(d => {
        out.innerHTML = `<strong>导入完成</strong> 新增 ${d.inserted} / 跳过 ${d.skipped} / 错误 ${d.error_rows}`;
        toast("导入成功", "success");
        if (window.loadHistory) loadHistory();
        if (window.loadStats) loadStats();
      })
      .catch(e => { out.textContent = "失败: " + (e.detail || JSON.stringify(e)); toast("导入失败", "error"); });
  }

  dz.addEventListener("click", () => fi.click());
  dz.addEventListener("dragover", e => { e.preventDefault(); dz.style.background = "var(--bg)"; });
  dz.addEventListener("dragleave", () => dz.style.background = "");
  dz.addEventListener("drop", e => {
    e.preventDefault();
    dz.style.background = "";
    const f = e.dataTransfer.files[0];
    if (f) upload(f);
  });
  fi.addEventListener("change", e => { const f = e.target.files[0]; if (f) upload(f); });
})();
