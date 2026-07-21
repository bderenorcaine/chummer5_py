# Implementation Plan

Companion to [Project Overview.md](Project%20Overview.md). This is the execution roadmap: a sequence of
work packages (WPs) from an empty `src/` to a headless MVP, then to the FastAPI/HTMX UI for that MVP.

## How to use this plan

- Each WP is scoped for **one agent conversation** and ends in **one git commit** referencing its number
  (e.g. `WP6: metatype selection and attribute allocation`).
- A WP's entry here, plus `Project Overview.md`, should be enough context for a fresh conversation to
  execute it cold — no dependency on any particular prior conversation's memory.
- A WP is done when: its acceptance criteria pass, `pytest` is green repo-wide, and the checkbox below is
  ticked (as part of that WP's commit).
- Don't start a WP mid-conversation if there isn't realistically enough context budget left to finish it
  cleanly — hand off to a fresh conversation instead of producing a rushed or half-finished package.

## Notes that shape the plan below

**The legacy `.chum5` test corpus is a weaker regression oracle than "34 golden files" suggests.** Of the
34 fixtures in `legacy/Chummer.Tests/TestFiles/`, only **11 are mundane** (no magic/resonance), and of
those, only **one** (`Yeti-#ffffff2.chum5`) uses `buildmethod = Priority` — the other 33 use `SumtoTen`,
a different chargen method that's out of MVP scope. Resolution: the 11 mundane fixtures (any build method)
validate **build-method-agnostic** formulas (attribute totals, skill dice pools, derived stats) — those
values are legacy-computed truth regardless of how the points were bought. Only `Yeti-#ffffff2.chum5`,
plus a handful of hand-authored cases checked directly against `priorities.xml`, validate the
**priority-table allocation logic** itself.

**MVP content scope = the SR5 core rulebook, checked via each data file's `<source>` tag.**
Discovered during WP2: legacy data files span many sourcebooks, and almost every entry (metatype,
metavariant, quality, skill, ...) carries a `<source>` tag identifying which one. MVP restricts to
`source == "SR5"` uniformly — this is what "mundane... core-rulebook math" in the Project Overview
concretely means at the data layer, not just a metatype-specific rule. Verified counts:
`metatypes.xml` → 5 of 21 (`Metahuman` category base types: Human, Elf, Dwarf, Ork, Troll; this
also excludes every metavariant, since all of them are non-`SR5`-sourced); `qualities.xml` → 96 of
803; `skills.xml` → 76 of 76 (no filtering needed, already all core). Any WP whose loader offers a
list of choices to the player (metatypes, qualities, and by extension gear/priorities content
later) needs this filter; see the SR5-scope clauses added to WP3 and WP6 below.

**Quality `<bonus>` nodes are a mini-language, not a single field.** `qualities.xml` bonus nodes range
from trivial (`<ambidextrous/>`) to nested value-bearing tags, mirroring the general Improvement bonus
grammar the legacy engine parses. MVP does not implement that general parser — WP3/WP8 curate a small
supported subset (flat attribute/skill bonuses) and exclude qualities using anything else from the
MVP-offered quality list, rather than silently ignoring their mechanical effect. WP22 (Phase H) widens
this subset with a precisely-verified list of what else is safely offerable and what still isn't.

**Post-MVP scoping (Phase G/H below) surfaced two hidden dependencies worth knowing before touching
either area.** Cyberware needs real Essence tracking as a prerequisite — today a hardcoded constant
(`chummer5.engine.derived.BASE_ESSENCE`) — not just new catalog content; adept magic needs unwinding
"Talent forced to E" across the web/session layers, not just engine data. Full detail in Project
Overview's Open Questions section (dated 2026-07-18 entries) and in Phase H's own intro below. Neither
blocks any WP currently on this list, which deliberately steers around both areas.

## Repo/package layout (established in WP1)

```
chummer5_py/
  legacy/            (unchanged)
  spec/
  pyproject.toml     (uv-managed)
  src/chummer5/
    data/            # loaders: legacy XML -> frozen dataclasses
    engine/          # domain model + Improvement engine (headless, no I/O)
    io/              # native save format + legacy .chum5 import
    web/             # FastAPI app, Jinja2 templates, static (incl. vendored HTMX)
  tests/
    fixtures/        # curated .chum5 subset + expected-value helpers
    unit/
    integration/
```

Toolchain defaults, set once in WP1 and not re-litigated per package: `uv` for packaging, `pytest` for
tests, `ruff` + `mypy` for lint/type feedback, plain `dataclasses` for the domain model (no pydantic
dependency in the engine — FastAPI's own pydantic use in the web layer is separate).

## Work packages

### Phase A — Foundation

- [x] **WP1 — Project scaffolding.**
  Goal: a buildable, empty Python project, developed inside a container rather than on the host.
  Deliverables: `.devcontainer/Containerfile` + `devcontainer.json` (Podman-backed; reopening the
  workspace in it relocates the VS Code extension host, including agent sessions, into the container —
  see `Project Overview.md`'s Development environment note for why, given the host is an immutable OS);
  root `.dockerignore` (excludes `legacy/` and `.git/` from build context); `pyproject.toml` (uv-managed),
  `src/chummer5/{data,engine,io,web}/` packages (empty `__init__.py`s), pytest + ruff + mypy configured,
  one smoke test.
  Depends on: nothing.
  Acceptance: `uv run pytest`, `uv run ruff check`, and `uv run mypy src` all pass **inside the
  container**. Verified via a one-off `podman run` mounting the workspace (no host Python/package
  mutation involved) — future work packages should instead develop via "Reopen in Container".

### Phase B — Static rules data

- [x] **WP2 — Metatype & priority data loader.**
  Goal: load metatype and priority-table rules data as typed Python structures.
  Deliverables: `src/chummer5/data/metatypes.py` parsing `legacy/Chummer/data/metatypes.xml` (attribute
  min/max/aug per metatype + metavariants) into frozen dataclasses; `src/chummer5/data/priorities.py`
  parsing `legacy/Chummer/data/priorities.xml`, **Standard table only** (Heritage/Attributes/Skills/
  Resources categories; Talent category loaded but MVP only consumes its "E - mundane" entry).
  Depends on: WP1.
  Acceptance: unit tests assert known hand-checked values (e.g. Human attribute ranges from
  `metatypes.xml`; priority-A Heritage karma/value table from `priorities.xml`).

- [x] **WP3 — Quality & skill data loader.**
  Goal: load quality and skill rules data.
  Deliverables: `src/chummer5/data/qualities.py` parsing `legacy/Chummer/data/qualities.xml` (id, name,
  category, karma cost, limit, raw bonus node); `src/chummer5/data/skills.py` parsing skill definitions
  (name, linked attribute, category/group). Restrict the loaded/offered quality catalog to
  `source == "SR5"` (96 of 803 entries — see "MVP content scope" note above) before applying the
  bonus-node classification below; `skills.xml`'s 76 entries are already all `source == "SR5"`, so
  no equivalent filtering is needed there. Classify each in-scope quality's bonus node as
  "MVP-supported" (flat attribute/skill bonus) or "not yet supported" — this classification is what
  WP8 filters on.
  Depends on: WP1.
  Acceptance: unit tests cover at least one supported and one unsupported bonus-node shape; loader
  reports counts of each so the split is visible.

### Phase C — Regression fixture harness

- [x] **WP4 — Legacy `.chum5` fixture parser & golden corpus.**
  Goal: turn legacy save files into comparable ground truth.
  Deliverables: `src/chummer5/io/legacy_chum5.py` (or `tests/fixtures/` helper) extracting MVP-relevant
  fields (metatype, priority selections, attributes, skills, qualities, karma, nuyen) from a `.chum5`
  file. Curate the fixture set per the corpus note above: copy/reference all 11 mundane fixtures from
  `legacy/Chummer.Tests/TestFiles/` for derived-stat comparisons, flag `Yeti-#ffffff2.chum5` specifically
  for priority-allocation comparisons. Document the split in `tests/fixtures/README.md`.
  Depends on: WP1.
  Acceptance: parser round-trips known raw fields for all 11 curated fixtures; `tests/fixtures/README.md`
  lists which fixture backs which kind of assertion.

### Phase D — Core engine (headless)

- [x] **WP5 — Improvement engine core.**
  Goal: the base+improvements composition mechanism, proven in isolation.
  Deliverables: `src/chummer5/engine/improvements.py` — `Improvement` dataclass (source type/id, target,
  value, rating, unique-name dedup group) + index (`dict[(type, target)] -> list[Improvement]`) +
  `resolve()` implementing sum + `UniqueName` dedup ("highest bonus wins").
  Depends on: WP1.
  Acceptance: unit tests using **synthetic** improvements only (no XML involved) — proves the resolution
  math before any real rules content touches it, including a stacking/dedup case.

- [x] **WP6 — Metatype selection & attribute allocation.**
  Goal: first real slice of chargen — pick a metatype, spend attribute points.
  Deliverables: `src/chummer5/engine/character.py` (`Character` aggregate, mundane fields only);
  metatype selection from a Heritage priority letter (via WP2 data), restricted to `metatypes.xml`
  entries with `source == "SR5"` (Human/Elf/Dwarf/Ork/Troll base types only — metavariants and
  non-core metatypes like Centaur/Sasquatch/A.I./Shapeshifters are excluded from MVP; see "MVP
  content scope" note above) when cross-referencing against a Heritage priority's metatype list;
  attribute point allocation from an Attributes priority letter within metatype min/max;
  `Attribute.Value = metatype minimum + points spent + Σ improvements` (via WP5).
  Depends on: WP2, WP5.
  Acceptance: tests against WP4's mundane fixture set (attribute totals) and specifically against
  `Yeti-#ffffff2.chum5` (allocation budget/spend logic).

- [x] **WP7 — Skill allocation & dice pools.**
  Goal: active skills, groups, specializations, and the dice pool formula.
  Deliverables: `src/chummer5/engine/skills.py` — Skills-priority-letter → point pools; dice pool =
  attribute + rating (+2 specialization).
  Depends on: WP3, WP6.
  Acceptance: tests against the fixture corpus.

- [x] **WP8 — Quality selection & minimal Improvement bonuses.**
  Goal: qualities affect karma and, for the supported subset, feed the Improvement engine.
  Deliverables: `src/chummer5/engine/qualities.py` — positive/negative quality picking, karma cost,
  negative-quality karma cap; only WP3's "MVP-supported" qualities produce `Improvement` records.
  Depends on: WP3, WP5, WP6.
  Acceptance: tests against fixtures restricted to MVP-supported qualities; an explicit test that an
  unsupported-bonus quality is excluded from the offered list rather than silently mis-applied.

- [x] **WP9 — Contacts & starting resources.**
  Goal: nuyen, contacts, and a minimal starting-gear stub.
  Deliverables: `src/chummer5/engine/resources.py` — Resources-priority-letter → starting nuyen;
  contacts (connection/loyalty, karma cost beyond free points); a deliberately minimal starter-gear
  purchase (flat nuyen deduction against a small curated list — explicitly not the full gear catalog).
  Depends on: WP6.
  Acceptance: tests against fixtures for nuyen/contact math.

- [x] **WP10 — Derived stats + full end-to-end regression. (Headless MVP milestone)**
  Goal: a complete, validated mundane priority-built character, computed headlessly end to end.
  Deliverables: `src/chummer5/engine/derived.py` — initiative, physical/mental/social limits, condition
  monitor boxes as pure functions of finalized attributes. Add the full-character regression test.
  Depends on: WP6, WP7, WP8, WP9.
  Acceptance: for every curated fixture, build the character end-to-end through the engine and diff every
  MVP-covered field against the legacy-computed values. **Headless MVP is complete when this passes.**

### Phase E — Save/load

- [x] **WP11 — Native save format.**
  Goal: persist and reload a character in the project's own format.
  Deliverables: `src/chummer5/io/save_format.py` — JSON format mirroring the domain model.
  Depends on: WP10.
  Acceptance: round-trip tests (build → save → load → equal).

- [x] **WP12 — Legacy `.chum5` import.**
  Goal: bring a real legacy character into the new engine, for MVP-covered content only.
  Deliverables: extends WP4's parser into a real import path for mundane, priority-built,
  MVP-feature-only legacy saves.
  Depends on: WP4, WP10.
  Acceptance: successfully imports `Yeti-#ffffff2.chum5`; imports of saves with out-of-scope content
  (magic, cyberware, etc.) fail with a specific, itemized error rather than silently dropping data.

### Phase F — FastAPI/HTMX UI

- [x] **WP13 — Web app skeleton.**
  Goal: the UI stack runs end to end, doing nothing yet.
  Deliverables: `src/chummer5/web/app.py` (FastAPI app factory), Jinja2 base layout, HTMX vendored
  locally (not CDN-loaded, to keep the app fully offline/local-first), `uvicorn` dev-run instructions,
  one trivial page.
  Depends on: WP1.
  Acceptance: `uvicorn chummer5.web.app:app` serves the trivial page; an HTMX-driven interaction on that
  page round-trips through the server.

- [x] **WP14 — Priority & metatype selection UI.**
  Goal: first real chargen screen.
  Deliverables: assign priority letters to the 4 MVP categories (Talent forced to E, not offered as a
  choice) and pick a metatype; server-side in-memory character-in-progress state keyed by a session
  cookie.
  Depends on: WP6, WP13.
  Acceptance: manual walkthrough creates a metatype+priority selection that matches what WP6's engine
  would produce for the same inputs.

- [x] **WP15 — Attribute & skill allocation UI.**
  Goal: spend attribute/skill points through the browser.
  Deliverables: point-spend forms with HTMX-driven live remaining-points and dice-pool preview.
  Depends on: WP7, WP14.
  Acceptance: manual walkthrough; values match engine output for the same inputs.

- [x] **WP16 — Qualities, contacts & resources UI.**
  Goal: round out chargen inputs.
  Deliverables: quality picker (MVP-supported catalog only), contacts editor, nuyen spend screen.
  Depends on: WP8, WP9, WP15.
  Acceptance: manual walkthrough; values match engine output for the same inputs.

- [x] **WP17 — Character sheet + save/load UI. (UI MVP milestone)**
  Goal: finish and persist a character through the browser, start to finish.
  Deliverables: read-only finished-character view (derived stats), save/download (native format via
  WP11), load/upload (native format + legacy `.chum5` import via WP12).
  Depends on: WP10, WP11, WP12, WP16.
  Acceptance: full manual walkthrough — create a mundane priority character in the browser end to end,
  save it, reload it, and (separately) import `Yeti-#ffffff2.chum5` — all producing correct values.
  **UI MVP is complete when this passes.**

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

- [ ] **WP35 — Cross-phase: Essence-driven Magic-rating loss.**
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

### Phase K — Post-MVP: Cyberware modifications (Capacity, subsystems, conditional bonuses)

**On hold, deliberately, as of 2026-07-21 — scoped now, started later.** Raised by a user question
after WP33 shipped: cyberlimbs, cybereyes, and cyberears can be upgraded with plugin-type subitems
in real SR5 (e.g. a cybereye taking a "Vision Enhancement" plugin), a mechanic WP31/32/33
deliberately excluded (both modules' own docstrings flag nested `<children>`/rating-scaled items as
out of scope, and `tests/integration/test_cyberware_fixtures.py` documents "top-level only" as a
considered choice, not an oversight). This phase is that mechanic, scoped and researched ahead of
time so a future conversation can pick it up cold — see `spec/rulebooks/learnings.md`'s "Pre-Phase-K
research" entry for the rulebook citations (the Capacity rule itself, p. 29100-29106; the
Essence-vs-Capacity dual-costing footnote, p. 453) this intro's own catalog research builds on.

**Four separable primitives, none of which Phase J's flat-item scope needed — this is why Phase K
is its own phase, not a Phase J add-on:**
1. **A rating-scaled formula resolver.** WP31 excluded every cyberware item whose `<cost>`/`<ess>`
   wasn't a bare literal (27 of 87 SR5 entries) precisely because nothing resolves `Rating * N`-style
   formulas yet.
2. **A purchase *tree*, not a flat list.** A limb with plugins installed into it needs parent/child
   structure; `CyberwareSelection.items` (WP32) is a flat tuple today, and legacy import (WP33)
   explicitly does not parse `<children>` at all.
3. **A second, per-purchase budget (Capacity)**, independent of the shared nuyen/Essence budgets
   Phase J already built, plus the Essence-vs-Capacity dual-costing choice at purchase time (same
   catalog row, two different cost modes depending on where it's installed).
4. **Conditional Improvements.** Checked directly: `chummer5.engine.improvements.Improvement` (WP5)
   has no `condition` field at all — every Improvement this engine has ever produced is
   unconditional by construction. At least one real subsystem bonus (Vision Enhancement's Mental
   limit bonus, "only on visual Perception tests") needs one. This is the single biggest, most
   foundational piece of this phase — a new engine primitive, not new catalog content.

**Catalog research (this session, via a one-off `xml.etree.ElementTree` read over all 87 SR5
`cyberware.xml` entries — re-confirm against the full file during implementation, this was an
exploratory pass, not an exhaustive audit the way WP21/31's own counts were).** Of the 27 SR5
entries WP31 excluded as non-flat, `<cost>`/`<ess>` reduce to only **6 distinct formula shapes**:
`Rating * N` (19 occurrences), a plain literal that failed only the *other* field's flatness check
(2), `FixedValues(N,N,N)` (2), `(Rating - MinRating + N) * N` (2), plus two one-off named formulas
(`Cybereyes Basic System`'s and `Cyberears`' own `<cost>`, each a unique small arithmetic expression
not shared by any other item). `<capacity>` (checked across all 87 SR5 entries, not just the
non-flat 27) reduces to **7 shapes**: a bare integer or bare `Rating`-formula (a parent's *budget*),
or the same shapes bracketed (`[N]`, `[Rating]`, `[Rating * N]` — a plugin's *cost*), plus a literal
`[*]` marker (2 occurrences: `Image Link`, `Sound Link` — bundled free with their parent, not a
player pick, see the learnings.md entry's own caveat about confirming this reading). **29 of the 87
SR5 entries carry `<allowsubsystems>` (i.e., are parents):** 16 are the Cyberlimb variants already in
WP31's flat catalog (their Capacity budget is already a bare int, e.g. `Synthetic Full Arm` → `8`);
2 are Cybereyes/Cyberears (rating-formula cost, currently excluded entirely); 11 are "Cyber Implant
Weapon"-category items (Grenade Launcher, Hand Blade, Heavy Pistol, ...) which are *themselves*
plugins into a limb (bracketed Capacity cost) **and** parents for a further "Cyber Implant Weapon
Accessory" subsystem layer — a genuine two-level nesting case; confirm whether any curated fixture
actually exercises it before deciding whether to support that third level or cut it explicitly.

**Sequencing rationale.** The formula resolver (WP36) and expanded data loader (WP37) are pure,
side-effect-free groundwork — proven/loaded before any purchase logic touches them, mirroring
WP5→WP6 and WP30→WP31's own "prove the primitive, then build on it" precedent. Conditional
Improvements (WP39) is scoped as its own isolated WP for the identical reason WP5 itself was: it's a
core-engine primitive change (touches `resolve()`'s call sites, not just cyberware), so it gets
proven with synthetic data before real content depends on it — deliberately sequenced independently
of WP37/38 (no data dependency either way) so it can be picked up first if that turns out to be the
more useful order. WP40-41 wire real content through the now-complete primitive set; WP42 (UI) is
last and deliberately excluded from this phase's own scope until WP36-41 are solid — this
conversation's own request not to build placeholder UI that gets thrown away applies here directly.

- [ ] **WP36 — Cyberware rating-formula resolver.**
  Goal: a small, tested, whitelisted evaluator for the rating-scaled cost/Essence/Capacity formula
  shapes `cyberware.xml` actually uses — proven against synthetic formula strings before any real
  catalog data touches it (mirrors WP5/WP30's "prove the mechanism in isolation first" precedent).
  Deliverables:
  - A resolver, e.g. `resolve_cyberware_formula(formula: str, *, rating: int, min_rating: int = 0)
    -> Decimal`, location TBD at implementation time (a new `chummer5.data.cyberware_formula` module,
    or a private helper inside `chummer5.data.cyberware` — decide and document).
  - Re-confirm this session's shape survey (see this phase's own intro) against the *complete* 87-
    entry SR5 set before finalizing which shapes to support — enumerate and hand-verify each rather
    than building a general arithmetic-expression parser (mirrors WP22/WP25/WP27's "classify known,
    named shapes" precedent, not a general expression/XPath evaluator). Decide, and document the
    decision: hardcode the two one-off named formulas (`Cybereyes Basic System`, `Cyberears`) by
    item name rather than generalizing a parser to cover them, since nothing else shares their shape.
  - Decide & document: is a bracketed value (`[N]`, `[Rating]`) parsed by this same resolver (stripping
    brackets first) or treated as a distinct concern from WP37's loader? Keep the resolver itself
    agnostic to "is this a budget or a cost" — that's a WP37/38 concern, not this one's.
  - Decide & document: is `[*]` (Image Link, Sound Link) a resolver concern at all, or purely a
    WP37/38 "bundled free" special case with nothing to resolve? (Current read: the latter — see
    learnings.md.)
  Depends on: nothing new.
  Acceptance: unit tests for every distinct shape confirmed present, each hand-checked against a
  real rulebook-table value (e.g. Vision Enhancement Rating 2 → Capacity cost 2, Essence 0.1, nuyen
  cost 8000; Cybereyes Basic System Rating 3 → nuyen cost 10000, Essence 0.4 — both already
  transcribed from the p. 453 table in this session's research, see learnings.md).

- [ ] **WP37 — Cyberware Capacity/subsystem data loader.**
  Goal: widen `chummer5.data.cyberware` to capture parent Capacity budgets, subsystem-category
  eligibility, and plugin Capacity cost — data layer only, no purchase logic yet (mirrors WP31's own
  sequencing relative to WP32).
  Deliverables:
  - Widen `Cyberware` (or a new sibling type — decide and document) with: a raw/resolved Capacity
    *budget* (parents only), a raw/resolved Capacity *cost* (plugins only, brackets stripped),
    `allowed_subsystem_categories: tuple[str, ...]` (parents only), and a `bundled_free: bool` (the
    `[*]` case).
  - **This WP must widen `load_cyberware()`'s own scope, not just its field set.** Today's loader
    only keeps items with a flat `<cost>` **and** flat `<ess>` (60 of 87 SR5 entries) — this whole
    phase's point is items *excluded* by that filter (Cybereyes, Cyberears, Customized/Enhanced
    Agility/Strength, the 11 Cyber Implant Weapons, ...). Add a second, explicitly-named loading path
    (e.g. `load_cyberware_subsystems()`, or a `include_rating_scaled: bool` parameter) rather than
    relaxing WP31's existing flat-only contract in place — several already-shipped WP31/32/33 tests
    depend on `load_cyberware()`'s current 60-item, flat-only behavior being unchanged.
  - Re-verify this phase's intro's "29 parents, 16 already-flat Cyberlimbs / 2 Cybereyes+Cyberears /
    11 Cyber Implant Weapons" split against the full data set; confirm whether any curated fixture
    exercises the Cyber Implant Weapon → Weapon Accessory two-level nesting case before deciding
    whether WP38 needs to support a third nesting level or can cut it explicitly (document either way).
  Depends on: WP36 (to store resolved, not just raw, Capacity values — decide whether this WP resolves
  eagerly at load time or keeps raw strings for WP38 to resolve per-purchase; document the choice).
  Acceptance: unit tests confirming the loader's new counts/fields against hand-checked
  `cyberware.xml` values; an explicit test that WP31's original `load_cyberware()` (60 flat items,
  existing field set, existing call sites) is completely unchanged — this WP must be additive to
  WP31/32/33, not a breaking change to already-shipped behavior.

- [ ] **WP38 — Purchase tree & Capacity budget validation.**
  Goal: let a cyberware purchase actually nest — a limb with plugins installed into it, validated
  against the parent's resolved Capacity budget.
  Deliverables:
  - `chummer5.engine.cyberware`: a purchase-tree type, e.g. `PurchasedCyberware(item, rating,
    installation: Literal["standalone", "subsystem"], plugins: tuple[PurchasedCyberware, ...])`.
    Decide & document whether this replaces `CyberwareSelection.items`'s current flat
    `tuple[Cyberware, ...]` outright (every existing purchase becomes a zero-plugin leaf) or sits
    alongside it — existing WP32/33 tests and the native save format both depend on today's flat
    shape, so this is a real compatibility decision, not a mechanical rename.
  - Capacity check: sum of each installed plugin's resolved Capacity cost (WP36/37) must not exceed
    the parent's resolved Capacity budget; category check: each plugin's category must be in the
    parent's `allowed_subsystem_categories`.
  - Essence-vs-Capacity dual costing: the same catalog item, bought standalone, still costs Essence
    exactly as today's engine already models; bought as a subsystem, it costs Capacity instead and
    contributes **zero** Essence — confirm this reading against `spec/rulebooks/learnings.md`'s own
    p. 29103 citation before implementing (already recorded, no new PDF pass needed for this part).
  - The `[*]` bundled-free case (Image Link, Sound Link): confirm via real fixture data whether any
    curated Cybereyes/Cyberears purchase ever appears *without* its bundled item before deciding
    whether to model it as always-auto-attached (simpler) or a skippable choice.
  Depends on: WP36, WP37.
  Acceptance: unit tests (synthetic data) for Capacity budget/category validation, including an
  over-capacity rejection and a wrong-category rejection; an integration test against a real
  fixture's actual limb+plugin combination (e.g. `Barrett.chum5`'s own `Synthetic Full Arm` +
  `Customized Agility` + `Enhanced Agility` + `Cyberlimb Optimization`, already dumped during this
  session's WP33 research) confirming the resolved Capacity spend matches what the limb's own
  Capacity budget allows.

- [ ] **WP39 — Conditional Improvements: a new engine primitive.**
  Goal: give `Improvement` (WP5) a real, typed condition mechanism — the one genuinely new,
  foundational engine primitive this phase needs, proven with synthetic data before any cyberware
  content uses it (mirrors WP5's own "prove in isolation" methodology, applied to itself).
  Deliverables:
  - `chummer5.engine.improvements`: `Improvement` gains an optional `condition` field — a typed
    predicate compiled once at construction (the Project Overview's own long-stated design intent
    for this, never yet implemented; confirmed this session that no `condition` field exists at all
    today). Keep it a named, hardcoded predicate per confirmed real shape (mirrors WP25's xpath-
    predicate precedent) — do not build a general expression/condition-string interpreter; nothing
    in this phase's own scope needs one.
  - `resolve()` needs additional call-site context to evaluate a condition against (e.g. "is the
    dice pool being resolved a visual Perception test") — this is a real signature change to
    `resolve()`'s call sites, not just an additive field. Scope the *smallest* context shape this
    phase's own real conditional bonuses (Vision Enhancement/Audio Enhancement/Spatial Recognizer,
    all "only on a specific test category") actually need, not a general "arbitrary game-state
    predicate" system.
  - Decide & document: is a `Condition` a closure/callable, a small tagged-union dataclass, or an
    Enum + parameters?
  Depends on: nothing new (touches only `engine/improvements.py`, mirrors WP5/WP30's isolation from
  real catalog content).
  Acceptance: unit tests with synthetic conditional improvements (a condition that's met and one
  that isn't, evaluated against the same target) proving `resolve()` only includes the met one;
  explicit test that every existing unconditional Improvement (all of WP5-WP35's content) is
  completely unaffected — `condition=None` must be a true no-op, zero behavioral drift for every
  character this engine builds today.

- [ ] **WP40 — Wire real conditional-bonus subsystem items.**
  Goal: reclassify Vision Enhancement, Audio Enhancement, and Spatial Recognizer from
  `NOT_YET_SUPPORTED`/excluded to real, condition-gated Improvements, using WP39's new primitive.
  Deliverables:
  - Extend `chummer5.data.cyberware`'s bonus classifier with a new `BonusSupport` value for
    "conditional flat bonus." Confirm each item's exact condition semantics via `pdftotext -layout`
    (their in-fiction test-category wording, e.g. Vision Enhancement's visual-Perception-only
    condition already identified this session) before hardcoding a predicate; record each citation
    in `spec/rulebooks/learnings.md`.
  - `chummer5.engine.cyberware`: apply these as conditional `Improvement`s (WP39) targeting the
    existing `MENTAL_LIMIT` improvement type (per the raw XML's own `<limitmodifier><limit>Mental
    </limit>`), gated by the appropriate new condition.
  Depends on: WP38, WP39.
  Acceptance: unit tests confirming the Mental limit bonus applies when resolving a visual-
  Perception-flagged dice pool and does not apply otherwise; explicit test that a non-visual Mental
  limit resolution (e.g. a Memory test) is unaffected by an installed Vision Enhancement.

- [ ] **WP41 — Cyberware modification save/load + legacy import.**
  Goal: thread the purchase tree (WP38) through native save/load and legacy import, which currently
  discards `<children>` entirely (a deliberate, documented WP31/33 scope cut, not an oversight).
  Deliverables:
  - `chummer5.io.save_format`: extend `CharacterSave`'s cyberware representation to carry the tree
    shape (parent + nested plugin picks), not just a flat id list.
  - `chummer5.io.legacy_chum5`: parse `<children>` recursively — reopens WP33's own "top-level only"
    decision now that there's an engine shape to receive the nested data; extend `LegacyCyberware`
    with a `children: tuple[LegacyCyberware, ...]` field.
  - `chummer5.io.legacy_import`: real per-plugin importability checks (each nested item independently
    resolved against WP37's subsystem catalog, itemized the same way WP33 itemizes top-level items)
    rather than continuing to ignore `<children>` wholesale.
  Depends on: WP38, WP40 (a saved/imported character may carry a conditional-bonus item).
  Acceptance: integration tests against real fixtures' actual nested purchases (e.g. `Barrett.chum5`'s
  `Synthetic Full Arm` + its 6 real children, already dumped during this session's WP33 research)
  confirming each resolvable child imports with the correct Capacity/Essence math, and non-resolvable
  ones (most of them, per WP33's own finding that most nested items are non-SR5-sourced or
  rating-scaled beyond what WP36/37 cover) are itemized, not silently dropped.

- [ ] **WP42 — Cyberware modification/subsystem UI.**
  Goal: expose subsystem/plugin purchase through the browser. Deliberately last, and deliberately
  out of scope until WP36-41 are solid — this project's own "rules engine first, UI last" principle,
  applied here specifically because a placeholder UI built against an incomplete engine shape would
  be throwaway work once the real shape lands.
  Deliverables:
  - A picker UI for "install a plugin into this limb/cybereye/cyberear," showing remaining Capacity
    live (mirrors WP15's live remaining-points precedent).
  - `_character_sheet_context`: show installed subsystems nested under their parent, and any
    conditional bonus's condition text alongside its value (so a player can see *why* a bonus applies
    only sometimes).
  Depends on: WP41.
  Acceptance: manual walkthrough — install a Cybereyes system, buy a Vision Enhancement plugin into
  it, confirm Capacity remaining updates live and the Mental limit bonus is visibly conditional on
  the character sheet.
