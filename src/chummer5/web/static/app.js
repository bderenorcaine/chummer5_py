// WP141: the page's own behavior, in one static file so the Content-Security-Policy can be
// `script-src 'self'` with no 'unsafe-inline' and no 'unsafe-eval'. Before WP141 these were four
// inline <script> blocks (one in base.html, three inside step fragments that htmx re-ran on every
// swap) plus an htmx event filter that htmx evaluates with `new Function`. Everything here listens
// on `document`, so it survives swaps without re-binding, and runs once per page load.
(function () {
  // --- WP64 (trimmed by WP97): sub-category <details> keep their open state across swaps -------
  // Each such <details> carries a stable data-details-key; the store lives here, outside every
  // swap target, so it survives a step's own fragment swap and a nav page swap.
  var openState = {};

  // `toggle` doesn't bubble, so listen in the capture phase to catch every <details>.
  document.addEventListener(
    "toggle",
    function (e) {
      var d = e.target;
      if (!(d instanceof HTMLDetailsElement)) return;
      var key = d.getAttribute("data-details-key");
      if (key) openState[key] = d.open;
    },
    true
  );

  document.addEventListener("htmx:afterSwap", function () {
    document.querySelectorAll("details[data-details-key]").forEach(function (d) {
      var key = d.getAttribute("data-details-key");
      if (key in openState) d.open = openState[key];
    });
  });

  // --- Number inputs autosubmit while typing (was `input[event.target.type=='number']`) -------
  // The step forms trigger on `change, number-input delay:400ms`: re-dispatched from here so htmx
  // needs no event-filter expression (which it would evaluate, and the CSP forbids).
  document.addEventListener("input", function (e) {
    var t = e.target;
    if (t instanceof HTMLInputElement && t.type === "number") {
      t.dispatchEvent(new CustomEvent("number-input", { bubbles: true }));
    }
  });

  // --- Client-side table filters (Skills, Resources' gear) ------------------------------------
  // Each hides rows of the tables inside its own fragment; a <details> group with no visible row
  // hides too, and a group with a match opens while a filter is active.
  function filterGroups(groupsSelector, rowSelector, matches, active) {
    document.querySelectorAll(groupsSelector).forEach(function (details) {
      var anyVisible = false;
      details.querySelectorAll(rowSelector).forEach(function (row) {
        var match = matches(row);
        row.hidden = !match;
        if (match) anyVisible = true;
      });
      details.hidden = !anyVisible;
      if (active && anyVisible) details.open = true;
    });
  }

  // Skills (WP150): the Filtered and Rated views. The server renders every section but Group,
  // each marked `data-skills-view`, and every row with `data-skill-key`/`-name`/`-rating`; this
  // only narrows them -- a row out of the view is hidden, and so is a section left empty. Both
  // fragments rebuild themselves on every autosave, so the state lives here and is reapplied to
  // whatever loads (the same shape as the <details> store above).
  var skillFilter = { query: "" };
  var ratedKeys = null; // the Rated view's rows, fixed when the tab opens

  function skillsTab() {
    var fragment = document.getElementById("skill-allocation");
    return fragment ? fragment.getAttribute("data-skills-tab") : null;
  }

  function narrowSkillViews(keep) {
    document.querySelectorAll("section[data-skills-view]").forEach(function (section) {
      var anyVisible = false;
      section.querySelectorAll("tr[data-skill-key]").forEach(function (row) {
        var match = keep(row);
        row.hidden = !match;
        if (match) anyVisible = true;
      });
      section.hidden = !anyVisible;
    });
  }

  function applySkillFilter() {
    var input = document.getElementById("skill-filter");
    if (!input || skillsTab() !== "filtered") return;
    skillFilter.query = input.value;
    var query = input.value.trim().toLowerCase();
    narrowSkillViews(function (row) {
      return !query || row.dataset.skillName.includes(query);
    });
  }

  // A fresh filter field (the Skills fragment re-rendered) gets the query back once; every load
  // reapplies it, since a Knowledge autosave brings new rows but no new field.
  function restoreSkillFilter() {
    var input = document.getElementById("skill-filter");
    if (!input) return;
    if (!input.dataset.restored) {
      input.dataset.restored = "true";
      input.value = skillFilter.query;
    }
    applySkillFilter();
  }

  // Rated: the rows rated when the tab opens stay listed until the player leaves it, so a row set
  // to 0 doesn't vanish under the cursor (standing rule 1). `entering` is a page render -- the tab
  // link, history, a reload -- as opposed to a fragment's own autosave swap.
  function applyRated(entering) {
    if (skillsTab() !== "rated") {
      ratedKeys = null;
      return;
    }
    if (entering || ratedKeys === null) {
      ratedKeys = {};
      document.querySelectorAll("section[data-skills-view] tr[data-skill-key]").forEach(function (row) {
        if (Number(row.dataset.skillRating) > 0) ratedKeys[row.dataset.skillKey] = true;
      });
    }
    narrowSkillViews(function (row) {
      return ratedKeys[row.dataset.skillKey] === true;
    });
  }

  function applyGearFilter() {
    var input = document.getElementById("gear-filter");
    if (!input) return;
    var query = input.value.trim().toLowerCase();
    filterGroups(
      "#gear-tables details",
      "tr[data-gear-name]",
      function (row) {
        return (
          !query || row.dataset.gearName.includes(query) || row.dataset.gearCategory.includes(query)
        );
      },
      Boolean(query)
    );
  }

  document.addEventListener("input", function (e) {
    var id = e.target && e.target.id;
    if (id === "skill-filter") applySkillFilter();
    else if (id === "gear-filter") applyGearFilter();
  });

  document.addEventListener("change", function (e) {
    var id = e.target && e.target.id;
    if (id === "skills-tab-select") followSkillsTabSelect(e.target);
  });

  // `htmx:load` fires for the initial page and for every piece of swapped-in content.
  document.addEventListener("htmx:load", function (e) {
    var elt = e.detail && e.detail.elt;
    var entering =
      !!elt &&
      !!elt.querySelector &&
      ((elt.classList && elt.classList.contains("page--skills")) ||
        elt.querySelector(".page--skills") !== null);
    restoreSkillFilter();
    applyRated(entering);
  });

  // WP150: the Skills tab dropdown (narrow widths). A choice clicks the strip's own link for that
  // tab -- hidden at this width, but still wired by htmx -- so it makes the same request and the
  // same history entry as a tab click.
  function followSkillsTabSelect(select) {
    var link = document.querySelector(
      '#skills-tabs a.view-tab[href="' + select.value + '"]'
    );
    if (link) link.click();
  }

  // --- WP144 (Phase Z): the Priorities page's drag-to-reorder and Sum-to-Ten spinners ----------
  // Everything rule-bearing is the server's (WP143): which letters the rows stand for, the point
  // scale and its texts, the ∑ target, and whether the form is confirmable. This only moves
  // tiles and steps spinners, writes the hidden letter inputs, and asks for a preview.

  // The preview listens for this on the form (`priority-input from:#priority-form delay:150ms`),
  // so a burst of changes becomes one request.
  function requestPriorityPreview(form) {
    noteLeaveEdit(); // WP145: the status on the page is now out of date
    if (form) form.dispatchEvent(new CustomEvent("priority-input", { bubbles: true }));
  }

  // Priority: after any reorder, each tile's hidden input takes the letter of the row it is in.
  function rewriteTileLetters(list) {
    var letters = (list.getAttribute("data-priority-letters") || "").split(" ");
    Array.prototype.forEach.call(list.children, function (tile, index) {
      var input = tile.querySelector('input[type="hidden"]');
      if (input && letters[index]) input.value = letters[index];
    });
  }

  function announceTile(tile) {
    var live = document.getElementById("priority-live");
    var input = tile.querySelector('input[type="hidden"]');
    if (!live || !input) return;
    var text = tile.getAttribute("data-announce-" + input.value.toLowerCase());
    if (text) live.textContent = text; // server-rendered (WP102): no text is composed here
  }

  function tilesReordered(list, moved) {
    rewriteTileLetters(list);
    if (moved) announceTile(moved);
    requestPriorityPreview(list.closest("form"));
  }

  // One Sortable per tile list. The panel is swapped in by navigation, the method switch, Revert
  // and CONFIRM, so every newly loaded list gets an instance -- and never a second one.
  function initPriorityTiles(root) {
    if (!window.Sortable || !root.querySelectorAll) return;
    var lists = Array.prototype.slice.call(root.querySelectorAll("#priority-tiles"));
    if (root.id === "priority-tiles") lists.push(root);
    lists.forEach(function (list) {
      if (window.Sortable.get(list)) return;
      window.Sortable.create(list, {
        animation: 150,
        // A touch must be held before it drags, so a swipe over the tiles still scrolls the
        // page (portrait phones). Mouse drags start at once.
        delay: 250,
        delayOnTouchOnly: true,
        touchStartThreshold: 5,
        ghostClass: "priority-tile--ghost",
        chosenClass: "priority-tile--chosen",
        onUpdate: function (evt) {
          tilesReordered(list, evt.item);
        },
      });
    });
  }

  document.addEventListener("htmx:load", function (e) {
    initPriorityTiles(e.detail && e.detail.elt ? e.detail.elt : document);
  });

  // A swapped-out list's instance goes with it.
  document.addEventListener("htmx:beforeCleanupElement", function (e) {
    var elt = e.detail && e.detail.elt;
    if (elt && elt.id === "priority-tiles" && window.Sortable) {
      var instance = window.Sortable.get(elt);
      if (instance) instance.destroy();
    }
  });

  // Keyboard reordering: Alt+↑ / Alt+↓ on a focused tile. The *neighbour* is moved, not the
  // tile: moving the focused node itself would drop its focus in most browsers.
  function moveTileByKey(tile, up) {
    var list = tile.parentNode;
    if (up) {
      var prev = tile.previousElementSibling;
      if (!prev) return;
      list.insertBefore(prev, tile.nextSibling);
    } else {
      var next = tile.nextElementSibling;
      if (!next) return;
      list.insertBefore(next, tile);
    }
    tile.focus();
    tilesReordered(list, tile);
  }

  // Sum-to-Ten: a spinner steps along the scale the server rendered beside it (lowest first).
  function sumToTenBox(el) {
    return el.closest(".sum-to-ten");
  }

  function scaleItem(box, points) {
    return box.querySelector('.sum-to-ten__scale > li[data-points="' + points + '"]');
  }

  // CONFIRM stays the server's call (`data-priority-confirmable`). The script may only disable
  // it early, while ∑ is off target -- including right after a preview answered for an older
  // state that was on target.
  function guardSumToTen(box) {
    var form = box.closest("form");
    var total = 0;
    box.querySelectorAll(".sum-to-ten__value").forEach(function (spinner) {
      total += Number(spinner.getAttribute("aria-valuenow")) || 0;
    });
    var target = Number(box.getAttribute("data-sum-to-ten-target"));
    var off = total !== target;
    var sum = box.querySelector(".sum-to-ten__sum");
    if (sum) sum.value = String(total);
    var row = box.querySelector(".sum-to-ten__row--total");
    if (row) row.classList.toggle("sum-to-ten__row--off", off);
    var confirm = form && form.querySelector(".priority-actions__confirm");
    if (confirm && off) confirm.disabled = true;
  }

  function stepSpinner(spinner, delta) {
    var box = sumToTenBox(spinner);
    if (!box) return;
    var min = Number(spinner.getAttribute("aria-valuemin"));
    var max = Number(spinner.getAttribute("aria-valuemax"));
    var now = Number(spinner.getAttribute("aria-valuenow"));
    var next = Math.max(min, Math.min(max, now + delta)); // stops at A and E, no wrapping
    var item = scaleItem(box, next);
    if (next === now || !item) return;
    spinner.setAttribute("aria-valuenow", String(next));
    spinner.setAttribute("aria-valuetext", item.getAttribute("data-valuetext"));
    spinner.textContent = item.textContent; // the server's own "E (0)" text for that step
    var input = spinner.parentNode.querySelector('input[type="hidden"]');
    if (input) input.value = item.getAttribute("data-letter");
    guardSumToTen(box);
    requestPriorityPreview(box.closest("form"));
  }

  document.addEventListener("keydown", function (e) {
    var t = e.target;
    if (!(t instanceof HTMLElement)) return;
    if (t.classList.contains("priority-tile") && e.altKey && !e.ctrlKey && !e.metaKey) {
      if (e.key === "ArrowUp" || e.key === "ArrowDown") {
        e.preventDefault();
        moveTileByKey(t, e.key === "ArrowUp");
      }
    } else if (t.classList.contains("sum-to-ten__value") && !e.altKey && !e.ctrlKey) {
      // Up raises the priority (towards A, more points).
      if (e.key === "ArrowUp" || e.key === "ArrowDown") {
        e.preventDefault();
        stepSpinner(t, e.key === "ArrowUp" ? 1 : -1);
      }
    }
  });

  document.addEventListener("click", function (e) {
    var button = e.target instanceof Element ? e.target.closest(".sum-to-ten__step") : null;
    if (!button) return;
    var spinner = button.parentNode.querySelector(".sum-to-ten__value");
    if (!spinner) return;
    // Focus the value, not the button, so the wheel and arrow keys work on it next.
    spinner.focus();
    stepSpinner(spinner, Number(button.getAttribute("data-step")));
  });

  // The wheel steps a spinner only while it has focus *and* the pointer is over it, so scrolling
  // the page across the panel never changes a value. Trackpads send many small pixel deltas:
  // those accumulate, one step per WHEEL_STEP. A mouse notch (a large delta) or a line/page-mode
  // event is one step, however large its delta.
  var WHEEL_STEP = 50;
  var WHEEL_IDLE_MS = 250;
  var wheel = { spinner: null, sum: 0, last: 0 };

  document.addEventListener(
    "wheel",
    function (e) {
      var area = e.target instanceof Element ? e.target.closest(".sum-to-ten__spinner") : null;
      var spinner = area && area.querySelector(".sum-to-ten__value");
      if (!spinner || document.activeElement !== spinner || e.deltaY === 0) return;
      e.preventDefault();
      var now = Date.now();
      if (
        wheel.spinner !== spinner ||
        now - wheel.last > WHEEL_IDLE_MS ||
        (wheel.sum !== 0 && wheel.sum > 0 !== e.deltaY > 0)
      ) {
        wheel.sum = 0;
      }
      wheel.spinner = spinner;
      wheel.last = now;
      if (e.deltaMode !== 0 || Math.abs(e.deltaY) >= WHEEL_STEP) {
        wheel.sum = 0;
        stepSpinner(spinner, e.deltaY < 0 ? 1 : -1); // wheel up: towards A
        return;
      }
      wheel.sum += e.deltaY;
      if (Math.abs(wheel.sum) >= WHEEL_STEP) {
        stepSpinner(spinner, wheel.sum < 0 ? 1 : -1);
        wheel.sum = 0;
      }
    },
    { passive: false }
  );

  // A preview swap re-renders CONFIRM from the server's verdict; re-apply the early disable if
  // the spinners have moved off target since that request went out.
  document.addEventListener("htmx:afterSwap", function (e) {
    var target = e.detail && e.detail.target;
    if (!target || target.id !== "priority-preview") return;
    var box = target.closest("form") && target.closest("form").querySelector(".sum-to-ten");
    if (box) guardSumToTen(box);
  });

  // --- WP145 (Phase Z): asking before unconfirmed priorities leave the page -------------------
  // While the Priorities panel holds edits the rest of the character doesn't use (status
  // "changed", or "unconfirmed" once the player has touched the form), anything that would take
  // the panel off the page asks first: Confirm and continue / Stay / Revert (or Discard) and
  // continue. htmx requests are held at `htmx:confirm`, plain links and forms at click/submit,
  // and the back button at `popstate`. Reload, closing the tab and typed URLs get the browser's
  // own generic prompt (`beforeunload`): a page can't show its own dialog there.
  var leave = {
    changeSeq: 0, // bumped by every edit in the panel
    sentSeq: 0, // `changeSeq` when the newest preview request went out
    answeredSeq: 0, // `changeSeq` the status on the page answers for
    touched: false, // the player edited this panel (what matters before the first confirmation)
    keepTouched: false, // the panel about to load is the panel's own response (method, CONFIRM)
    url: null, // the Priorities page's URL, to put back when the back button is held
    resume: null, // what "continue" does, while the dialog is open
    afterConfirm: null, // what to do once the server says the confirmation succeeded
    passBack: false, // a back navigation the player already agreed to
    unloading: false, // a page navigation the player already agreed to
  };

  function noteLeaveEdit() {
    leave.changeSeq += 1;
    leave.touched = true;
  }

  function prioritySection() {
    return document.getElementById("priority-section");
  }

  // The dirty window: until a preview answers for the latest edit, the status attribute is stale,
  // so the form counts as dirty -- never "clean" on the strength of an out-of-date attribute.
  function priorityDirty() {
    if (!prioritySection()) return false;
    if (leave.changeSeq > leave.answeredSeq) return true;
    var status = document.getElementById("priority-status");
    var value = status && status.getAttribute("data-priority-status");
    return value === "changed" || (value === "unconfirmed" && leave.touched);
  }

  // Confirm only when the server says the form is confirmable *for the latest edit*.
  function syncLeaveConfirm(dialog) {
    var status = document.getElementById("priority-status");
    var confirmable =
      status &&
      status.getAttribute("data-priority-confirmable") === "true" &&
      leave.changeSeq <= leave.answeredSeq;
    var button = dialog.querySelector('[data-leave-choice="confirm"]');
    if (button) button.disabled = !confirmable;
  }

  function askBeforeLeaving(resume) {
    var dialog = document.getElementById("priority-leave");
    if (!dialog || typeof dialog.showModal !== "function") {
      resume(); // no <dialog> support: the edits are lost, as they were before WP145
      return;
    }
    leave.resume = resume;
    syncLeaveConfirm(dialog);
    if (!dialog.open) dialog.showModal(); // Stay has `autofocus`; Escape closes as Stay
  }

  function confirmThen(resume) {
    var form = document.getElementById("priority-form");
    if (!form) return;
    leave.afterConfirm = resume;
    if (typeof form.requestSubmit === "function") form.requestSubmit();
    else window.htmx.trigger(form, "submit");
  }

  // The dialog's buttons. Whatever closes it otherwise (Escape) is Stay.
  document.addEventListener("click", function (e) {
    var button = e.target instanceof Element ? e.target.closest("[data-leave-choice]") : null;
    if (!button) return;
    var choice = button.getAttribute("data-leave-choice");
    var resume = leave.resume;
    leave.resume = null;
    var dialog = button.closest("dialog");
    if (dialog && dialog.open) dialog.close(choice);
    if (!resume || choice === "stay") return;
    if (choice === "confirm") confirmThen(resume);
    else resume(); // revert/discard: nothing server-side changed, so just go
  });

  document.addEventListener(
    "close",
    function (e) {
      if (e.target && e.target.id === "priority-leave") leave.resume = null;
    },
    true // `close` doesn't bubble
  );

  // Success is the server's explicit signal (`HX-Trigger-After-Settle: priorities-confirmed`),
  // fired once the swap -- a whole new shell, on the first confirmation -- has settled.
  document.addEventListener("priorities-confirmed", function () {
    var resume = leave.afterConfirm;
    leave.afterConfirm = null;
    if (resume) resume();
  });

  // ... and anything else (an error, a refused first store, a 409 notice) means stay: the
  // response shows why at the bottom of the panel, as usual.
  document.addEventListener("htmx:afterRequest", function (e) {
    var d = e.detail || {};
    if (!leave.afterConfirm || !d.elt || d.elt.id !== "priority-form") return;
    var signal = d.xhr && d.xhr.getResponseHeader("HX-Trigger-After-Settle");
    if (!d.successful || !signal || signal.indexOf("priorities-confirmed") === -1) {
      leave.afterConfirm = null;
    }
  });

  // Edits the WP144 widgets don't report: the Metatype and method dropdowns. Capture phase, so
  // the edit is counted before htmx sends the request it triggers.
  document.addEventListener(
    "change",
    function (e) {
      var id = e.target && e.target.id;
      if (id === "metatype-select" || id === "priority-method") noteLeaveEdit();
    },
    true
  );

  document.addEventListener("htmx:beforeRequest", function (e) {
    var d = e.detail || {};
    var section = prioritySection();
    if (d.elt && d.elt.id === "priority-preview") {
      leave.sentSeq = leave.changeSeq;
    } else if (section && d.target === section) {
      // Method switch and CONFIRM keep "touched"; Revert is back to the confirmed state.
      var path = (d.requestConfig && d.requestConfig.path) || "";
      leave.keepTouched = path.indexOf("/ui/priorities/revert") !== 0;
    }
  });

  document.addEventListener("htmx:afterSwap", function (e) {
    var target = e.detail && e.detail.target;
    if (!target || target.id !== "priority-preview") return;
    leave.answeredSeq = Math.max(leave.answeredSeq, leave.sentSeq);
    var dialog = document.getElementById("priority-leave");
    if (dialog && dialog.open) syncLeaveConfirm(dialog);
  });

  // A panel arriving (page load, navigation, method switch, Revert, CONFIRM) is the server's
  // answer for everything it shows.
  document.addEventListener("htmx:load", function (e) {
    var elt = e.detail && e.detail.elt;
    if (!elt || !elt.querySelector) return;
    if (elt.id !== "priority-section" && !elt.querySelector("#priority-section")) return;
    leave.sentSeq = leave.answeredSeq = leave.changeSeq;
    leave.touched = leave.keepTouched;
    leave.keepTouched = false;
    leave.url = window.location.href;
  });

  // htmx requests that would take the panel off the page: anything swapped over it (the step
  // nav into #page, a whole-shell swap) and any change made outside it (a character switch
  // re-renders the shell). Not the panel's own requests, not the background refreshes of other
  // regions, and not the display preferences (/ui/prefs/), which don't leave the page.
  function leavesPriorities(d) {
    var section = prioritySection();
    if (!section || !d.elt || section.contains(d.elt)) return false;
    if (String(d.path || "").indexOf("/ui/prefs/") === 0) return false;
    if (d.target && d.target.contains && d.target.contains(section)) return true;
    return String(d.verb).toLowerCase() !== "get";
  }

  // Continue an htmx request that was held. After a first confirmation the shell is new, so the
  // control that asked is gone: replay through its counterpart in the new shell.
  function resumeHtmx(d) {
    return function () {
      if (document.body.contains(d.elt)) {
        d.issueRequest(true);
        return;
      }
      var verb = String(d.verb).toLowerCase();
      var twin = document.querySelector("[hx-" + verb + '="' + CSS.escape(d.path) + '"]');
      if (twin) twin.click();
      else if (verb === "get") window.location.href = d.path;
    };
  }

  // Capture phase, so this runs before tabs.js's switch warning (WP138) and, when it asks,
  // stops that one: one dialog per action. Continuing skips htmx's own confirmation too.
  document.addEventListener(
    "htmx:confirm",
    function (e) {
      var d = e.detail || {};
      if (!leavesPriorities(d) || !priorityDirty()) return;
      e.preventDefault();
      e.stopPropagation();
      askBeforeLeaving(resumeHtmx(d));
    },
    true
  );

  // Plain links that leave the page in this tab (the character list, the account page, ...).
  document.addEventListener(
    "click",
    function (e) {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey)
        return;
      var a = e.target instanceof Element ? e.target.closest("a[href]") : null;
      if (!a || (a.target && a.target !== "_self") || a.hasAttribute("download")) return;
      if (a.hasAttribute("hx-get") || a.hasAttribute("hx-post")) return; // htmx:confirm's
      var href = a.getAttribute("href") || "";
      if (href.charAt(0) === "#" || !priorityDirty()) return;
      e.preventDefault();
      askBeforeLeaving(function () {
        leave.unloading = true;
        window.location.href = a.href;
      });
    },
    true
  );

  // Plain form submissions that leave the page (logout).
  document.addEventListener(
    "submit",
    function (e) {
      var form = e.target;
      if (!(form instanceof HTMLFormElement)) return;
      if (form.hasAttribute("hx-post") || form.hasAttribute("hx-get")) return;
      if ((form.getAttribute("method") || "").toLowerCase() === "dialog" || !priorityDirty()) return;
      e.preventDefault();
      var action = form.getAttribute("action");
      askBeforeLeaving(function () {
        leave.unloading = true;
        // After a first confirmation the title bar is new: submit its copy of the form.
        var live = document.body.contains(form)
          ? form
          : document.querySelector('form[action="' + CSS.escape(action || "") + '"]');
        if (live) live.submit(); // `submit()` fires no submit event, so this doesn't ask again
      });
    },
    true
  );

  // The back (or forward) button. htmx's history restore can't be cancelled, so this listener --
  // added before htmx sets `window.onpopstate` at DOM-ready, hence called first -- stops it, puts
  // the Priorities URL back on top, and asks. Continuing goes back to where the player was
  // headed: it is the entry right under the one put back, whichever button was pressed.
  window.addEventListener("popstate", function (e) {
    if (leave.passBack) {
      leave.passBack = false;
      return;
    }
    if (!priorityDirty() || !leave.url) return;
    e.stopImmediatePropagation();
    history.pushState({ htmx: true }, "", leave.url);
    askBeforeLeaving(function () {
      leave.passBack = true;
      history.back();
    });
  });

  window.addEventListener("beforeunload", function (e) {
    if (leave.unloading || !priorityDirty()) return;
    e.preventDefault();
    e.returnValue = ""; // older browsers ask only when this is set
  });
})();
