/**
 * Tamasha Events — Event Creation Wizard
 * Handles: step navigation, AJAX step submission, Quill, venue search,
 * tag chips, collaborator search, ticket type rows, review panel,
 * publish / save-as-draft actions.
 */
(function ($) {
  "use strict";

  var cfg = (window.TAMASHA || {}).wizard || {};
  var STEP_URL = cfg.stepUrl || "/events/wizard/step/{step}/";
  var VENUE_SRCH = cfg.venueSearchUrl || "/events/venues/search/";
  var VENUE_SAVE = cfg.venueSaveUrl || "/events/venues/save/";
  var COLLAB_SRCH = cfg.collabSearchUrl || "/events/collaborators/search/";
  var DISCARD_URL = cfg.discardUrl || "/events/wizard/discard/";
  var CSRF = cfg.csrfToken || "";
  var currentStep = 1;
  var maxReached = cfg.stepReached || 1;
  var draft = cfg.draftData || {}; // step_data from server

  // Nominatim endpoint
  var NOMINATIM = "https://nominatim.openstreetmap.org/search";

  // ── Quill instance ────────────────────────────────────────
  var quill = new Quill("#quill-editor", {
    theme: "snow",
    placeholder: "Describe your event — lineup, agenda, what to expect…",
    modules: {
      toolbar: [
        [{ header: [2, 3, false] }],
        ["bold", "italic", "underline", "strike"],
        ["blockquote"],
        [{ list: "ordered" }, { list: "bullet" }],
        ["link"],
        ["clean"],
      ],
    },
  });

  // ── State ─────────────────────────────────────────────────
  var selectedTags = {}; // { id|'custom:name': { id, name, isCustom } }
  var selectedVenue = null; // { id, name, city, address, lat, lng, osm_id }
  var selectedCollabs = {}; // { pk: { id, organization_name, email } }
  var ticketTypes = []; // array of ticket data objects
  var bannerFile = null; // File object

  // ── Helpers ───────────────────────────────────────────────
  function stepUrl(n) {
    return STEP_URL.replace("{step}", n);
  }

  function csrfHeaders() {
    return { "X-CSRFToken": CSRF, "X-Requested-With": "XMLHttpRequest" };
  }

  function setLoading($btn, loading) {
    if (loading) {
      $btn
        .data("original-html", $btn.html())
        .prop("disabled", true)
        .html(
          '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Saving…',
        );
    } else {
      $btn
        .prop("disabled", false)
        .html($btn.data("original-html") || $btn.html());
    }
  }

  function showFieldError(id, msg) {
    var $el = $("#error-" + id);
    $el.text(msg).prop("hidden", false);
  }

  function clearFieldErrors() {
    $(".wizard-field__error").text("").prop("hidden", true);
    $(".ticket-error-name, .ticket-error-price, .ticket-error-quantity")
      .text("")
      .prop("hidden", true);
  }

  // ── Step navigation ───────────────────────────────────────
  function goToStep(n) {
    if (n < 1 || n > 6) return;
    $("#step-" + currentStep).addClass("d-none");
    $("#step-" + n).removeClass("d-none");

    // Update sidebar nav
    $(".wizard-steps-nav__item").each(function () {
      var s = parseInt($(this).data("step-nav"), 10);
      var $btn = $(this).find(".wizard-steps-nav__btn");
      $(this).removeClass("is-active is-completed");
      $btn.removeAttr("aria-current");

      if (s === n) {
        $(this).addClass("is-active");
        $btn.attr("aria-current", "step");
      } else if (s < n) {
        $(this).addClass("is-completed");
      }
      // Enable nav button if step was already reached
      if (s <= maxReached) {
        $btn.prop("disabled", false);
      }
    });

    currentStep = n;

    // Populate review panel on step 6
    if (n === 6) buildReviewPanel();

    // Scroll wizard body to top
    $("html, body").animate(
      { scrollTop: $(".wizard-body").offset().top - 100 },
      200,
    );
  }

  // ── Sidebar nav clicks ────────────────────────────────────
  $(document).on("click", "[data-goto-step]", function () {
    var target = parseInt($(this).data("goto-step"), 10);
    if (target <= maxReached) goToStep(target);
  });

  // ── Back buttons ──────────────────────────────────────────
  $(document).on("click", ".wizard-back-btn", function () {
    var s = parseInt($(this).data("step"), 10);
    goToStep(s - 1);
  });

  // ── Next buttons ──────────────────────────────────────────
  $(document).on("click", ".wizard-next-btn", function () {
    var $btn = $(this);
    var step = parseInt($btn.data("step"), 10);
    clearFieldErrors();

    if (step === 3) {
      // Banner is optional — submit step 3 directly
      submitStep(3, $btn);
      return;
    }
    if (step === 4) {
      submitStep(4, $btn);
      return;
    }
    submitStep(step, $btn);
  });

  // ── Submit individual steps ───────────────────────────────
  function submitStep(step, $btn) {
    setLoading($btn, true);

    if (step === 5) {
      submitStep5($btn);
      return;
    }

    var formData = buildFormData(step);

    $.ajax({
      url: stepUrl(step),
      method: "POST",
      data: formData,
      processData: false,
      contentType: false,
      headers: { "X-CSRFToken": CSRF, "X-Requested-With": "XMLHttpRequest" },
      success: function (data) {
        if (data.success) {
          if (step > maxReached) maxReached = step;
          goToStep(step + 1);
        } else {
          renderErrors(data.errors || {});
        }
      },
      error: function (xhr) {
        var data = xhr.responseJSON || {};
        renderErrors(
          data.errors || { __all__: "Something went wrong. Please try again." },
        );
      },
      complete: function () {
        setLoading($btn, false);
      },
    });
  }

  function buildFormData(step) {
    var fd = new FormData();
    fd.append("csrfmiddlewaretoken", CSRF);

    if (step === 1) {
      fd.append("title", $("#id_title").val().trim());
      fd.append("category", $("#id_category").val());
      fd.append("description", $("#id_description").val());

      // Predefined tag PKs as comma-separated
      var predefinedIds = Object.values(selectedTags)
        .filter(function (t) {
          return !t.isCustom;
        })
        .map(function (t) {
          return t.id;
        });
      fd.append("predefined_tags", predefinedIds.join(","));

      // Custom tag names as comma-separated
      var customNames = Object.values(selectedTags)
        .filter(function (t) {
          return t.isCustom;
        })
        .map(function (t) {
          return t.name;
        });
      fd.append("custom_tags", customNames.join(","));
    }

    if (step === 2) {
      fd.append("timezone", $("#id_timezone").val());
      fd.append("starts_at", $("#id_starts_at").val());
      fd.append("ends_at", $("#id_ends_at").val());
      fd.append("venue_name", $("#id_venue_name").val());
      fd.append("venue_city", $("#id_venue_city").val());
      fd.append("venue_address", $("#id_venue_address").val());
      fd.append("venue_lat", $("#id_venue_lat").val());
      fd.append("venue_lng", $("#id_venue_lng").val());
      fd.append("venue_osm_id", $("#id_venue_osm_id").val());
      fd.append("venue_id", $("#id_venue_id").val());
    }

    if (step === 3) {
      if (bannerFile) fd.append("banner", bannerFile);
    }

    if (step === 4) {
      var ids = Object.keys(selectedCollabs).join(",");
      fd.append("collaborator_ids", ids);
    }

    return fd;
  }

  function submitStep5($btn) {
    var data = collectTicketTypes();
    if (!data) {
      setLoading($btn, false);
      return;
    }

    $.ajax({
      url: stepUrl(5),
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify({ ticket_types: data }),
      headers: csrfHeaders(),
      success: function (resp) {
        if (resp.success) {
          ticketTypes = data;
          if (5 > maxReached) maxReached = 5;
          goToStep(6);
        } else {
          renderErrors(resp.errors || {});
        }
      },
      error: function (xhr) {
        var resp = xhr.responseJSON || {};
        renderErrors(resp.errors || { __all__: "Something went wrong." });
      },
      complete: function () {
        setLoading($btn, false);
      },
    });
  }

  function renderErrors(errors) {
    $.each(errors, function (field, msg) {
      if (field === "__all__") {
        window.showToast(String(msg), "danger");
      } else {
        // Field errors from step 5 ticket rows
        var ticketMatch = field.match(/^ticket_(\d+)$/);
        if (ticketMatch) {
          var idx = parseInt(ticketMatch[1], 10);
          var $row = $(".ticket-type-row").eq(idx);
          $row
            .find(".ticket-error-name")
            .text(String(msg))
            .prop("hidden", false);
        } else {
          showFieldError(field, Array.isArray(msg) ? msg[0] : String(msg));
        }
      }
    });
  }

  // ── Quill: sync to hidden input on change ─────────────────
  quill.on("text-change", function () {
    $("#id_description").val(
      quill.root.innerHTML === "<p><br></p>" ? "" : quill.root.innerHTML,
    );
  });

  // ── Tag chips ─────────────────────────────────────────────
  $(document).on("click", ".tag-chip", function () {
    var $chip = $(this);
    var tagId = $chip.data("tag-id");
    var tagName = $chip.data("tag-name");
    var key = String(tagId);

    if (selectedTags[key]) {
      delete selectedTags[key];
      $chip.removeClass("is-selected").attr("aria-pressed", "false");
      removeTagPill(key);
    } else {
      selectedTags[key] = { id: tagId, name: tagName, isCustom: false };
      $chip.addClass("is-selected").attr("aria-pressed", "true");
      addTagPill(key, tagName);
    }
  });

  // Custom tag input
  $("#custom-tag-input").on("keydown", function (e) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      var name = $(this).val().trim().replace(/,$/, "");
      if (!name) return;
      addCustomTag(name);
      $(this).val("");
    }
    // Backspace removes last tag
    if (e.key === "Backspace" && !$(this).val()) {
      var keys = Object.keys(selectedTags);
      if (keys.length) {
        var lastKey = keys[keys.length - 1];
        removeTag(lastKey);
      }
    }
  });

  function addCustomTag(name) {
    var key = "custom:" + name.toLowerCase();
    if (selectedTags[key]) return;
    if (Object.keys(selectedTags).length >= 15) {
      window.showToast("Maximum 15 tags allowed.", "warning");
      return;
    }
    selectedTags[key] = { id: null, name: name, isCustom: true };
    addTagPill(key, name);
  }

  function addTagPill(key, name) {
    var $pill = $(
      '<span class="tag-pill" data-tag-key="' +
        key +
        '">' +
        name +
        '<button type="button" class="tag-pill__remove" aria-label="Remove tag ' +
        name +
        '">' +
        '<i class="bi bi-x" aria-hidden="true"></i>' +
        "</button></span>",
    );
    $("#selected-tags").append($pill);
  }

  function removeTag(key) {
    delete selectedTags[key];
    removeTagPill(key);
    // Deselect predefined chip if applicable
    $('[data-tag-id="' + key + '"]')
      .removeClass("is-selected")
      .attr("aria-pressed", "false");
  }

  function removeTagPill(key) {
    $('#selected-tags .tag-pill[data-tag-key="' + key + '"]').remove();
  }

  $(document).on("click", ".tag-pill__remove", function () {
    var key = $(this).closest(".tag-pill").data("tag-key");
    removeTag(String(key));
  });

  // ── Venue search ──────────────────────────────────────────
  var venueTimer;
  $("#venue-search").on("input", function () {
    clearTimeout(venueTimer);
    var q = $(this).val().trim();
    if (q.length < 2) {
      hideVenueSuggestions();
      return;
    }
    venueTimer = setTimeout(function () {
      fetchVenues(q);
    }, 350);
  });

  function fetchVenues(q) {
    $.ajax({
      url: VENUE_SRCH,
      data: { q: q },
      headers: { "X-Requested-With": "XMLHttpRequest" },
      success: function (data) {
        var results = data.results || [];
        if (results.length < 3) {
          fetchNominatim(q, results);
        } else {
          renderVenueSuggestions(results);
        }
      },
    });
  }

  function fetchNominatim(q, localResults) {
    $.ajax({
      url: NOMINATIM,
      data: { q: q + " Tanzania", format: "json", limit: 5, addressdetails: 1 },
      headers: { "Accept-Language": "en" },
      success: function (results) {
        var nominatimItems = (results || []).map(function (r) {
          var addr = r.address || {};
          return {
            id: null,
            name: r.display_name.split(",")[0].trim(),
            address: r.display_name,
            city: addr.city || addr.town || addr.village || addr.county || "",
            country: addr.country || "Tanzania",
            lat: r.lat,
            lng: r.lon,
            osm_id: String(r.osm_id),
            source: "nominatim",
          };
        });

        // Deduplicate by name against local results
        var localNames = localResults.map(function (r) {
          return r.name.toLowerCase();
        });
        var filtered = nominatimItems.filter(function (r) {
          return localNames.indexOf(r.name.toLowerCase()) === -1;
        });

        renderVenueSuggestions(localResults.concat(filtered));
      },
      error: function () {
        renderVenueSuggestions(localResults);
      },
    });
  }

  function renderVenueSuggestions(items) {
    var $box = $("#venue-suggestions").empty();
    if (!items.length) {
      hideVenueSuggestions();
      return;
    }

    items.forEach(function (v) {
      var badge =
        v.source === "local"
          ? '<span class="venue-suggestion-item__badge">Saved</span>'
          : "";
      var $item = $(
        '<div class="venue-suggestion-item" role="option" tabindex="0">' +
          '<i class="bi bi-geo-alt venue-suggestion-item__icon" aria-hidden="true"></i>' +
          "<div>" +
          '<div class="venue-suggestion-item__name">' +
          $("<span>").text(v.name).html() +
          "</div>" +
          '<div class="venue-suggestion-item__address">' +
          $("<span>")
            .text(v.city || v.address)
            .html() +
          "</div>" +
          "</div>" +
          badge +
          "</div>",
      );
      $item.on("click keydown", function (e) {
        if (e.type === "click" || e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          selectVenue(v);
        }
      });
      $box.append($item);
    });

    $box.prop("hidden", false);
    $("#venue-search").attr("aria-expanded", "true");
  }

  function hideVenueSuggestions() {
    $("#venue-suggestions").prop("hidden", true).empty();
    $("#venue-search").attr("aria-expanded", "false");
  }

  function selectVenue(v) {
    selectedVenue = v;

    // Populate hidden fields
    $("#id_venue_id").val(v.id || "");
    $("#id_venue_name").val(v.name);
    $("#id_venue_city").val(v.city);
    $("#id_venue_address").val(v.address || "");
    $("#id_venue_lat").val(v.lat || "");
    $("#id_venue_lng").val(v.lng || "");
    $("#id_venue_osm_id").val(v.osm_id || "");

    // Show selected card
    $("#venue-selected-name").text(v.name);
    $("#venue-selected-address").text(
      [v.address, v.city].filter(Boolean).join(", "),
    );
    $("#venue-selected").prop("hidden", false);
    $("#venue-search")
      .val("")
      .closest(".venue-search-wrap")
      .find("input")
      .prop("hidden", true);
    hideVenueSuggestions();

    // Save to local DB if from Nominatim
    if (v.source === "nominatim") {
      $.ajax({
        url: VENUE_SAVE,
        method: "POST",
        contentType: "application/json",
        data: JSON.stringify(v),
        headers: csrfHeaders(),
        success: function (resp) {
          if (resp.id) {
            $("#id_venue_id").val(resp.id);
            selectedVenue.id = resp.id;
          }
        },
      });
    }
  }

  $("#venue-clear-btn").on("click", function () {
    selectedVenue = null;
    $(
      "#id_venue_id, #id_venue_name, #id_venue_city, #id_venue_address, #id_venue_lat, #id_venue_lng, #id_venue_osm_id",
    ).val("");
    $("#venue-selected").prop("hidden", true);
    $("#venue-search")
      .val("")
      .closest(".venue-search-wrap")
      .find("input")
      .prop("hidden", false);
    $("#venue-search").trigger("focus");
  });

  // Close suggestions on outside click
  $(document).on("click", function (e) {
    if (!$(e.target).closest(".venue-search-wrap").length)
      hideVenueSuggestions();
  });

  // ── Banner drop zone ──────────────────────────────────────
  var $dz = $("#banner-dropzone");
  var $input = $("#banner-upload");

  $dz.on("click", function (e) {
    if (!$(e.target).is("#banner-remove-btn, #banner-remove-btn *")) {
      $input.trigger("click");
    }
  });
  $dz.on("keydown", function (e) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      $input.trigger("click");
    }
  });

  $dz
    .on("dragover dragenter", function (e) {
      e.preventDefault();
      $dz.addClass("is-dragover");
    })
    .on("dragleave dragend drop", function (e) {
      e.preventDefault();
      $dz.removeClass("is-dragover");
    })
    .on("drop", function (e) {
      var file = e.originalEvent.dataTransfer.files[0];
      if (file) processBannerFile(file);
    });

  $input.on("change", function () {
    if (this.files[0]) processBannerFile(this.files[0]);
  });

  function processBannerFile(file) {
    var allowed = ["image/jpeg", "image/png", "image/webp"];
    if (allowed.indexOf(file.type) === -1) {
      showFieldError("banner", "Only JPG, PNG or WebP images are allowed.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      showFieldError("banner", "File must be under 10 MB.");
      return;
    }
    bannerFile = file;
    var reader = new FileReader();
    reader.onload = function (e) {
      $("#banner-preview-img").attr("src", e.target.result);
      $("#banner-idle").prop("hidden", true);
      $("#banner-preview").prop("hidden", false);
    };
    reader.readAsDataURL(file);
    clearFieldErrors();
  }

  $("#banner-remove-btn").on("click", function (e) {
    e.stopPropagation();
    bannerFile = null;
    $input.val("");
    $("#banner-preview").prop("hidden", true);
    $("#banner-idle").prop("hidden", false);
  });

  // ── Collaborator search ───────────────────────────────────
  var collabTimer;
  $("#collab-search").on("input", function () {
    clearTimeout(collabTimer);
    var q = $(this).val().trim();
    if (q.length < 2) {
      $("#collab-suggestions").prop("hidden", true).empty();
      return;
    }
    collabTimer = setTimeout(function () {
      fetchCollabs(q);
    }, 350);
  });

  function fetchCollabs(q) {
    $.ajax({
      url: COLLAB_SRCH,
      data: { q: q },
      headers: { "X-Requested-With": "XMLHttpRequest" },
      success: function (data) {
        var $box = $("#collab-suggestions").empty();
        var results = (data.results || []).filter(function (r) {
          return !selectedCollabs[r.id];
        });
        if (!results.length) {
          $box.prop("hidden", true);
          return;
        }
        results.forEach(function (r) {
          var $item = $(
            '<div class="collab-suggestion-item" role="option" tabindex="0">' +
              "<div>" +
              '<div class="collab-suggestion-item__name">' +
              $("<span>").text(r.organization_name).html() +
              "</div>" +
              '<div class="collab-suggestion-item__email">' +
              $("<span>").text(r.email).html() +
              "</div>" +
              "</div>" +
              '<span class="collab-suggestion-item__add">+ Add</span>' +
              "</div>",
          );
          $item.on("click keydown", function (e) {
            if (e.type === "click" || e.key === "Enter") {
              e.preventDefault();
              addCollaborator(r);
              $("#collab-search").val("");
              $box.prop("hidden", true).empty();
            }
          });
          $box.append($item);
        });
        $box.prop("hidden", false);
      },
    });
  }

  function addCollaborator(r) {
    if (selectedCollabs[r.id]) return;
    selectedCollabs[r.id] = r;
    renderCollabCards();
  }

  function removeCollaborator(id) {
    delete selectedCollabs[id];
    renderCollabCards();
  }

  function renderCollabCards() {
    var $list = $("#collab-selected-list");
    $list.empty();
    var keys = Object.keys(selectedCollabs);

    if (!keys.length) {
      $list.append(
        '<p class="collab-empty-msg" id="collab-empty-msg">' +
          '<i class="bi bi-people me-2 opacity-50" aria-hidden="true"></i>' +
          "No collaborators added yet.</p>",
      );
      $("#id_collaborator_ids").val("");
      return;
    }

    keys.forEach(function (id) {
      var r = selectedCollabs[id];
      var init = r.organization_name.charAt(0).toUpperCase();
      var $card = $(
        '<div class="collab-card" data-collab-id="' +
          id +
          '">' +
          '<div class="d-flex align-items-center gap-3">' +
          '<span class="collab-card__avatar">' +
          init +
          "</span>" +
          "<div>" +
          '<div class="collab-card__name">' +
          $("<span>").text(r.organization_name).html() +
          "</div>" +
          '<div class="collab-card__email">' +
          $("<span>").text(r.email).html() +
          "</div>" +
          "</div></div>" +
          '<button type="button" class="collab-card__remove" aria-label="Remove ' +
          $("<span>").text(r.organization_name).html() +
          '">' +
          '<i class="bi bi-x-lg" aria-hidden="true"></i>' +
          "</button></div>",
      );
      $card.find(".collab-card__remove").on("click", function () {
        removeCollaborator(id);
      });
      $list.append($card);
    });

    $("#id_collaborator_ids").val(keys.join(","));
  }

  // ── Ticket types ──────────────────────────────────────────
  var ticketIndex = 0;

  $("#add-ticket-btn").on("click", function () {
    addTicketRow({});
  });

  function addTicketRow(data) {
    var $tmpl = $("#ticket-type-template").prop("content");
    var $clone = $($tmpl).find(".ticket-type-row").clone();
    var idx = ticketIndex++;

    $clone.attr("data-ticket-index", idx);
    $clone.find(".ticket-type-row__label").text("Ticket Type " + (idx + 1));

    // Populate from data (edit mode)
    if (data.name) $clone.find('[name="tt_name"]').val(data.name);
    if (data.price != null) $clone.find('[name="tt_price"]').val(data.price);
    if (data.quantity) $clone.find('[name="tt_quantity"]').val(data.quantity);
    if (data.max_per_order)
      $clone.find('[name="tt_max_per_order"]').val(data.max_per_order);
    if (data.description)
      $clone.find('[name="tt_description"]').val(data.description);
    if (data.sale_starts_at)
      $clone.find('[name="tt_sale_starts_at"]').val(data.sale_starts_at);
    if (data.sale_ends_at)
      $clone.find('[name="tt_sale_ends_at"]').val(data.sale_ends_at);
    if (data.is_sold_out)
      $clone.find(".ticket-soldout-cb").prop("checked", true);
    if (data.id) $clone.data("ticket-id", data.id);

    $clone.find(".ticket-type-row__remove").on("click", function () {
      $clone.remove();
    });

    $("#ticket-types-list").append($clone);
  }

  function collectTicketTypes() {
    var types = [];
    var valid = true;

    $(".ticket-type-row").each(function (i) {
      var $row = $(this);
      var name = $row.find('[name="tt_name"]').val().trim();
      var price = $row.find('[name="tt_price"]').val();
      var qty = $row.find('[name="tt_quantity"]').val();

      if (!name) {
        $row
          .find(".ticket-error-name")
          .text("Name is required.")
          .prop("hidden", false);
        valid = false;
      }
      if (price === "" || isNaN(parseFloat(price)) || parseFloat(price) < 0) {
        $row
          .find(".ticket-error-price")
          .text("Enter a valid price (0 for free).")
          .prop("hidden", false);
        valid = false;
      }
      if (!qty || parseInt(qty) < 1) {
        $row
          .find(".ticket-error-quantity")
          .text("Quantity must be at least 1.")
          .prop("hidden", false);
        valid = false;
      }

      types.push({
        id: $row.data("ticket-id") || null,
        name: name,
        description: $row.find('[name="tt_description"]').val().trim(),
        price: price,
        quantity: parseInt(qty) || 0,
        max_per_order:
          parseInt($row.find('[name="tt_max_per_order"]').val()) || 10,
        sale_starts_at: $row.find('[name="tt_sale_starts_at"]').val() || null,
        sale_ends_at: $row.find('[name="tt_sale_ends_at"]').val() || null,
        is_sold_out: $row.find(".ticket-soldout-cb").prop("checked"),
        is_active: true,
        sort_order: i,
      });
    });

    if (!valid) return null;
    if (!types.length) {
      showFieldError("tickets", "Add at least one ticket type.");
      return null;
    }
    return types;
  }

  // ── Review panel ──────────────────────────────────────────
  function buildReviewPanel() {
    var $grid = $("#review-grid").empty();

    // Step 1: Basic info
    var step1 = draft["1"] || {};
    var tagNames =
      Object.values(selectedTags)
        .map(function (t) {
          return t.name;
        })
        .join(", ") || "—";
    $grid.append(
      buildReviewSection("Basic Info", 1, [
        { label: "Title", value: $("#id_title").val() || step1.title || "—" },
        {
          label: "Category",
          value: $("#id_category option:selected").text() || "—",
        },
        { label: "Tags", value: tagNames },
      ]),
    );

    // Step 2: Date & Venue
    $grid.append(
      buildReviewSection("Date & Venue", 2, [
        { label: "Start", value: $("#id_starts_at").val() || "—" },
        { label: "End", value: $("#id_ends_at").val() || "—" },
        { label: "Timezone", value: $("#id_timezone").val() || "—" },
        { label: "Venue", value: $("#id_venue_name").val() || "—" },
        { label: "City", value: $("#id_venue_city").val() || "—" },
      ]),
    );

    // Step 3: Banner
    var bannerVal = bannerFile ? bannerFile.name : "No banner uploaded";
    $grid.append(
      buildReviewSection("Banner", 3, [{ label: "File", value: bannerVal }]),
    );

    // Step 4: Collaborators
    var collabNames =
      Object.values(selectedCollabs)
        .map(function (c) {
          return c.organization_name;
        })
        .join(", ") || "None";
    $grid.append(
      buildReviewSection("Collaborators", 4, [
        { label: "Co-hosts", value: collabNames },
      ]),
    );

    // Step 5: Tickets
    var ticketSummary = [];
    $(".ticket-type-row").each(function () {
      var name = $(this).find('[name="tt_name"]').val() || "Unnamed";
      var price = $(this).find('[name="tt_price"]').val();
      var qty = $(this).find('[name="tt_quantity"]').val();
      var label = price == 0 ? name + " — Free" : name + " — TZS " + price;
      ticketSummary.push({
        label: "Tier",
        value: label + " · " + qty + " tickets",
      });
    });
    if (!ticketSummary.length)
      ticketSummary = [{ label: "Tickets", value: "None added" }];
    $grid.append(buildReviewSection("Tickets", 5, ticketSummary));
  }

  function buildReviewSection(title, step, rows) {
    var rowsHtml = rows
      .map(function (r) {
        return (
          '<div class="review-row">' +
          '<span class="review-row__label">' +
          $("<span>").text(r.label).html() +
          "</span>" +
          '<span class="review-row__value">' +
          $("<span>").text(r.value).html() +
          "</span>" +
          "</div>"
        );
      })
      .join("");

    var $sec = $(
      '<div class="review-section">' +
        '<div class="review-section__header">' +
        '<span class="review-section__title">' +
        $("<span>").text(title).html() +
        "</span>" +
        '<button type="button" class="review-section__edit" data-goto-step="' +
        step +
        '">Edit</button>' +
        "</div>" +
        '<div class="review-section__body">' +
        rowsHtml +
        "</div>" +
        "</div>",
    );
    return $sec;
  }

  // ── Publish / Save as Draft ───────────────────────────────
  function submitFinal(action) {
    var $btn = action === "publish" ? $("#publish-btn") : $("#save-draft-btn");
    setLoading($btn, true);

    var fd = new FormData();
    fd.append("csrfmiddlewaretoken", CSRF);
    fd.append("action", action);
    if (bannerFile) fd.append("banner", bannerFile);

    $.ajax({
      url: stepUrl(6),
      method: "POST",
      data: fd,
      processData: false,
      contentType: false,
      headers: { "X-CSRFToken": CSRF, "X-Requested-With": "XMLHttpRequest" },
      success: function (data) {
        if (data.success) {
          window.showToast(data.message || "Done!", "success");
          setTimeout(function () {
            window.location.href = data.redirect_url;
          }, 800);
        } else {
          var errors = data.errors || {};
          $.each(errors, function (k, v) {
            window.showToast(String(v), "danger");
          });
          setLoading($btn, false);
        }
      },
      error: function () {
        window.showToast("Something went wrong. Please try again.", "danger");
        setLoading($btn, false);
      },
    });
  }

  $("#publish-btn").on("click", function () {
    submitFinal("publish");
  });
  $("#save-draft-btn").on("click", function () {
    submitFinal("draft");
  });

  // ── Discard draft ─────────────────────────────────────────
  $("#wizardDiscardConfirmBtn").on("click", function () {
    bootstrap.Modal.getInstance(
      document.getElementById("wizardConfirmModal"),
    ).hide();
    $.ajax({
      url: DISCARD_URL,
      method: "POST",
      headers: csrfHeaders(),
      success: function () {
        window.location.href = "/events/create/";
      },
    });
  });

  // ── Restore draft data on load (edit mode) ────────────────
  function restoreDraft() {
    var s1 = draft["1"] || {};
    if (s1.title) $("#id_title").val(s1.title);
    if (s1.category_id) $("#id_category").val(s1.category_id);
    if (s1.description) {
      quill.root.innerHTML = s1.description;
      $("#id_description").val(s1.description);
    }

    // Restore tags in original saved order using tag_ids as the sequence
    if (s1.tag_ids && s1.tag_ids.length) {
      // Build a name lookup for custom tags: pk → name
      // Custom tags were saved with their PKs in tag_ids and names in custom_names.
      // We need to map PKs back to names — fetch from the server isn't feasible here,
      // so we store a pk→name map in the draft alongside custom_names.
      var customPkToName = s1.custom_pk_names || {};

      // Build set of predefined chip PKs available in the DOM
      var predefinedAvailable = {};
      $("[data-tag-id]").each(function () {
        predefinedAvailable[$(this).data("tag-id")] = $(this);
      });

      s1.tag_ids.forEach(function (id) {
        if (predefinedAvailable[id]) {
          // Predefined tag — activate chip and add pill
          var $chip = predefinedAvailable[id];
          if (!selectedTags[String(id)]) {
            selectedTags[String(id)] = {
              id: id,
              name: $chip.data("tag-name"),
              isCustom: false,
            };
            $chip.addClass("is-selected").attr("aria-pressed", "true");
            addTagPill(String(id), $chip.data("tag-name"));
          }
        } else if (customPkToName[id]) {
          // Custom tag — restore by name using the pk→name map
          var name = customPkToName[id];
          var key = "custom:" + name.toLowerCase();
          if (!selectedTags[key]) {
            selectedTags[key] = { id: null, name: name, isCustom: true };
            addTagPill(key, name);
          }
        }
      });
    }

    var s2 = draft["2"] || {};
    if (s2.timezone) $("#id_timezone").val(s2.timezone);
    if (s2.starts_at) $("#id_starts_at").val(s2.starts_at.slice(0, 16));
    if (s2.ends_at) $("#id_ends_at").val(s2.ends_at.slice(0, 16));
    if (s2.venue_name) {
      selectVenue({
        id: s2.venue_id || null,
        name: s2.venue_name,
        city: s2.venue_city || "",
        address: s2.venue_address || "",
        lat: s2.venue_lat || "",
        lng: s2.venue_lng || "",
        osm_id: s2.venue_osm_id || "",
        source: "local",
      });
    }

    var s4 = draft["4"] || {};
    if (s4.collaborator_ids && s4.collaborator_ids.length) {
      // Collaborators are restored from server context — skipped here
      // as we don't have full profile data in the draft; organizer re-adds if needed.
    }

    var s5 = draft["5"] || {};
    if (s5.ticket_types && s5.ticket_types.length) {
      s5.ticket_types.forEach(function (tt) {
        addTicketRow(tt);
      });
    }

    // Jump to furthest step reached
    if (maxReached > 1) {
      goToStep(maxReached > 6 ? 6 : maxReached);
    }
  }

  // ── DateTime constraints ──────────────────────────────────
  function toLocalDateTimeString(date) {
    // Returns 'YYYY-MM-DDTHH:MM' in local time for use as min attribute
    var pad = function (n) {
      return String(n).padStart(2, "0");
    };
    return (
      date.getFullYear() +
      "-" +
      pad(date.getMonth() + 1) +
      "-" +
      pad(date.getDate()) +
      "T" +
      pad(date.getHours()) +
      ":" +
      pad(date.getMinutes())
    );
  }

  function initDateTimeConstraints() {
    var $start = $("#id_starts_at");
    var $end = $("#id_ends_at");

    // Start cannot be in the past
    var now = toLocalDateTimeString(new Date());
    $start.attr("min", now);

    // End must be after start — update min whenever start changes
    $start.on("change", function () {
      var startVal = $(this).val();
      if (startVal) {
        $end.attr("min", startVal);
        // If end is already set and is now before start, clear it
        if ($end.val() && $end.val() <= startVal) {
          $end.val("");
        }
      }
    });

    // If start already has a value on load (edit mode), apply min to end
    if ($start.val()) {
      $end.attr("min", $start.val());
    }
  }

  // ── Init ──────────────────────────────────────────────────
  $(function () {
    initDateTimeConstraints();
    if (Object.keys(draft).length) restoreDraft();
    // Ensure step 1 is visible on fresh load
    goToStep(maxReached > 1 ? maxReached : 1);
  });
})(window.jQuery);
