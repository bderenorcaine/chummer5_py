# WP4 — Legacy `.chum5` fixture parser & golden corpus

Status: complete
Ref: [Implementation Plan.md](../Implementation%20Plan.md) — Phase C, WP4.

## Goal

Turn legacy `.chum5` save files into comparable ground truth: a parser that extracts MVP-relevant
raw fields (metatype, priority selections, attributes, skills, qualities, karma, nuyen) from a save
file, plus a curated, documented subset of the legacy corpus for later WPs to build against.

## Log

### 2026-07-17 — Source data reconnaissance

No `.xsd` exists for the `.chum5` save format (unlike `metatypes.xml`/`qualities.xml`/`skills.xml`,
which do have one, if a stale one per WP2's note) — everything below came from reading real fixture
files with `xml.etree.ElementTree` and cross-referencing the legacy C# where the meaning of a field
wasn't obvious from the data alone.

**Confirming "11 mundane fixtures."** Grepped `<magenabled>`/`<resenabled>`/`<buildmethod>`/
`<metatype>` across all 34 files in `legacy/Chummer.Tests/TestFiles/`. `magenabled == False` gives
exactly 11 files, matching the Implementation Plan's count. Cross-checked against the file
contents: 5 of those 11 (`Bastion`, `Rez0luti0n2.0`, `SCSi`, `Serpent`, `Yeti-#ffffff2`) have
`<resenabled>True</resenabled>` and a `<prioritytalent>Technomancer</prioritytalent>` — meaning
"mundane" as this project has used the term since WP2 is specifically `magenabled == False`, *not*
"no magic and no resonance." This isn't a new decision, just a discovered consequence of a
precedent already set: WP2's worklog defines "mundane" this way when establishing that every mundane
fixture is `Metahuman`-category. Documented explicitly in `tests/fixtures/README.md` since it's easy
to misread "mundane" as excluding Technomancers too. It doesn't affect WP4's own validity — these
fixtures still ground-truth *build-method-agnostic derived-stat formulas* (attributes, skills,
karma, nuyen), which don't care whether the character can also compile sprites; they just can't be
*built* by MVP's future chargen engine (WP6+ still can't construct a Technomancer, but WP4 doesn't
build characters, it only extracts what a save file already says).

**`.chum5` structure, as parsed:**
- Root is `<character>`. `<attributes>`, `<qualities>`, `<contacts>` are direct children.
- Skills are nested three levels deep: `<newskills><skills><skill>` (active, `isknowledge=False`
  uniformly at this path) and, separately, `<newskills><knoskills><skill>` (knowledge skills,
  `isknowledge=True`, with an inline `<name>` since they aren't drawn from a fixed catalog).
  `<newskills><groups><group>` holds skill *group* ratings (`id`/`name`/`base`/`karma`).
- An active `<skill>` never repeats its own name — only `<suid>`, a GUID matching
  `chummer5.data.skills.Skill.id` (confirmed by hand: Yeti's Resonance-Active skill with
  `<suid>f338d383-...</suid>` matches `skills.xml`'s `<id>f338d383-...</id>` entry for "Compiling").
  Resolving that join is left to whichever WP actually needs skill names (WP7), not this parser —
  WP4's contract is "what the save file literally contains."
- A `<quality>` *does* carry its own `<name>` directly, plus `<id>` (cross-references
  `chummer5.data.qualities.Quality.id`), `<bp>` (karma cost, already signed per qualities.xml's
  convention), `<qualitytype>` (`Positive`/`Negative`), and `<source>`.
- `<priorityskills>` appears **twice** as a direct child of `<character>`, with two unrelated
  shapes: once as a scalar `"<letter>,<n>"` value (the Skills priority category, structurally
  identical to its four siblings `prioritymetatype`/`priorityattributes`/`priorityspecial`/
  `priorityresources`), and once as a list wrapper (`<priorityskill>` children — bonus skill picks
  from the Talent choice, e.g. a Technomancer's three free Resonance skills). `ElementTree`'s
  `root.findall("priorityskills")` just returns both in document order, so the parser disambiguates
  by shape (any children vs. none), not position, since nothing in the format guarantees order.
- **Every `<priority*>` scalar field maps to a WP2 `PriorityTable` category, under a different
  name.** `prioritymetatype` -> Heritage, `priorityattributes` -> Attributes, `priorityspecial` ->
  Talent, `priorityskills` (scalar) -> Skills, `priorityresources` -> Resources. Traced the naming
  through `SelectMetatypePriority.cs`, which populates `cboHeritage` from `prioritymetatype` et al.
  `PrioritySelections`'s field names follow WP2's category names, not the save file's, so callers
  don't need to hold this mapping in their heads.
- **The raw value's shape and the mystery of the trailing number.** Every observed `<priority*>`
  value is `"<letter>,<n>"` (e.g. `"D,1"`), except the Skills scalar, which is `""` for every
  SumtoTen-built Mundane-talent fixture in the corpus (10 of 11; only Technomancer-talent SumtoTen
  fixtures and the one Priority-built fixture have a non-empty Skills value) — so the parser can't
  assume the comma is always present. Traced `_strPriorityMetatype` et al. through
  `Character.cs`/`SelectMetatypePriority.cs`: the UI only ever reads `priority[0]` as the letter
  (`SetPrioritySelectionAsync`'s `x.FindString(priority[0].ToString())`); no reachable code path for
  a *loaded* character interprets the trailing number. Empirically checked what it actually is
  anyway, across all 55 non-empty `<letter>,<n>` values in the 11-fixture corpus: `n` is always
  `4 - "ABCDE".index(letter)` (A->4, B->3, C->2, D->1, E->0) — a fully redundant reverse-rank of the
  letter itself, not independent information. Since the app doesn't read it back and it carries no
  data the letter doesn't already have, `PrioritySelections` exposes the raw string as-is (so nothing
  is silently dropped) plus a `priority_letter()` helper for the one confirmed-meaningful part,
  rather than modeling the number as a real field.
- **`<startingnuyen>` matches WP2's `Resources` priority table exactly, for both build methods.**
  Cross-checked every fixture's `starting_nuyen` (parsed from its own `<startingnuyen>`) against
  `load_priorities().resources[priority_letter(raw_resources)].nuyen` from WP2's loader — all 11
  match (450000/275000/140000/6000, per the Resources priority letter each fixture's raw
  `<priorityresources>` encodes). This is a genuine cross-validation between two independently
  written parsers (WP2's `priorities.xml` reader and this WP's save-file reader) that happen to
  agree on a real rules number, not just an internal-consistency check — baked into
  `test_starting_nuyen_matches_resources_priority_letter` so it keeps validating both loaders
  against each other going forward.
- `<gameplayoption>` (Standard/Prime Runner/Street Level, the same table selector WP2's
  `priorities.xml` Resources category keys off) is `"Standard"` for all 11 curated fixtures —
  confirms they're comparable against WP2's Standard-only loader without a table mismatch.

### Design decisions

- **Reference the legacy `.chum5` files, don't copy them into `tests/`.** The 11 curated fixtures
  total ~9MB; `tests/fixtures/mundane_chum5.py`'s `mundane_fixture_path()` resolves straight into
  `legacy/Chummer.Tests/TestFiles/`. Copying would double that for zero benefit — the legacy corpus
  is already checked into this repo, isn't expected to change, and a copy risks silently drifting
  from the source of truth it's supposed to be validating against. See `tests/fixtures/README.md`.
- **Only active skills, no knowledge skills.** Mirrors WP3's precedent (`skills.xml`'s
  `<knowledgeskills>` is out of MVP scope per the Project Overview's in-scope list). The parser
  never touches `<newskills><knoskills>`, so `LegacyCharacter.skills` needs no `is_knowledge` flag —
  every entry is structurally guaranteed active.
- **No contacts, despite being general MVP scope.** WP4's own deliverable list (Implementation
  Plan) names "metatype, priority selections, attributes, skills, qualities, karma, nuyen" — not
  contacts. WP9 ("Contacts & starting resources") is the WP that actually needs them; adding a
  `LegacyContact` here would be scope creep against an explicit, WP-scoped field list. `<contacts>`
  is easy to add to this parser later without disturbing anything already built on it.
- **Raw fields only, no cross-referencing against `chummer5.data`'s loaders inside the parser
  itself.** `LegacySkill.suid`/`LegacyQuality.id` are kept as opaque strings; resolving them into
  `Skill`/`Quality` objects is left to WP7/WP8, which already depend on WP3. This keeps WP4's own
  dependency graph at just WP1, per the Implementation Plan, and keeps this module's job legible as
  "what does the file say" rather than "what does the file mean."
  `test_starting_nuyen_matches_resources_priority_letter` still cross-checks against WP2's loader,
  but that's a *test* doing double-loader validation, not the parser itself taking on a dependency.
- **`tests/fixtures/mundane_chum5.py` as a PEP 420 namespace package, no `__init__.py`.** Existing
  tests (`tests/unit/*.py`) have no shared cross-file helper and don't need one; WP4 is the first WP
  needing a fixture registry importable from more than one test file (this WP's own
  `tests/integration/`, and WP6-WP10 later). `python -m pytest` — already this project's documented
  workaround for the workspace-path mismatch (see Project Overview's "Stale `.venv` console scripts"
  note) — puts the repo root on `sys.path`, so `tests.fixtures.mundane_chum5` and
  `tests.integration.*` are importable as namespace packages with no `pyproject.toml` change and no
  new empty `__init__.py` files to maintain.
- **`tests/integration/`, not `tests/unit/`, for `test_legacy_chum5.py`.** This is the first WP to
  populate `tests/integration/` (per the Implementation Plan's repo layout). The distinction drawn:
  `tests/unit/` exercises one loader against the small, stable `legacy/Chummer/data/*.xml` rules
  files; `tests/integration/` exercises the corpus of large, real, externally-authored save files —
  closer in spirit to the later end-to-end fixture-corpus regression tests (WP10) than to a unit test
  of one function.

### Implementation

- `src/chummer5/io/legacy_chum5.py`: `LegacyAttribute`, `LegacySkill`, `LegacySkillGroup`,
  `LegacyQuality`, `PrioritySelections` (+ `priority_letter()` helper), `LegacyCharacter`,
  `load_chum5()`. Follows WP2/WP3's `ET.parse` + `findtext(tag, default)` + frozen-dataclass style;
  `LegacyCharacter.attributes` is a `MappingProxyType`, matching WP2's precedent for keeping a
  `frozen=True` dataclass read-only end to end.
- `tests/fixtures/mundane_chum5.py`: `MUNDANE_FIXTURES` (the 11 names), `PRIORITY_BUILD_FIXTURE`
  (`"Yeti-#ffffff2.chum5"`), `mundane_fixture_path()`.
- `tests/fixtures/README.md`: documents the referenced-not-copied decision, the "mundane means
  `magenabled=False`, not `resenabled=False` too" clarification, and which fixture(s) back which
  kind of assertion (build-method-agnostic vs. priority-allocation), per WP4's acceptance criteria.
- `tests/integration/test_legacy_chum5.py`: a hand-checked-value table (`_KNOWN_RAW_FIELDS`,
  independently derived with a bare `ElementTree` read, not by trusting the parser's own output)
  parametrized across all 11 fixtures for metatype/karma/nuyen/quality-count; the
  WP2-loader cross-check for starting nuyen; and deeper single-fixture tests for Yeti (priority
  selections, an attribute, the Technomancer quality, skill groups) and Barrett (attributes,
  qualities) as a second, SumtoTen-built data point.

### Verification

- `uv run python -m pytest -q`: 64 passed (34 pre-existing from WP1-WP3 + 30 new in
  `tests/integration/test_legacy_chum5.py`), including the cross-loader nuyen check against WP2's
  `load_priorities()` for all 11 fixtures.
- `uv run python -m ruff check .` / `ruff format --check .`: clean (a few line-length wraps and one
  `ruff format` pass needed during development, fixed before the final run).
- `uv run python -m mypy src`: clean, strict mode (tests aren't mypy-checked, same scope as WP2/WP3).
- Environment note (repeat of WP2/WP3's, not a new finding): checkout mounted at
  `/workspaces/chummer5_py`, `.devcontainer/devcontainer.json` pins `workspaceFolder` to
  `/workspace`; used `uv run python -m {pytest,ruff,mypy}` throughout, per the documented workaround.

## Files touched

- `src/chummer5/io/legacy_chum5.py` (new)
- `tests/fixtures/mundane_chum5.py` (new)
- `tests/fixtures/README.md` (new)
- `tests/integration/test_legacy_chum5.py` (new)
- `spec/worklogs/WP4.md` (new, this file)
- `spec/Implementation Plan.md` (WP4 checkbox ticked)

## Outcome

WP4 complete: `load_chum5()` parses every MVP-relevant raw field (metatype, priority selections,
attributes, skills, skill groups, qualities, karma, nuyen) from a legacy `.chum5` save file into
frozen dataclasses; the 11-fixture mundane corpus is curated and documented in
`tests/fixtures/README.md`, with `Yeti-#ffffff2.chum5` flagged as the sole priority-build fixture;
and the acceptance criteria (parser round-trips known raw fields for all 11 curated fixtures,
verified against independently hand-checked values; `tests/fixtures/README.md` documents which
fixture backs which kind of assertion) are met.
