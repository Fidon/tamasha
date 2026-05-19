/**
 * Tamasha Events — Toast Manager
 *
 * Responsibilities:
 * 1. Auto-initialize Bootstrap toasts rendered server-side (Django messages)
 * 2. Provide global showToast() for AJAX responses
 */

(function ($) {
  "use strict";

  // ── Auto-initialize server-rendered toasts ─────────────────────────────
  function initServerToasts() {
    var toastEls = document.querySelectorAll(".toast");
    toastEls.forEach(function (el) {
      var toast = bootstrap.Toast.getOrCreateInstance(el);
      toast.show();
    });
  }

  // ── Programmatic toast for AJAX / JS use ──────────────────────────────
  /**
   * showToast(message, type)
   * @param {string} message  - Text to display
   * @param {string} type     - 'success' | 'danger' | 'warning' | 'info'
   */
  window.showToast = function (message, type) {
    type = type || "info";

    var config = {
      success: {
        icon: "check-circle",
        colorVar: "var(--color-success-text)",
        bgVar: "var(--color-success-bg)",
        borderVar: "var(--color-success-border)",
      },
      danger: {
        icon: "exclamation-circle",
        colorVar: "var(--color-danger-text)",
        bgVar: "var(--color-danger-bg)",
        borderVar: "var(--color-danger-border)",
      },
      warning: {
        icon: "exclamation-triangle",
        colorVar: "var(--color-warning-text)",
        bgVar: "var(--color-warning-bg)",
        borderVar: "var(--color-warning-border)",
      },
      info: {
        icon: "info-circle",
        colorVar: "var(--color-info-text)",
        bgVar: "var(--color-info-bg)",
        borderVar: "var(--color-info-border)",
      },
    };

    var c = config[type] || config.info;
    var id = "toast-" + Date.now();
    var isDark =
      document.documentElement.getAttribute("data-theme") !== "light";

    var html = [
      '<div id="' +
        id +
        '" class="toast align-items-center show mb-2" role="alert"',
      '     aria-live="assertive" aria-atomic="true"',
      '     data-bs-autohide="true" data-bs-delay="5000"',
      '     style="background:' +
        c.bgVar +
        ";border-color:" +
        c.borderVar +
        ';min-width:280px;max-width:360px;">',
      '  <div class="d-flex align-items-center gap-2 p-3">',
      '    <i class="bi bi-' +
        c.icon +
        ' flex-shrink-0" style="color:' +
        c.colorVar +
        ';font-size:var(--text-lg);" aria-hidden="true"></i>',
      '    <span class="flex-grow-1 text-sm" style="color:' +
        c.colorVar +
        ';">' +
        message +
        "</span>",
      '    <button type="button" class="btn-close ms-2 flex-shrink-0" data-bs-dismiss="toast" aria-label="Dismiss"',
      '            style="filter:' +
        (isDark ? "invert(1)" : "") +
        ';opacity:0.6;"></button>',
      "  </div>",
      "</div>",
    ].join("");

    var container = document.querySelector(".toast-container");
    if (!container) {
      container = document.createElement("div");
      container.className = "toast-container position-fixed bottom-0 end-0 p-3";
      container.setAttribute("aria-live", "polite");
      container.setAttribute("aria-atomic", "true");
      container.style.zIndex = "var(--z-toast)";
      document.body.appendChild(container);
    }

    container.insertAdjacentHTML("beforeend", html);

    var toastEl = document.getElementById(id);
    var toast = bootstrap.Toast.getOrCreateInstance(toastEl);
    toast.show();

    toastEl.addEventListener("hidden.bs.toast", function () {
      toastEl.remove();
    });
  };

  // ── Init on DOM ready ──────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", function () {
    // Bootstrap bundle must be loaded before this runs.
    // base.html loads bootstrap.bundle before this file via defer,
    // so DOMContentLoaded fires after all deferred scripts.
    initServerToasts();
  });
})(window.jQuery);
