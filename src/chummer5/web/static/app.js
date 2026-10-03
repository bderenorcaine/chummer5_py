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
})();
