# WP7 — Skill allocation & dice pools

Status: complete
Ref: [Implementation Plan.md](../Implementation%20Plan.md) — Phase D, WP7.

## Goal

Active skills, groups, and specializations: a Skills-priority-letter point budget (points and skill
groups, separately), and the dice pool formula (attribute + rating, +2 for a specialization).

## Log

### 2026-07-17 — Legacy cross-reference: skill groups override, they don't add

Read `legacy/Chummer/Backend/Skills/Skill.cs` (`Base`, `LearnedRating`, `TotalBaseRating`, `Rating`,
`RatingMaximum`, `PoolOtherAttribute`, `DefaultModifier`, `GetSpecializationBonus`) and
`SkillGroup.cs` (`Base`) directly, since — unlike WP6's attribute formula, which the Project
Overview already states explicitly — the Implementation Plan's one-line WP7 summary ("Skills-priority-letter
→ point pools; dice pool = attribute + rating (+2 specialization)") doesn't spell out how individual
skill points and skill group points interact.

**Finding: `Skill.Base` returns the *group's* rating, not `group + own points`, whenever the group
has any points spent, gated by `CharacterSettings.StrictSkillGroupsInCreateMode` (field default
`false` in `CharacterSettings.cs`, but this repo has no checked-in settings preset overriding it —
see the aside below). This is the SR5 core rule that buying a skill group at rating N sets every
member skill to rating N as one purchase; buying an individual member skill on top of an already-
bought group ("breaking" the group) is a *different*, karma-only action outside MVP's priority-build
scope.** Confirmed against `Yeti-#ffffff2.chum5` (the corpus's one `buildmethod == Priority`
fixture, reused here for the same reason WP6 reused it for attributes — skill allocation doesn't
depend on the Talent/magic path either): Yeti's `<groups>` has `Firearms` and `Stealth` both at
`base = 1`; cross-referencing every one of Yeti's 62 skill entries against `skills.xml`, every skill
belonging to `Firearms` or `Stealth` has its *own* `base = 0`, and every skill with nonzero own
`base` (Compiling/Registering → `Tasking`, Cybercombat/Electronic Warfare/Hacking → `Cracking`,
Computer/Software → `Electronics`) belongs to a group that is itself unbought (`base = 0` for
`Tasking`/`Cracking`/`Electronics` in `<groups>`). No fixture entry exercises the "broken group"
case, which fits: Yeti is a `buildmethod == Priority` build, and breaking a group requires spending
karma the priority-build math already accounts for separately. `create_skill_allocation` turns this
into a construction-time rule — a `skill_points` entry for a skill whose group also has
`group_points` spent raises `ValueError` — rather than silently letting one side win, mirroring
WP6's "never partially/silently apply" precedent (also WP3's for quality bonuses).

**Aside — `StrictSkillGroupsInCreateMode`/`UsePointsOnBrokenGroups` defaults.** Both fields default
to `false` at the C# field-declaration site (`CharacterSettings.cs`), which read backwards from what
the corpus shows (`false` would mean *no* override, i.e. individual points stack on top of a bought
group — the opposite of what Yeti's data demonstrates). Searched the whole repo for any checked-in
settings preset (`*.xml`) that sets `strictskillgroupsincreatemode`/`usepointsonbrokengroups` and
found none — the shipped default preset that actually governs a fresh character (loaded from
`CharacterSettings.LoadFromXml`'s caller chain, not from a file in this repo) isn't present in the
checkout. Since the fixture data itself is unambiguous (real legacy-computed output, not a setting
this repo can misread), WP7 takes the *data* as ground truth over the field declaration and
implements the "override" behavior — flagging the discrepancy here rather than silently trusting a
possibly-misleading C# default that this repo can't actually trace to a shipped preset.

**Finding: chargen-time rating cap is 6, not the post-creation 12.** `Skill.RatingMaximum` branches
on `CharacterObject.Created`: `CharacterSettings.MaxSkillRatingCreate` (field default `6`) applies
until creation is finished, `MaxSkillRating` (default `12`) after. MVP only ever builds freshly-
created characters, so `MAX_SKILL_RATING_CREATE = 6` is the only cap modeled — this matches SR5's
core rulebook "no skill above rating 6 during character creation" rule directly, so unlike the
`StrictSkillGroups` aside above, there was no ambiguity to resolve here.

**Finding: specialization bonus is `CharacterSettings.SpecializationBonus => 2`, gated on
`TotalBaseRating != 0` and `!IsExoticSkill`.** Read `SkillSpecialization.cs`'s `SpecializationBonus`
getter directly; the `2` is a `static` property, not data-driven, so there's no XML value to
cross-check — the Implementation Plan's own "+2 specialization" phrasing already named the number,
this just confirms where it comes from and its two gates (`skill_rating(...) > 0`, `not
skill.exotic`) in the legacy source rather than assuming them.

**Finding: untrained ("defaulting") skill use applies a flat -1, from
`Skill.DefaultModifier`'s unconditional fallthrough (`return -1`), gated on `Skill.Default` (this
project's `can_default`, already loaded by WP3).** The several `ImprovementType`-driven ways
`DefaultModifier` can be zeroed out (Reflex Recorder, `RemoveSkillDefaultPenalty`, ...) are all out
of MVP scope (no cyberware, no such Improvement type modeled) — `DEFAULT_MODIFIER = -1` is applied
unconditionally whenever `can_default` and rating `== 0`.

**Finding: no `.chum5` field stores a skill's computed dice pool.** Checked a full `<skill>` element
from Yeti's save — `guid`/`suid`/`isknowledge`/`skillcategory`/`karma`/`base`/`notes`/
`buywithkarma`, nothing pool-shaped. Unlike attributes (`<totalvalue>`), there's no legacy-computed
ground truth to diff the `dice_pool()` formula against directly. `test_yeti_skill_allocation_matches_engine_end_to_end`
therefore only validates allocation/rating (budgets, group-override behavior) against the corpus;
the dice pool formula itself (attribute + rating + specialization + defaulting) is covered by
synthetic tests in `tests/unit/test_skill_allocation.py`, the same "prove the formula in isolation"
approach WP5 used for the Improvement engine core.

**Karma-bought skill points are out of scope, mirroring WP6's precedent for attributes.** Two of
Yeti's skills (Compiling, Computer) have nonzero `<karma>` alongside `<base>` — `LearnedRating =
Karma + Base` in the legacy source, but `create_skill_allocation`/`skill_rating` only ever consume
`<base>` (the priority-budget-funded points). WP6 has the same gap for attributes (never modeled
karma-bought points beyond the priority budget) but didn't flag it explicitly in its worklog; this
one does, so a future reader doesn't have to rediscover it independently for skills. Costs nothing
in test coverage here since (per the point above) there's no computed-pool ground truth to check a
karma-inclusive rating against anyway.

### Design decisions

- **`SkillAllocation.skill_points` is keyed by `Skill.id`; `group_points` is keyed by skill group
  name.** Mirrors WP4's own choice for `LegacySkillGroup` (skill groups have no id in `skills.xml`,
  only a name) and keeps the corpus cross-reference direct: `LegacySkill.suid` joins straight to
  `Skill.id`, `LegacySkillGroup.name` joins straight to `Skill.skill_group`.
- **Improvement lookups use `skill.name`, not `skill.id`, as the target key** — a deliberate
  asymmetry from the point above, not an inconsistency. WP3's `FlatBonus.target_name` (the field a
  future WP8 quality bonus would carry into an `Improvement.target`) is a plain skill *name* string
  (e.g. Natural Athlete's bonus names "Running"/"Swimming" by name, not id) — `skill_rating()`
  resolves `ImprovementType.SKILL` against `skill.name` specifically so a WP8-constructed
  Improvement lands on the right skill without WP8 having to know this module's internal id
  convention. Verified there's no motivating same-name collision risk: skill names are unique across
  the 76-entry active-skill catalog (exotic skills share a generic catalog name across per-instance
  purchases, but MVP doesn't model per-instance exotic skill selection at all yet, so this doesn't
  bite here).
- **`create_skill_allocation` takes the full `skills` catalog, not just budget numbers**, so it can
  validate skill ids/group names and enforce the strict-group rule itself — same shape as WP6's
  `create_character`, which takes `metatype_choice` (not just a budget int) for the same reason
  (needs the metatype's own attribute ranges to validate against).
- **`dice_pool`'s `specialized` parameter is a bare `bool`, not a tracked field on
  `SkillAllocation`.** WP7's scope (per the Implementation Plan) is the point budget and the pool
  formula, not the *cost* of buying a specialization (a real SR5 rule — 1 point or karma per
  specialization — that the Plan text doesn't mention for this WP and isn't validated against any
  corpus ground truth here either). Keeping specialization state out of `SkillAllocation` avoids
  half-modeling a cost rule this WP was never asked to implement; `dice_pool()` stays a pure function
  of "would this test be specialized," which is all a caller (a future WP9/WP10/UI) needs.
- **No `Character` field added for skills.** Followed the same modular pattern WP3 established for
  data loaders (`skills.py`/`qualities.py` sit alongside `metatypes.py`/`priorities.py`, not folded
  into one big loader) and that the Implementation Plan's own WP8/WP9 phrasing implies (their
  deliverables are also standalone `engine/*.py` modules, not edits to `Character`): `skills.py`
  reads a `Character` (for `attribute_value`/`improvements`) but doesn't write into it. WP10
  ("Derived stats + full end-to-end regression") is where the Implementation Plan already schedules
  wiring every engine module into one finished-character build, so `Character` doesn't need a
  half-populated `skills` field sitting unused until then.

### Implementation

- `src/chummer5/engine/skills.py` (new): `MAX_SKILL_RATING_CREATE` (6), `SPECIALIZATION_BONUS` (2),
  `DEFAULT_MODIFIER` (-1); `SkillPointBudget` + `skill_point_budget()`; `SkillAllocation` +
  `create_skill_allocation()` (id/name/negative/cap/strict-group/budget validation, mirroring WP6's
  `create_character` validation style); `skill_rating()` (group-override-or-own-points + Σ
  improvements, capped); `dice_pool()` (rating + attribute, +2 specialization, or -1 defaulting, or
  0).

### Verification

- `uv run python -m pytest -q`: 109 passed (90 pre-existing from WP1-WP6 + 18 new in
  `tests/unit/test_skill_allocation.py` covering budget validation (within/over budget for both
  pools, partial spend, negative spend, over-cap, unknown skill id, unknown group name, the
  strict-group conflict rule), `skill_rating()`'s group-override-vs-own-points behavior and its
  Improvement-sum-and-cap composition, and `dice_pool()`'s formula (plain rating+attribute,
  specialization bonus gated on positive rating, specialization ignored for exotic skills, the -1
  defaulting penalty when allowed, 0 when not) + 1 new fixture-driven test in
  `tests/integration/test_character_fixtures.py`: `test_yeti_skill_allocation_matches_engine_end_to_end`,
  validating the full Skills-priority-letter allocation path against Yeti's recorded skill/group
  base points (budget respected, group spend matches exactly, group-override and own-points
  `skill_rating()` resolution both checked against a real skill from each case).
- `uv run python -m ruff check .` / `ruff format --check .`: clean.
- `uv run python -m mypy src`: clean, strict mode.
- Environment note (repeat of WP2-WP6's, not a new finding): checkout mounted at
  `/workspaces/chummer5_py`, `.devcontainer/devcontainer.json` pins `workspaceFolder` to
  `/workspace`; used `uv run python -m {pytest,ruff,mypy}` throughout, per the documented
  workaround.
- Rulebook PDF not consulted this WP (repeat of WP6's note) — the legacy C# (`Skill.cs`,
  `SkillGroup.cs`, `SkillSpecialization.cs`) plus `priorities.xml`/`skills.xml` and the
  `Yeti-#ffffff2.chum5` fixture were sufficient to pin down every formula and the group-override
  rule; no rules question remained that only the rulebook text itself could resolve. No new
  `spec/rulebooks/*.md` learnings file created as a result (none existed before this WP either — see
  WP6's equivalent note).

## Files touched

- `src/chummer5/engine/skills.py` (new)
- `tests/unit/test_skill_allocation.py` (new)
- `tests/integration/test_character_fixtures.py` (extended: skill-allocation Yeti test)
- `spec/worklogs/WP7.md` (new, this file)
- `spec/Implementation Plan.md` (WP7 checkbox ticked)

## Outcome

WP7 complete: `skill_point_budget()` reads a Skills-priority-letter's two point pools (individual
skills, skill groups) from `priorities.xml`; `create_skill_allocation()` validates a spend against
both budgets plus SR5's chargen rating cap (6) and the "strict skill groups" rule (a bought group's
rating overrides its member skills' own points, and the two can't both carry points for the same
skill); `skill_rating()` resolves that precedence plus Σ Improvements; `dice_pool()` implements
attribute + rating (+2 specialization, gated on positive rating and non-exotic; or a flat -1
"defaulting" penalty at rating 0 for skills that allow it). Validated against
`Yeti-#ffffff2.chum5`'s full priority-built skill allocation (budgets, group-vs-individual
resolution) and, for the dice pool formula itself — which no `.chum5` fixture stores a computed
value for — via synthetic unit tests, the same pattern WP5 established for the Improvement engine.
