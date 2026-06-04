(function () {
  const KEY = "theme";
  const root = document.documentElement;
  function apply(t) {
    if (t === "system") {
      const sys = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
      root.setAttribute("data-theme", sys);
    } else {
      root.setAttribute("data-theme", t);
    }
  }
  function get() { return localStorage.getItem(KEY) || "system"; }
  function set(t) { localStorage.setItem(KEY, t); apply(t); updateBtn(); }
  function updateBtn() {
    const btn = document.getElementById("theme-btn");
    if (btn) btn.textContent = get() === "dark" ? "☀️" : "🌙";
  }
  apply(get());
  updateBtn();
  window.__setTheme = set;
  window.__getTheme = get;
})();
