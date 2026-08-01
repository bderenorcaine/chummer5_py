[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase V — Post-MVP: UI improvement requests

Feature requests captured 2026-07-27 in the same manual-testing session that raised Phase U's bugs —
QoL improvements to the chargen UI, not defects. Recorded here as future WPs; none is blocking and
they can be picked up in any order. Numbered from WP67, after Phase U claims WP64-66.

**2026-08-01 — WP83/WP84 added from a second manual-testing pass** on the now-complete chargen page
(WP67-71 all landed). One is a defect in WP67's own filter rather than a new request, and is filed
here with it rather than in a third UI-bugfix phase; the other is the first styling this project has
ever had, prompted by the page having grown to ~14 stacked sections.

- [x] **WP67 — Skill picker: filter to skills with a positive rating.**
  Goal: let a player narrow the active-skills list to only the skills they've actually put points in
  (rating > 0), on top of the existing by-name text filter.
  Notes: `_skill_allocation.html:159-177` already has a vanilla-JS name filter over
  `tr[data-skill-name]` rows; this is a small extension — add a checkbox ("Only rated skills") that
  hides rows whose displayed `Rating` is 0 (the rating is already rendered per row, and each row's
  `<details>` category visibility is already recomputed by the existing filter loop). Purely
  client-side, no server round-trip, consistent with WP61's filter design.
  Depends on: nothing.

- [x] **WP68 — Knowledge/Language skills: display a dice pool, like active skills.**
  Goal: the knowledge/language picker (`_knowledge_skills.html`) shows Name/Category/Rating but no
  dice **Pool**; add one column mirroring the active-skills picker.
  Notes: pool = rating + linked attribute (the linked attribute is the category's — Academic/
  Professional → LOG, Street/Interests → INT, Language → INT). `chummer5.web.routes.knowledge`'s
  context builder would compute it per row from the chosen category's linked attribute and the
  character's attribute value; add a `Pool` column to the two tables. Specializations on knowledge
  skills, if supported, get the same `X (Y)` treatment WP65 introduces for active skills.
  Depends on: lighter if done after WP65 (reuse the `X (Y)` spec-pool display helper).

- [x] **WP69 — Spell picker: group spells by category/type and filter for known/unknown.**
  Goal: the spell list (`_spell_selection.html`) is currently one flat table; make it (a) groupable
  by category/type (Combat, Detection, Health, Illusion, Manipulation — the `spell.category` already
  rendered per row) and (b) filterable to show only known (selected) or unknown (unselected) spells.
  Notes: mirror WP61's collapsible-`<details>`-per-category + client-side-filter pattern from the
  skill picker. Grouping is presentation-only; the known/unknown filter keys off each row's
  `row.selected` (already in context). No engine change.
  Depends on: nothing (reuses WP61's grouping/filter pattern).

- [x] **WP70 — Bind spirits at a Force lower than the Magic rating.**
  Goal: currently every bound spirit is fixed at Force = Magic rating (`_spirit_selection.html:14`:
  "each at Force {{ spirit_force }} (your current Magic rating)" — no Force input at all). SR5 lets a
  character bind a spirit at any Force from 1 up to (typically) twice Magic; at chargen the practical
  request is Force ≤ Magic. Add a per-spirit Force selector.
  Notes: this is an engine + UI change, not presentation-only — the binding Karma cost scales with
  Force (Force × Karma per service), so `chummer5.engine.spirits` (the WP46 binding-cost logic) must
  take a per-spirit Force rather than assuming Magic, and `_spirit_selection.html` gains a Force
  `<input>` per row validated against the character's Magic. Check the exact SR5 Force cap and
  chargen binding-cost formula against the rulebook before implementing.
  Depends on: `chummer5.engine.spirits` (Phase M / WP46).

- [x] **WP71 — Gear picker: name/category filter.**
  Goal: the starter-gear picker (`_resources.html`) has collapsible categories but no filter; add a
  by-name (and optionally by-category) text filter like the skill picker's.
  Notes: reuse WP61's exact vanilla-JS filter pattern (`data-*` attribute per row + one `input`
  listener hiding non-matching rows and empty categories). Purely client-side. Naturally pairs with
  WP66 (Rating-priced gear) since a larger catalog makes a filter more valuable, but doesn't depend
  on it.
  Depends on: nothing.

- [x] **WP83 — Skill picker: the filter controls must survive the section being re-rendered.**
  Goal: WP67's "Only rated skills" checkbox (and WP61's by-name text filter alongside it) reset to
  their unfiltered defaults on every skill change, so a player narrowing the picker to their rated
  skills lost that narrowing the moment they edited a rating — exactly when they least want the
  full 76-row list back.
  Notes: not a filter bug — a swap-lifetime bug. `_skill_allocation.html`'s form posts with
  `hx-swap="outerHTML"` on `#skill-allocation`, so htmx rebuilds the controls, the rows, *and* the
  filter script itself from server-rendered HTML on every change; the checkbox comes back at its
  rendered default and the script's closure state dies with the old subtree. Same problem WP64's
  `<details>` store solves for open/closed state, so it takes the same shape: keep the state
  outside the swapped subtree, restore the controls from it, re-apply immediately.
  Depends on: WP67 (the checkbox), WP61 (the text filter).
  Landed as a `window.__skillFilterState` store in `_skill_allocation.html`'s own filter script —
  read back into both controls when the re-rendered script runs, written on every `applyFilter()`,
  and re-applied at init so the rebuilt rows honour it without a second click. Deliberately *not*
  session state: the filter is presentation-only and the server contract stays "render every
  offered skill row", so the only new server-side assertion is that the re-rendered fragment
  carries the restore code (`tests/unit/test_web_attribute_skill_allocation.py`). Persists across
  htmx swaps but not a full page reload, matching WP64's own in-memory store rather than reaching
  for `localStorage`.

- [x] **WP84 — Chargen page: separate the sections visually.**
  Goal: `_chargen_body.html` stacks ~14 `<details>` sections in one `#chargen-body` with no
  styling of any kind, so the page read as one undifferentiated column of text and it was hard to
  tell where one chargen step ended and the next began.
  Notes: the project had no stylesheet at all before this WP — only the vendored htmx under
  `static/`. Keep it that small: this is section separation, not a visual redesign, and it must not
  restyle the forms/tables *inside* a section (in particular nothing may set `display` on a
  `tr`, which WP61/WP67's filters toggle via the `hidden` attribute).
  Depends on: nothing.
  Landed as `src/chummer5/web/static/app.css`, linked from `base.html` and served off the same
  local `/static` mount as the vendored htmx (same no-CDN reason — `test_web_app.py` asserts both).
  Each `#chargen-body > div` becomes its own box with a top rule, a left accent bar, and an
  alternating background tint: two signals rather than one, because the accordion keeps at most one
  section open, so adjacent *collapsed* sections have only their headers to be told apart by. Nested
  `<details>` (skill categories, gear/cyberware groups) get a lighter indent + hairline so the two
  levels don't compete, and the `error`/`warning`/`info` classes the templates have emitted since
  WP14 finally have colours. Light and dark both handled via `prefers-color-scheme` + `color-scheme`.
  Verified by serving and asserting rather than by eye — this devcontainer has no browser.
