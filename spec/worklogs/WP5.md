# WP5 — Improvement engine core

Status: complete
Ref: [Implementation Plan.md](../Implementation%20Plan.md) — Phase D, WP5.

## Goal

The base+improvements composition mechanism, proven in isolation: an `Improvement` record shape, an
index for O(1) lookup by `(ImprovementType, target)`, and `resolve()` implementing sum +
`UniqueName` dedup ("highest bonus wins"), validated with synthetic improvements only — no real
rules content (metatype/quality data) touches this yet.

## Log

### 2026-07-17 — Legacy cross-reference

The Project Overview's "Improvement engine design" section already specifies the intended shape in
prose; before implementing, read the actual legacy C# it's based on to get field names and the
exact dedup algorithm right rather than re-deriving them from the prose alone:

- `legacy/Chummer/Backend/Improvements/Improvement.cs`: confirmed the field set the class actually
  carries — `ImprovedName` (target key), `SourceName` (source instance id, e.g. one quality's
  GUID), `Value`, `Rating` (default 1), `UniqueName` (dedup group), `Condition` (a raw string,
  unparsed at this layer), plus two enums: `ImprovementType` (target *kind* — `Attribute`, `Text`,
  `Armor`, ... — a very large enum covering every mechanic the legacy engine supports) and
  `ImprovementSource` (what *granted* it — `Quality`, `Metatype`, `Cyberware`, `Spell`, ... — also
  large). Kept the same two names (`ImprovementType`, `ImprovementSource`) in the new engine so a
  reader jumping to the C# for a rules question isn't translating vocabulary on top of translating
  logic.
- `legacy/Chummer/Backend/Static/Managers/ImprovementManager.cs`'s `MetaValueOfCoreAsync` (the
  implementation behind the public `ValueOf`/`AugmentedValueOf` family, ~465 call sites per the
  Project Overview's performance note): confirmed the actual dedup algorithm, since "highest bonus
  wins" alone doesn't specify the grouping key. It groups by `UniqueName` *within* a given
  `(ImprovementType, ImprovedName)` lookup, takes the highest `Value` per distinct `UniqueName`,
  and adds each group's winner once; Improvements with an empty/no `UniqueName` are never grouped —
  each contributes its own `Value` individually. Also confirmed `Value` is a plain stored field,
  not `Value * Rating` computed at read time — whatever creates an `Improvement` is expected to
  have already folded any rating-dependent math into `Value` before storing it, so `resolve()`
  summing `value` directly (not `value * rating`) matches legacy behavior, not just a simplification
  of it.
  **Not ported:** legacy's `"precedence0"`/`"precedence-1"`/`"precedence1"` magic `UniqueName`
  values, which encode a separate, more elaborate stacking override (used for a handful of
  Essence-loss/cyberzombie mechanics) layered on top of the plain dedup pass. None of MVP's scope
  (metatype/quality/priority bonuses to attributes and skills) uses them; noting this here so a
  future WP that *does* hit one of those mechanics doesn't assume plain `UniqueName` dedup already
  covers it.

### Design decisions

- **No `condition` field.** The Project Overview's design prose lists "an optional condition" as
  part of the shape, and legacy's `Improvement.Condition` exists as a raw string. Left out of this
  WP's dataclass anyway: WP5's own deliverable list (Implementation Plan) doesn't ask for it, and
  per WP3's quality-bonus classification, every MVP-supported quality bonus is unconditional — there
  is no real consumer for a condition predicate anywhere in MVP's scope. Adding it now would be
  exactly the "design for hypothetical future requirements" this project's conventions say to avoid.
  If a later WP needs one, the Project Overview's own guidance already specifies how: compile it to
  a typed predicate once at construction, not a string re-parsed at read time.
- **`ImprovementType`/`ImprovementSource` kept intentionally small, not legacy's full enums.**
  Legacy's `ImprovementType` has 100+ members (`Armor`, `MatrixInitiative`, `SkillsoftAccess`, ...)
  and `ImprovementSource` ~40 (`Cyberware`, `Spell`, `Tradition`, ...) — covering mechanics (magic,
  matrix, cyberware, vehicles) explicitly out of MVP scope. Populated only what the Project Overview
  itself already names: `ImprovementType.ATTRIBUTE`/`SKILL` (its own two examples of composed
  derived values, `attribute.Value`/`skill.Pool`); `ImprovementSource.METATYPE`/`QUALITY`/
  `PRIORITY` (its own list of what MVP's "minimal Improvement mechanism" subset covers: "metatype
  bonuses, quality bonuses, priority-derived bonuses"). Every member traces to an explicit sentence
  already in the spec, not a guess at what WP6-9 will turn out to need — more are added when a
  concrete WP actually introduces a new kind of target or source, per the same "don't design ahead
  of a real consumer" principle as the `condition` decision above.
- **`ImprovementIndex` as a small class, not a bare dict + free function.** The Implementation
  Plan's deliverable phrasing ("index... + `resolve()`") reads dict-and-function-shaped, but the
  Project Overview's design notes talk about the index being "rebuilt on mutation" (`add`/`remove`),
  which implies something stateful holding both the flat list and its derived index together — a
  bare module-level dict has no natural place to hang `add`/`remove_source` methods that keep both
  in sync. A small class is the least-surface-area way to keep "the list is the source of truth,
  the index is a derived cache rebuilt on every mutation" from becoming two things a caller has to
  remember to keep in sync by hand. `remove_source` (not a generic `remove(improvement)`) mirrors
  the Project Overview's own framing directly: "removing the source cleanly removes its
  improvements" — the unit of removal is a source instance
  (`(ImprovementSource, source_id)`), not an individual `Improvement` object.
- **`rating` stored but unused by `resolve()`.** Kept on the dataclass because both the
  Implementation Plan's deliverable list and legacy's field set include it, but confirmed via the
  legacy read above that `resolve()` (== legacy `ValueOf`) never multiplies by it — so this WP
  doesn't invent multiplication semantics nothing has asked for yet. It's metadata a future WP's
  construction logic may read (e.g. "this bonus scaled off a rating-3 source"), not an input to the
  sum.

### Implementation

- `src/chummer5/engine/improvements.py`: `ImprovementType`, `ImprovementSource` (both `Enum`),
  `Improvement` (frozen dataclass: `improvement_type`, `target`, `value`, `source_type`,
  `source_id`, `rating=1`, `unique_name=None`), `ImprovementIndex` (`add`, `remove_source`,
  `resolve`, plus a read-only `improvements` property for introspection/tests).

### Verification

- `uv run python -m pytest -q`: 74 passed (64 pre-existing from WP1-WP4 + 10 new in
  `tests/unit/test_improvements.py`), covering: empty-index resolve, plain stacking (no
  `unique_name`), cross-target/cross-type isolation, `UniqueName` dedup to the highest value,
  stacking combined with a deduped group in the same resolve, two distinct `unique_name` groups
  both contributing independently, `remove_source` removing only its own source's improvements
  (including a same-`source_id`-different-`source_type` case, to prove identity is the pair not
  just the id string), a deduped group falling back to its remaining member after its highest
  source is removed, and a mutate-then-resolve check that the index isn't stale after `add`/
  `remove_source`.
- `uv run python -m ruff check .` / `ruff format --check .`: clean (one line-length wrap needed in
  the module docstring, fixed before the final run).
- `uv run python -m mypy src`: clean, strict mode.
- Environment note (repeat of WP2-WP4's, not a new finding): checkout mounted at
  `/workspaces/chummer5_py`, `.devcontainer/devcontainer.json` pins `workspaceFolder` to
  `/workspace`; used `uv run python -m {pytest,ruff,mypy}` throughout, per the documented
  workaround.

## Files touched

- `src/chummer5/engine/improvements.py` (new)
- `tests/unit/test_improvements.py` (new)
- `spec/worklogs/WP5.md` (new, this file)
- `spec/Implementation Plan.md` (WP5 checkbox ticked)

## Outcome

WP5 complete: `Improvement` + `ImprovementIndex` implement the base+improvements composition
mechanism (sum, plus `UniqueName` "highest bonus wins" dedup scoped per `(ImprovementType,
target)`), proven entirely with synthetic improvements per the acceptance criteria, including a
stacking/dedup case and a source-removal case. No real rules content (metatype/quality/priority
data) depends on this yet — that starts with WP6.
