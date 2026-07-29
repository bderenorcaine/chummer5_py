[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase V — Post-MVP: UI improvement requests

Feature requests captured 2026-07-27 in the same manual-testing session that raised Phase U's bugs —
QoL improvements to the chargen UI, not defects. Recorded here as future WPs; none is blocking and
they can be picked up in any order. Numbered from WP67, after Phase U claims WP64-66.

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

- [ ] **WP69 — Spell picker: group spells by category/type and filter for known/unknown.**
  Goal: the spell list (`_spell_selection.html`) is currently one flat table; make it (a) groupable
  by category/type (Combat, Detection, Health, Illusion, Manipulation — the `spell.category` already
  rendered per row) and (b) filterable to show only known (selected) or unknown (unselected) spells.
  Notes: mirror WP61's collapsible-`<details>`-per-category + client-side-filter pattern from the
  skill picker. Grouping is presentation-only; the known/unknown filter keys off each row's
  `row.selected` (already in context). No engine change.
  Depends on: nothing (reuses WP61's grouping/filter pattern).

- [ ] **WP70 — Bind spirits at a Force lower than the Magic rating.**
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

- [ ] **WP71 — Gear picker: name/category filter.**
  Goal: the starter-gear picker (`_resources.html`) has collapsible categories but no filter; add a
  by-name (and optionally by-category) text filter like the skill picker's.
  Notes: reuse WP61's exact vanilla-JS filter pattern (`data-*` attribute per row + one `input`
  listener hiding non-matching rows and empty categories). Purely client-side. Naturally pairs with
  WP66 (Rating-priced gear) since a larger catalog makes a filter more valuable, but doesn't depend
  on it.
  Depends on: nothing.
