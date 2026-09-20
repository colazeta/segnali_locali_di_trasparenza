(() => {
  const input = document.querySelector("#municipality-search");
  const results = document.querySelector("#search-results");
  const buttons = Array.from(document.querySelectorAll(".filter-button"));
  if (!input || !results) return;

  const base = window.PIAO_BASE_PATH || "";
  let data = [];
  let activeFilter = "all";
  let loaded = false;

  const escapeHtml = (value) =>
    String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");

  const normalise = (value) =>
    String(value ?? "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();

  const statusClass = (status) => {
    if (status === "target_period_present") return "status-target";
    if (status === "prior_period_only") return "status-prior";
    if (status === "no_piao_observed") return "status-none";
    return "status-error";
  };

  async function ensureData() {
    if (loaded) return;
    const response = await fetch(`${base}/data/municipalities.json`, {
      cache: "no-store",
    });
    if (!response.ok) throw new Error("Municipality index unavailable");
    data = await response.json();
    loaded = true;
  }

  function selectedRows() {
    const query = normalise(input.value);
    return data
      .filter((row) => activeFilter === "all" || row.status === activeFilter)
      .filter((row) => {
        if (!query) return true;
        return [
          row.name,
          row.istat_code,
          row.region,
          row.supra,
        ].some((value) => normalise(value).includes(query));
      })
      .slice(0, 40);
  }

  function render() {
    if (!loaded) return;
    const rows = selectedRows();
    if (!rows.length) {
      results.innerHTML =
        '<p class="search-hint">Nessun comune corrisponde ai criteri selezionati.</p>';
      return;
    }

    results.innerHTML = rows
      .map(
        (row) => `
          <a class="search-result" href="${escapeHtml(row.href)}">
            <span>
              <strong>${escapeHtml(row.name)}</strong>
              <small>${escapeHtml(row.region)} · ISTAT ${escapeHtml(row.istat_code)}${row.latest_period ? " · ultimo " + escapeHtml(row.latest_period) : ""}</small>
            </span>
            <span class="status-mini ${statusClass(row.status)}">${escapeHtml(row.status_label)}</span>
          </a>
        `
      )
      .join("");
  }

  async function activate() {
    try {
      await ensureData();
      render();
    } catch (error) {
      console.error(error);
      results.innerHTML =
        '<p class="search-hint">La ricerca non è disponibile in questo momento.</p>';
    }
  }

  input.addEventListener("input", activate);
  input.addEventListener("focus", activate);

  buttons.forEach((button) => {
    button.addEventListener("click", async () => {
      activeFilter = button.dataset.filter || "all";
      buttons.forEach((item) => item.classList.toggle("is-active", item === button));
      await activate();
    });
  });
})();
