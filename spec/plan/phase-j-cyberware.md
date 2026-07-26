[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase J — Post-MVP: Cyberware

Grounded in the Project Overview's own 2026-07-18 entry: Essence tracking is a genuine prerequisite,
not incidental catalog content — `chummer5.engine.derived.BASE_ESSENCE` is a fixed `6`, and
`chummer5.io.legacy_import` hard-rejects any `.chum5` carrying cyberware/bioware at all
(`_blocking_reasons`' `has_cyberware` check).

**A finding not previously recorded anywhere in this spec: 8 of the 11 curated "mundane" fixtures
already carry real cyberware.** `BLUE`, `Barrett`, `Bastion`, `Blindfire`, `Fuzzy-chargen`,
`Gentle Earthquake`, `Monomax (approved) 3`, and `SCSi` each have between 3 and 16 real cyberware
entries — "mundane" has only ever meant `<magenabled>False</magenabled>` (`tests/fixtures/
README.md`'s own definition), never "augmentation-free." Every existing derived-stat test already
anticipated this correctly rather than by accident:
`test_cross_corpus_attribute_value_matches_when_unaugmented` explicitly skips any attribute a
fixture's own cyberware boosts, and `social_limit` (Essence-dependent) is only ever asserted against
real fixture data via Yeti specifically — zero cyberware. No latent bug, but this phase inherits real,
ready-to-use fixture coverage for Essence math the moment it exists — bigger than any Phase G/H/I
candidate's fixture backing except Lifestyle's.

**A second finding that scopes the catalog cut.** The real per-instance Essence cost stored in these
8 fixtures is very often *not* a plain number — `<ess>` frequently holds the source catalog's
unresolved rating formula (`Rating * 0.3`, `FixedValues(2,3,5)`, ...), because the legacy engine
evaluates it at read time rather than storing a resolved value per purchase. Cross-referencing
`cyberware.xml`'s 87 SR5 entries against a flat-cost-AND-flat-essence filter (mirroring WP21's gear
cut exactly) narrows to **60 entries** — but only a modest subset of those (Datajack, the 8 Cyberlimb
variants, Smartlink, Bone Lacing (Titanium)) actually appear, unmodified by a rating formula, in 6 of
the 8 real cyberware-bearing fixtures. The flat-catalog cut below is still the right smallest-first
step (mirrors WP21's own reasoning), but — unlike WP20's Lifestyle milestone — **full `<totaless>`
reproduction against these fixtures is not a realistic acceptance bar for this phase alone**; say so
explicitly rather than overclaiming coverage.

**Grade is also explicitly cut to smallest scope.** `cyberware.xml`'s `<grades>` table defines 5
SR5-sourced grades (Standard/Used/Alphaware/Betaware/Deltaware), each multiplying both cost and
essence. This phase offers **Standard grade only** (multiplier 1.0x on both — consume `<cost>`/`<ess>`
as-is), deferring grade selection entirely, mirroring WP21's Availability-cap cut in spirit.

**Bioware is explicitly not in this phase's scope** despite sharing the identical Essence pool
(confirmed: `bioware.xml`'s own `<ess>` fields subtract from the same Essence stat) — only 23 of 213
`bioware.xml` entries are `source == "SR5"`, and only 8 of those are flat-cost-and-essence, small
enough to be a clean, self-contained follow-up once this phase's Essence mechanism exists, not bundled
in now.

**Cross-phase interaction, flagged rather than silently ignored.** SR5 reduces a magically active
character's Magic (or Resonance) rating as Essence is lost to cyberware/bioware — a real rule
connecting this phase directly to Phase I. Neither phase's fixture corpus can exercise it (no fixture
is simultaneously Priority-built, magic-enabled, and cyberware-bearing), and building it prematurely
in whichever phase lands first would guess at an interaction between two features that don't fully
exist yet. Scoped as this phase's final WP (WP35), sequenced after both phases' own engine work.

- [x] **WP30 — Essence as a real, Improvement-driven `Character` value.**
  Goal: replace the `BASE_ESSENCE` constant with a real, reducible value, proven with synthetic data
  before any cyberware catalog exists to produce it for real — mirrors WP5's own sequencing relative
  to WP6+.
  Deliverables:
  - `chummer5.engine.improvements`: new `ImprovementType.ESSENCE` and `ImprovementSource.CYBERWARE`,
    extending the existing enums the same incremental way WP10/WP22 already have. Model Essence loss
    as a negative-`value` `Improvement` targeting `ImprovementType.ESSENCE` at the existing
    `_GLOBAL_TARGET` sentinel — staying consistent with the Project Overview's own stated philosophy
    ("every derived value equals a base term plus Σ improvements") rather than a bespoke
    `Character.essence` field that bypasses the index.
  - **A real decision this WP must make and document, not default silently**: every
    `Improvement.value` today is `int`. SR5 essence costs are routinely fractional (`0.75`, `1.0`,
    `1.5`, `0.25` all appear in `cyberware.xml`'s flat subset). Decide between (a) widening
    `Improvement.value` to `Decimal`/`float` engine-wide, (b) a parallel `essence_value: Decimal`
    field used only by `ESSENCE`-typed improvements, or (c) tracking essence in hundredths as an
    int and dividing only at display time. Record the tradeoffs in this WP's worklog — this is the
    engine's first fractional value anywhere, a real precedent-setting choice.
  - `chummer5.engine.derived`: `social_limit`'s Essence term switches from the `BASE_ESSENCE`
    constant to `6 + character.improvements.resolve(ImprovementType.ESSENCE, _GLOBAL_TARGET)` — same
    number, different role: a fixed starting point rather than a hardcoded final answer.
  Depends on: nothing new (touches `engine/improvements.py`, `engine/derived.py`,
  `engine/character.py` only).
  Acceptance: unit tests with synthetic `ESSENCE` improvements (including a fractional case, per
  whichever representation was chosen); the existing Yeti-based `social_limit` test
  (`ceil((5*2+5+6)/3) == 7`, essence fixed at 6, zero improvements) passes unchanged, proving zero
  behavioral drift for every cyberware-free character built so far.

- [x] **WP31 — Cyberware data loader.**
  Goal: load the SR5-core, flat-cost, flat-essence, Standard-grade cyberware catalog as typed Python
  structures.
  Deliverables:
  - `chummer5.data.cyberware.py` (new): loader for `legacy/Chummer/data/cyberware.xml`, restricted
    to `source == "SR5"` AND a plain integer `<cost>` AND a plain (possibly fractional) `<ess>` — 60
    of 87 SR5 entries, confirmed. Grade is not offered (see phase intro); consume `<cost>`/`<ess>`
    directly as Standard-grade values. Preserve `category` (9 distinct: Bodyware/Headware/Eyeware/
    Earware/Cyberlimb/Cyberlimb Enhancement/Cyberlimb Accessory/Cyber Implant Weapon Accessory/Cyber
    Implant Weapon) for WP34's UI grouping, mirroring WP21's gear-category precedent.
  - Classify each item's `<bonus>` node with a 3-way scheme mirroring
    `chummer5.data.qualities.BonusSupport` — decide and document whether to reuse that enum or
    define an equivalent one, since this is the second data module needing the identical shape:
    **`FLAT_BONUS`** for items whose `<bonus><conditionmonitor><physical>` maps directly onto the
    existing `ImprovementType.PHYSICAL_CM` (confirmed present on the Cyberlimb variants; verify the
    exact count during implementation). Two of those also carry
    `<disablequality>Celerity</disablequality>` — verified inert for MVP purposes since Celerity
    isn't among the ~14 qualities `mvp_quality_catalog` currently offers; document this as a
    verified-currently-moot interaction (WP22-style), not a silent gap. **`NOT_YET_SUPPORTED`** for
    items with a real but unmodeled effect (an armor/unarmed-damage bundle, Smartlink, sonic
    resistance, a limit-modifier item — none map onto anything this engine's combat-free scope
    tracks). **`NO_EFFECT`** for the remaining items with an empty/absent `<bonus>` (pure
    Essence/nuyen cost) — confirmed the large majority of the 60; unlike WP22's qualities, an empty
    `<bonus>` here already means literally nothing beyond Essence, so no name-gate is needed, only
    the count.
  Depends on: nothing new (pure data classification, mirrors WP3's independence from WP5).
  Acceptance: unit tests confirming the loader's counts (60 flat items; the
  FLAT_BONUS/NOT_YET_SUPPORTED/NO_EFFECT split) and that a rating-scaled item (e.g. Wired Reflexes,
  confirmed present with a `FixedValues(2,3,5)` essence formula in real fixture data) is correctly
  excluded rather than mis-parsed.

- [x] **WP32 — Cyberware selection & Improvement application.**
  Goal: compose WP30's Essence mechanism with WP31's catalog and WP6's `Character` into a buildable
  cyberware purchase.
  Deliverables:
  - `chummer5.engine.cyberware.py` (new): `create_cyberware_selection(item_ids, catalog,
    nuyen_budget)`, validating no unknown ids and that total nuyen cost doesn't exceed the **same
    shared Resources-priority budget** gear and lifestyle already draw from (WP20/WP21 precedent —
    confirm, don't assume, that it's really one shared pool for cyberware too). Decide whether
    duplicate purchases are ever legal (most cyberware is one-per-character, but bilateral items
    like cybereyes plausibly aren't) by checking the real data rather than assuming.
  - `apply_cyberware_improvements`, mirroring `apply_quality_improvements`'s shape: for each
    selected item, one `Improvement(ESSENCE, value=-item.essence_cost, source_type=CYBERWARE,
    source_id=item.id)` always, plus whatever `FLAT_BONUS` items contribute (`PHYSICAL_CM`).
  - `Character` gains `cyberware_selection: CyberwareSelection | None` ("`None` until committed",
    WP18/WP20 precedent).
  - Guard against Essence going negative: verify the actual SR5-correct chargen behavior via
    `pdftotext -layout` rather than assuming, and record it in `spec/rulebooks/learnings.md`.
  Depends on: WP30, WP31.
  Acceptance: unit tests for nuyen-budget and Essence-floor validation; integration tests against the
  real purchases confirmed in the phase intro (Datajack/Cyberlimbs/Smartlink/Bone Lacing across
  BLUE/Barrett/Bastion/Blindfire/Monomax/Gentle Earthquake) confirming each flat item's Essence cost
  matches the fixture's own per-item `<ess>` value exactly, and that a Cyberlimb purchase correctly
  raises `physical_condition_monitor` by 1 via the existing `PHYSICAL_CM` type — the clearest
  "reuses an existing mechanism" win this phase has, worth its own explicit assertion.

- [x] **WP33 — Cyberware-aware save/load + legacy import unblocking.**
  Goal: let a cyberware-bearing character round-trip through native save/load and legacy `.chum5`
  import.
  Deliverables:
  - `chummer5.io.save_format`/`legacy_import`: thread `cyberware_selection` through
    `CharacterSave`/`build_character` (mechanical, WP18/WP20 precedent).
  - `chummer5.io.legacy_import`: remove/narrow the blanket `if legacy.has_cyberware:
    reasons.append(...)` rejection in `_blocking_reasons`; replace with real support up to this
    phase's flat/Standard-grade scope, itemizing any item that doesn't resolve against the WP31
    catalog (rating-scaled, non-Standard-grade, or non-SR5 — per the phase intro, the *common* case
    in real fixtures, not the exception) as a specific "cannot import: {item} is rating-scaled/
    non-Standard-grade cyberware, out of scope" reason.
  - `chummer5.io.legacy_chum5`: extend `LegacyCharacter` beyond today's boolean `has_cyberware` to
    real per-item data (name, essence cost, grade) — needed both to decide per-item importability
    above and to cross-check `totaless` against WP30's Essence mechanism.
  Depends on: WP30, WP31, WP32.
  Acceptance: per the phase intro, **no fixture in the corpus is both Priority-built and
  cyberware-bearing**, so this WP cannot claim a full end-to-end Priority-built import success the
  way WP12/WP28 could — say so rather than manufacturing a misleading acceptance criterion. Instead:
  integration tests importing each of the 8 real cyberware-bearing fixtures (SumtoTen-built, so only
  build-method-agnostic fields are checked, per WP4's own established split) confirm every
  flat/Standard-grade item among their real purchases imports with the correct Essence cost, and
  every rating-scaled/non-Standard item is itemized as a specific, named rejection reason rather than
  silently dropped or a generic failure.

- [x] **WP34 — Cyberware chargen UI + character sheet.**
  Goal: expose cyberware purchase through the browser, category-grouped like WP21's gear picker, and
  show Essence/cyberware on the character sheet.
  Deliverables:
  - `chummer5.web.app`/templates: a cyberware picker section — decide and document whether it folds
    into the existing Resources/gear screen (`_resources.html`) given they share one nuyen budget,
    the same choice WP20 already made explicitly for lifestyle vs. gear.
  - `_character_sheet_context`: current Essence (replacing any fixed "6" display), cyberware list,
    condition-monitor totals reflecting any Cyberlimb-granted bonus.
  Depends on: WP32, WP33.
  Acceptance: manual walkthrough — build a character with at least one Cyberlimb and one
  no-bonus item through the browser, confirming nuyen spend, Essence, and physical condition monitor
  all match WP32's engine output; a parallel walkthrough with zero cyberware confirms Essence
  displays as 6 and every other value is pixel-for-pixel unchanged from before this phase.

- [x] **WP35 — Cross-phase: Essence-driven Magic-rating loss.**
  Goal: implement the one real rules interaction between Phase I and Phase J — SR5 reduces a
  magically active character's Magic rating as Essence is lost to cyberware. Deliberately last in
  this phase: it's the one WP in either phase whose entire premise depends on both phases' engine
  layers already existing (Phase I's `magic_type`/MAG resolution, this phase's Essence mechanism),
  and neither phase's own fixture corpus can validate it in isolation (per both phases' intros).
  Deliverables:
  - Confirm the exact SR5 formula via `pdftotext -layout` before implementing anything — record the
    citation in `spec/rulebooks/learnings.md`. Do not assume a linear "1 Essence lost = 1 Magic
    lost" rule without checking; SR5's actual wording is more specific than that shorthand.
  - Wire the result into `Character`'s MAG resolution path from Phase I's WP25 — for a Mundane
    character (`magic_type is None`), this must be a no-op by construction, not a special case to
    remember to skip.
  - Extend `_character_sheet_context` to show a reduced Magic rating distinctly (e.g. "4 (reduced
    from 6 by Essence loss)"), rather than silently displaying the lowered number unexplained.
  Depends on: Phase I's WP25 and this phase's WP30 — in practice, safe to start only once both
  phases have otherwise shipped.
  Acceptance: unit tests combining synthetic `ESSENCE` and magic-rating data (no real fixture can,
  per above) against the confirmed rulebook formula; explicit test that a Mundane character's build/
  character sheet is completely unaffected by any amount of cyberware, and that a magic character
  with zero cyberware sees no reduction — the two boundary cases most likely to regress silently.

