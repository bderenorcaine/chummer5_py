[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase M — Post-MVP: Magic expansion (Bound Spirits, Foci, Mentor Spirits)

Scoped 2026-07-21 alongside Phase L, from the same chapter-extraction survey. All three items are
Step Seven/"Additional Purchases & Restrictions" content (`spec/rulebooks/character_creation_chapter.md`)
gated behind Phase I's Magician/Adept support already existing. **Deliberately three separate WPs, not
one** — a user question during scoping confirmed Bound Spirits, Foci, and Mentor Spirits are wildly
different sizes (a roster-entry-plus-budget-check versus a real gear catalog versus a ~20-archetype
classification pass), and bundling them would either starve the small ones of review attention or let
the big one (Mentor Spirits) block the small ones from shipping.

**None of this phase's three features appear in either of Phase I's two real fixtures** (`Miko.chum5`,
`Wesson.chum5`) — confirmed directly: neither file has a `<spirits>` (bound-spirit) container, a
`<focus>` element, or an actually-selected Mentor Spirit quality (both files' `<qualities>` blocks were
searched for "Mentor Spirit" and found none, despite the *quality's* raw XML shape appearing elsewhere
in the file as inert catalog reference data). Every WP in this phase must therefore verify its mechanics
by hand against the rulebook/legacy C# rather than against real fixture data — say so explicitly in each
WP's acceptance criteria rather than overclaiming coverage, the same honesty standard WP25 applied to
its own two-fixture limitations.

- [x] **WP46 — Bound Spirits.**
  Goal: let a Magician spend leftover Karma binding spirits, modeled as **roster entries with a budget
  check only** — deliberately **not** modeling a spirit's own stat block, skills, or powers (optional or
  otherwise). Confirmed via the rulebook's own Additional Purchases table (Step Seven, p. 98): "1 Karma
  per service (Force of spirit is equal to Character's Magic Attribute rating)... Can only have a number
  of bound spirits equal to Charisma." A spirit's Force is **always exactly the caster's Magic rating**,
  not player-chosen — the only two numbers a player picks are which spirit type/category and how many
  services (which sets the Karma cost 1:1).
  Deliverables:
  - `chummer5.engine.magic` (or a new `chummer5.engine.spirits`, decide & document): a `BoundSpirit`
    dataclass (spirit type/category name, Force — always `character.attribute_value("MAG")`, services)
    and `create_bound_spirit_selection(picks, character, karma_budget)` validating count ≤ Charisma and
    total Karma (= Σ services) against whatever leftover-Karma budget is available at the time this
    lands (no technical dependency on Phase O's unified ledger, but wire into it if that phase ships
    first rather than adding a second, competing Karma-tracking mechanism).
  - Confirm the actual list of spirit-type names to offer (Air, Earth, Fire, Water, Man/Guidance/Task/
    Guardian spirits per tradition, per the Magic chapter — not yet extracted into this project's chapter
    file since it's outside "Creating a Shadowrunner") via a `pdftotext -layout` pass over the Magic
    chapter's own Spirits section (rulebook cites p. 303 for this); record the citation in
    `spec/rulebooks/learnings.md` per this project's established practice. Decide whether the offered
    list is tradition-dependent (Hermetic vs. Shamanic spirit-type names differ) by checking
    `traditions.xml` directly rather than assuming a single universal list.
  - `Character` gains `bound_spirits: tuple[BoundSpirit, ...] = ()`.
  - **Explicitly out of scope for this WP, documented rather than silently omitted**: a bound spirit's
    own powers/skills (including optional powers a player could pick per spirit) — deferred indefinitely,
    per this scoping session's own ruling; only re-open if a future need for spirit stat blocks emerges
    (e.g., if this engine ever models in-play testing, which it currently doesn't for anything).
  - `chummer5.web`: a bound-spirits picker on the leftover-Karma/contacts screen (decide whether it folds
    into the existing contacts UI or gets its own section, mirroring WP20's "shared screen" precedent).
  - `chummer5.io.save_format`/`legacy_import`: thread `bound_spirits` through the normal mechanical path.
  Depends on: Phase I (WP25, for Magic rating/`magic_type`).
  Acceptance: unit tests for the count (≤ Charisma) and Karma (= Σ services) budget checks; **no real
  fixture exercises this** (confirmed above) — acceptance is hand-verified against the rulebook table
  directly, documented as such in the worklog.

- [x] **WP47 — Foci (gear catalog, bonding, and per-category bonuses).**
  Goal: let a Magic-active character buy a focus (nuyen, from a new gear-catalog entry) and bond it
  (Karma, from leftover-Karma budget), applying whichever of the 7 focus categories' bonuses the item
  grants.
  **Confirmed directly against both the rulebook and `legacy/Chummer/data/gear.xml`, not assumed —
  smaller lift than initially feared:**
  - Bonding cost is a **flat `Force x N` per category**, not a general formula (rulebook, "Focus Table,"
    Magic chapter p. 318): Enchanting Foci x3, Metamagic Foci x3, Power Foci x6, Qi Foci x2, Spell Foci
    x2, Spirit Foci x2, Weapon Foci x3.
  - Each focus item's nuyen `<cost>` in `gear.xml` is also a simple linear formula (e.g. Alchemical
    Focus: `Rating * 5000`) — confirm this holds for all ~15-20 SR5 focus entries before assuming
    uniformity, but no general rating-formula resolver (WP36's kind) is needed, just a per-item linear
    multiplier, the same shape WP20/26's own small formula-parsing already handles elsewhere.
  - **A real trap, caught during scoping rather than during implementation**: the rulebook states **two
    different bonded-Force caps** depending on context — "the maximum Force of all your bonded foci
    can't exceed your Magic x 5" (Magic chapter, p. 318, the general/lifetime rule) versus **"Magic
    Rating x 2"** specifically "at character creation" (Step Seven's own Additional Purchases table,
    p. 98). This WP must implement the **tighter chargen-time cap (x2)**, not the general x5 rule — a
    classifier that only reads the Magic-chapter text would silently implement the wrong, looser cap.
  - Each focus item's `<bonus>` node grants a real per-category effect (e.g. Alchemical Focus:
    `<specificskill><name>Alchemy</name><bonus>Rating</bonus></specificskill>` plus a
    `<selecttradition/>` free-text pick) — classify these with the same `BonusSupport`-style scheme
    WP22/27/31 already established (`FLAT_BONUS`/`NOT_YET_SUPPORTED`), verifying each of the ~7-20
    entries individually rather than assuming uniformity across categories.
  Deliverables:
  - `chummer5.data.gear` (or a new `chummer5.data.foci`, decide & document): load the `Foci` category
    from `gear.xml`, filtered to `source == "SR5"` and Availability ≤ 12 (per this project's 2026-07-21
    Availability ruling); parse each item's linear cost multiplier and bonding-cost category.
  - `chummer5.engine.magic`: `create_foci_selection(picks, character, nuyen_budget, karma_budget)`
    validating count ≤ Magic rating and Σ Force ≤ Magic rating x 2 (the chargen-specific cap above), plus
    the nuyen cost (shared Resources budget) and Karma bonding cost (leftover-Karma budget) for each.
  - `Character` gains `foci_selection: FociSelection | None`; apply each bonded focus's classified bonus
    as an `Improvement` (new `ImprovementSource.FOCUS`).
  - `chummer5.web`/`chummer5.io.save_format`/`legacy_import`: normal mechanical threading (WP20/26
    precedent).
  Depends on: Phase I (WP25), and Phase O's unified Karma ledger if it lands first (otherwise a
  standalone Karma-budget check, same as WP46).
  Acceptance: unit tests for the dual-cap distinction (a build that's legal under the x5 general rule but
  illegal under the x2 chargen rule must be rejected) and for at least one `FLAT_BONUS` category's
  applied Improvement; **no real fixture exercises this** (confirmed above) — hand-verified acceptance,
  documented as such.

- [x] **WP48 — Mentor Spirits.**
  Goal: let a Magic-active character take the Mentor Spirit quality and choose a specific archetype,
  each granting **3 distinct bonuses** (general, magician-only, adept-only) — confirmed via the rulebook
  (Magic chapter, "Mentor Spirit Archetypes," p. 320-ish, not yet page-confirmed for this project — do
  that first via `pdftotext -layout` and record the citation in `spec/rulebooks/learnings.md`).
  **Sized like WP22 (qualities) or WP27 (powers), not like a quick add-on** — confirmed the archetype
  count is "20+", each needing individual verification of its 3 bonuses' mechanical shape (flat,
  conditional, or unmodeled), the same classify-every-entry discipline those two WPs established. This
  is the largest of Phase M's three WPs; sequence it last within the phase so Bound Spirits/Foci aren't
  blocked behind it.
  **A real prerequisite this WP must handle, not assume already done**: the Mentor Spirit quality itself
  (5 Karma, `<bonus><selectmentorspirit/></bonus>` — a free-text-selection shape) was excluded from
  WP22's offered catalog on the same grounds as Spirit Affinity (magic-gated, unreachable under
  pre-Phase-I MVP). Now that Phase I exists, this WP must add Mentor Spirit to the offered catalog for
  Magic-active characters specifically (mirroring how `offerable_quality_catalog` already gates
  metatype-granted qualities per character, WP23's precedent) before the archetype-selection mechanism
  built on top of it means anything.
  Deliverables:
  - `chummer5.data.mentors` (new): loader for whatever legacy data file carries mentor-spirit archetypes
    (confirm the exact file — likely `mentors.xml` or a section of `traditions.xml`, don't assume) parsed
    into `(name, general_bonus, magician_bonus, adept_bonus)` triples, `source == "SR5"` filtered.
  - Classify each archetype's 3 bonus slots individually with the established `BonusSupport` scheme
    (`FLAT_BONUS`/`NOT_YET_SUPPORTED`/`NO_EFFECT` as appropriate) — do not assume uniformity across
    archetypes; some slots will likely land in each bucket, mirroring WP22/27's own findings.
  - `chummer5.engine.qualities`: extend the Mentor Spirit quality's application to require an archetype
    selection (mirroring how `create_quality_selection` already handles other quality-specific data,
    though this is the first quality needing a *catalog-backed* selection rather than a flat bonus or
    free-text field with no catalog at all — a genuinely new shape, flag this explicitly).
  - `Character`/save-format/legacy-import: thread the selected archetype through the normal mechanical
    path once the above is settled.
  Depends on: Phase I (WP25), WP22/WP23 (extends the existing quality-offering/classification machinery).
  Acceptance: unit tests for the loader and per-archetype bonus classification (at least one
  `FLAT_BONUS`, one `NOT_YET_SUPPORTED` case, mirroring WP22/27's acceptance shape); **no real fixture
  exercises this** (confirmed above) — hand-verified acceptance, documented as such.

