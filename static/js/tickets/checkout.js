/**
 * Tamasha Events — Checkout Page
 * Handles: ticket quantity selection, order summary,
 * payment method toggle, AJAX order submission,
 * USSD polling, card redirect.
 */
(function ($) {
  "use strict";

  var cfg = (window.TAMASHA || {}).checkout || {};
  var CHECKOUT_URL = cfg.checkoutUrl || "";
  var CSRF = cfg.csrfToken || "";

  // ── State ─────────────────────────────────────────────────
  var quantities = {}; // { ticket_type_id: qty }
  var pollTimer = null;
  var pollUrl = null;
  var pollAttempts = 0;
  var MAX_POLLS = 36; // 36 × 5s = 3 minutes then give up

  // ── DOM refs ──────────────────────────────────────────────
  var $submitBtn = $("#checkout-submit-btn");
  var $submitTxt = $("#submit-btn-text");
  var $submitBtnMobile = $("#checkout-submit-btn-mobile");
  var $submitTxtMobile = $("#submit-btn-text-mobile");
  var $stickyTotal = $("#sticky-total");
  var $summaryItems = $("#summary-items");
  var $summaryEmpty = $("#summary-empty");
  var $subtotalEl = $("#summary-subtotal");
  var $totalEl = $("#summary-total");
  var $ussdModal = $("#ussdPendingModal");
  var ussdModalInst = null;

  // ── Format TZS ────────────────────────────────────────────
  function formatTZS(amount) {
    if (amount === 0) return "Free";
    return "TZS " + Number(amount).toLocaleString("en-TZ");
  }

  // ── Quantity controls ─────────────────────────────────────
  $(document).on("click", ".ticket-qty-control__inc", function () {
    var $row = $(this).closest(".ticket-selector__row");
    var id = $row.data("ticket-id");
    var max = Math.min(
      parseInt($row.data("max"), 10),
      parseInt($row.data("max-per-order"), 10),
    );
    var cur = quantities[id] || 0;
    if (cur >= max) return;
    quantities[id] = cur + 1;
    updateQtyDisplay($row, quantities[id]);
    updateSummary();
  });

  $(document).on("click", ".ticket-qty-control__dec", function () {
    var $row = $(this).closest(".ticket-selector__row");
    var id = $row.data("ticket-id");
    var cur = quantities[id] || 0;
    if (cur <= 0) return;
    quantities[id] = cur - 1;
    updateQtyDisplay($row, quantities[id]);
    updateSummary();
  });

  function updateQtyDisplay($row, qty) {
    var $val = $row.find(".ticket-qty-control__val");
    var max = Math.min(
      parseInt($row.data("max"), 10),
      parseInt($row.data("max-per-order"), 10),
    );
    $val.text(qty);
    $row.find(".ticket-qty-control__dec").prop("disabled", qty <= 0);
    $row.find(".ticket-qty-control__inc").prop("disabled", qty >= max);
    $row.toggleClass("is-selected", qty > 0);
  }

  // ── Order summary ─────────────────────────────────────────
  function updateSummary() {
    var total = 0;
    var lines = [];

    $(".ticket-selector__row").each(function () {
      var $row = $(this);
      var id = $row.data("ticket-id");
      var qty = quantities[id] || 0;
      var price = parseFloat($row.data("price")) || 0;
      var name = $row.data("name") || "";
      if (qty > 0) {
        var sub = price * qty;
        total += sub;
        lines.push({ name: name, qty: qty, sub: sub, free: price === 0 });
      }
    });

    // Render summary lines
    $summaryItems.empty();
    if (lines.length === 0) {
      $summaryItems.append($summaryEmpty.prop("hidden", false));
      $summaryEmpty.prop("hidden", false);
    } else {
      $summaryEmpty.prop("hidden", true);
      lines.forEach(function (l) {
        var priceStr = l.free ? "Free" : formatTZS(l.sub);
        $summaryItems.append(
          '<div class="checkout-summary__item">' +
            '<span><span class="checkout-summary__item-name">' +
            $("<span>").text(l.name).html() +
            "</span> &times; " +
            l.qty +
            "</span>" +
            "<span>" +
            priceStr +
            "</span>" +
            "</div>",
        );
      });
    }

    $subtotalEl.text(formatTZS(total));
    $totalEl.text(formatTZS(total));
    $stickyTotal.text(formatTZS(total));

    var hasSelection = lines.length > 0;
    var btnLabel = hasSelection
      ? total === 0
        ? "Get Free Tickets"
        : "Proceed to Payment"
      : "Select tickets to continue";
    var mobileBtnLabel = hasSelection
      ? total === 0
        ? "Get Free Tickets"
        : "Pay Now"
      : "Select tickets";

    $submitBtn
      .prop("disabled", !hasSelection)
      .html(
        '<i class="bi bi-lock me-2" aria-hidden="true"></i><span>' +
          btnLabel +
          "</span>",
      );
    $submitTxt = $submitBtn.find("span");

    $submitBtnMobile.prop("disabled", !hasSelection);
    $submitTxtMobile.text(mobileBtnLabel);
  }

  // ── Payment method toggle ─────────────────────────────────
  $(document).on("change", 'input[name="payment_method"]', function () {
    var method = $(this).val();
    $(".payment-method-option").removeClass("is-selected");
    $(this).closest(".payment-method-option").addClass("is-selected");
    $("#mobile-network-wrap").toggle(method === "MOBILE_MONEY");
  });

  // Sync visual state on load
  $('input[name="payment_method"]:checked').trigger("change");

  // ── Field error helpers ───────────────────────────────────
  function showError(field, msg) {
    $("#error-" + field)
      .text(msg)
      .prop("hidden", false);
    $("#id_" + field).addClass("is-invalid");
  }
  function clearErrors() {
    $(".checkout-field__error").text("").prop("hidden", true);
    $(".form-control").removeClass("is-invalid");
  }

  // ── Collect buyer data ────────────────────────────────────
  function collectBuyer() {
    return {
      full_name: $("#id_full_name").val().trim(),
      email: $("#id_email").val().trim(),
      phone: $("#id_phone").val().trim(),
      payment_method:
        $('input[name="payment_method"]:checked').val() || "MOBILE_MONEY",
      mobile_network: $("#id_mobile_network").val(),
    };
  }

  function collectSelections() {
    var sels = [];
    Object.keys(quantities).forEach(function (id) {
      if (quantities[id] > 0) {
        sels.push({
          ticket_type_id: parseInt(id, 10),
          quantity: quantities[id],
        });
      }
    });
    return sels;
  }

  // ── Submit ────────────────────────────────────────────────
  $submitBtn.on("click", function () {
    doSubmit();
  });
  $submitBtnMobile.on("click", function () {
    doSubmit();
  });

  function doSubmit() {
    clearErrors();

    var buyer = collectBuyer();
    var selections = collectSelections();

    // Client-side validation
    var valid = true;
    if (!buyer.full_name) {
      showError("full_name", "Full name is required.");
      valid = false;
    }
    if (!buyer.email) {
      showError("email", "Email address is required.");
      valid = false;
    }

    // Phone: exactly 10 digits starting with 0
    var phone = buyer.phone.replace(/[\s\-]/g, "");
    if (!phone) {
      showError("phone", "Phone number is required.");
      valid = false;
    } else if (!/^0\d{9}$/.test(phone)) {
      showError(
        "phone",
        "Enter a valid 10-digit number starting with 0, e.g. 0784561427.",
      );
      valid = false;
    } else {
      buyer.phone = phone; // use cleaned version
    }

    if (buyer.payment_method === "MOBILE_MONEY" && !buyer.mobile_network) {
      showError("mobile_network", "Please select your mobile network.");
      valid = false;
    }
    if (!valid) return;

    setSubmitting(true);

    $.ajax({
      url: CHECKOUT_URL,
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify({ buyer: buyer, selections: selections }),
      headers: { "X-CSRFToken": CSRF, "X-Requested-With": "XMLHttpRequest" },
      success: function (data) {
        if (!data.success) {
          handleServerErrors(
            data.errors || { __all__: data.error || "Something went wrong." },
          );
          setSubmitting(false);
          return;
        }

        // Free order
        if (data.free) {
          window.showToast("Registration confirmed! Redirecting…", "success");
          setTimeout(function () {
            window.location.href = data.redirect_url;
          }, 800);
          return; // page redirects — no need to reset button
        }

        // USSD push
        if (data.mobile) {
          pollUrl = data.poll_url;
          // Persist poll URL so page refresh doesn't lose it
          try {
            sessionStorage.setItem("tamasha_poll_url", pollUrl);
          } catch (e) {}
          setSubmitting(false);
          showUssdModal(data.message);
          startPolling();
          return;
        }

        // Card redirect
        if (data.card && data.checkout_url) {
          window.showToast("Redirecting to secure payment…", "info");
          setTimeout(function () {
            window.location.href = data.checkout_url;
          }, 600);
          return; // page redirects — no need to reset button
        }

        setSubmitting(false);
        window.showToast("Something went wrong. Please try again.", "danger");
      },
      error: function (xhr) {
        setSubmitting(false);
        var data = xhr.responseJSON || {};
        if (data.errors) {
          handleServerErrors(data.errors);
        } else {
          window.showToast(
            data.error || "Something went wrong. Please try again.",
            "danger",
          );
        }
      },
    });
  } // end doSubmit

  function setSubmitting(loading) {
    if (loading) {
      $submitBtn
        .prop("disabled", true)
        .html(
          '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Processing…',
        );
      $submitBtnMobile
        .prop("disabled", true)
        .html(
          '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Processing…',
        );
    } else {
      var hasSelection = Object.values(quantities).some(function (q) {
        return q > 0;
      });
      var total = 0;
      Object.keys(quantities).forEach(function (id) {
        if (quantities[id] > 0) {
          var price =
            parseFloat(
              $('.ticket-selector__row[data-ticket-id="' + id + '"]').data(
                "price",
              ),
            ) || 0;
          total += price * quantities[id];
        }
      });
      var btnLabel = !hasSelection
        ? "Select tickets to continue"
        : total === 0
          ? "Get Free Tickets"
          : "Proceed to Payment";
      var mobileBtnLabel = !hasSelection
        ? "Select tickets"
        : total === 0
          ? "Get Free Tickets"
          : "Pay Now";
      $submitBtn
        .prop("disabled", !hasSelection)
        .html(
          '<i class="bi bi-lock me-2" aria-hidden="true"></i><span>' +
            btnLabel +
            "</span>",
        );
      $submitBtnMobile
        .prop("disabled", !hasSelection)
        .html(
          '<i class="bi bi-lock me-1" aria-hidden="true"></i><span>' +
            mobileBtnLabel +
            "</span>",
        );
      $stickyTotal.text(formatTZS(total));
    }
  }

  function handleServerErrors(errors) {
    $.each(errors, function (field, msgs) {
      var msg = Array.isArray(msgs) ? msgs[0] : String(msgs);
      if (field === "__all__" || field === "non_field_errors") {
        window.showToast(msg, "danger");
      } else {
        showError(field, msg);
      }
    });
  }

  // ── USSD modal + polling ──────────────────────────────────
  function showUssdModal(message) {
    if (message) $("#ussd-message").html(message);
    if (!ussdModalInst) {
      ussdModalInst = new bootstrap.Modal($ussdModal[0], {
        backdrop: "static",
      });
    }
    ussdModalInst.show();
  }

  function startPolling() {
    if (!pollUrl) return;
    pollAttempts = 0;
    pollTimer = setInterval(function () {
      pollAttempts++;
      if (pollAttempts > MAX_POLLS) {
        stopPolling();
        if (ussdModalInst) ussdModalInst.hide();
        window.showToast(
          "Payment confirmation timed out. If you completed payment, check your email for tickets or contact support.",
          "warning",
        );
        return;
      }
      $.ajax({
        url: pollUrl,
        method: "GET",
        headers: { "X-Requested-With": "XMLHttpRequest" },
        success: function (data) {
          if (data.confirmed) {
            stopPolling();
            if (ussdModalInst) ussdModalInst.hide();
            window.showToast("Payment confirmed! Redirecting…", "success");
            setTimeout(function () {
              window.location.href = data.redirect_url;
            }, 800);
          }
        },
      });
    }, 5000);
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  $("#ussd-cancel-btn").on("click", function () {
    stopPolling();
    if (ussdModalInst) ussdModalInst.hide();
    window.showToast(
      "Payment cancelled. Your order has not been charged.",
      "warning",
    );
  });

  // ── Init ──────────────────────────────────────────────────
  $(function () {
    updateSummary();
    // Initialise all dec buttons as disabled (qty starts at 0)
    $(".ticket-qty-control__dec").prop("disabled", true);
  });
})(window.jQuery);
