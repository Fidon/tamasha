/**
 * Tamasha Events — Become Organizer JS
 * Handles organizer application form AJAX submission + pitch counter.
 */

(function ($) {
  "use strict";

  function getCsrf() {
    return document.cookie.match(/csrftoken=([^;]+)/)?.[1] || "";
  }

  function setLoading(loading) {
    var $btn = $("#organizer-btn");
    var $label = $btn.find(".btn-label");
    var $spinner = $btn.find(".btn-spinner");
    $btn.prop("disabled", loading);
    $label.toggleClass("d-none", loading);
    $spinner.toggleClass("d-none", !loading);
  }

  function clearErrors() {
    $(".field-error").text("");
    $(".form-control").removeClass("is-invalid");
    $("#organizer-form-error").addClass("d-none").text("");
  }

  function showFieldErrors(errors) {
    $.each(errors, function (field, messages) {
      var msg = Array.isArray(messages) ? messages[0] : messages;
      var $err = $("#err-" + field);
      if ($err.length) {
        $err.text(msg);
        $("#id_" + field).addClass("is-invalid");
      }
    });
  }

  // ── Pitch character counter ────────────────────────────────────────────
  $("#id_pitch").on("input", function () {
    var count = $(this).val().length;
    var $counter = $("#pitch-count");
    $counter.text(count);
    $counter.css(
      "color",
      count < 50 ? "var(--color-warning-text)" : "var(--color-success-text)",
    );
  });

  // ── Form submission ────────────────────────────────────────────────────
  $("#organizer-form").on("submit", function (e) {
    e.preventDefault();
    clearErrors();
    setLoading(true);

    $.ajax({
      url: window.location.pathname,
      method: "POST",
      data: $(this).serialize(),
      headers: { "X-CSRFToken": getCsrf() },
      success: function (res) {
        setLoading(false);
        if (res.success) {
          window.showToast(res.message, "success");
          // Reload after short delay so user sees the pending state
          setTimeout(function () {
            window.location.reload();
          }, 1800);
        }
      },
      error: function (xhr) {
        setLoading(false);
        var data = xhr.responseJSON || {};
        if (data.errors) {
          showFieldErrors(data.errors);
        } else {
          $("#organizer-form-error")
            .text(
              data.error || "Failed to submit application. Please try again.",
            )
            .removeClass("d-none");
        }
      },
    });
  });
})(window.jQuery);
