/**
 * Tamasha Events — Auth JS
 * Handles: signup form, login form, password toggle, field error display.
 * Shared across signup.html, login.html, password_reset_confirm.html.
 */

(function ($) {
  "use strict";

  // ── Utilities ──────────────────────────────────────────────────────────

  function getCsrf() {
    return document.cookie.match(/csrftoken=([^;]+)/)?.[1] || "";
  }

  function setLoading(btn, loading) {
    var $btn = $(btn);
    var $label = $btn.find(".btn-label");
    var $spinner = $btn.find(".btn-spinner");
    $btn.prop("disabled", loading);
    $label.toggleClass("d-none", loading);
    $spinner.toggleClass("d-none", !loading);
  }

  function clearErrors() {
    $(".field-error").text("");
    $(".form-control").removeClass("is-invalid");
    $("#form-error, #profile-form-error, #organizer-form-error")
      .addClass("d-none")
      .text("");
  }

  function showFieldErrors(errors) {
    $.each(errors, function (field, messages) {
      var $err = $("#err-" + field);
      var $input = $("#id_" + field);
      var msg = Array.isArray(messages) ? messages[0] : messages;
      if ($err.length) {
        $err.text(msg);
        $input.addClass("is-invalid");
      }
    });
  }

  function showFormError(msg, selector) {
    var $el = $(selector || "#form-error");
    $el.text(msg).removeClass("d-none");
  }

  // ── Password toggle ────────────────────────────────────────────────────

  $(document).on("click", ".btn-password-toggle", function () {
    var targetId = $(this).data("target");
    var $input = $("#" + targetId);
    var $icon = $(this).find("i");
    var isPass = $input.attr("type") === "password";

    $input.attr("type", isPass ? "text" : "password");
    $icon.toggleClass("bi-eye", !isPass).toggleClass("bi-eye-slash", isPass);
    $(this).attr("aria-label", isPass ? "Hide password" : "Show password");
  });

  // ── Signup form ────────────────────────────────────────────────────────

  $("#signup-form").on("submit", function (e) {
    e.preventDefault();
    clearErrors();
    setLoading("#signup-btn", true);

    $.ajax({
      url: window.location.pathname,
      method: "POST",
      data: $(this).serialize(),
      headers: { "X-CSRFToken": getCsrf() },
      success: function (res) {
        if (res.success) {
          window.location.href = res.redirect;
        }
      },
      error: function (xhr) {
        setLoading("#signup-btn", false);
        var data = xhr.responseJSON || {};
        if (data.errors) {
          showFieldErrors(data.errors);
        } else {
          showFormError(
            data.error || "Something went wrong. Please try again.",
          );
        }
      },
    });
  });

  // ── Login form ─────────────────────────────────────────────────────────

  $("#login-form").on("submit", function (e) {
    e.preventDefault();
    clearErrors();
    setLoading("#login-btn", true);

    // Inject localStorage theme so server can sync on login
    var theme = localStorage.getItem("tamasha-theme") || "dark";
    $("#login-theme-input").val(theme);

    var nextParam =
      new URLSearchParams(window.location.search).get("next") || "";
    var url =
      window.location.pathname +
      (nextParam ? "?next=" + encodeURIComponent(nextParam) : "");

    $.ajax({
      url: url,
      method: "POST",
      data: $(this).serialize(),
      headers: { "X-CSRFToken": getCsrf() },
      success: function (res) {
        if (res.success) {
          window.location.href = res.redirect || "/";
        }
      },
      error: function (xhr) {
        setLoading("#login-btn", false);
        var data = xhr.responseJSON || {};
        if (xhr.status === 403) {
          // Axes lockout
          window.location.href = "/accounts/login/?locked=1";
          return;
        }
        if (data.errors) {
          // Django AuthenticationForm puts errors under '__all__'
          var allErrors = data.errors["__all__"] || data.errors;
          if (allErrors["__all__"]) {
            showFormError(allErrors["__all__"][0]);
          } else {
            showFieldErrors(allErrors);
          }
        } else {
          showFormError(data.error || "Invalid email or password.");
        }
      },
    });
  });
})(window.jQuery);
