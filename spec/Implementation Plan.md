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

- [ ] **WP20 — Lifestyle selection.**
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

- [ ] **WP21 — Expand the starter-gear catalog to the full flat-cost SR5 equipment set.**
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

- [ ] **WP22 — Offer more qualities: verified-inert flavor picks + the Limit-bonus trio.**
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
