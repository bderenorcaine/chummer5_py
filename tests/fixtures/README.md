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

## Synthetic whole-character fixtures (Phase S / WP72)

The `.chum5` corpus above is a fixed snapshot — only `Yeti-#ffffff2` is a mundane Priority build, so
every *interaction between subsystems* (a Priority build bearing cyberware, a magician losing Essence
to it, a Step-Seven leftover-Karma spend) has no real fixture. WP59 confirmed the corpus can't grow
(the legacy test harness only round-trips existing saves, never emits a computed character) and that
hand-authoring fake `.chum5` files is strictly worse than an honest synthetic fixture — see
`spec/worklogs/WP59.md`.

`synthetic.py` + `synthetic_fixtures.py` are the alternative: a `SyntheticCharacter` input literal
(priorities, metatype, name-keyed attribute/skill/group/specialization/quality picks) fed through the
**real** engine by `build_synthetic()`, paired with a hand-derived `expected` table whose every entry
carries an inline `citations` source (`priorities.xml`, a `learnings/phase-*.md` formula, a legacy C#
getter). `assert_fixture()` builds each fixture and asserts every `expected` metric both computes to
its target *and* carries a citation — a magic number with no cited source is itself a test failure.
This is the WP5/WP30 synthetic-*primitive* pattern extended to a whole character exercising an
*interaction* — the axis the `.chum5` corpus structurally can't cover. It sits **beside** the
`.chum5` registry, not in place of it: the 11 legacy files stay the ground truth for
build-method-agnostic derived-stat formulas.

The fixtures double as **playable Shadowrun characters** — legal, fully-spent priority builds with a
name and concept, not degenerate test artifacts, and authored as **one coherent runner team** (see
`phase-s-test-fixtures.md` §5): WP72's Renata "Cheshire" Vance (human infiltrator), WP73's Dražen
"Rebar" Kovač (Ork street samurai), WP74's Sabine "Cinder" Aumann (Human Hermetic combat mage),
WP75's Yseult "Wren" Marchetti (Elf Shamanic face), and WP76's Bakari "Nullsec" Osei (Dwarf decker,
and the set's one Sum-to-Ten build). This
costs nothing in rigour: a fully-spent budget hits the engine's validators at their exact limits, and
a coherent character touches more interaction paths. Only the mechanically derived numbers are
asserted; a fixture's loadout/contacts/lifestyle prose is flavour, not engine-checked.

WP72 landed the harness + one reference fixture (`REFERENCE_MUNDANE_FIXTURE`). WP73-76 each **add
their own input field(s) to `SyntheticCharacter` and the matching `build_synthetic()` wiring
together** — the dataclass deliberately declares only what a fixture already exercises, not
speculative shapes. **WP73 (landed)** adds the `cyberware`/`bioware` name-list fields and the
`cyberware:*`/`bioware:*` metric keys, closing gaps G1/G2 (a Priority build bearing cyberware; and
cyberware + bioware Essence costs stacking against the one shared pool) via `STREET_SAMURAI_FIXTURE`.
**WP74 (landed)** adds the magic input fields (`magic_type`/`talent_letter`/`tradition`/
`magic_granted_skills`/`spells`/`mentor_spirit`/`foci`) — a magic build now assigns Talent a real
A-D letter instead of the mundane-only forced E — plus the `magic:*`/`drain_resistance`/
`power_points`/`foci:*`/`spells:*` metric keys, closing gaps G3/G6 (a magician whose cyberware
Essence loss reduces Magic, carrying a bonded focus and a mentor spirit) via `COMBAT_MAGE_FIXTURE`.
**WP75 (landed)** adds the Step Seven leftover-Karma input fields (`karma_attribute_points`/
`karma_skill_points`/`karma_group_points`/`karma_specializations`, resolved in
`save_format.build_character`'s own attributes→skills→spells order) plus the
`karma_attribute:karma_cost`/`karma_skill:karma_cost`/`karma_skill:broken_groups` metric keys,
closing gaps G4/G5 (a Karma-funded skill raise that breaks a purchased skill group, a Karma-funded
specialization, a Karma-raised skill group, and a spell beyond the free Talent budget) via
`SHAMAN_FACE_FIXTURE`. **WP76 (landed)** adds the `build_method` field, which selects which
letter-assignment rule `build_synthetic()` validates the five priority letters against — Priority's
bijection or Sum-to-Ten's repeats-allowed/total-exactly-10 rule — closing gap G7 via
`DECKER_FIXTURE`, whose `B/B/C/C/E` spread is legal Sum-to-Ten and *illegal* Priority. It needed no
new metric key: `Character` carries no build-method field (that's session/save state), so the letter
assignment is asserted by construction plus the explicit Priority-rejection test. Tests live in
`tests/integration/test_synthetic_fixtures.py`.

**WP86 (landed)** retypes `cyberware` from a flat name list to `tuple[str | CyberwarePick, ...]`,
closing the harness half of gap G8. WP73-76 could only buy rating-1, plugin-free leaves; WP38/WP41/
WP42 built purchase *trees*, and the `razorboy.json` save proves players use them. A bare
`"Datajack"` still means what it always did, so those four fixtures' literals are unchanged; a
`CyberwarePick("Cyberears", rating=3, plugins=(...))` says the rest. Declaring a parent's *bundled*
free subsystem (Sound Link, Image Link) is an error rather than a second paid copy — the engine
installs those itself. The new `cyberware:<name path>:capacity_budget`/`:capacity_spent`/
`:capacity_remaining`/`:capacity_cost` keys address one node of the tree by a `/`-separated path of
catalog names, which is what makes "these plugins fill the parent exactly" assertable at all: the
engine only ever checks that they *fit*.

**WP87 (landed)** adds the *spend* side — `gear`, `rating_gear`, `lifestyle`, `karma_converted`,
`contacts`, `knowledge_skills`, `languages`, `karma_knowledge_points` — closing the harness half of
gap G12. Every one of these already had an engine function `build_synthetic()` simply never called,
so a fixture could prove its dice pools were right but not that its *budgets balanced*. They're
wired in `io/save_format.build_character`'s own evaluation order, not a new one: knowledge after
qualities (Bilingual's `NATIVE_LANGUAGE_LIMIT` Improvement must already be on the index), contacts
and Lifestyle before Resources, Resources before cyberware (which now draws from `nuyen_remaining`
rather than the raw priority figure — identical for WP73-76, which buy no gear), and
`create_resources_selection` re-called as each later shared-budget spender becomes known. The
`nuyen:*`, `contacts:*` and `knowledge:*`/`languages:*` metric keys read the results; the two
free-point budgets deliberately read **natural**, not augmented, attributes (p. 95).

## Native save-format fixtures (Phase S / WP85)

`saves/` holds files in **this project's own save format**, kept byte-for-byte as the web UI wrote
them. The first is `razorboy.json` — a Human Sum-to-Ten street samurai built by a player rather than
derived from the implementation plan, which is exactly why it's here: shopping for a *character*
walked it straight through six things the plan's own coverage inventory never enumerated (a cyberware
purchase *tree* with plugins and full Capacity budgets, an Essence floor of 0.10, an augmentation
that raises an attribute, conditional Improvements, the spend side of every budget, and a skill
pushed past the chargen maximum by an Improvement). See `spec/plan/phase-s-test-fixtures.md` §6.

This is the only regression guard the save *format* itself has. Every other save test builds a
`CharacterSave` in code and round-trips it, which can only prove the writer and reader agree with
each other — it cannot catch a change that leaves both self-consistent while breaking a file an
older build already wrote. A checked-in file can, and `tests/integration/test_native_save_fixtures
.py` fails loudly (never skips) if one stops loading.

**Copied, not referenced** — the inverse of the `.chum5` corpus's choice above, for the mirror-image
reason: these files are *ours* and a few KB each, with no upstream source of truth to drift from, so
there is nowhere else for them to live.

### Files

- `native_saves.py` — `NATIVE_SAVE_FIXTURES` (the names), `RAZORBOY_SAVE`, `native_save_path()`
  (name -> path under `saves/`).
- `mundane_chum5.py` — `MUNDANE_FIXTURES` (the 11 names), `PRIORITY_BUILD_FIXTURE` (Yeti),
  `MAGIC_PRIORITY_BUILD_FIXTURES` (Miko, Wesson — WP25), `mundane_fixture_path()` (name -> path
  under `legacy/Chummer.Tests/TestFiles/`, works for any fixture name in the corpus, not just the
  mundane 11). Importable as `tests.fixtures.mundane_chum5` (a PEP 420 namespace package — no
  `__init__.py` needed; `pytest`'s `python -m pytest` invocation, already this project's documented
  workaround for the workspace-path mismatch, puts the repo root on `sys.path`).
- `synthetic.py` — the `SyntheticCharacter` dataclass, `build_synthetic()`, `resolve_metric()`, and
  `assert_fixture()` (WP72); `CyberwarePick`/`cyberware_purchase_request()` (WP86).
- `synthetic_fixtures.py` — the hand-authored `SyntheticCharacter` literals and `SYNTHETIC_FIXTURES`
  tuple (WP72's `REFERENCE_MUNDANE_FIXTURE`, WP73's `STREET_SAMURAI_FIXTURE`, WP74's
  `COMBAT_MAGE_FIXTURE`, WP75's `SHAMAN_FACE_FIXTURE`, WP76's `DECKER_FIXTURE` — Phase S's full
  five-fixture list, all landed).
- This README.
