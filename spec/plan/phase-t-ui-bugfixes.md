[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase T — Post-MVP: UI bugfixes & skill-picker QoL

Raised 2026-07-24 from manual browser testing of the shipped UI (the first hands-on pass since
Phase Q's spec reorganization) — two real bugs plus a follow-on QoL request, unrelated to each other
except in being discovered in the same session. Numbered from WP60, the next free number after
Phase Q/R/S claimed WP57-59.

- [x] **WP60 — Fix karma-summary context-key collision (Attributes/Skills sections silently showed
  Knowledge's own karma numbers on a full-page reload).**
  Goal: fix a real, reproduced bug — reported as "buying a quality seems to reset the karma summary
  for attributes," actually "any full-page render with more than one karma-consuming section
  populated shows the wrong numbers," qualities being an incidental trigger, not the cause.
  Deliverables:
  - Root cause: `_chargen_body_context` merges `_attribute_allocation_context`'s,
    `_skill_allocation_context`'s, and `_knowledge_selection_context`'s own context dicts together
    for `chargen.html`'s full-page render; all three used to return the identically-named
    `"karma_budget"`/`"karma_remaining"` keys, so Python's dict-spread merge let whichever was
    applied last (Knowledge) silently clobber the other two's numbers. Confirmed by direct
    reproduction against the running app (`TestClient` + `app.state.sessions` introspection) — the
    underlying `Character`/session state was correct throughout; only the display-context assembly
    was wrong.
  - Renamed the three offending context builders' return keys to the prefixed pattern
    `_spell_selection_context`/`_spirit_selection_context`/`_foci_selection_context` already use:
    `attribute_karma_budget`/`attribute_karma_remaining`, `skill_karma_budget`/
    `skill_karma_remaining`, `knowledge_karma_budget`/`knowledge_karma_remaining`. Updated
    `_attribute_allocation.html`/`_skill_allocation.html`/`_knowledge_skills.html` to match.
  - New regression test proving the full-page render shows each section's own (distinct) numbers,
    not just each `POST` route's isolated response (the only thing previously tested).
  Depends on: nothing new.
  Acceptance: `pytest`/`ruff`/`mypy` all green; new regression test fails on the pre-fix code and
  passes after. See [WP60.md](../worklogs/WP60.md) for the full reproduction trace.

- [x] **WP61 — Widen the Skills-priority buy UI to Magical Active skills for magic-active
  characters; collapsible skill categories + a name filter; a whole-page one-section-open-at-a-time
  accordion.**
  Goal: fix a real, previously-documented-but-deferred gap (a Magician/Adept can't spend regular
  Skill points or leftover Karma on Spellcasting or any other Magical Active skill — only their
  Talent free-grant raises one at all), plus two bundled QoL requests for the same picker and for
  the chargen page as a whole.
  Deliverables:
  - **Bug fix**: `MUNDANE_SKILLS`/`MUNDANE_SKILL_GROUPS` (module-level constants excluding every
    MAG/RES-linked skill) were the *only* source the Skills-priority buy UI offered — flagged as a
    real, deliberate-but-unresolved gap in WP29's own worklog (2026-07-19), pending a decision on
    which subset of Magical Active skills to offer. Resolved by reusing
    `chummer5.engine.magic.MAGICAL_SKILL_CATEGORIES` (renamed from the private
    `_MAGICAL_SKILL_CATEGORIES`, the exact `{"Magical Active", "Pseudo-Magical Active"}` filter
    already verified against the legacy `GetMagicalSkillList()` for WP25's free-skill grant) — a
    magic-active character (`character.magic_type is not None`, Magician or Adept alike) can now
    spend regular Skill points and leftover Karma on any skill in that category set, not just their
    free grant. `create_skill_allocation`/`create_karma_skill_selection` needed no engine changes —
    the restriction was purely `web/app.py`'s own UI curation, already generic underneath.
  - **A second, previously-undiscovered bug surfaced and fixed alongside the above**:
    `MUNDANE_SKILLS`'s original exclusion (`s.attribute not in ("MAG", "RES")`) was attribute-based,
    not category-based — a plausible-looking but wrong proxy. 3 of the 12 Magical/Pseudo-Magical
    Active skills (Assensing/INT, Astral Combat/WIL, Arcana/LOG) use a non-MAG linked attribute for
    their dice pool despite requiring Awakened status to use at all, so the old filter let *any*
    character, including Mundane, already buy them — made visible by this WP's own category
    grouping (a Mundane character's picker showed its own "Magical Active" header). Fixed by
    switching the exclusion to `Skill.category not in (MAGICAL_SKILL_CATEGORIES | {"Resonance
    Active"})`, shrinking `MUNDANE_SKILLS` from 64 to 61 entries (the 3 corrected skills plus the
    already-excluded 12) — a real, if narrow, latent gap since WP2 first drew this line.
  - **QoL 1**: skill rows grouped into collapsible `<details>`/`<summary>` categories, mirroring
    `_resources.html`'s existing gear-category grouping exactly (`itertools.groupby` on
    `skill.category`, open-by-default only when a category has an active row). A small client-side
    filter (`data-skill-name` + one vanilla-JS listener, no build step) narrows visible rows by
    typed text.
  - **QoL 2 (expanded scope, added after initial plan review)**: all 14 chargen sections
    (`_chargen_body.html`) wrapped in a shared-`name` `<details>` accordion — native
    one-section-open-at-a-time behavior, zero JS. `ChargenSession` gains `open_section: str`
    tracking which section renders `open` on the next full-page render; each section's own
    successful `POST` sets it to that section's id. A collapsed section's `<summary>` shows a
    warning marker when it has an active error/budget-warning, so WP19-style "no longer fits"
    diagnostics stay visible without forcing every section open.
  Depends on: nothing new (Bug 2's fix touches only `web/app.py`'s UI curation and a public rename
  in `engine/magic.py`; both QoL items are presentation-only).
  Acceptance: `pytest`/`ruff`/`mypy` all green; unit test confirming a Magician/Adept's skill picker
  offers Magical Active skills (and a Mundane character's stays unchanged); manual walkthrough
  building a Human Shaman confirms Spellcasting is purchasable, grouped under a collapsible
  "Magical Active" category, filterable by name; manual walkthrough of the accordion confirms only
  one section is open at a time and a collapsed section with an active warning shows a visible
  marker. See [WP61.md](../worklogs/WP61.md).
