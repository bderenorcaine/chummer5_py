[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase I — Post-MVP: Magic (Magicians & Physical Adepts)

SR5's magic/resonance leg was cut wholesale from MVP by forcing Talent to letter E ("Mundane") — the
Project Overview's 2026-07-18 entry already flags that unwinding this is "real plumbing in the web
layer, not just an engine default," which is why it wasn't scoped as the smallest post-MVP step back
in Phase H. This phase is that unwind, deliberately scoped to the two archetypes that share the Magic
(not Resonance) priority mechanic and need no Matrix/Resonance modeling at all: **Magician and
(physical) Adept.**

**Explicit, verified scope cuts.** Technomancer/A.I. stay excluded — Resonance is out of scope per the
Project Overview, permanently, not just for MVP. **Mystic Adept is excluded too, by explicit product
decision (2026-07-19), not a smallest-scope pragmatism call** — unlike every other cut in this list,
it isn't being deferred for being large or under-researched; it's simply not being built. This
conveniently also removes the one piece of pre-decision research that would otherwise have blocked
WP25 (Project Overview's 2026-07-18 entry flagged Mystic Adept's Power Point split as unresolved, and
that PP split is a Mystic-Adept-only wrinkle — a pure Adept's PP is a simple 1:1 Magic-rating grant
with no split to derive, so nothing about Adept alone is left open). Aspected Magician, Apprentice,
Explorer, and Enchanter (the other Talent options at letters B/C) and Aware (letter D) are also
excluded: each is a real SR5 archetype with its own restricted-access rules (an Aspected Magician can
cast *or* conjure, never both; Apprentice/Explorer/Enchanter are setting-specific restricted picks)
that neither of this phase's two real fixtures exercises, and that would each need its own
rules-research pass — mirroring WP22's "don't default to including any of them" posture for quality
tranches, applied here to Talent options instead. `traditions.xml`'s **Custom** tradition (also
`source == "SR5"`) is cut too: unlike Hermetic/Shamanic, it requires the player to hand-define a
drain-attribute pair and spirit-affinity table rather than picking a fixed catalog entry — a different
kind of feature, not a fixed-cost addition. Only **Hermetic** and **Shamanic** are offered, and only
for Magician — Adepts don't cast spells and pick no tradition at all.

**Ground truth is thin but real.** Of the full 34-fixture corpus, only 3 files are
`buildmethod = Priority` at all (see the corpus note atop this document): `Yeti-#ffffff2.chum5`
(already spent on mundane content), `Miko.chum5` (Elf Magician, Talent letter A, tradition Shinto),
and `Wesson.chum5` (Human Adept, Talent letter C, tradition Christian Theurgy). Both Miko's and
Wesson's traditions are non-SR5-sourced (Shinto is `SG`, Christian Theurgy is `FA`) — real fixtures
for the *rating*/spell-count/power-list math this phase implements, but not for tradition-specific
mechanics (the drain-attribute pair), which stay hand-verified against Hermetic/Shamanic's own
SR5-sourced entries instead.

**A mechanical finding, confirmed against both real fixtures, about how Magic's *starting* rating
works — corrected 2026-07-20 after initially being mis-stated as "not a point-buy" at all; see
`spec/worklogs/WP29.md`'s "Correction" section and `spec/rulebooks/learnings.md`'s "Post-WP29
correction" entry for the full research.** Every other attribute this engine models is `metatype
minimum + points spent + Σ improvements`, funded from a priority-derived budget the player spends
against (the Attributes letter for primary attributes, the Heritage letter for EDG). Magic's
*minimum* works differently: the chosen Talent option's `magic` field
(`chummer5.data.priorities.TalentOption.magic`) is the character's *starting* MAG rating (no
metatype-minimum term contributes), not a metatype-derived floor the way every other attribute's
minimum is. But — confirmed via the core rulebook (p.65: Special Attribute Points "may be split...
between... Edge and Magic or Resonance") and the legacy engine (`MAG.AssignLimits(talentOption
.magic, magMax, magMax)` sets that value as MAG's *minimum*, then reuses the exact same `Base`-adding
formula EDG uses) — that starting rating **can** be raised further by spending Special Attribute
Points from the same Heritage-derived pool EDG draws from, up to the metatype's own Magic maximum
(6 for every SR5-core metatype). Neither Miko nor Wesson happened to exercise this (both landed on a
Talent letter/codename combo already at the metatype maximum, leaving no headroom), which is why the
original research missed it. `"MAG"` still isn't added to `SPECIAL_ATTRIBUTES`/`ALLOCATABLE_
ATTRIBUTES` the way EDG lives there — its allocatability is character-specific (only legal once a
magic-active Talent is confirmed), so it's validated by a separate function,
`chummer5.engine.magic.create_magic_attribute_points`, cross-checked against EDG's own spend rather
than folded into `create_character`'s unconditional validation.

**The Talent free-skill grant is in scope for this phase (explicit product decision, 2026-07-19) — and
the legacy C# turns out to specify it precisely enough that no general rules-language interpreter is
needed.** WP2's loader deliberately left `<talent>`'s nested `<skillqty>`/`<skillval>`/`<skilltype>`
(a free skill grant into a restricted list — Magician letter A grants 2 skills at rating 5, letter B
grants 2 at rating 4; Adept letter B grants 1 at rating 4, letters C/D grant none) unparsed, calling it
"out of MVP scope" back when Talent wasn't a real choice at all — leaving it unimplemented would make
a Magician/Adept built through this engine strictly *cheaper* than SR5 allows, the same "never
partially apply" concern `chummer5.data.qualities`' own docstring raises for Quality bonuses. Reading
`SelectMetatypePriority.cs` directly (the legacy form that actually applies this grant) resolves the
real eligibility rule per `skilltype` value, and only two of its cases are ever hit by this phase's
offered Talent options: `skilltype = "magic"` (Magician, both letters) resolves via
`GetMagicalSkillList()` — literally `skills/skill[category = "Magical Active" or category =
"Pseudo-Magical Active"]`, a plain filter on `chummer5.data.skills.Skill.category`, a field the loader
already exposes; `skilltype = "xpath"` (Adept, letter B only) evaluates a literal XPath boolean
expression carried in that element's own `xpath` attribute — for this one case, confirmed verbatim:
`not(attribute = 'RES' or attribute = 'DEP') and (not(category = 'Magical Active') or skillgroup = ''
or not(skillgroup))`, i.e. "any active skill not linked to RES/DEP, excluding Magical Active skills
that belong to a skill group" — again expressible as a plain predicate over `Skill.attribute`/
`.category`/`.skill_group`, all fields the loader already exposes. **Recognize this one known
expression as a named, hardcoded predicate (mirroring WP3/WP22's "classify known shapes" method) —
do not build a general XPath evaluator for it**; nothing in this phase's offered scope ever produces a
different `xpath` value, and if a future phase does, it should extend the classifier explicitly rather
than this phase silently guessing at generality it doesn't need yet.

- [x] **WP24 — Talent as a real 5th priority category (plumbing only; still Mundane-only).**
  Goal: retire "Talent forced to E" as a hardcoded assumption threaded through the web layer, with
  **zero new player-visible capability yet** — a pure restructuring WP in the same spirit as WP18.
  Deliverables:
  - `chummer5.web.session`: widen the priority-letter assignment from a 4-category permutation
    (Heritage/Attributes/Skills/Resources over `PRIORITY_LETTERS`) to 5 (adding Talent) — a new
    `talent_letter` field with a `DEFAULT_TALENT_LETTER`, chosen so the existing 4 defaults plus a
    5th remain a valid A-E permutation.
  - `chummer5.web.app`: `_priority_form_context`/`submit_priorities` validate a 5-way permutation
    instead of 4; the Talent letter's *option* still resolves unconditionally to
    `priorities.mundane_talent()` at this stage (no picker yet) — this WP only proves the
    letter-assignment plumbing, the same way WP14 proved metatype+priority-letter assignment before
    WP15 added spend logic on top of it.
  - Decide & document (WP18-style): does `Character` need its own `talent_letter` field alongside
    `heritage_letter`/`attributes_letter` (duplicated from session state for the same reason those
    two already are — WP25 needs to look up the chosen letter's options against
    `priorities.talent`)?
  Depends on: nothing new.
  Acceptance: `pytest`/`ruff`/`mypy` green; full regression of all 12 curated fixtures (11 WP4 +
  Yeti) unchanged, proving zero behavioral drift; manual walkthrough confirms a 5-letter permutation
  is now required and the priority form round-trips correctly with Talent still implicitly Mundane.

- [x] **WP25 — Magic type, Magic rating, tradition selection, and the Talent free-skill grant.**
  Goal: let the Talent letter's *option* be chosen (Mundane/Magician/Adept — this phase's offered
  set) and derive `Character`'s Magic rating, Power Points, and (Magician only) tradition and the
  Talent-granted free skill(s).
  Deliverables:
  - `chummer5.data.traditions.py` (new): loader for `legacy/Chummer/data/traditions.xml`, restricted
    to `source == "SR5"` **and** name != "Custom" (Hermetic, Shamanic — 2 of the 3 SR5 entries),
    each carrying its drain-attribute pair (confirm the exact element shape when implementing, don't
    assume it mirrors another file's shape).
  - `chummer5.engine.character`: `Character` gains `magic_type: str | None` (Talent codename —
    `"Magician"`/`"Adept"`, `None` for Mundane) and `tradition: Tradition | None` (always `None` for
    Adept/Mundane). Per the phase-intro finding, **do not** add `"MAG"` to
    `SPECIAL_ATTRIBUTES`/`ALLOCATABLE_ATTRIBUTES` — decide and document whether MAG resolution is a
    new `Character` method or a special case inside `attribute_value`.
  - `chummer5.engine.magic.py` (new): `create_magic_selection(talent_letter, talent_codename,
    tradition_id, priorities, traditions_catalog)`, validating the codename is one of that letter's
    real options and, for Magician, that a tradition was chosen from the 2-entry catalog. Power
    Points = Magic rating 1:1 for Adept (no split to derive, now that Mystic Adept is out of scope —
    still worth a one-line rulebook citation for completeness).
  - **Implement the Talent free-skill grant** (`skill_qty`/`skill_val`/`skill_type`, already parsed
    at the flat-scalar level by WP2) per the phase intro's traced mechanism: a `skilltype = "magic"`
    grant (Magician, both offered letters) offers any skill with `category` in `{"Magical Active",
    "Pseudo-Magical Active"}`; a `skilltype = "xpath"` grant (Adept, letter B only) offers any skill
    matching the one known predicate traced in the phase intro. `create_magic_selection` (or a
    sibling function) validates the player picks exactly `skill_qty` distinct skills from the
    correct eligible set for the chosen codename/letter, each landing at rating `skill_val` — decide
    and document how this interacts with `chummer5.engine.skills.SkillAllocation` (a granted rating
    is not bought with Skills-priority points, so it must not double-count against that budget, but
    it should still show up as the skill's real total rating).
  Depends on: WP24.
  Acceptance: unit tests for `create_magic_selection`'s validation and for both free-skill-grant
  predicates (a Magical-Active-category case, and the Adept-letter-B xpath-equivalent case); unit
  test confirming a granted free skill doesn't consume Skills-priority budget. Integration tests
  against Miko (Magician, letter A, MAG=6, 2 free skills at rating 5) and Wesson (Adept, letter C,
  MAG=4) confirming the resolved Magic rating matches exactly — note in the test/worklog that Miko's
  own `.chum5` doesn't cleanly separate which of her skill points came from the free grant versus
  regular Skills-priority spend (`newskills/skills/skill`'s `<base>` field commingles both), so the
  free-grant *mechanism* is verified against the traced legacy-C# rule directly, not by reproducing
  Miko's exact numbers; explicit test that Mundane still resolves to no magic type/MAG/free skills,
  unchanged from before this WP. Note: Wesson (Adept, letter C) grants no free skill at all — only
  Adept letter B does — so Wesson cannot exercise the xpath-predicate path; that path is
  hand-verified against the traced rule only, the same "no real fixture, verify by hand" honesty
  this project already applies elsewhere (e.g. WP8's quality karma cap).

- [x] **WP26 — Spell selection (Magician).**
  Goal: let a Magician pick spells up to their Talent option's `spells` budget (Miko: 10, at
  letter A).
  Deliverables:
  - `chummer5.data.spells.py` (new): loader for `legacy/Chummer/data/spells.xml`, restricted to
    `source == "SR5"` (93 of 363 entries, spanning Combat/Detection/Health/Illusion/
    Manipulation/Rituals). No casting-test/drain-resolution modeling needed at chargen (mirrors
    mundane MVP's own "no combat system" posture) — a spell is a roster entry, not a computed value.
  - `chummer5.engine.magic.py`: `create_spell_selection(spell_ids, catalog, budget)`, validating
    count <= the Talent option's `spells` field and no duplicates — the same shape as
    `create_contact_selection`'s free-point-budget check.
  - `Character` gains `spell_selection: SpellSelection | None`.
  Depends on: WP25.
  Acceptance: unit tests for budget/duplicate validation; integration test against Miko confirming
  all 10 of her real spell names resolve against the SR5-scoped catalog — flag, don't silently drop,
  any that don't.

- [x] **WP27 — Adept power selection.**
  Goal: let an Adept spend Power Points on Adept Powers.

  **A real trap, caught before implementation rather than after: `<bonus><selectattribute>` is not
  a single shape.** The rulebook (p.309) names a general rule, "Adept Drain: Some powers cause
  Drain... resisted with Body + Willpower," distinct from a Magician's tradition-based Drain. Two of
  the 28 SR5 powers actually trigger it: Adrenaline Boost (+2 Initiative this turn, Drain equal to
  levels next turn) and **Attribute Boost — whose `<bonus>` node is `<selectattribute>` with a bare
  list of eligible attributes and no `<val>` child at all**, because its real effect is "make a
  Magic + Attribute Boost Rating Test; each hit raises the attribute by 1 until the boost ends, then
  take Drain" — a temporary, test-gated, Drain-costing effect, not a permanent bonus. This is the
  same raw child tag (`selectattribute`) that Improved Physical Attribute's `<bonus>` also uses —
  but Improved Physical Attribute's carries a `<val>Rating</val>` child (a real, permanent,
  rating-scaled bonus) that Attribute Boost's lacks. **The correct classifier checks for that `<val>`
  child, not just the `selectattribute` tag** — a naive "any `selectattribute` bonus is a flat
  attribute bonus" rule would have silently misapplied Attribute Boost as a permanent stat increase.
  Adrenaline Boost has no `<bonus>` element at all, so it already lands in `NOT_YET_SUPPORTED` by
  the standard "empty bonus" rule — but confirm this by reading its rulebook effect, don't assume an
  empty `<bonus>` means inert (WP22's own "don't assume, verify" discipline for `NO_EFFECT` extends
  here: an empty `<bonus>` on a power that turns out to *cause Drain* is exactly the kind of case
  that discipline exists to catch).

  Deliverables:
  - `chummer5.data.powers.py` (new): loader for `legacy/Chummer/data/powers.xml`, restricted to
    `source == "SR5"` (28 of 109 entries). Classify each power's `<bonus>` with a 3-way
    `BonusSupport` shape mirroring WP3/WP22's for qualities, with one real difference from that
    precedent: **every power's bonus value is the literal token `"Rating"`, not a hardcoded int**
    (confirmed on every power checked so far, including the `NOT_YET_SUPPORTED` Improved Physical
    Attribute case above) — the classifier/applier must resolve `value = per-level magnitude x the
    purchased power rating`, not just `int()` the field the way `chummer5.data.qualities` does.
    **`FLAT_BONUS`** candidates, each individually verified rather than shape-matched alone:
    Improved Physical Attribute (`selectattribute` **with** a `<val>` child -> `ATTRIBUTE`); Improved
    Potential (Social/Mental/Physical) x3 (`sociallimit`/`mentallimit`/`physicallimit`, `levels =
    False` so the resolved rating is always 1 -> the same types WP22's Indomitable trio uses);
    Enhanced Perception (two hardcoded named skills, Perception and Assensing, each at the power's
    rating -> `SKILL`). **Flag, don't silently include, extra complexity**: Improved Ability (skill)
    needs two more real rules beyond a flat bonus — the target skill must already be known at rating
    >= 1 (`<selectskill minimumrating="1">`), and the rulebook caps the achievable improvement at
    "your current skill level x 1.5, rounded up" (p.309) — decide whether this WP implements that cap
    or defers Improved Ability specifically, documented either way. **`NOT_YET_SUPPORTED`**: Attribute
    Boost and Adrenaline Boost (Drain-costing, test-gated — see above) plus everything needing
    combat/Matrix/social-test/healing-rate mechanics this engine doesn't model (Combat Sense, Killing
    Hands, Spell Resistance, Rapid Healing, ...). Check for a genuinely-inert `NO_EFFECT` case among
    the rest the way WP22 found for qualities rather than assuming there isn't one.
  - Both PP-cost shapes exist among the candidate `FLAT_BONUS` powers: rating-scaled
    (`levels=True`, cost = `points * rating`) and single-purchase (`levels=False`). Handle both, not
    just the simpler one.
  - `chummer5.engine.magic.py`: `create_power_selection(power_ids_with_ratings, catalog,
    power_point_budget)`, validating total PP spend against WP25's resolved Power Points;
    `apply_power_improvements` mirroring `apply_quality_improvements`'s shape (new
    `ImprovementSource.ADEPT_POWER`).
  - `Character` gains `power_selection: PowerSelection | None`.
  Depends on: WP25.
  Acceptance: unit tests for PP-budget validation (including a rating-scaled power) and specifically
  a test that Attribute Boost is classified `NOT_YET_SUPPORTED` despite sharing a raw child tag with
  a `FLAT_BONUS` power — the exact regression this WP's intro exists to prevent. Integration test
  against Wesson confirming his 6 real powers resolve against the catalog and his PP spend fits his
  MAG-4-derived budget. **Wesson's own fixture includes two powers this WP cannot fully support
  (Combat Sense, and Attribute Boost per the finding above)** — assert both explicitly as excluded/
  `NOT_YET_SUPPORTED` rather than skipping them quietly, mirroring WP8/WP22's established acceptance
  pattern.

- [x] **WP28 — Drain Resistance + magic-aware save/load + legacy import unblocking.**
  Goal: finish the derived-stat surface magic chargen needs, and let a real magic character
  round-trip through native save/load and legacy `.chum5` import.

  **Correction to this phase's earlier framing: Drain Resistance is not Magician-only.** WP27's own
  research turned up the rulebook's named "Adept Drain" rule (p.309, confirmed via `pdftotext
  -layout`) — some Adept Powers (Adrenaline Boost, Attribute Boost; both `NOT_YET_SUPPORTED` per
  WP27's classifier, since the *test-and-consequence* resolution around them is out of this engine's
  combat-free scope) cost Drain when activated, "resisted with Body + Willpower" — a fixed formula,
  unlike a Magician's tradition-dependent pair, and not gated on which powers were actually bought
  (the same way Physical/Mental/Social Limit are shown regardless of build specifics). So Drain
  Resistance is a real, cheaply-computable derived stat for **both** Magician and Adept — just via
  two different formulas — and only actually absent for Mundane.
  Deliverables:
  - `chummer5.engine.derived`: `drain_resistance(character)`, dispatching on `magic_type`: for
    Magician, the tradition's drain-attribute pair + `Σ improvements`; for Adept, `BOD + WIL + Σ
    improvements` (fixed, per the Adept Drain rule above — no tradition involved); `None`/not
    meaningful for Mundane (mirrors `BASE_ESSENCE`'s own docstring pattern for a similarly-scoped
    assumption). Cite the p.309 rule explicitly in `spec/rulebooks/learnings.md`, matching how
    WP27's own citation for it should be recorded.
  - `chummer5.io.save_format`/`legacy_import`: thread `magic_type`/`tradition`/`spell_selection`/
    `power_selection` through `CharacterSave`/`build_character` (mechanical, WP18/WP20 precedent).
  - `chummer5.io.legacy_import`: remove the blanket `if legacy.magic_enabled: reasons.append(...)`
    rejection in `_blocking_reasons`; replace with real support up to this phase's scope, itemizing
    remaining gaps (an unsupported Talent codename, an unresolvable tradition/spell/power name) as
    specific reasons rather than one blanket one. Leaves `has_cyberware`'s rejection untouched —
    that's Phase J's job.
  - `chummer5.io.legacy_chum5`: extend `LegacyCharacter` to parse tradition name, spell names, power
    names+ratings, and MAG total — today only the boolean `magic_enabled` is parsed.
  Depends on: WP25, WP26, WP27.
  Acceptance: unit tests for `drain_resistance` against hand-computed values for both offered
  traditions **and** for the fixed Adept (BOD+WIL) formula; integration test importing Miko and
  Wesson end to end (previously impossible — both currently hit the blanket `magic_enabled`
  rejection) confirming their resolved Magic rating/spells/powers match; a still-rejected case (any
  non-SR5-tradition or non-offered-codename fixture, of which the corpus has several among the 23
  non-mundane fixtures) produces a specific itemized reason, not a crash.

- [x] **WP29 — Magic chargen UI + character sheet.**
  Goal: expose Talent/tradition/spell/power selection through the browser, and show Magic
  rating/spells/powers/Drain on the character sheet.
  Deliverables:
  - `chummer5.web.app`/templates: a Talent-and-tradition screen (mirrors WP14's shape), spell-picker
    and power-picker screens (mirror WP16's quality-picker shape: filtered catalog, running-budget
    display), each gated to appear only when `magic_type` requires it. Decide and document the
    chargen-flow branching this introduces — every screen so far has been unconditionally shown.
  - `_character_sheet_context`: Magic rating, tradition, spells, powers, Drain Resistance, "None
    until committed" like every other section, hidden entirely (not shown as zeroes) for Mundane.
  Depends on: WP25, WP26, WP27, WP28.
  Acceptance: full manual walkthrough — build a Magician matching Miko's choices and an Adept
  matching Wesson's, through the browser end to end, confirming the character sheet matches the
  engine's output for the same inputs; a third walkthrough confirms a Mundane build's flow and
  character sheet are pixel-for-pixel unchanged from before this phase — the real regression risk,
  given WP24 makes Talent selection mandatory for every character, magic or not.

