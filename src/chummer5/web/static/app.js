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

  // --- Client-side table filters (Skills, Resources' gear, Spells) -----------------------------
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

  // Skills. The fragment -- inputs, rows and all -- is rebuilt on every hx-post to /ui/skills, so
  // the filter's state lives here and is restored into the fresh controls after each swap (the
  // same shape as the <details> store above).
  var skillFilter = { query: "", ratedOnly: false };

  function applySkillFilter() {
    var input = document.getElementById("skill-filter");
    var rated = document.getElementById("skill-rated-only");
    if (!input || !rated) return;
    var query = input.value.trim().toLowerCase();
    var onlyRated = rated.checked;
    skillFilter.query = input.value;
    skillFilter.ratedOnly = onlyRated;
    filterGroups(
      "#skill-tables details",
      "tr[data-skill-name]",
      function (row) {
        var matchesName = !query || row.dataset.skillName.includes(query);
        var matchesRated = !onlyRated || Number(row.dataset.skillRating) > 0;
        return matchesName && matchesRated;
      },
      Boolean(query || onlyRated)
    );
  }

  function restoreSkillFilter() {
    var input = document.getElementById("skill-filter");
    var rated = document.getElementById("skill-rated-only");
    if (!input || !rated || input.dataset.restored) return;
    input.dataset.restored = "true";
    input.value = skillFilter.query;
    rated.checked = skillFilter.ratedOnly;
    applySkillFilter();
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

  function applySpellFilter() {
    var select = document.getElementById("spell-known-filter");
    if (!select) return;
    var mode = select.value;
    filterGroups(
      "#spell-tables details",
      "tr[data-spell-selected]",
      function (row) {
        var selected = row.dataset.spellSelected === "true";
        return mode === "all" || (mode === "known" && selected) || (mode === "unknown" && !selected);
      },
      mode !== "all"
    );
  }

  document.addEventListener("input", function (e) {
    var id = e.target && e.target.id;
    if (id === "skill-filter") applySkillFilter();
    else if (id === "gear-filter") applyGearFilter();
  });

  document.addEventListener("change", function (e) {
    var id = e.target && e.target.id;
    if (id === "skill-rated-only") applySkillFilter();
    else if (id === "spell-known-filter") applySpellFilter();
  });

  // `htmx:load` fires for the initial page and for every piece of swapped-in content.
  document.addEventListener("htmx:load", restoreSkillFilter);

  // --- WP144 (Phase Z): the Priorities page's drag-to-reorder and Sum-to-Ten spinners ----------
  // Everything rule-bearing is the server's (WP143): which letters the rows stand for, the point
  // scale and its texts, the ∑ target, and whether the form is confirmable. This only moves
  // tiles and steps spinners, writes the hidden letter inputs, and asks for a preview.

  // The preview listens for this on the form (`priority-input from:#priority-form delay:150ms`),
  // so a burst of changes becomes one request.
  function requestPriorityPreview(form) {
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
})();
