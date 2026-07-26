[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase G — Post-MVP: chargen state-model refinement

Two related but separately-committable fixes to the *shape* of chargen state, raised in a design
discussion after the UI MVP milestone (not a rules or scope change — no new SR5 content, no new
Improvement types). Both are internal restructuring; neither is expected to change any computed
value for an existing character.

**Why these are split into two WPs, and in this order.** WP19's actual bug (priority
reconfirmation discards a player's existing attribute/skill spend instead of re-validating it) is
independently fixable against today's `ChargenSession`-sibling-fields shape. But WP18's fold gives
WP19 a real technical assist: today, `submit_attributes`/`submit_priorities` call `create_character()`
fresh on every edit, which always attaches a brand-new, empty `ImprovementIndex` — the *reason*
`_relink_quality_improvements`/`_replace_committed_qualities` exist at all (see WP16/WP17's
worklogs). Once `Character` holds every selection as its own field, an attribute-point edit can
become "validate, then `dataclasses.replace(character, attribute_points=...)`" instead of a full
rebuild — and because `dataclasses.replace` copies every untouched field *by reference*, the same
`ImprovementIndex` instance (and the same `skill_allocation`/`quality_selection`/etc.) carries
forward automatically, with nothing to re-link. WP19's remaining job shrinks to exactly the
re-validate-and-diagnose behavior itself, on a shape where "keep everything except the one field
that changed" is the natural operation rather than a five-field manual synchronization problem.
Doing the fold first means WP19 gets written once, against its final shape.

- [x] **WP18 — Fold skill/quality/contact/resources selections into `Character`.**
  Goal: make `Character` the single aggregate representing a character-in-progress, so that (for
  example) a quality selection is a property of the character, not sibling state independently
  threaded through the web session, the save format, and legacy import. Raised directly by a design
  discussion: the current split (only metatype/attributes live on `Character`; skills/qualities/
  contacts/gear live as separate `ChargenSession` fields, reunited only ad hoc in `save_format.py`'s
  `BuiltCharacter`) reads as "qualities aren't part of the character," which contradicts SR5's own
  model and has no technical justification beyond which WP happened to build which module first
  (confirmed by reading WP7's own worklog: skills got their own object "to avoid `Character`... a
  half-populated `skills` field sitting unused" until a later WP, a sequencing convenience, not a
  conceptual claim).
  Deliverables:
  - `src/chummer5/engine/character.py`: widen `Character` with four new fields —
    `skill_allocation: SkillAllocation | None`, `quality_selection: QualitySelection | None`,
    `contact_selection: ContactSelection | None`, `resources_selection: ResourcesSelection | None`
    — each defaulting to `None` until that stage of chargen is committed, the same "unset until
    confirmed" shape `attribute_points`/`improvements` already have. `create_character` itself is
    otherwise unchanged. Every stage-specific update (spending skill points, picking qualities,
    editing contacts, buying gear) becomes `dataclasses.replace(character, x=new_value)` against
    the session's existing `Character`, not a write to a same-named `ChargenSession` field.
  - Decide, and document the decision in this WP's worklog, whether `submit_attributes` also moves
    from "call `create_character()` fresh" to "validate the new attribute points, then
    `dataclasses.replace`" as part of this WP, or leaves that for WP19. Either is acceptable for
    WP18 alone; if deferred, `_relink_quality_improvements` stays necessary for that one route
    until WP19 lands, and this WP's worklog should say so explicitly rather than leaving it
    ambiguous which WP actually retired it.
  - `src/chummer5/io/save_format.py`: retire `BuiltCharacter` — `build_character()` constructs one
    fully-populated `Character` directly (a save always carries every selection at once, so no
    incremental `replace` is needed here). Every caller of `BuiltCharacter.skill_allocation` etc.
    (including `tests/`) updates to `character.skill_allocation` etc.
  - `src/chummer5/io/legacy_import.py`: `ImportResult` wraps `Character` instead of
    `BuiltCharacter` (mechanical — it already only forwarded `build_character`'s output).
  - `src/chummer5/web/session.py`: `ChargenSession` drops `skill_allocation`, `quality_selection`,
    `contacts`, `gear_names` as separate fields, keeping only `character: Character | None` (plus
    the 4 priority letters and `metatype_id`, which remain genuine pre-`Character` UI state) and
    whatever scratch fields the existing "echo a *rejected* submission back into its form"
    pattern needs (WP15/WP16's precedent) — those must stay separate from `character`, since they
    represent input that was *not* committed.
  - `src/chummer5/web/app.py`: every route/context-builder reads/writes through
    `session.character.x` instead of `session.x`.
  - Update `tests/` throughout for the new shape. No behavioral assertion should need to change —
    this WP relocates data, it does not change what any formula computes.
  Depends on: WP17.
  Acceptance: `pytest`/`ruff`/`mypy` all green; WP17's own manual walkthrough (create → save →
  reload into a fresh session; separately, import `Yeti-#ffffff2.chum5`) reproduced with identical
  results — this WP is a pure internal restructuring, not a behavior change.

- [x] **WP19 — Re-validate instead of reset on priority/metatype reconfirmation.**
  Goal: replace `submit_priorities`'s current behavior — silently discarding attribute points,
  skill allocation, and gear spend outright on every reconfirmation (`create_character(choice, ...,
  {})`, `session.skill_allocation = None`, `session.gear_names = ()`) — with keeping the player's
  existing selections, re-validating them against the new budgets/ranges, and surfacing exactly
  what's now invalid. `create_character`/`create_skill_allocation`/etc. already raise itemized
  `ValueError`s for over-budget or out-of-range spend (e.g. `"primary attribute spend {X} exceeds
  Attributes priority {Y}'s budget of {Z}"`); this WP is "attempt the update and surface the
  failure," not new validation logic. Quality and contact selections are unaffected by this WP —
  neither is metatype/priority-letter-budgeted (see `ChargenSession`'s existing docstring), and
  neither currently resets; only the two paths that *do* reset without needing to (attribute
  points, skill points + gear) change.
  Deliverables:
  - `submit_priorities`: attempt to carry the session's existing `attribute_points` (and, where
    the Attributes/Skills letter or metatype actually changed, the existing `skill_allocation`/
    `gear_names` too) into the reconfirmed `Character` rather than clearing them first. On a
    validation failure under the new letter/metatype, keep the character in an explicit
    invalid-pending state and surface which field(s) are over/under and by how much (e.g. "BOD
    exceeds the new Attributes budget by 2 — reduce it to continue"), rather than silently
    resetting to empty.
  - Decide and document: does an over-budget-after-reconfirmation character block further chargen
    progress (e.g. the character sheet) until fixed, or is it allowed to sit visibly-invalid until
    the player corrects it? Recommend the latter, consistent with this project's existing "don't
    require the full budget to be spent, validate at the boundary" philosophy — but this is a real
    UX call to make explicitly in this WP's worklog, not to default into silently.
  - Extend `_priority_form_context`/`_attribute_allocation_context`/`_skill_allocation_context` to
    carry and render this new "now invalid because a priority just changed" message, distinctly
    from today's "you just submitted something bad" validation-error message where reasonable.
  Depends on: WP18 (re-validating `character.attribute_points`/`character.skill_allocation` in
  place, on the unified shape, is what makes "keep the values, just recheck them" one operation
  rather than a five-field manual synchronization problem — see the Phase G intro above).
  Acceptance: manual walkthrough — build a character, spend attribute and skill points, lower the
  Attributes priority letter below the current spend; confirm the UI still shows the existing
  allocation with a specific "over budget by N" message rather than a blank/reset form. A parallel
  case where the new letter's budget still fits the existing spend confirms nothing is disturbed.
  Unit tests for both the still-valid and now-invalid transitions.

