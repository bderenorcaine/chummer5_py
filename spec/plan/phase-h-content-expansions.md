[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase H — Post-MVP: smallest-scope content expansions

Raised in the same post-MVP design discussion as Phase G, after surveying five candidate
expansions (cyberware, a fuller equipment catalog, adept-first magic, quality bonus-language
widening, and lifestyle selection) against the actual legacy data files rather than assuming their
size. Two findings shaped what's scoped here versus deferred: **cyberware requires real Essence
tracking as a hidden prerequisite** (today `chummer5.engine.derived.BASE_ESSENCE` is a fixed
constant, and `legacy_import.py` hard-rejects any save containing cyberware) **and adept magic
requires unwinding "Talent forced to E,"** which is threaded through the web/session/priorities
layers more invasively than any other candidate — both are real next milestones, deliberately not
scoped here as the *smallest* next step. Lifestyle selection, equipment-catalog expansion, and a
bounded slice of quality-bonus-language widening are, by contrast, genuinely small: each reuses an
existing mechanism (the Resources-priority nuyen budget, the `StarterGearItem` flat-cost shape, the
`FlatBonus`/`Improvement` machinery respectively) rather than needing a new one.

**All three should land after WP18** (Phase G's `Character`-folding WP), not in parallel with it —
each adds a new committed selection (`LifestyleSelection`, a widened `ResourcesSelection`, more
offerable qualities), which is exactly the shape WP18 is designed to hold cleanly. Building any of
them against today's scattered `ChargenSession`-sibling shape means redoing that plumbing right
after WP18 changes it. WP22 (qualities) touches no `Character` fields, so it has no *technical*
dependency on WP18, but shares files (`engine/qualities.py`, `web/app.py`'s quality routes) with
it — sequence after WP18 anyway to avoid merge conflicts, unless deliberately run in parallel on a
separate branch.

- [x] **WP20 — Lifestyle selection.**
  Goal: add the mandatory core-rulebook Lifestyle chargen step (rulebook, p.369: "A character must
  select one of the lifestyles below to be their primary Lifestyle") — currently absent from the
  engine entirely (confirmed: zero references anywhere in `src/`) despite being squarely within
  MVP's own stated scope ("starting nuyen/resources spent on a basic gear purchase" already implies
  a Resources-priority spend; lifestyle is the same kind of spend and the rulebook treats it as a
  mandatory line item of the same chargen step, not a separate one). Not excluded by Project
  Overview's scope lists either way — an oversight, not a deliberate cut.
  Deliverables:
  - `src/chummer5/data/lifestyle.py` (new): loader for `legacy/Chummer/data/lifestyles.xml`,
    filtered to `source == "SR5"` (9 raw entries) and further to the 6 real starting tiers (Street,
    Squatter, Low, Middle/Medium, High, Luxury) — exclude the "ID ERROR" placeholder and the two
    Hospitalized entries explicitly (document why: not valid starting-lifestyle choices), the same
    "exclude, don't silently drop" pattern WP2/WP3/WP6 already established for out-of-scope
    metatypes/qualities.
  - `src/chummer5/engine/lifestyle.py` (new): `LifestyleSelection` (tier, months, total cost) +
    `create_lifestyle_selection(tier_name, months, catalog)`, validating the tier is known and
    computing `cost = tier.monthly_cost * months`. Confirm the actual minimum-months rule via
    `pdftotext -layout` against the rulebook's Lifestyle section (p.369-373) before hardcoding one —
    don't assume "1" from fixture inspection alone — and record the citation in
    `spec/rulebooks/learnings.md`, per this project's established practice (see WP8/WP9/WP10's
    entries there).
  - Wire the lifestyle cost into the **same** Resources-priority nuyen budget
    `create_resources_selection` already draws from for gear (confirmed via fixture cross-check:
    every one of the 11 curated mundane fixtures' `<lifestyle>` cost comes out of the same pool as
    its gear spend, not a separate currency) — decide in the worklog whether this means widening
    `ResourcesSelection` itself to include a `lifestyle` field, or a separate selection checked
    against the same remaining-budget number; document the choice and why.
  - The 9-entry SR5 lifestyle-qualities catalog (extra comforts/security modifiers) is explicitly
    **out of scope for this WP** — none of the 11 curated fixtures need it to reproduce their base
    lifestyle cost — mirroring `resources.py`'s own "not the full gear catalog" precedent.
  - `src/chummer5/web/`: a lifestyle-selection form. Decide and document whether this is a new
    section/route or folds into the existing Resources section (`_resources.html`/
    `submit_resources`), given both spend from one shared budget.
  - `src/chummer5/io/save_format.py` / `legacy_import.py`: thread the lifestyle selection through
    `CharacterSave`/`build_character`, the same mechanical addition every prior selection type
    already got.
  Depends on: WP18.
  Acceptance: unit tests for tier lookup and cost math against hand-checked `lifestyles.xml` values;
  integration tests against all 11 curated mundane fixtures' real `<lifestyle>` data
  (`baselifestyle`/`months`/`cost`) — the best fixture coverage of any Phase G/H candidate surveyed,
  use it fully rather than only hand-checked cases.

- [x] **WP21 — Expand the starter-gear catalog to the full flat-cost SR5 equipment set.**
  Goal: grow `STARTER_GEAR_CATALOG` from 5 hand-picked items to the real SR5-core, flat-cost
  gear/armor/weapon catalog — confirmed at **411 items** (266 gear + 11 armor + 134 weapons,
  `source == "SR5"` and a plain integer `<cost>`, no `Rating`/`FixedValues`/`Variable` formula) —
  via a real XML loader instead of a hardcoded list. Zero new Improvement/engine mechanics needed
  for this subset; the biggest visible content increase available at the lowest technical risk of
  the candidates surveyed.
  Deliverables:
  - `src/chummer5/data/gear.py` (new): loaders for `legacy/Chummer/data/{gear,armor,weapons}.xml`,
    filtered to `source == "SR5"` AND flat-cost as defined above. Explicitly exclude, with the
    exclusion documented rather than silently dropped: rating-scaled/`FixedValues`/`Variable`-cost
    items (125 of 391 SR5 gear entries, 1 of 12 SR5 armor entries — `Clothing`); and the 3
    additive-stacking armor items (`Helmet`, `Ballistic Shield`, `Riot Shield` — `armor='+2'`/`'+6'`
    stacking math is genuinely different from every other flat item's single rating). Preserve each
    item's category (34 distinct among the flat subset) for the UI grouping below.
  - `src/chummer5/engine/resources.py`: replace the hardcoded `STARTER_GEAR_CATALOG` tuple with the
    loaded catalog; `StarterGearItem` gains an optional `category` field, and armor items gain an
    `armor_rating` field (armor's own rating, not a nuyen concept).
  - **Explicitly do not implement** SR5's Availability-cap rule (Restricted/Forbidden-availability
    purchases are capped by a Priority-derived Availability budget) despite ~57% of SR5 gear and
    69% of SR5 weapons carrying such a code — flag this as a deliberate, documented scope cut (the
    same pattern as the already-established skill-karma and 7-point-contact cuts), not a silent
    gap. A natural candidate for its own later WP once this catalog's size makes the gap visible.
  - `src/chummer5/web/`: `_resources.html`'s gear picker needs restructuring for ~400 items instead
    of 5 — category-grouped, not a single flat list; a real (if modest) UI task distinct from
    WP15/16's small fixed lists.
  Depends on: WP18.
  Acceptance: unit tests confirming the loader's counts (411 flat items total, matching this
  research) and that a rating-scaled/`Variable`-cost item is correctly excluded rather than
  mis-parsed; existing gear-purchase fixture tests still pass unchanged.

- [x] **WP22 — Offer more qualities: verified-inert flavor picks + the Limit-bonus trio.**
  Goal: widen the offered SR5 quality catalog beyond today's 3 (Catlike, Double-Jointed, Natural
  Athlete), using this session's verified classification of all 93 currently-`NOT_YET_SUPPORTED`
  SR5 qualities — without ever offering a quality whose real mechanical effect would be silently
  dropped, preserving `chummer5.data.qualities`' own stated rule ("MVP never partially applies a
  quality's effects").
  Deliverables:
  - **Tranche 1 — the Indomitable trio (Mental/Physical/Social).** Each `<bonus>` maps directly onto
    an existing `ImprovementType` (`MENTAL_LIMIT`/`PHYSICAL_LIMIT`/`SOCIAL_LIMIT`), already consumed
    unconditionally by `chummer5.engine.derived`. Extend `chummer5.data.qualities._classify_bonus`'s
    flat-shape recognition to cover `<mentallimit>`/`<physicallimit>`/`<sociallimit>` (a bare
    numeric value, no condition — verified present) the same way it already covers
    `<specificskill>`/`<specificattribute>`; extend
    `chummer5.engine.qualities._TARGET_KIND_TO_IMPROVEMENT_TYPE` with the 3 new target kinds.
  - **Tranche 2 — 8 verified-inert qualities.** Gearhead, Guts, Juryrigger, Natural Hardening,
    Low-Light Vision, Thermographic Vision, Simsense Vertigo, Unsteady Hands — each confirmed this
    session to have an empty `<bonus/>`, no `<required>`/`<forbidden>` gate, and no hardcoded
    by-name special-casing anywhere in the legacy C# (`grep`-checked). Their real SR5 effects are
    genuinely in-play/narrative (light-condition perception, fear-test resistance, repair time,
    Matrix-attack resistance on gear, called-shot penalties) — none produce a chargen-time
    computed value. Add a new `BonusSupport` value (e.g. `NO_EFFECT`) distinct from `FLAT_BONUS`,
    so "verified mechanically inert" stays visibly different from "has a flat numeric bonus" rather
    than conflating the two.
  - **Explicitly excluded, reasons recorded in this WP's worklog** (verified, not assumed): Astral
    Beacon, Astral Chameleon, Focused Concentration (magic-gated via `<required>` — unreachable for
    any mundane character); Gremlins (not actually bonus-empty — carries
    `<firstlevelbonus><notoriety>1</notoriety></firstlevelbonus>`, gated behind the wholly
    unmodeled Notoriety/reputation system shared with 18 other SR5 qualities).
  - **Deliberately deferred, not defaulted into this WP:** Human-Looking (gated to Elf/Dwarf/Ork —
    all in-scope metatypes, genuinely offerable, but needs a new "required metatype" check with no
    precedent in the engine) and the two forbidden-pairs, Insomnia (Basic)/(Full) and Distinctive
    Style/Blandness (need a new "mutually exclusive quality" check). Both are small, real, and
    self-contained, but a genuinely different kind of change (a new validation axis on
    `create_quality_selection`) than tranches 1-2's pure data-classification changes, and nothing
    else in the 96-quality set would ride along to amortize building it — scope as a follow-up WP
    once/if it's worth it on its own, don't bundle by default.
  - **This WP's first real task, not a chat-turn shortcut:** a proper `pdftotext -layout` +
    rulebook-citation pass (same methodology as WP8/WP9/WP10, recorded in
    `spec/rulebooks/learnings.md`) over the ~20 remaining `selecttext`-only SR5 qualities not
    already covered above (Home Ground, Code of Honor, Codeblock, Social Stress, Natural Immunity
    ×2, Spirit Affinity, Prejudiced ×6, SINner ×3 — Allergy's 8 variants stay excluded, already
    correctly bucketed as toxin/pathogen-resist, a system this project doesn't model). Several of
    these (SINner, Prejudiced) carry real, currently-unmodeled narrative/mechanical weight
    (background checks, social-test penalties) despite a shape-trivial `<bonus>` node — offering
    them for karma with zero consequence applied would violate the "never partially apply" rule in
    spirit even though not in mechanism. Do not default to including any of them; only add ones this
    pass confirms are as genuinely inert as tranche 2's 8.
  Depends on: WP3, WP8 (already satisfied); sequence after WP18 to avoid merge conflicts on shared
  files (`engine/qualities.py`, `web/app.py`'s quality routes), though there's no technical
  dependency on WP18's `Character`-folding itself.
  Acceptance: unit tests — every newly-offerable quality (3 Indomitable + 8 verified-inert, plus
  whatever the rulebook-research pass adds, taking the offered catalog from 3/96 upward)
  individually selectable and correctly karma-charged; the 3 Indomitable qualities verified to
  actually raise the relevant Limit via `chummer5.engine.derived`; an explicit test that every
  excluded-with-reasons quality (Astral Beacon/Chameleon, Focused Concentration, Gremlins) stays
  excluded from the offered list, mirroring WP8's own "excluded... rather than silently mis-applied"
  acceptance criterion.

- [x] **WP23 — Grant metatype-inherent qualities for free (Low-Light Vision, Thermographic Vision,
  Resistance to Pathogens/Toxins).**
  Goal: fix a real, previously-undiscovered gap surfaced while reviewing WP22 — SR5 grants specific
  qualities automatically and for free to certain metatypes (Elf/Ork → Low-Light Vision, Dwarf →
  Thermographic Vision + Resistance to Pathogens/Toxins, Troll → Thermographic Vision; Human → none),
  and this engine currently models none of it (`chummer5.data.metatypes.Metatype` never parses the
  base `<metatype><qualities>` block at all — only `Metavariant` does, and metavariants are entirely
  out of MVP scope). See Project Overview's 2026-07-19 Open Questions entry for the full discovery
  writeup and legacy-C# citations (`QualitySource.Metatype`, `Character.cs` ~line 44348). This
  directly follows from WP22: Low-Light Vision/Thermographic Vision are now purchasable
  (`NO_EFFECT`), so a non-Human character can currently spend karma re-buying a quality they should
  already have for free, with nothing to stop them.
  Deliverables:
  - `src/chummer5/data/metatypes.py`: widen `Metatype` with `qualities_positive: tuple[str, ...]`/
    `qualities_negative: tuple[str, ...]` (mirroring `Metavariant`'s existing fields), parsed from
    the base `<metatype><qualities>` block via the existing `_parse_quality_names` helper.
  - `src/chummer5/engine/qualities.py`: `resolve_metatype_qualities(metatype, catalog) ->
    tuple[Quality, ...]` — resolves `qualities_positive`/`qualities_negative` names against the full
    SR5-scoped quality catalog (not `mvp_quality_catalog` — granting is unconditional, not gated on
    what MVP can offer a player to *buy*), raising `ValueError` for an unresolvable name (a real
    data-integrity guard: these names are fixed by the shipped XML, so a mismatch means a real bug,
    not an expected edge case). `apply_quality_improvements` gains an optional `source_type:
    ImprovementSource = ImprovementSource.QUALITY` parameter (existing callers unaffected) so
    metatype-granted Improvements record under the already-reserved, currently-unused
    `ImprovementSource.METATYPE` instead of `QUALITY` — keeps `ImprovementIndex.remove_source`
    able to retract exactly one or the other. `offerable_quality_catalog(character, catalog) ->
    tuple[Quality, ...]` = `mvp_quality_catalog(catalog)` minus whatever `character
    .metatype_qualities` already grants, so a player can never spend karma re-buying an inherent
    racial quality (passing this narrowed catalog straight into `create_quality_selection` is
    sufficient — no signature change needed there, since it already re-derives
    `mvp_quality_catalog` from whatever catalog it's given).
  - `src/chummer5/engine/character.py`: `Character` gains `metatype_qualities: tuple[Quality,
    ...] = ()` — the same "empty until derived" shape other selections have, except this one is
    never player-submitted, only ever set to `resolve_metatype_qualities`'s output.
  - `src/chummer5/web/app.py`: a new `_relink_metatype_qualities(character, catalog)` helper
    (mirrors `_relink_quality_improvements`/`_relink_contact_selection`'s existing pattern) —
    removes whatever Improvements `character.metatype_qualities` already holds (a no-op on the
    always-fresh index `submit_attributes` constructs; a real removal on `submit_priorities`'s
    carried-forward index when the metatype actually changed), resolves the character's *current*
    `metatype`'s qualities fresh, applies them, and reattaches. Call it from both `submit_priorities`
    (both the fresh-character and reconfirm branches) and `submit_attributes`, the same two real
    "(re)construct a `Character`" sites WP18/WP19 already established. `_quality_selection_context`/
    `submit_qualities` use `offerable_quality_catalog(character, QUALITIES)` instead of the raw
    `MVP_QUALITIES` module constant, so the picker and its validation both exclude already-granted
    qualities. `_quality_selection.html` gains a short informational line listing `character
    .metatype_qualities`. `_character_sheet_context`'s quality display includes `character
    .metatype_qualities` alongside `quality_selection`'s picks, visibly distinguished as
    metatype-granted (e.g. not counted in `quality_karma_cost`, which stays `quality_selection`-only).
  - `src/chummer5/io/save_format.py`: `build_character` resolves and applies `metatype_qualities`
    the same way it already does `quality_selection`, including it in the final `replace(...)`.
    Deliberately **not** a new `CharacterSave` field — it's 100% determined by `metatype` plus the
    current quality catalog, so persisting it would just be redundant, frozen-at-save-time data;
    re-deriving at load time also means a loaded character always reflects the current catalog.
  - `src/chummer5/io/legacy_chum5.py`: `LegacyQuality` gains `qualitysource: str` (parsed from
    `<qualitysource>`), so a real `.chum5`'s metatype-granted qualities are distinguishable from
    player-picked ones at all.
  - `src/chummer5/io/legacy_import.py`: excludes `qualitysource == "Metatype"` legacy qualities from
    the candidate list passed to `create_quality_selection` — they're not a player pick to import
    faithfully; the normal construction pipeline re-derives and re-grants them from the imported
    metatype instead, exactly as it does for a freshly-built character. (Confirmed this is a real,
    currently-live bug, not a hypothetical: before WP22, an Elf/Dwarf/Ork/Troll import would have
    misreported its free racial quality as a "dropped" unsupported quality; after WP22 it would
    misreport it as a real karma-costing pick, since Low-Light Vision/Thermographic Vision are now
    `mvp_quality_catalog`-offered and `LegacyQuality` never captured `qualitysource` to tell the two
    cases apart.)
  Depends on: WP22 (shares `engine/qualities.py` and the same quality-catalog-filtering concern;
  sequenced directly after since WP22 is what turned this from a theoretical gap into a concretely
  wrong purchasable-catalog and legacy-import bug, not just a missing feature).
  Acceptance: unit tests for the widened loader (Elf/Dwarf/Ork/Troll's exact granted names, Human's
  empty tuple, hand-checked against `metatypes.xml`); `resolve_metatype_qualities`/
  `apply_quality_improvements`'s new `source_type` param/`offerable_quality_catalog` each tested in
  isolation; integration tests against the 5 curated mundane fixtures with a non-Human core metatype
  (`BLUE`/Ork, `Blindfire`/Elf, `Gentle Earthquake`/Troll, `Monomax (approved) 3`/Troll,
  `Rez0luti0n2.0`/Dwarf) confirming the resolved `metatype_qualities` matches each fixture's own
  `qualitysource=Metatype` entries; a test that submitting an already-granted quality's id to
  `/ui/qualities` is rejected; a manual walkthrough building an Elf confirms Low-Light Vision appears
  on the character sheet at zero karma cost and is absent from the purchasable picker.

