[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase L — Post-MVP: Easy wins (Karma-to-Nuyen, Sum-to-Ten, Bioware)

Scoped 2026-07-21 from a full survey of `spec/rulebooks/character_creation_chapter.md` (the freshly
extracted Steps One-Nine) against this project's current engine. All three items reuse an existing
mechanism end-to-end rather than needing a new one: Karma-to-Nuyen is a formula on top of two budgets
that already exist (`resources.py`'s nuyen budget, `qualities.py`'s Karma tracking); Sum-to-Ten reuses
`priorities.xml`/`chummer5.data.priorities` completely unchanged, just with a different letter-assignment
validity rule than WP14's bijection check; Bioware reuses WP30's Essence mechanism and WP32's
nuyen-budget/Improvement-application shape verbatim, pointed at a second, much smaller XML file.

- [x] **WP43 — Karma-to-Nuyen conversion.**
  Goal: let a player convert up to 10 Karma into nuyen during Step Six/Seven, per the rulebook (p. 94):
  "They may convert up to 10 Karma at a rate of 2,000 nuyen per Karma point for gear" — confirmed
  against the legacy engine too: `Miko.chum5`'s own `CharacterSettings` block carries
  `<nuyenbp>10</nuyenbp>`/`<nuyenmaxbp>10</nuyenmaxbp>`, matching the rulebook's cap exactly (10 Karma
  max). Confirm during implementation which `.chum5` field records the amount a specific character
  actually converted (`nuyenbp`/`nuyenmaxbp` above are the *setting*, not necessarily a per-character
  spend record) rather than assuming a name.
  Deliverables:
  - `chummer5.engine.resources`: a `karma_to_nuyen(karma_spent: int) -> int` helper (`karma_spent * 2000`,
    validated `0 <= karma_spent <= 10`), and thread the resulting nuyen into whatever budget
    `create_resources_selection` resolves gear/lifestyle/cyberware/bioware purchases against — confirm
    (don't assume) this is exactly "add to the existing nuyen_budget parameter" rather than a separate
    pool, mirroring how WP20/WP32 each had to confirm their own budget was genuinely shared before wiring
    it in.
  - Whatever unified Karma-tracking mechanism exists by the time this lands (this WP has no technical
    dependency on Phase O's ledger, but if Phase O ships first, wire the spend through it rather than a
    bespoke field) needs to record the Karma spent here so it can't be double-spent on qualities/contacts.
  - `chummer5.web.app`: a small form control on the Resources screen (`_resources.html`) for "convert N
    Karma to nuyen," with the resulting nuyen folding into the existing gear/lifestyle/cyberware total
    live (HTMX partial re-render, WP15's precedent).
  - `chummer5.io.save_format`/`legacy_import`: thread the converted amount through `CharacterSave`/
    `build_character` (mechanical, WP20 precedent).
  Depends on: nothing new (touches `engine/resources.py`, `web/app.py`, `io/save_format.py` only).
  Acceptance: unit test for the `karma_to_nuyen` formula and its 10-Karma ceiling; integration test
  confirming converted nuyen is available for gear/lifestyle/cyberware/bioware purchases in the same
  transaction; manual walkthrough converting Karma and watching the gear budget update live.

- [x] **WP44 — Sum-to-Ten build method.**
  Goal: let a player choose Sum-to-Ten instead of Priority for letter assignment — same Priority Table,
  same per-letter meaning, a different validity rule. Confirmed directly in the legacy C#
  (`SelectMetatypePriority.cs`'s `SumToTen`/`GetSumToTenValue`, `CharacterSettings.cs`'s `_intSumtoTen`
  field): each letter has a fixed point value (**A=4, B=3, C=2, D=1, E=0** by default), **letters may
  repeat** across the 5 categories (unlike Priority's bijection), and the sum of the 5 chosen letters'
  point values must not exceed a target that **defaults to 10** (hence the name) — confirmed this is
  configurable in the legacy engine (`CharacterSettings._intSumtoTen`) but this project can hardcode 10
  the same way `QUALITY_KARMA_LIMIT` is hardcoded rather than exposing a settings system that doesn't
  otherwise exist.
  **This build method is not in the SR5 core rulebook PDF at all** (confirmed: zero hits for "sum to
  ten" across the whole document) — it's a legacy-Chummer/errata-sourced alternate rule, not a rulebook
  citation. Record this provenance in `spec/rulebooks/learnings.md` explicitly (mirroring WP20's own
  "the number came from the legacy C#, not rulebook prose" precedent) so a future agent doesn't go
  hunting for rulebook text that isn't there.
  Deliverables:
  - `chummer5.web.session`: a `build_method` field on the session (`Priority` default, `SumToTen`
    alternative) — decide and document whether `Character` itself needs to carry this too (WP18-style
    "does this belong on the aggregate" call) given save/load and legacy import both need to know which
    validity rule produced a given letter assignment.
  - `chummer5.web.app`/`chummer5.engine.character` (or a new small module): a `create_sum_to_ten_selection`
    (or equivalent) validating 5 letters (repeats allowed) sum to ≤ 10 under the point table above,
    parallel to the existing bijection check `submit_priorities` already runs for Priority.
    Decide & document: does choosing Sum-to-Ten change the UI to a set of 5 independent letter
    dropdowns (repeats allowed) with a live running-total display (mirroring the legacy `lblSumtoTen`
    "X/10" label), replacing WP14's "pick 4 distinct letters from {A,B,C,D}" control for that session?
  - `chummer5.io.legacy_import`: `LegacyCharacter`'s `buildmethod` field (already parsed, per
    `CharacterBuildMethod.SumtoTen` in the legacy enum) currently causes non-Priority saves to be
    rejected somewhere in `_blocking_reasons` — confirm this during implementation and widen it to accept
    Sum-to-Ten specifically (still rejecting `Karma`/`LifeModule`, per this project's own explicit ruling
    that the Karma build method stays out of scope — see Project Overview's 2026-07-21 entry).
  Depends on: nothing new (touches `web/session.py`, `web/app.py`, `io/legacy_import.py`).
  Acceptance: unit tests for the sum-to-10 validator (including a repeats-allowed case that would be
  illegal under Priority's bijection, and an over-10 rejection); since none of the 12 curated fixtures
  use Sum-to-Ten as their `buildmethod` (per this project's own corpus note — the 33 non-mundane/
  non-Yeti fixtures that *do* use it are all outside MVP's mundane/magic-scoped content), acceptance
  is necessarily hand-verified against the legacy C#'s own point table rather than a real fixture, same
  honesty standard as WP8's quality karma cap; note this explicitly in the worklog. Manual walkthrough:
  build a character via Sum-to-Ten with two categories sharing the same letter, confirm it's accepted
  when Priority's bijection would have rejected it.

- [x] **WP45 — Bioware (data loader, selection, save/load, and legacy import).**
  Goal: add the SR5-core, flat-cost/flat-essence, Standard-grade bioware catalog, reusing Phase J's
  Essence/nuyen-budget machinery directly. Scoped as **one WP**, not split into loader/selection/
  save-load like cyberware's WP31/32/33 — the catalog is confirmed tiny (only 8 of 213 `bioware.xml`
  entries are `source == "SR5"` **and** flat-cost/flat-essence, per Project Overview's 2026-07-19
  cyberware-scoping entry), so the reviewability rationale that justified splitting cyberware into three
  WPs doesn't apply here; document this "one WP is enough" call explicitly rather than defaulting to it.
  Deliverables:
  - `chummer5.data.bioware` (new): loader for `legacy/Chummer/data/bioware.xml`, filtered to
    `source == "SR5"` AND flat `<cost>` AND flat `<ess>`, mirroring `chummer5.data.cyberware`'s filter
    and `BonusSupport` classification scheme exactly (reuse the enum, don't redefine an equivalent one —
    confirm during implementation whether the existing type already generalizes cleanly). Additionally
    filter out any item with Availability > 12, per this project's 2026-07-21 ruling on the Availability
    mechanic (Project Overview) — bioware is new-enough content that it should apply the agreed
    simplification from day one, unlike WP21/WP31's pre-existing catalogs which don't filter by
    Availability at all.
  - `chummer5.engine.bioware` (new) or fold into `chummer5.engine.cyberware` (decide & document which):
    `create_bioware_selection`, drawing from the **same shared nuyen budget** cyberware/gear/lifestyle
    already use, and contributing to the **same shared Essence pool** cyberware already reduces
    (`ImprovementType.ESSENCE`, `ImprovementSource.BIOWARE` — a new source, same type). Confirm bioware
    and cyberware Essence costs are genuinely additive against one shared pool rather than tracked
    separately (the rulebook doesn't suggest otherwise, but confirm against `Character.cs` directly, the
    same discipline WP32 applied to its own shared-pool question).
  - `Character` gains `bioware_selection: BiowareSelection | None`.
  - `chummer5.io.save_format`/`legacy_import`: thread `bioware_selection` through the normal
    mechanical path (WP18/WP20 precedent); widen whatever blanket bioware-rejection exists in
    `_blocking_reasons` today (confirm exact current behavior — Project Overview's 2026-07-18 entry
    predates this WP and may already be stale on this point) to itemized per-item rejection for
    non-flat/non-Standard-grade items, mirroring WP33.
  - `chummer5.web`: fold the bioware picker into the existing cyberware/Resources section
    (`_cyberware.html`/`_resources.html`) — decide & document, mirroring WP34's own "does this share a
    screen with cyberware" call.
  Depends on: WP30, WP31, WP32 (reuses their Essence/nuyen-budget/Improvement-application machinery
  directly).
  Acceptance: unit tests confirming the loader's count (8 flat SR5 items, or the actual number found —
  re-verify rather than trust this session's figure) and Availability filter; integration test
  confirming a bioware purchase reduces Essence exactly like an equivalent-cost cyberware purchase does,
  and that cyberware + bioware Essence costs stack correctly against the one shared pool. No fixture in
  the 12-item mundane corpus carries real bioware (only cyberware) — acceptance for the Essence-stacking
  case is therefore synthetic/hand-verified, not fixture-backed; say so in the worklog rather than
  overclaiming coverage, the same honesty standard Phase J's own WP33 applied to its cyberware-import
  acceptance criteria.

