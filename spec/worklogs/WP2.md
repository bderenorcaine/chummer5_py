# WP2 — Metatype & priority data loader

Status: in progress
Ref: [Implementation Plan.md](../Implementation%20Plan.md) — Phase B, WP2.

## Goal

Load `legacy/Chummer/data/metatypes.xml` and `legacy/Chummer/data/priorities.xml` (Standard
prioritytable only) into frozen Python dataclasses, with unit tests against hand-checked values.

## Log

### 2026-07-17 — Source data reconnaissance

Read both source XML files directly (not just the `.xsd`, which is stale in places — e.g. it's
missing the `<prioritytable>` element that's actually present in the data) before writing any
dataclasses.

`metatypes.xml`:
- 21 top-level `<metatype>` entries across 3 categories: `Metahuman` (Human, Elf, Dwarf, Ork,
  Troll — 5), `Metasapient` (Centaur, Naga, Pixie, Sasquatch, A.I. — 5), `Shapeshifter` (11).
- Each metatype carries `bod/agi/rea/str/cha/int/log/wil/ini/edg/mag/res/ess/dep` ×
  `min/max/aug` (14 attributes × 3 = 42 scalar fields), `karma`, `category`, `source`, `page`,
  and an optional `<metavariants>` list of the same shape (minus a couple of fields) plus
  `<qualities><positive>/<negative>`.
- Confirmed via `legacy/Chummer.Tests/TestFiles/*.chum5` (the fixture corpus WP4 will curate)
  that every **mundane** (`magenabled=False`) fixture uses a `Metahuman`-category metatype
  (Human/Elf/Dwarf/Ork/Troll). All `Metasapient`/`Shapeshifter` entries carry a
  `<bonus><enableattribute><name>MAG</name></enableattribute></bonus>` (Centaur/Sasquatch/etc.)
  and are inherently Awakened — mechanically unreachable for a mundane build. (Note: `magmin`
  is *not* the signal for this — Human also has `magmin=1`; that's just the range Magic *would*
  occupy if something granted it. The actual gate is the `enableattribute` bonus node, part of
  the general Improvement engine machinery this project explicitly defers post-MVP.) This
  confirms the project overview's "mundane only" MVP scope doesn't need to exclude these
  metatypes at the **data loader** level; it's the character-creation engine (WP6+) that will
  restrict which metatypes are offerable, and it can't do so from `bonus` content anyway since
  that parser doesn't exist yet — WP6 will need its own explicit allowlist (e.g. `category ==
  "Metahuman"`) rather than deriving eligibility from this file's `bonus` nodes. The loader
  parses all 21 metatypes faithfully regardless, since that's a cheap, low-judgment,
  general-purpose parse and the file is small.

`priorities.xml`:
- `<priorities>` is a flat list of 35 `<priority>` nodes, disambiguated by `<category>`
  (Heritage/Talent/Attributes/Skills/Resources) and, for Resources only, `<prioritytable>`
  (Standard/Prime Runner/Street Level — confirmed against legacy C# usage in
  `SelectMetatypePriority.cs`, which filters on `prioritytable = ... or not(prioritytable)`).
  Heritage/Talent/Attributes/Skills have no `<prioritytable>` element and apply to all three
  tables uniformly — only Resources values differ per table (450k/275k/140k/50k/6k for Standard
  vs. two other tables). WP2 scope is Standard only, so the loader takes the first
  `prioritytable=Standard` (or table-agnostic) match per category/letter.
- Talent's `<talent>` sub-nodes (Magician/Mystic Adept/Technomancer/A.I./Mundane) carry
  `required`/`forbidden`/`qualities`/`skillgroupchoices`/`skillchoices` nested structures that
  encode cross-references into the general Improvement/quality-selection machinery — the same
  kind of "mini-language" the Implementation Plan already calls out for quality `<bonus>` nodes.
  Decision: parse the flat scalar fields of every `<talent>` (name, codename/value, magic,
  resonance, depth, spells, cfp, skillqty/val/type, specialattribpoints) for all 5 letters —
  this is what "Talent category loaded" means — but don't build a parser for the nested
  required/forbidden/qualities sub-elements. Those only matter once magic/resonance chargen is
  implemented post-MVP, at which point this loader gets revisited anyway. MVP consumes only
  `letter="E", codename="Mundane"`.
- `priortysumtotenvalues` (SumtoTen build method support data) is out of scope per the
  Implementation Plan's build-method note and is not parsed.

### Design decisions

- **Attribute ranges as a dict, not 42 flat fields.** `Metatype`/`Metavariant` expose
  `attributes: Mapping[str, AttributeRange]` keyed by the standard SR5 abbreviations
  (`BOD/AGI/REA/STR/CHA/INT/LOG/WIL/INI/EDG/MAG/RES/ESS/DEP`) rather than 42 separate
  `bodmin`/`bodmax`/... fields, both for ergonomics and because this is the same shape WP6's
  `Attribute.Value` composition will want. Verified the abbreviation set against legacy
  `AttributeSection.cs` (`GetAttributeByName`) for naming consistency with the source project —
  note legacy's primary-attribute set omits `INI` (Initiative is derived, not priority-spent),
  but the XML still carries an `ini` range, so it's kept in the dict for fidelity; WP6 isn't
  obligated to let players spend points on it.
- **Dropped fields:** `movement` (walk/run/sprint — not part of any MVP-covered derived stat per
  the Project Overview's derived-stats list), `bonus`, `powers`, `addweapon`,
  `qualityrestriction`, `halveattributepoints` — all either empty in the Metahuman rows that
  matter for MVP or only meaningful for non-Metahuman metatypes / the general Improvement engine,
  both out of MVP scope. Kept `source`/`page` (cheap, useful for future UI citations).
- **Mappings are read-only via `types.MappingProxyType`**, since a `frozen` dataclass only
  prevents reassigning the field, not mutating a plain `dict` stored in it.
- Both loaders take an explicit `xml_path` parameter defaulting to the real
  `legacy/Chummer/data/*.xml` location (resolved relative to the package file, not cwd), so tests
  can point at fixture XML snippets for edge cases without touching the real file.

### Implementation

- `src/chummer5/data/metatypes.py`: `AttributeRange`, `Metavariant`, `Metatype`, `load_metatypes()`.
- `src/chummer5/data/priorities.py`: `HeritagePriority`/`AttributesPriority`/`SkillsPriority`/
  `ResourcesPriority`/`TalentPriority` (+ their option/metavariant sub-dataclasses),
  `PriorityTable`, `load_priorities()`. `PriorityTable.mundane_talent()` is a small convenience
  that looks up letter `"E"`, codename `"Mundane"` — the one Talent entry MVP actually consumes —
  so WP6 doesn't need to know the Talent category's internal shape.
- Both loaders default their `xml_path` parameter to the real `legacy/Chummer/data/*.xml` files
  (path resolved relative to the package file via `Path(__file__).resolve().parents[3]`, not cwd),
  but accept an override so future tests can exercise edge cases (e.g. a metatype with no
  metavariants, a priority letter with multiple talent options) without needing hand-crafted fixture
  files for this WP's tests — the real legacy files already exercise every shape needed.
- Mappings (`Metatype.attributes`, `PriorityTable.heritage`, etc.) are wrapped in
  `types.MappingProxyType` so a `frozen=True` dataclass is actually read-only end to end, not just
  at the top level.

### Verification

- `uv run pytest -q`: 17 passed (9 in `test_metatypes.py`, 8 in `test_priorities.py`, covering:
  metatype count, Human/Troll attribute ranges, Nartaki/Dwarf metavariant karma costs, Heritage
  priority A/E metatype lists + special-attribute-point values, Attributes/Skills point tables,
  Resources table confirmed as Standard-only (450k/275k/140k/50k/6k, not Prime Runner's or Street
  Level's numbers), and the Talent category's Mundane entry).
- `uv run ruff check .`: clean (one line-length fix needed in a comment).
- `uv run ruff format --check .`: clean.
- `uv run mypy src`: clean, strict mode.
- Environment note (not a repo change): this session's checkout is mounted at
  `/workspaces/chummer5_py`, but `.devcontainer/devcontainer.json` sets `workspaceFolder` to
  `/workspace`, and the pre-existing `.venv` had entry-point scripts shebanged to the latter path,
  so `uv run pytest` failed with "No such file or directory" even though the binary existed.
  Fixed for this session by `rm -rf .venv && uv sync --group dev` (regenerates the venv from
  `pyproject.toml`/`uv.lock` at the actual mount path; `.venv/` is gitignored, so this touches no
  tracked files). Not something WP2 needed to change in the repo itself.

## Files touched

- `src/chummer5/data/metatypes.py` (new)
- `src/chummer5/data/priorities.py` (new)
- `tests/unit/test_metatypes.py` (new)
- `tests/unit/test_priorities.py` (new)
- `spec/worklogs/WP2.md` (new, this file)
- `spec/Implementation Plan.md` (WP2 checkbox ticked)

## Outcome

WP2 complete: both loaders parse the real legacy data files into frozen dataclasses, unit tests
assert hand-checked values from both source XML files, and the acceptance criteria (`pytest`,
`ruff`, `mypy` all green) are met.
