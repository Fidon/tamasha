/**
 * Tamasha Events — Event Detail Page
 * Handles: organizer actions via Bootstrap modal, share button.
 */
(function ($) {
  "use strict";

  var cfg = window.TAMASHA || {};
  var csrf = cfg.csrfToken || "";
  var isPrimary = cfg.isPrimaryOrganizer || false;

  // ── Bootstrap confirmation modal ──────────────────────────
  var $modal = $("#confirmModal");
  var $modalOk = $("#confirmModalOk");
  var pendingUrl = null;
  var pendingAction = null;

  if (isPrimary && $modal.length) {
    // Populate modal when a trigger button opens it
    $modal[0].addEventListener("show.bs.modal", function (e) {
      var $trigger = $(e.relatedTarget);
      var title = $trigger.data("confirm-title") || "Confirm";
      var body = $trigger.data("confirm-body") || "Are you sure?";
      var label = $trigger.data("confirm-label") || "Confirm";
      var isDanger = $trigger.data("confirm-danger");

      pendingUrl = $trigger.data("url");
      pendingAction = $trigger.data("action");

      $("#confirmModalLabel").text(title);
      $("#confirmModalBody").text(body);
      $modalOk
        .text(label)
        .removeClass("btn-primary btn-danger")
        .addClass(isDanger ? "btn-danger" : "btn-primary");
    });

    // Execute the action when OK is clicked
    $modalOk.on("click", function () {
      if (!pendingUrl) return;

      var $btn = $modalOk;
      $btn
        .prop("disabled", true)
        .html(
          '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Working…',
        );

      bootstrap.Modal.getInstance($modal[0]).hide();

      $.ajax({
        url: pendingUrl,
        method: "POST",
        data: { csrfmiddlewaretoken: csrf },
        success: function (data) {
          if (data.success) {
            window.showToast(data.message || "Done.", "success");
            if (data.redirect_url) {
              setTimeout(function () {
                window.location.href = data.redirect_url;
              }, 900);
            } else {
              setTimeout(function () {
                window.location.reload();
              }, 900);
            }
          } else {
            window.showToast(data.error || "Something went wrong.", "danger");
          }
        },
        error: function () {
          window.showToast("Request failed. Please try again.", "danger");
        },
        complete: function () {
          $btn
            .prop("disabled", false)
            .text($btn.data("confirm-label") || "Confirm");
          pendingUrl = null;
          pendingAction = null;
        },
      });
    });
  }

  // ── Share: copy link ──────────────────────────────────────
  $(document).on("click", '[data-share="copy"]', function () {
    var url = $(this).data("url") || window.location.href;
    copyToClipboard(url, "Link copied to clipboard!");
  });

  // ── Share: copy for Instagram ─────────────────────────────
  $(document).on("click", '[data-share="instagram"]', function () {
    var url = $(this).data("url") || window.location.href;
    var title = $(this).data("title") || document.title;
    var caption = title + "\n\n" + url;
    copyToClipboard(
      caption,
      "Caption copied! Paste it into your Instagram post.",
    );
  });

  function copyToClipboard(text, successMsg) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard
        .writeText(text)
        .then(function () {
          window.showToast(successMsg, "success");
        })
        .catch(function () {
          fallbackCopy(text, successMsg);
        });
    } else {
      fallbackCopy(text, successMsg);
    }
  }

  function fallbackCopy(text, successMsg) {
    var $tmp = $("<textarea>").val(text).appendTo("body").select();
    try {
      document.execCommand("copy");
      window.showToast(successMsg || "Copied!", "success");
    } catch (e) {
      window.showToast("Could not copy. Please copy manually.", "danger");
    }
    $tmp.remove();
  }
})(window.jQuery);
