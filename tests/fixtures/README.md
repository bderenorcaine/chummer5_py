# Test fixtures

## Legacy `.chum5` golden corpus (WP4)

`legacy/Chummer.Tests/TestFiles/` has 34 real, legacy-computed `.chum5` characters. This project
uses 11 of them as a regression oracle — see `mundane_chum5.py` for the registry these tests import,
and [Implementation Plan.md](../../spec/Implementation%20Plan.md)'s corpus note for the full
reasoning behind the split below.

**Referenced, not copied.** `mundane_chum5.py`'s `MUNDANE_FIXTURES`/`mundane_fixture_path()` point
straight at `legacy/Chummer.Tests/TestFiles/`, rather than duplicating the files under `tests/`. The
11 curated files total ~9MB; copying them would double that for no benefit (the legacy corpus is
already checked into this repo and isn't expected to change), and would risk the copies silently
drifting from the source of truth. If `legacy/` is ever excluded from a checkout, this fixture set
simply becomes unavailable — same as any other test that depends on `legacy/`.

### Which 11, and why

"Mundane" here means `<magenabled>False</magenabled>` — established in WP2's reconnaissance, not
redefined here. This is **not** the same as "no Resonance either": 5 of the 11
(`Bastion`, `Rez0luti0n2.0`, `SCSi`, `Serpent`, `Yeti-#ffffff2`) have
`<resenabled>True</resenabled>` and are actually Technomancers (confirmed via each file's
`<prioritytalent>` — e.g. Yeti's is literally `Technomancer`). They're still valid fixtures for this
WP's purposes: the Project Overview's MVP scope excludes magic/resonance from *character creation*,
but the **derived-stat formulas** these fixtures validate (attribute totals, skill dice pools,
initiative, limits) are build-method- and talent-agnostic — an attribute's `Value = metatype minimum
+ points spent + improvements` doesn't care whether the character can also compile sprites. A
Technomancer-built fixture is just as valid ground truth for `Attribute.total_value` as a strictly
mundane one. (It would *not* be a valid fixture for testing what MVP's chargen engine can build —
WP6+ still can't construct a Technomancer — but WP4 only extracts raw fields, it doesn't build
characters.)

Of the 11, only **`Yeti-#ffffff2.chum5`** has `<buildmethod>Priority</buildmethod>`; the other 10 use
`SumtoTen`, a different chargen method out of MVP scope. So:

- **All 11** back **build-method-agnostic** assertions: attributes, skills, skill groups, qualities,
  karma, nuyen — anything that's a property of the finished character, independent of how the points
  were allocated. `tests/integration/test_legacy_chum5.py`'s `test_round_trips_known_raw_fields` and
  the deeper per-field tests (attributes, qualities, skill groups) exercise this for every fixture.
- **Only `Yeti-#ffffff2.chum5`** (`PRIORITY_BUILD_FIXTURE`) backs **priority-table allocation**
  assertions — e.g. `test_yeti_priority_selections` checks the raw `<priority*>` letters against
  WP2's `load_priorities()` data. WP6's attribute-allocation tests will lean on this fixture
  specifically, alongside hand-authored cases checked directly against `priorities.xml`.

### Phase I: `MAGIC_PRIORITY_BUILD_FIXTURES` (WP25+)

Two more `buildmethod == Priority` fixtures, `Miko.chum5` (Elf Magician, Talent letter A) and
`Wesson.chum5` (Human Adept, Talent letter C) — the corpus's *only* magic-capable Priority-built
characters (see the Implementation Plan's Phase I intro for why: of 34 fixtures, only 3 are
`Priority`-built at all, and Yeti is mundane). Deliberately **not** added to `MUNDANE_FIXTURES`
(both have `<magenabled>True</magenabled>`) — they back Phase I's own Magic-type/Magic-rating/
tradition/Talent-free-skill-grant tests (`tests/unit/test_magic.py`,
`tests/integration/test_magic_fixtures.py`) rather than the mundane-corpus derived-stat/priority
-allocation tests above. See `spec/worklogs/WP25.md` for what each fixture's own `<priorityskills>`
element confirms about the Talent free-skill grant (Miko: Counterspelling + Spellcasting; Wesson:
Pistols — the latter a correction to the Implementation Plan's own claim that Wesson's letter grants
none). Neither fixture's actual tradition (Shinto/Christian Theurgy, both non-`SR5`-sourced) is one
of this phase's 2 offered traditions (Hermetic/Shamanic) — expected, not a gap; see the phase intro.

### Files

- `mundane_chum5.py` — `MUNDANE_FIXTURES` (the 11 names), `PRIORITY_BUILD_FIXTURE` (Yeti),
  `MAGIC_PRIORITY_BUILD_FIXTURES` (Miko, Wesson — WP25), `mundane_fixture_path()` (name -> path
  under `legacy/Chummer.Tests/TestFiles/`, works for any fixture name in the corpus, not just the
  mundane 11). Importable as `tests.fixtures.mundane_chum5` (a PEP 420 namespace package — no
  `__init__.py` needed; `pytest`'s `python -m pytest` invocation, already this project's documented
  workaround for the workspace-path mismatch, puts the repo root on `sys.path`).
- This README.
