# WP3 — Quality & skill data loader

Status: complete
Ref: [Implementation Plan.md](../Implementation%20Plan.md) — Phase B, WP3.

## Goal

Load `legacy/Chummer/data/qualities.xml` (SR5-scoped) and `legacy/Chummer/data/skills.xml` into
frozen Python dataclasses, classifying each in-scope quality's `<bonus>` node as MVP-supported
("flat bonus" to a named attribute or skill) or not, so WP8 can filter on that classification later.

## Log

### 2026-07-17 — Source data reconnaissance

`qualities.xml`:
- 803 `<quality>` entries total; 96 have `source == "SR5"` (matches the count already recorded in
  the Implementation Plan from WP2's cross-check). Confirmed the split is 47 Positive / 49 Negative.
- Every quality carries `id`/`name`/`karma`/`category`/`source`/`page`; `karma` is already
  negative-signed in the source data for Negative-category qualities (e.g. `Addiction (Severe)` is
  `-20`), so no sign-flip logic is needed downstream. `limit` (37 of 96) is not uniformly numeric —
  values seen include plain integers (`6`), `"True"`/`"False"`, and formulas (`{arm} - 1` for
  Ambidextrous) — so it's kept as a raw optional string rather than parsed further.
- `<bonus>` is the general Improvement-bonus mini-language the Implementation Plan already flagged
  as out of scope for a full parser. Enumerated every SR5-scoped quality's bonus shape by child-tag
  set; of 96, only 3 (`Catlike`, `Double-Jointed`, `Natural Athlete`) reduce to one or more
  unconditional `<specificskill><name>/<bonus></specificskill>` nodes with no other fields — no
  `<condition>`, no category-wide targeting, no player selection. Everything else (24 `selecttext`
  select-a-target choices, category-wide/conditional `skillattribute` bonuses like Analytical Mind,
  `notoriety` shifts, multi-tag combinations, attribute `<max>`/`<min>` range changes like Lucky's
  `specificattribute><max>`, empty `<bonus/>`, and one quality — Gremlins — with no `<bonus>` element
  at all, using `<firstlevelbonus>` instead) is classified `NOT_YET_SUPPORTED`.
- The mirror shape for attributes (`<specificattribute><name>/<val></specificattribute>`, an
  unconditional flat *value* bonus, as opposed to Lucky's `<max>` range bonus) exists in the general
  schema — the Implementation Plan's "flat attribute/skill bonuses" phrasing names both — but no
  currently in-scope SR5 quality happens to use it standalone. Classifier logic supports it anyway
  (symmetric with the skill case), exercised by a hand-authored fixture
  (`tests/unit/fixtures/qualities_flat_attribute_bonus.xml`) rather than left untested until some
  future book's data exercises it for real.

`skills.xml`:
- 76 `<skill>` entries under `<skills>`, all already `source == "SR5"` (matches WP2's cross-check;
  re-verified here) — no source filter needed, unlike qualities/metatypes.
- `<knowledgeskills>` exists in the same file but is out of MVP scope: the Project Overview's
  in-scope list says "active skills (+ specializations, skill groups)" and doesn't mention knowledge
  skills, so the loader only touches `<skills>`.
- Every skill carries `id`/`name`/`attribute`/`category`/`default`/`skillgroup`/`specs`/`source`/
  `page`. `skillgroup` is an empty element (not absent) for the 28 skills that don't belong to a
  group (e.g. Animal Handling) — parsed to `None` rather than `""`. `default` (whether the skill can
  be used untrained, at rating 0) is a real SR5 mechanic directly relevant to WP7's dice-pool
  formula, so it's kept as `can_default`, not dropped. `exotic` (3 skills: Exotic Melee Weapon,
  Exotic Ranged Weapon, Pilot Exotic Vehicle) marks skills bought per-specific-item rather than as a
  single general rating — also kept, since it changes how a rating purchase means something
  different for these skills. `specs` is a *suggested* specialization list, not an enforced one (SR5
  allows freeform specializations); kept as an unordered-in-source but positionally-preserved tuple.
- Dropped (mirroring WP2's precedent of dropping non-MVP mechanics fields): `requiresflymovement`/
  `requiresgroundmovement`/`requiresswimmovement` (movement-type gates on a handful of Vehicle
  skills — not part of any MVP-covered derived stat).

### Design decisions

- **`BonusSupport` enum + `FlatBonus` dataclass, not a boolean flag.** A bare `bool` would lose the
  actual bonus data for the 3 supported qualities; WP8 needs the target/value, not just "is this
  usable." `flat_bonuses` is a tuple (not a single value) because Natural Athlete grants two
  independent flat skill bonuses from one quality.
- **Classification is all-or-nothing per quality, not per-bonus-child.** If any child of `<bonus>`
  isn't a recognized flat shape, the whole quality is `NOT_YET_SUPPORTED` — mirrors the Implementation
  Plan's explicit instruction ("exclude qualities using anything else... rather than silently
  ignoring their mechanical effect"): WP3/WP8 never partially apply a quality's effects.
  `raw_bonus` (the serialized `<bonus>` element) is kept on every quality regardless of support
  status, so a future, richer parser has the original data to work from without re-reading XML.
- **`count_by_support()` as a small standalone function, not a field on some aggregate object.**
  The acceptance criteria just needs the split to be visible/testable; a `Mapping[BonusSupport, int]`
  keyed by the enum (both keys always present, defaulting to 0 via `Counter`) is the simplest shape
  that a unit test can assert exact counts against.
- **Synthetic fixture file for the untested-in-real-data flat-attribute-bonus shape.** Following
  WP2's precedent of accepting an `xml_path` override for tests, `tests/unit/fixtures/` now holds a
  small hand-authored `qualities.xml`-shaped snippet — used only because the real 96-entry SR5 subset
  doesn't currently exercise that specific shape standalone; every other test in `test_qualities.py`
  runs against the real file per the Implementation Plan's general preference for using real legacy
  data over hand-crafted fixtures wherever it already covers the needed shape.

### Implementation

- `src/chummer5/data/qualities.py`: `FlatBonus`, `BonusSupport`, `Quality`, `load_qualities()`,
  `count_by_support()`. `load_qualities()` filters to `source == "SR5"` before classification, same
  filter-then-parse order as WP2's metatype loader will need once WP6 applies its own filter.
- `src/chummer5/data/skills.py`: `Skill`, `load_skills()`. No source filtering (already all SR5).
- Both loaders follow WP2's `xml_path: Path = DEFAULT_*_PATH` override convention, path resolved
  relative to the package file via `Path(__file__).resolve().parents[3]`, not cwd.

### Verification

- `uv run python -m pytest -q`: 34 passed (18 pre-existing from WP1/WP2 + 9 in `test_qualities.py`
  + 7 in `test_skills.py`), covering: SR5-only filtering and count (96 qualities / 76 skills),
  Positive/Negative split, negative karma sign, the 3 real supported-quality cases individually and
  via aggregate `count_by_support()` (3 supported / 93 not), a conditional-bonus and a
  no-bonus-element quality both classified `NOT_YET_SUPPORTED`, the synthetic flat-attribute-bonus
  fixture, skill group presence/absence, `can_default`, `exotic`, and specialization list contents.
- `uv run python -m ruff check .` / `ruff format --check .`: clean (two line-length wraps and one
  reformat needed during development, fixed before final run).
- `uv run python -m mypy src`: clean, strict mode (tests aren't mypy-checked — `pyproject.toml`'s
  `[tool.mypy]` scopes to `packages = ["chummer5"]` only, same as WP2).
- Environment note (repeat of WP2's, not a new finding): this checkout is mounted at
  `/workspaces/chummer5_py` while `.devcontainer/devcontainer.json` pins `workspaceFolder` to
  `/workspace`; invoked all tools as `uv run python -m {pytest,ruff,mypy}` per the Project Overview's
  documented workaround rather than the bare `uv run {pytest,ruff,mypy}` form.

## Files touched

- `src/chummer5/data/qualities.py` (new)
- `src/chummer5/data/skills.py` (new)
- `tests/unit/test_qualities.py` (new)
- `tests/unit/test_skills.py` (new)
- `tests/unit/fixtures/qualities_flat_attribute_bonus.xml` (new)
- `spec/worklogs/WP3.md` (new, this file)
- `spec/Implementation Plan.md` (WP3 checkbox ticked)

## Outcome

WP3 complete: both loaders parse the real legacy data files (qualities restricted to `source ==
"SR5"`; skills needs no filter, already all SR5), quality bonus nodes are classified
supported/not-yet-supported per the Implementation Plan's "flat attribute/skill bonus" rule with the
split visible via `count_by_support()`, and the acceptance criteria (`pytest`, `ruff`, `mypy` all
green; at least one supported and one unsupported bonus-node shape covered by tests) are met.
