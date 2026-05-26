/**
 * Tamasha Events — Event List Page
 * Handles: infinite scroll, filter interactions, search debounce.
 */
(function ($) {
  "use strict";

  var cfg = window.TAMASHA || {};
  var listUrl = cfg.eventsListUrl || "/events/";
  var lastId = cfg.initialLastId || null;
  var hasMore = cfg.hasMore !== false;
  var isLoading = false;
  var filters = $.extend(
    {
      q: "",
      category: "",
      city: "",
      date_from: "",
      date_to: "",
      price_min: "",
      price_max: "",
      free: "",
      weekend: "",
    },
    cfg.activeFilters || {},
  );

  var $grid = $("#events-grid");
  var $sentinel = $("#scroll-sentinel");
  var $loader = $("#load-more-loader");
  var $endMsg = $("#events-end-message");
  var $resetBtn = $("#filters-reset-btn");
  var $emptyReset = $("#empty-reset-btn");
  var $filtersPanel = $("#events-filters");
  var $filtersToggle = $("#filters-toggle-btn");
  var $searchInput = $("#events-search-input");
  var $searchClear = $("#search-clear-btn");

  // ── Build query string from current filters ──────────────
  function buildQuery(extra) {
    var params = $.extend({}, filters, extra || {});
    var parts = [];
    $.each(params, function (k, v) {
      if (v !== "" && v !== null && v !== undefined) {
        parts.push(encodeURIComponent(k) + "=" + encodeURIComponent(v));
      }
    });
    return parts.length ? "?" + parts.join("&") : "";
  }

  // ── Push filter state to URL without reload ───────────────
  function pushState() {
    var url = listUrl + buildQuery();
    history.replaceState(null, "", url);
  }

  // ── Fetch events (initial load or infinite scroll) ────────
  function fetchEvents(append) {
    if (isLoading) return;
    if (append && !hasMore) return;

    isLoading = true;
    $loader.prop("hidden", false);

    var extra = append ? { after: lastId } : {};
    var qs = buildQuery(extra);

    $.ajax({
      url: listUrl + qs,
      method: "GET",
      headers: { "X-Requested-With": "XMLHttpRequest" },
      success: function (data) {
        if (!append) {
          $grid.empty();
          $endMsg.prop("hidden", true);
        }

        if (data.html && data.html.trim()) {
          $grid.append(data.html);
          lastId = data.last_id;
          hasMore = data.has_more;
          showEmpty(false);
        } else if (!append) {
          showEmpty(true);
        }

        if (!hasMore) {
          $endMsg.prop("hidden", false);
        }
      },
      error: function () {
        window.showToast("Failed to load events. Please try again.", "danger");
      },
      complete: function () {
        isLoading = false;
        $loader.prop("hidden", true);
      },
    });
  }

  // ── Reset scroll cursor and refetch from top ──────────────
  function refetch() {
    lastId = null;
    hasMore = true;
    fetchEvents(false);
    pushState();
    updateResetVisibility();
  }

  // ── Empty state ───────────────────────────────────────────
  function showEmpty(show) {
    var $empty = $("#events-empty");
    if (show) {
      if (!$empty.length) {
        $grid.append(
          '<div id="events-empty" class="events-empty" aria-live="polite">' +
            '<div class="events-empty__icon"><i class="bi bi-calendar-x" aria-hidden="true"></i></div>' +
            '<h2 class="events-empty__title">No events found</h2>' +
            '<p class="events-empty__text">Try adjusting your filters or check back soon.</p>' +
            '<button type="button" class="btn btn-outline-primary" id="empty-reset-btn">Clear all filters</button>' +
            "</div>",
        );
        bindEmptyReset();
      } else {
        $empty.show();
      }
    } else {
      $empty.remove();
    }
  }

  // ── Show/hide reset button ────────────────────────────────
  function updateResetVisibility() {
    var active = Object.values(filters).some(function (v) {
      return v !== "" && v !== null;
    });
    $resetBtn.toggleClass("d-none", !active);
  }

  // ── Reset all filters ─────────────────────────────────────
  function resetFilters() {
    filters = {
      q: "",
      category: "",
      city: "",
      date_from: "",
      date_to: "",
      price_min: "",
      price_max: "",
      free: "",
      weekend: "",
    };

    // Reset UI controls
    $searchInput.val("");
    $("[data-filter]").each(function () {
      var $el = $(this);
      var type = this.type;
      if (
        type === "text" ||
        type === "number" ||
        type === "date" ||
        type === "search"
      ) {
        $el.val("");
      }
    });
    $('[data-filter="category"]').removeClass("active");
    $('[data-filter="category"][data-value=""]').addClass("active");
    $('[data-filter="free"], [data-filter="weekend"]')
      .removeClass("active")
      .attr("aria-pressed", "false");

    refetch();
  }

  // ── Infinite scroll via IntersectionObserver ──────────────
  function initIntersectionObserver() {
    if (!window.IntersectionObserver || !$sentinel.length) return;
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting && hasMore && !isLoading) {
            fetchEvents(true);
          }
        });
      },
      { rootMargin: "200px" },
    );
    observer.observe($sentinel[0]);
  }

  // ── Search: debounced ─────────────────────────────────────
  var searchTimer;
  $searchInput.on("input", function () {
    clearTimeout(searchTimer);
    var val = $(this).val().trim();
    searchTimer = setTimeout(function () {
      filters.q = val;
      refetch();
    }, 420);
  });

  $searchClear.on("click", function () {
    filters.q = "";
    $searchInput.val("").trigger("focus");
    refetch();
  });

  // ── Category buttons ──────────────────────────────────────
  $(document).on("click", '[data-filter="category"]', function () {
    var $btn = $(this);
    $('[data-filter="category"]')
      .removeClass("active")
      .attr("aria-selected", "false");
    $btn.addClass("active").attr("aria-selected", "true");
    filters.category = $btn.data("value");
    refetch();
  });

  // ── Toggle chips (free / weekend) ─────────────────────────
  $(document).on("click", ".events-filter-chip", function () {
    var $chip = $(this);
    var key = $chip.data("filter");
    var val = $chip.data("value");
    var active = $chip.hasClass("active");

    $chip.toggleClass("active", !active).attr("aria-pressed", String(!active));

    filters[key] = active ? "" : String(val);
    refetch();
  });

  // ── Date / city / price inputs: debounced ─────────────────
  var filterTimer;
  $(document).on("input change", "[data-filter]", function () {
    var $el = $(this);
    var key = $el.data("filter");
    var tag = this.tagName.toLowerCase();

    // Skip category and chip buttons — handled separately above
    if (tag === "button") return;

    clearTimeout(filterTimer);
    var val = $el.val().trim();
    filterTimer = setTimeout(function () {
      filters[key] = val;
      refetch();
    }, 400);
  });

  // ── Reset button ──────────────────────────────────────────
  $resetBtn.on("click", resetFilters);

  function bindEmptyReset() {
    $(document).on("click", "#empty-reset-btn", resetFilters);
  }
  bindEmptyReset();

  // ── Mobile filter panel toggle ────────────────────────────
  $filtersToggle.on("click", function () {
    var open = $filtersPanel.hasClass("is-open");
    $filtersPanel.toggleClass("is-open", !open);
    $(this).attr("aria-expanded", String(!open));
  });

  // Close panel when tapping outside on mobile
  $(document).on("click", function (e) {
    if (
      $filtersPanel.hasClass("is-open") &&
      !$filtersPanel[0].contains(e.target) &&
      !$filtersToggle[0].contains(e.target)
    ) {
      $filtersPanel.removeClass("is-open");
      $filtersToggle.attr("aria-expanded", "false");
    }
  });

  // ── Init ──────────────────────────────────────────────────
  $(function () {
    initIntersectionObserver();
    updateResetVisibility();
  });
})(window.jQuery);
