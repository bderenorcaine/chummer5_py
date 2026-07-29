[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase U — Post-MVP: UI bugfixes round 2

Raised 2026-07-27 from a second hands-on manual browser-testing pass over the shipped chargen UI
(the first since Phase T). Five defects reported; verified against the current templates/routes and
grouped below into three WPs (two summary WPs bundling small/related fixes, one standalone for the
larger gear gap). Numbered from WP64, the next free number after Phase R claimed WP62-63.

**Verification notes shared by more than one WP below.** Three of the five reported defects share a
single root cause: an htmx `hx-swap="outerHTML"` on a section's `<form>` throws away and rebuilds that
section's DOM subtree on every submit, discarding any *client-only* state it held — a manually toggled
`<details>`, the focused/caret position of a text `<input>`, native `<details name>` accordion
grouping. This is the same class of problem `chummer5.web.session.ChargenSession`'s "Post-WP61 fix"
docstring already documents for the top-level accordion; these WPs extend that reasoning to the
sub-accordion and to text inputs.

- [x] **WP64 — Persist `<details>` open/closed state across htmx section swaps (reported bugs:
  "accordion lets more than one section open at once" and "changing a skill rating re-expands
  collapsed skill categories").**
  Goal: make both levels of `<details>` — the 14 top-level chargen sections and the per-category
  sub-groups inside the skill picker — keep the open/closed state the *player* set, rather than
  reverting to a server-derived default on every htmx swap.
  Verified root causes:
  - **Top-level accordion ("more than one section open at once" — was this intended?):** *Partly
    intended, now surfacing as a defect.* WP61 originally gave every section's `<details>` a shared
    `name="chargen-section"` for native one-at-a-time exclusivity, then **deliberately removed the
    `name`** because it raced with htmx's `outerHTML` swap and collapsed the section a player had
    just interacted with (full write-up in `chummer5.web.session.ChargenSession`'s docstring, "Post-
    WP61 fix"). Exclusivity is now only re-established server-side, on the *next* full-page render,
    via `ChargenSession.open_section`. So: manually clicking several `<summary>` bars open (no server
    round-trip) leaves them all open — the reported behavior. Confirmed: `grep -n "<details"` over
    `web/templates/` shows no `name=` attribute on any of the 14 section `<details>` (see
    `_skill_allocation.html:3`, `_attribute_allocation.html:3`, etc.).
  - **Skill sub-categories re-expanding:** `_skill_allocation.html:87-91` renders each category's
    `<details open>` **whenever any row in it has points/karma/a specialization** — a purely
    server-derived open state, re-evaluated on every `POST /ui/skills` render
    (`chummer5.web.routes.skills._skill_allocation_context` builds `skill_row_groups`). So a player
    who manually collapses a category that *has* active skills sees it snap back open the instant any
    skill rating change triggers the section's `outerHTML` swap. Confirmed in the template and in
    the context builder.
  Deliverables:
  - A single, shared client-side mechanism (a small vanilla-JS `htmx:beforeSwap`/`afterSwap` listener,
    consistent with WP61's existing no-build-step skill-filter `<script>`; or htmx `hx-preserve` on
    the `<details>` elements — implementer's call, whichever is cleaner) that captures each
    `<details>`'s `open` state before a swap and restores the player's choice after, at both the
    section and skill-category level.
  - Restore true one-section-at-a-time behavior for the top-level accordion **without** reintroducing
    the WP61 htmx race (i.e. not by simply re-adding `name=` — a toggle listener that closes sibling
    sections client-side, reconciled after swaps, is the intended shape). **Decided 2026-07-27:
    restore exclusivity** (not won't-fix) — opening one `<summary>` must collapse the others, and
    that state must survive the next htmx swap.
  - Keep the existing `open_section` server default working for genuine full-page reloads (a fresh
    page load has no client state to restore).
  Depends on: nothing new (presentation/JS only; no engine or route-signature change).
  Acceptance: `pytest`/`ruff`/`mypy` green; manual walkthrough — collapse a skill category that has
  active skills, change an unrelated skill's rating, confirm the category stays collapsed; open two
  sections and confirm the intended exclusivity behavior. Regression test at whatever level is
  practical (the open-state logic that's currently server-side is unit-testable; the pure-JS part is
  manual-walkthrough-verified, matching WP61's own precedent).

- [x] **WP65 — Two small skill/input display fixes: specialization pool shown as "X (Y)", and
  text-input focus no longer lost mid-typing.**
  Goal: bundle two unrelated-but-small reported defects into one summary WP.
  Verified root causes:
  - **Specialization pool shows only the higher number:** `_skill_allocation.html:149` renders a
    single `{{ row.pool }}`, and `chummer5.web.routes.skills._skill_allocation_context` computes it
    as one `dice_pool(display, allocation, skill)` value which *already includes* the +2
    specialization bonus (`chummer5.engine.skills.dice_pool:502-511`, `SPECIALIZATION_BONUS = 2`). So
    a specialized skill displays only the specialized pool, never the base. Expected: `X (Y)` where
    `X` is the pool without the spec bonus and `Y = X + 2`.
  - **Text inputs lose focus after "a few seconds":** every section form carries
    `hx-trigger="change, input delay:400ms"` with `hx-swap="outerHTML"` (confirmed by `grep` over
    all templates — `_skill_allocation.html:28`, `_contacts.html:19`, `_knowledge_skills.html:23`,
    `_resources.html:23`, etc.). Typing in a *text* field (specialization, contact name, knowledge
    name, free-text quality detail, ...) fires a `POST` ~400 ms after the last keystroke; the
    `outerHTML` swap destroys and rebuilds the focused input, dropping focus. The `input delay`
    trigger exists for the *number* spinners' responsiveness; text fields don't need it.
  Deliverables:
  - Pool display: compute both `dice_pool(..., specialized=False)` and `dice_pool(..., specialized=
    True)` in the context builder (the `specialized=` override already exists — see the function's
    WP50 docstring), and render `X (Y)` in the template **only when the skill actually has a
    specialization** (priority-point or Karma-funded); a plain skill keeps its single value. Confirm
    the exact intended format against the reporter if `X` should be the always-shown base and `(Y)`
    the specialized variant (this WP assumes yes).
  - Focus fix: stop text inputs from triggering a mid-typing swap — the minimal shape is to keep
    `input delay` for `number` inputs but have text inputs submit on `change` (blur) only. Options:
    split the trigger, scope `input` to `[type=number]`, or give text inputs stable `id`s so htmx's
    built-in focus restoration kicks in. Implementer's call; verify no section regresses its live
    number-spinner updating.
  Depends on: nothing new.
  Acceptance: `pytest`/`ruff`/`mypy` green; unit test asserting a specialized skill row exposes both
  pool numbers (and a non-specialized one exposes a single value); manual walkthrough typing a
  multi-word specialization / contact name without losing focus mid-word.

- [ ] **WP66 — Rating-priced gear: offer fake SINs, AR glasses/goggles/contacts, earbuds/headphones
    and the rest of the Rating-cost SR5 catalog (reported: "gear list does not include fake SINs, AR
    glasses, or earbuds/headphones").**
  Goal: close a real, previously-documented content gap — the starter-gear catalog offers only
  **flat-cost** entries, silently excluding an entire class of common, essential runner gear.
  Verified root cause: `chummer5.data.gear`'s loaders keep only entries whose `<cost>` parses as a
  flat integer (`_flat_cost`), and `chummer5.engine.resources.build_starter_gear_catalog` builds
  `STARTER_GEAR_CATALOG` from those. Every item the reporter named is priced by a **`Rating * N`
  formula**, so all are dropped:
  - Fake SIN — `gear.xml:7517`, `<cost>Rating * 2500</cost>`, `<avail>(Rating * 3)F</avail>`.
  - Glasses (`Rating * 100`), Contacts (`Rating * 200`), Goggles (`Rating * 50`) — Vision Devices.
  - Earbuds, Headphones (`Rating * 50`) — Audio Devices.
  This is a deliberate WP21 MVP cut (its own docstring flags "120 `Rating`-formula excluded"), not a
  regression — but the excluded set contains gear a mundane character routinely needs, so it's worth
  lifting now.
  Deliverables:
  - Extend `chummer5.data.gear` to load `Rating * N` (and equivalent per-rating) cost items, carrying
    their `<rating>` cap.
  - Extend the starter-gear model/engine (`StarterGearItem`, `create_resources_selection`,
    `build_starter_gear_catalog`) so a Rating-priced item is purchased *at a chosen rating*, with
    cost `= rating × unit`, validated against the item's max rating and the nuyen budget. This is the
    one genuinely non-trivial WP of the three — it adds a per-item rating dimension the current
    flat-cost model doesn't have.
  - `_resources.html` gains a rating selector for Rating-priced rows; the resources route parses and
    validates it.
  - **Availability cap (decided 2026-07-27):** several of these (Fake SIN at higher ratings =
    `(Rating*3)F` → up to 18F) exceed the Availability ≤ 12 line the Project Overview settled on
    2026-07-21 for new catalogs. **Cap the offered rating so each item's computed availability stays
    ≤ 12** — i.e. parse each item's `<avail>` formula and clamp the selectable rating range to the
    highest rating whose availability is ≤ 12 (Fake SIN `(Rating*3)F` → max offered rating 4 = 12F;
    a flat-availability item keeps its full `<rating>` range). This is the first place the gear
    catalog enforces the availability cap at all (WP21 never did — Project Overview's own
    "Unmodeled/undone" note); scope the enforcement to Rating-priced items this WP introduces, don't
    retroactively re-filter the existing flat-cost catalog. Record the approach in the decisions-log.
  Depends on: `chummer5.data.gear`, `chummer5.engine.resources` (Phase D/H). No magic/cyberware
  interaction.
  Acceptance: `pytest`/`ruff`/`mypy` green; new tests covering a Rating-priced purchase (cost scales
  with chosen rating; over-rating and over-budget both rejected); manual walkthrough buying a Fake
  SIN and AR Glasses at a chosen rating. Update `chummer5.data.gear`'s module docstring counts and
  WP21's noted exclusion.
