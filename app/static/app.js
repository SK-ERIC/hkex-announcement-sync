(function () {
  "use strict";

  const API = "/api";
  let currentLang = "en";
  let currentPage = 1;
  let pageSize = 20;
  let totalCount = 0;

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  // --- Language ---

  function initLang() {
    const saved = localStorage.getItem("hkex_lang");
    if (saved) {
      currentLang = saved;
      $$(".lang-switch button").forEach((b) => {
        b.classList.toggle("active", b.dataset.lang === currentLang);
      });
    }
  }

  $$(".lang-switch button").forEach((btn) => {
    btn.addEventListener("click", () => {
      currentLang = btn.dataset.lang;
      localStorage.setItem("hkex_lang", currentLang);
      $$(".lang-switch button").forEach((b) => b.classList.toggle("active", b === btn));
      updatePlaceholders();
      currentPage = 1;
      loadAnnouncements();
    });
  });

  function updatePlaceholders() {
    const placeholders = {
      en: { sync: "Stock codes, e.g. 00700,09988", filter: "e.g. 00700" },
      zh: { sync: "股票代碼，如 00700,09988", filter: "如 00700" },
      cn: { sync: "股票代码，如 00700,09988", filter: "如 00700" },
    };
    const p = placeholders[currentLang] || placeholders.en;
    $("#sync-codes").placeholder = p.sync;
    $("#stock-code").placeholder = p.filter;
  }

  // --- Filters ---

  $("#search-btn").addEventListener("click", () => {
    currentPage = 1;
    loadAnnouncements();
  });

  // Allow Enter key in stock code input
  $("#stock-code").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      currentPage = 1;
      loadAnnouncements();
    }
  });

  // --- Sync ---

  $("#sync-btn").addEventListener("click", async () => {
    const btn = $("#sync-btn");
    btn.disabled = true;
    btn.textContent = "Syncing...";

    const codesRaw = $("#sync-codes").value.trim();
    const mode = $("#sync-mode").value;
    const stock_codes = codesRaw ? codesRaw.split(",").map((s) => s.trim()).filter(Boolean) : null;

    try {
      const resp = await fetch(`${API}/sync`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stock_codes, mode }),
      });
      const { task_id } = await resp.json();
      pollSyncStatus(task_id);
    } catch (err) {
      showSyncStatus("failed", "Failed to trigger sync: " + err.message);
      btn.disabled = false;
      btn.textContent = "Sync Now";
    }
  });

  async function pollSyncStatus(taskId) {
    const statusEl = $("#sync-status");
    statusEl.classList.remove("hidden");
    statusEl.className = "sync-status running";
    statusEl.innerHTML = '<span>Syncing announcements...</span><span class="spinner"></span>';

    const poll = async () => {
      try {
        const resp = await fetch(`${API}/sync/status/${taskId}`);
        const data = await resp.json();

        if (data.status === "running" || data.status === "pending") {
          const p = data.progress || {};
          statusEl.innerHTML =
            `<span>Syncing... (${p.synced || 0} synced, ${p.skipped || 0} skipped)</span>`;
          setTimeout(poll, 2000);
          return;
        }

        if (data.status === "success") {
          const p = data.progress || {};
          showSyncStatus("success", `Sync complete: ${p.synced || 0} new, ${p.skipped || 0} skipped`);
          loadAnnouncements();
          loadSyncSummary();
        } else {
          showSyncStatus("failed", `Sync failed: ${data.error || "unknown error"}`);
          loadSyncSummary();
        }
      } catch {
        showSyncStatus("failed", "Lost connection to sync task");
      }

      const btn = $("#sync-btn");
      btn.disabled = false;
      btn.textContent = "Sync Now";
    };

    setTimeout(poll, 1000);
  }

  function showSyncStatus(type, msg) {
    const el = $("#sync-status");
    el.classList.remove("hidden");
    el.className = `sync-status ${type}`;
    el.innerHTML = `<span>${msg}</span>`;
    if (type === "success") {
      setTimeout(() => el.classList.add("hidden"), 5000);
    }
  }

  // --- Announcements ---

  async function loadAnnouncements() {
    const listEl = $("#announcement-list");
    listEl.innerHTML = '<div class="loading">Loading</div>';

    const params = new URLSearchParams({ page: currentPage, page_size: pageSize, language: currentLang });
    const stockCode = $("#stock-code").value.trim();
    const dateFrom = $("#date-from").value;
    const dateTo = $("#date-to").value;
    if (stockCode) params.set("stock_code", stockCode);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);

    try {
      const resp = await fetch(`${API}/announcements?${params}`);
      const data = await resp.json();
      totalCount = data.total;
      renderList(data.items);
      renderPagination(data.total, data.page, data.page_size);
    } catch (err) {
      listEl.innerHTML = `<div class="empty-state"><p>Failed to load: ${err.message}</p></div>`;
    }
  }

  function renderList(items) {
    const listEl = $("#announcement-list");

    if (!items || items.length === 0) {
      listEl.innerHTML = '<div class="empty-state"><p>No announcements found.</p></div>';
      return;
    }

    const html = items
      .map(
        (item) => `
      <div class="announcement-card" data-id="${item.id}">
        <div class="card-header">
          <span class="card-stock">${item.stock_code}</span>
          <span class="card-stock-name">${esc(item.stock_name)}</span>
          ${item.filing_type ? `<span class="card-type">${esc(item.filing_type)}</span>` : ""}
          <span class="card-date">${formatDate(item.announcement_date)}</span>
        </div>
        <div class="card-title">${esc(item.title)}</div>
      </div>
    `
      )
      .join("");

    listEl.innerHTML = `<div class="announcement-list">${html}</div>`;

    listEl.querySelectorAll(".announcement-card").forEach((card) => {
      card.addEventListener("click", () => showDetail(card.dataset.id));
    });
  }

  function renderPagination(total, page, size) {
    const el = $("#pagination");
    const totalPages = Math.ceil(total / size);

    if (totalPages <= 1) {
      el.classList.add("hidden");
      return;
    }

    el.classList.remove("hidden");
    $("#prev-btn").disabled = page <= 1;
    $("#next-btn").disabled = page >= totalPages;
    $("#page-info").textContent = `Page ${page} of ${totalPages} (${total} items)`;
  }

  $("#prev-btn").addEventListener("click", () => {
    if (currentPage > 1) {
      currentPage--;
      loadAnnouncements();
    }
  });

  $("#next-btn").addEventListener("click", () => {
    const totalPages = Math.ceil(totalCount / pageSize);
    if (currentPage < totalPages) {
      currentPage++;
      loadAnnouncements();
    }
  });

  // --- Detail Modal ---

  async function showDetail(id) {
    const modal = $("#modal");
    const body = $("#modal-body");
    body.innerHTML = '<div class="loading">Loading</div>';
    modal.classList.remove("hidden");

    try {
      const resp = await fetch(`${API}/announcements/${id}?language=${currentLang}`);
      const item = await resp.json();

      body.innerHTML = `
        <div class="detail-header">
          <div class="detail-stock">
            <span class="card-stock">${item.stock_code}</span>
            ${esc(item.stock_name)}
          </div>
          <div class="detail-title">${esc(item.title)}</div>
        </div>
        <div class="detail-meta">
          <div class="meta-item">
            <span class="meta-label">Date</span>
            <span class="meta-value">${formatDate(item.announcement_date)}</span>
          </div>
          ${item.filing_type ? `
          <div class="meta-item">
            <span class="meta-label">Type</span>
            <span class="meta-value">${esc(item.filing_type)}</span>
          </div>` : ""}
          ${item.file_size ? `
          <div class="meta-item">
            <span class="meta-label">Size</span>
            <span class="meta-value">${formatSize(item.file_size)}</span>
          </div>` : ""}
          ${item.file_type ? `
          <div class="meta-item">
            <span class="meta-label">Format</span>
            <span class="meta-value">${esc(item.file_type)}</span>
          </div>` : ""}
        </div>
        ${item.short_text || item.long_text ? `
        <div class="detail-text">${esc(item.long_text || item.short_text)}</div>
        ` : ""}
        <div class="detail-actions">
          ${item.download_url ? `
          <a href="${item.download_url}?language=${currentLang}" class="btn btn-primary" download>Download PDF</a>
          ` : ""}
          ${item.hkex_url ? `
          <a href="${item.hkex_url}" target="_blank" rel="noopener" class="btn btn-secondary">View on HKEX</a>
          ` : ""}
        </div>
      `;
    } catch (err) {
      body.innerHTML = `<div class="empty-state"><p>Failed to load detail: ${err.message}</p></div>`;
    }
  }

  // Modal close
  $(".modal-close").addEventListener("click", closeModal);
  $(".modal-backdrop").addEventListener("click", closeModal);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });

  function closeModal() {
    $("#modal").classList.add("hidden");
  }

  // --- Helpers ---

  function esc(str) {
    if (!str) return "";
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  }

  function formatDate(dt) {
    if (!dt) return "—";
    return new Date(dt).toLocaleDateString("en-GB", { year: "numeric", month: "short", day: "numeric" });
  }

  function formatDateTime(dt) {
    if (!dt) return "—";
    return new Date(dt).toLocaleString("en-GB", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function formatSize(bytes) {
    if (!bytes) return "—";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1024 / 1024).toFixed(1) + " MB";
  }

  // --- Sync Summary ---

  async function loadSyncSummary() {
    try {
      const resp = await fetch(`${API}/sync/summary`);
      const data = await resp.json();
      renderSyncSummary(data);
    } catch {
      // silently ignore
    }
  }

  function renderSyncSummary(data) {
    const el = $("#sync-summary");
    if (!data.last_sync_at && data.total_syncs === 0) {
      el.classList.add("hidden");
      return;
    }
    el.classList.remove("hidden");

    const timeEl = $("#summary-time");
    const statusEl = $("#summary-status");
    const syncedEl = $("#summary-synced");
    const totalEl = $("#summary-total");

    timeEl.textContent = data.last_sync_at ? formatDateTime(data.last_sync_at) : "--";

    if (data.last_sync_status) {
      statusEl.textContent = data.last_sync_status;
      statusEl.className = `summary-value status-${data.last_sync_status}`;
    } else {
      statusEl.textContent = "--";
      statusEl.className = "summary-value";
    }

    syncedEl.textContent = data.last_sync_synced != null ? data.last_sync_synced : "--";
    totalEl.textContent = data.total_announcements != null ? data.total_announcements : "--";
  }

  // --- Init ---

  initLang();
  updatePlaceholders();
  loadSyncSummary();
  loadAnnouncements();
})();
