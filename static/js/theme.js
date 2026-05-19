/**
 * Tamasha Events — Theme Manager
 *
 * Responsibilities:
 * 1. FART prevention — apply correct theme before first paint (inline <script> in <head>)
 * 2. Runtime toggle — switch theme without page reload
 * 3. Persistence — localStorage for anonymous, synced with server for authenticated users
 * 4. Icon state — keep all theme toggle buttons in sync
 */

(function () {
  "use strict";

  const STORAGE_KEY = "tamasha-theme";
  const VALID_THEMES = ["dark", "light"];
  const DEFAULT_THEME = "dark";

  // ── Resolve the initial theme ──────────────────────────────────────────
  function getSystemPreference() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  function getSavedTheme() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return VALID_THEMES.includes(saved) ? saved : null;
    } catch {
      return null;
    }
  }

  function resolveTheme() {
    // Priority: localStorage → server-rendered data-theme attribute → OS preference → default
    const saved = getSavedTheme();
    const serverSide = document.documentElement.getAttribute("data-theme");
    const valid = VALID_THEMES.includes(serverSide) ? serverSide : null;
    return saved || valid || getSystemPreference() || DEFAULT_THEME;
  }

  // ── Apply theme to <html> ──────────────────────────────────────────────
  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
  }

  // ── Persist preference ─────────────────────────────────────────────────
  function saveTheme(theme) {
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // localStorage unavailable (private browsing, storage full) — silent fail
    }
  }

  // ── Sync toggle button icons ───────────────────────────────────────────
  function syncToggleIcons(theme) {
    const btns = document.querySelectorAll("[data-theme-toggle]");
    btns.forEach(function (btn) {
      const iconDark = btn.querySelector(".theme-icon-dark");
      const iconLight = btn.querySelector(".theme-icon-light");
      const label = btn.querySelector(".theme-label");

      if (iconDark) iconDark.classList.toggle("d-none", theme === "dark");
      if (iconLight) iconLight.classList.toggle("d-none", theme === "light");
      if (label)
        label.textContent = theme === "dark" ? "Light mode" : "Dark mode";

      btn.setAttribute(
        "aria-label",
        theme === "dark" ? "Switch to light mode" : "Switch to dark mode",
      );
      btn.setAttribute("aria-pressed", theme === "dark" ? "false" : "true");
    });
  }

  // ── Sync preference with server (authenticated users) ─────────────────
  function syncWithServer(theme) {
    const endpoint = document.documentElement.dataset.themeSyncUrl;
    if (!endpoint) return;

    const csrfToken = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1];
    if (!csrfToken) return;

    fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
        "X-Requested-With": "XMLHttpRequest",
      },
      body: JSON.stringify({ theme }),
    }).catch(function () {
      // Silent fail — localStorage is the source of truth until next page load
    });
  }

  // ── Toggle handler ─────────────────────────────────────────────────────
  function toggleTheme() {
    const current =
      document.documentElement.getAttribute("data-theme") || DEFAULT_THEME;
    const next = current === "dark" ? "light" : "dark";

    applyTheme(next);
    saveTheme(next);
    syncToggleIcons(next);
    syncWithServer(next);
  }

  // ── Bind toggle buttons ────────────────────────────────────────────────
  function bindToggleButtons() {
    document.addEventListener("click", function (e) {
      const btn = e.target.closest("[data-theme-toggle]");
      if (btn) toggleTheme();
    });
  }

  // ── Watch OS preference changes ────────────────────────────────────────
  function watchSystemPreference() {
    window
      .matchMedia("(prefers-color-scheme: dark)")
      .addEventListener("change", function (e) {
        // Only follow OS if user hasn't explicitly chosen a theme
        if (!getSavedTheme()) {
          const theme = e.matches ? "dark" : "light";
          applyTheme(theme);
          syncToggleIcons(theme);
        }
      });
  }

  // ── FART prevention: run immediately (before DOM ready) ───────────────
  applyTheme(resolveTheme());

  // ── Full init: run after DOM is ready ─────────────────────────────────
  document.addEventListener("DOMContentLoaded", function () {
    const theme = resolveTheme();
    applyTheme(theme);
    syncToggleIcons(theme);
    bindToggleButtons();
    watchSystemPreference();
  });
})();
