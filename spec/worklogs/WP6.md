# WP6 — Metatype selection & attribute allocation

Status: complete
Ref: [Implementation Plan.md](../Implementation%20Plan.md) — Phase D, WP6.

## Goal

First real slice of chargen: pick a metatype (from a Heritage priority letter, restricted to
`source == "SR5"` per the MVP content-scope filter), spend attribute points (from an Attributes
priority letter, within metatype min/max), and compose the result with WP5's Improvement engine —
`Attribute.Value = metatype minimum + points spent + Σ improvements`.

## Log

### 2026-07-17 — Legacy cross-reference: two separate attribute-point budgets, not one

Went in expecting a single "Attributes priority letter -> points -> spend across attributes"
budget, per the Implementation Plan's own summary of the deliverable. Reading
`legacy/Chummer/Backend/Attributes/Attribute.Core.cs`'s `Value`/`TotalBase`/`FreeBase` and
`legacy/Chummer/data/priorities.xml` together surfaced a wrinkle the plan text doesn't mention:
**EDG is not funded by the Attributes priority letter at all.** It's funded by a *second*, separate
pool — "special attribute points" — whose size depends on the combination of the Heritage priority
letter *and* the specific metatype chosen (e.g. `priorities.xml`'s Heritage letter D lists
`Human` with `<value>3</value>`, Elf with `<value>0</value>` — same letter, different metatype,
different budget). Confirmed this isn't a guess by cross-checking arithmetic against
`Yeti-#ffffff2.chum5` (the corpus's one `buildmethod == Priority` fixture, Human at Heritage D,
Attributes A): its 8 primary attributes (BOD/AGI/REA/STR/CHA/INT/LOG/WIL) sum to exactly 24 points
spent above metatype minimum, matching `priorities.xml`'s Attributes-A value of 24 exactly; its EDG
is 3 points above metatype minimum (2), matching Human-at-Heritage-D's special-attribute-points
value of 3 exactly, and *not* derived from the 24-point Attributes budget at all. Modeling this as
one merged 27-point pool would have happened to reproduce Yeti's numbers by coincidence (since
Yeti's fixture spends every point of both pools) but would be wrong in general — e.g. it would let
a hypothetical build overspend EDG by underspending a primary attribute, which the real game
doesn't allow. `PRIMARY_ATTRIBUTES` (Attributes-priority-funded) and `SPECIAL_ATTRIBUTES` (funded by
`HeritageMetatypeOption.special_attribute_points`) are validated as two independent budgets in
`create_character()` because of this.

`MAG`/`RES` are the legacy engine's other two special attributes (same pool as EDG), left out of
`SPECIAL_ATTRIBUTES` entirely rather than modeled as an always-zero option — mundane MVP characters
never buy them (Talent forced to E, "Mundane", per the Project Overview), so there's no real
consumer for them yet; a magic/resonance follow-up WP would need to actually validate the "spend
across EDG *and* MAG/RES from the same pool" interaction that MVP doesn't exercise.

**`<totalvalue>` is the *augmented* value, not the plain `metatype minimum + points spent`
number.** Discovered while trying to cross-validate the formula against the other 10 (SumToTen-built)
mundane fixtures: `metatype_min + base + karma` matched `<totalvalue>` exactly for only 3 of the 10
(`Rez0luti0n2.0`, `Serpent`, and — already known — `Yeti`); the rest had mismatches as large as +6
(e.g. `Barrett`'s INT: min 1 + base 5 = 6, but `<totalvalue>` says 7). Traced this to
`Attribute.Core.cs`'s `TotalValue` vs. `Value`: `TotalValue` (`CalculatedTotalValue`, what the save
file actually stores) folds in cyberware/gear augmentation; `Value` (the unaugmented figure this
WP's formula actually reproduces) is never itself written to the save file — there is no field to
diff the unaugmented formula against for an attribute a character has cybered up. This isn't a bug
in either the fixture or this WP's formula, just a corpus limitation worth flagging so a future
reader doesn't assume every fixture attribute is fair game: `tests/integration/test_character_fixtures.py`'s
cross-corpus test computes the natural value independently and only asserts where it happens to
equal `<totalvalue>` (i.e., where nothing augments that attribute), skipping the rest with a
comment rather than either asserting a wrong number or silently testing nothing.

**Metavariants (Gnome/Minotaur/Cyclops among the mundane corpus) really do need excluding, not just
as a documentation note.** 3 of the 11 mundane fixtures (`Rez0luti0n2.0`/Gnome, `Gentle
Earthquake`/Minotaur, `Monomax (approved) 3`/Cyclops) have a `<metavariant>`. Checked concretely
that their recorded `metatypemin`/`metatypemax` differ substantially from the base metatype's own
range in `metatypes.xml` (e.g. Dwarf's own AGI range is 1-6; Rez0luti0n2.0/Gnome's saved
`metatypeaugmax` etc. reflect Gnome's own, different range) — so cross-checking these three against
the base `Dwarf`/`Troll` entries from `sr5_metatypes()` would silently compare against the wrong
numbers, not just "less precise" ones. The cross-corpus fixture test explicitly skips any fixture
with a non-`None` `metavariant`, per the Project Overview's "metavariants are out of MVP scope"
rule, already established in WP2.

### Design decisions

- **`sr5_metatypes()`/`metatype_choices()` do the SR5-scope filtering WP2 deliberately deferred.**
  WP2's `load_metatypes()` returns every book's metatypes unfiltered, `source` field intact, by
  design (see `spec/worklogs/WP2.md`) — this WP is the first consumer that offers metatypes as a
  player choice, so it's the one that applies the filter. `priorities.xml`'s Heritage metatype
  lists include every book's metatypes too (checked Heritage A's list: `A.I.`, `Centaur`, `Naga`,
  `Sasquatch`, every `Shapeshifter: *` variant, alongside the 5 core types) — `metatype_choices()`
  cross-references by name against the SR5-filtered catalog and silently drops anything with no
  match, the same "excluded, not erroring" pattern WP3 already established for the quality catalog.
- **`MetatypeChoice` as its own dataclass, not reusing `Metatype`.** `special_attribute_points`/
  `karma` are a property of *this Heritage letter's* offer of a metatype, not of the metatype
  itself — the same metatype has a different special-attribute-points budget at a different
  Heritage letter (Human: 9/7/5/3/1 points at A/B/C/D/E respectively). Folding these onto `Metatype`
  would be wrong (they're not an intrinsic metatype property) and would also require `Metatype` to
  know about `PriorityTable`, inverting WP2's data-layer/engine-layer separation.
  - **No metavariant selection modeled at all.** Per the Project Overview, metavariants are out of
  MVP scope entirely (every metavariant is non-`SR5`-sourced) — `MetatypeChoice`/`Character` only
  ever carry a base `Metatype`, never a `Metavariant`, so there's no half-built metavariant field
  to leave dangling until a later WP actually needs one.
- **Budget validation doesn't require full spend.** `create_character()` rejects spending *more*
  than either budget but allows spending less — SR5 doesn't require every priority point to be
  spent on attributes, and treating "must spend everything" as an engine invariant would be
  inventing a rule nothing in the source data or legacy code asks for (a UI nudge belongs in the
  UI, not baked into the domain model).
- **`Character.improvements` is a real, live `ImprovementIndex`, exercised by nothing yet.** No
  metatype- or priority-derived `Improvement` actually gets constructed in this WP: checked all 5
  core metatypes' `<bonus>` nodes in `metatypes.xml` and confirmed none of them (Human/Elf/Ork:
  empty; Dwarf: `lifestylecost`; Troll: `armor`/`reach`/`lifestylecost`) grant an attribute effect,
  so there is genuinely nothing to wire up yet. Still threaded the field through from the start
  (per the Project Overview's `Attribute.Value` formula already naming a Σ-improvements term) so
  WP8's quality bonuses have a place to land without reshaping `Character` later — `resolve()` on an
  empty index is just 0, so this costs nothing now.
- **`attribute_points` keyed by attribute code, not split into separate primary/special dict
  fields on `Character`.** The *budgets* are two different pools (validated separately in
  `create_character`), but once a `Character` is built, "how many points did this attribute get and
  from where" collapses to one number per code — nothing downstream (WP7 dice pools, WP10 derived
  stats) cares which pool a point came from, so the finished aggregate doesn't carry that
  distinction either.

### Implementation

- `src/chummer5/engine/character.py`: `CORE_RULEBOOK_SOURCE`, `PRIMARY_ATTRIBUTES`,
  `SPECIAL_ATTRIBUTES`, `ALLOCATABLE_ATTRIBUTES`; `sr5_metatypes()`; `MetatypeChoice` +
  `metatype_choices()`; `Character` (frozen dataclass: `metatype`, `heritage_letter`,
  `attributes_letter`, `special_attribute_points`, `attribute_points`, `improvements`) with
  `attribute_range()`/`attribute_value()`; `create_character()` (budget + range validation,
  raises `ValueError` with a specific message per failure kind).

### Verification

- `uv run python -m pytest -q`: 90 passed (74 pre-existing from WP1-WP5 + 16 new in
  `tests/unit/test_character.py` covering `sr5_metatypes`/`metatype_choices` filtering, both budget
  checks (over- and under-spend), metatype-maximum clamping, negative/unallocatable-attribute
  rejection, and Improvement-engine composition on top of points spent — including a case where an
  improvement pushes past what points alone would reach but the metatype maximum still clamps it +
  1 new pair of fixture-driven tests in `tests/integration/test_character_fixtures.py`: the full
  priority-build path against `Yeti-#ffffff2.chum5` (all 9 allocatable attributes), and a
  build-method-agnostic cross-corpus check (skips the 3 metavariant fixtures and, per-attribute,
  any attribute augmented by out-of-scope cyberware/gear — asserts at least one (fixture, attribute)
  pair actually got checked, so the skip logic can't silently degrade into a no-op test).
- `uv run python -m ruff check .` / `ruff format --check .`: clean (one import-order fix via
  `ruff check --fix` during development).
- `uv run python -m mypy src`: clean, strict mode.
- Environment note (repeat of WP2-WP5's, not a new finding): checkout mounted at
  `/workspaces/chummer5_py`, `.devcontainer/devcontainer.json` pins `workspaceFolder` to
  `/workspace`; used `uv run python -m {pytest,ruff,mypy}` throughout, per the documented
  workaround.
- Rulebook PDF not consulted this WP — the legacy C# (`Attribute.Core.cs`,
  `SelectMetatypePriority.cs`) plus `priorities.xml`/`metatypes.xml` and the `Yeti-#ffffff2.chum5`
  fixture were sufficient to pin down the exact formula and the two-budget split; no rules question
  remained that only the rulebook text itself could resolve.

## Files touched

- `src/chummer5/engine/character.py` (new)
- `tests/unit/test_character.py` (new)
- `tests/integration/test_character_fixtures.py` (new)
- `spec/worklogs/WP6.md` (new, this file)
- `spec/Implementation Plan.md` (WP6 checkbox ticked)

## Outcome

WP6 complete: `sr5_metatypes()`/`metatype_choices()` select a metatype from a Heritage priority
letter, restricted to `source == "SR5"`; `create_character()` allocates attribute points from two
independently-validated budgets (Attributes-priority points for the 8 primary attributes,
Heritage-priority-and-metatype-dependent special-attribute points for EDG) within metatype
min/max; `Character.attribute_value()` implements `metatype minimum + points spent + Σ
improvements`, composed with WP5's `ImprovementIndex` (unexercised by real data yet, but ready for
WP8). Validated against `Yeti-#ffffff2.chum5` (the full priority-allocation path) and, for the
value formula alone, against every unaugmented attribute across the rest of the mundane corpus.
