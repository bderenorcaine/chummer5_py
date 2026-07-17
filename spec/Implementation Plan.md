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
MVP-offered quality list, rather than silently ignoring their mechanical effect.

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

- [ ] **WP4 — Legacy `.chum5` fixture parser & golden corpus.**
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

- [ ] **WP5 — Improvement engine core.**
  Goal: the base+improvements composition mechanism, proven in isolation.
  Deliverables: `src/chummer5/engine/improvements.py` — `Improvement` dataclass (source type/id, target,
  value, rating, unique-name dedup group) + index (`dict[(type, target)] -> list[Improvement]`) +
  `resolve()` implementing sum + `UniqueName` dedup ("highest bonus wins").
  Depends on: WP1.
  Acceptance: unit tests using **synthetic** improvements only (no XML involved) — proves the resolution
  math before any real rules content touches it, including a stacking/dedup case.

- [ ] **WP6 — Metatype selection & attribute allocation.**
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

- [ ] **WP7 — Skill allocation & dice pools.**
  Goal: active skills, groups, specializations, and the dice pool formula.
  Deliverables: `src/chummer5/engine/skills.py` — Skills-priority-letter → point pools; dice pool =
  attribute + rating (+2 specialization).
  Depends on: WP3, WP6.
  Acceptance: tests against the fixture corpus.

- [ ] **WP8 — Quality selection & minimal Improvement bonuses.**
  Goal: qualities affect karma and, for the supported subset, feed the Improvement engine.
  Deliverables: `src/chummer5/engine/qualities.py` — positive/negative quality picking, karma cost,
  negative-quality karma cap; only WP3's "MVP-supported" qualities produce `Improvement` records.
  Depends on: WP3, WP5, WP6.
  Acceptance: tests against fixtures restricted to MVP-supported qualities; an explicit test that an
  unsupported-bonus quality is excluded from the offered list rather than silently mis-applied.

- [ ] **WP9 — Contacts & starting resources.**
  Goal: nuyen, contacts, and a minimal starting-gear stub.
  Deliverables: `src/chummer5/engine/resources.py` — Resources-priority-letter → starting nuyen;
  contacts (connection/loyalty, karma cost beyond free points); a deliberately minimal starter-gear
  purchase (flat nuyen deduction against a small curated list — explicitly not the full gear catalog).
  Depends on: WP6.
  Acceptance: tests against fixtures for nuyen/contact math.

- [ ] **WP10 — Derived stats + full end-to-end regression. (Headless MVP milestone)**
  Goal: a complete, validated mundane priority-built character, computed headlessly end to end.
  Deliverables: `src/chummer5/engine/derived.py` — initiative, physical/mental/social limits, condition
  monitor boxes as pure functions of finalized attributes. Add the full-character regression test.
  Depends on: WP6, WP7, WP8, WP9.
  Acceptance: for every curated fixture, build the character end-to-end through the engine and diff every
  MVP-covered field against the legacy-computed values. **Headless MVP is complete when this passes.**

### Phase E — Save/load

- [ ] **WP11 — Native save format.**
  Goal: persist and reload a character in the project's own format.
  Deliverables: `src/chummer5/io/save_format.py` — JSON format mirroring the domain model.
  Depends on: WP10.
  Acceptance: round-trip tests (build → save → load → equal).

- [ ] **WP12 — Legacy `.chum5` import.**
  Goal: bring a real legacy character into the new engine, for MVP-covered content only.
  Deliverables: extends WP4's parser into a real import path for mundane, priority-built,
  MVP-feature-only legacy saves.
  Depends on: WP4, WP10.
  Acceptance: successfully imports `Yeti-#ffffff2.chum5`; imports of saves with out-of-scope content
  (magic, cyberware, etc.) fail with a specific, itemized error rather than silently dropping data.

### Phase F — FastAPI/HTMX UI

- [ ] **WP13 — Web app skeleton.**
  Goal: the UI stack runs end to end, doing nothing yet.
  Deliverables: `src/chummer5/web/app.py` (FastAPI app factory), Jinja2 base layout, HTMX vendored
  locally (not CDN-loaded, to keep the app fully offline/local-first), `uvicorn` dev-run instructions,
  one trivial page.
  Depends on: WP1.
  Acceptance: `uvicorn chummer5.web.app:app` serves the trivial page; an HTMX-driven interaction on that
  page round-trips through the server.

- [ ] **WP14 — Priority & metatype selection UI.**
  Goal: first real chargen screen.
  Deliverables: assign priority letters to the 4 MVP categories (Talent forced to E, not offered as a
  choice) and pick a metatype; server-side in-memory character-in-progress state keyed by a session
  cookie.
  Depends on: WP6, WP13.
  Acceptance: manual walkthrough creates a metatype+priority selection that matches what WP6's engine
  would produce for the same inputs.

- [ ] **WP15 — Attribute & skill allocation UI.**
  Goal: spend attribute/skill points through the browser.
  Deliverables: point-spend forms with HTMX-driven live remaining-points and dice-pool preview.
  Depends on: WP7, WP14.
  Acceptance: manual walkthrough; values match engine output for the same inputs.

- [ ] **WP16 — Qualities, contacts & resources UI.**
  Goal: round out chargen inputs.
  Deliverables: quality picker (MVP-supported catalog only), contacts editor, nuyen spend screen.
  Depends on: WP8, WP9, WP15.
  Acceptance: manual walkthrough; values match engine output for the same inputs.

- [ ] **WP17 — Character sheet + save/load UI. (UI MVP milestone)**
  Goal: finish and persist a character through the browser, start to finish.
  Deliverables: read-only finished-character view (derived stats), save/download (native format via
  WP11), load/upload (native format + legacy `.chum5` import via WP12).
  Depends on: WP10, WP11, WP12, WP16.
  Acceptance: full manual walkthrough — create a mundane priority character in the browser end to end,
  save it, reload it, and (separately) import `Yeti-#ffffff2.chum5` — all producing correct values.
  **UI MVP is complete when this passes.**
