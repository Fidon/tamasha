/**
 * Tamasha Events — Profile JS
 * Handles profile update form AJAX submission with multipart support.
 */

(function ($) {
  "use strict";

  function getCsrf() {
    return document.cookie.match(/csrftoken=([^;]+)/)?.[1] || "";
  }

  function setLoading(btnId, loading) {
    var $btn = $(btnId);
    var $label = $btn.find(".btn-label");
    var $spinner = $btn.find(".btn-spinner");
    $btn.prop("disabled", loading);
    $label.toggleClass("d-none", loading);
    $spinner.toggleClass("d-none", !loading);
  }

  function clearErrors() {
    $(".field-error").text("");
    $(".form-control").removeClass("is-invalid");
    $("#profile-form-error").addClass("d-none").text("");
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

  $("#profile-form").on("submit", function (e) {
    e.preventDefault();
    clearErrors();
    setLoading("#profile-btn", true);

    var formData = new FormData(this);

    $.ajax({
      url: window.location.pathname,
      method: "POST",
      data: formData,
      processData: false,
      contentType: false,
      headers: { "X-CSRFToken": getCsrf() },
      success: function (res) {
        setLoading("#profile-btn", false);
        if (res.success) {
          window.showToast(res.message, "success");
        }
      },
      error: function (xhr) {
        setLoading("#profile-btn", false);
        var data = xhr.responseJSON || {};
        if (data.errors) {
          showFieldErrors(data.errors);
        } else {
          $("#profile-form-error")
            .text(data.error || "Failed to update profile. Please try again.")
            .removeClass("d-none");
        }
      },
    });
  });
})(window.jQuery);
