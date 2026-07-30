# Implementation Plan

Companion to [Project Overview.md](Project%20Overview.md). This is the execution roadmap: a sequence of
work packages (WPs) from an empty `src/` to a headless MVP, then to the FastAPI/HTMX UI for that MVP, and
on through post-MVP phases.

**This file is an index, not the plan itself (as of WP57/Phase Q).** Each phase's own WP entries live in
`spec/plan/phase-<letter>-<slug>.md` — open only the phase file(s) relevant to the work at hand, not every
phase in the project's history. This file keeps only what's genuinely cross-cutting: how to use the plan,
the notes below that more than one phase depends on, the repo layout, and the phase index table.

## How to use this plan

- Each WP is scoped for **one agent conversation** and ends in **one git commit** referencing its number
  (e.g. `WP6: metatype selection and attribute allocation`).
- A WP's entry in its phase file, plus this file's cross-cutting notes and `Project Overview.md`, should
  be enough context for a fresh conversation to execute it cold — no dependency on any particular prior
  conversation's memory, and no need to read other phases' files unless a WP's own "Depends on" line points
  at one.
- A WP is done when: its acceptance criteria pass, `pytest` is green repo-wide, and the checkbox in its
  phase file is ticked (as part of that WP's commit).
- Don't start a WP mid-conversation if there isn't realistically enough context budget left to finish it
  cleanly — hand off to a fresh conversation instead of producing a rushed or half-finished package.
- Adding a new phase: give it its own `spec/plan/phase-<letter>-<slug>.md` file (see Phase Q/R/S for the
  research-intro pattern when a phase needs scoping before its WPs can be written), and add one row to the
  phase table below.

## Notes that shape the plan below

**The legacy `.chum5` test corpus is a weaker regression oracle than "34 golden files" suggests.** Of the
34 fixtures in `legacy/Chummer.Tests/TestFiles/`, only **11 are mundane** (no magic/resonance), and of
those, only **one** (`Yeti-#ffffff2.chum5`) uses `buildmethod = Priority` — the other 33 use `SumtoTen`,
a different chargen method that's out of MVP scope. Resolution: the 11 mundane fixtures (any build method)
validate **build-method-agnostic** formulas (attribute totals, skill dice pools, derived stats) — those
values are legacy-computed truth regardless of how the points were bought. Only `Yeti-#ffffff2.chum5`,
plus a handful of hand-authored cases checked directly against `priorities.xml`, validate the
**priority-table allocation logic** itself. (Phase S is a 2026-07-24 research pass into whether this
corpus can realistically grow at all — see `spec/plan/phase-s-test-fixtures.md`.)

**MVP content scope = the SR5 core rulebook, checked via each data file's `<source>` tag.**
Discovered during WP2: legacy data files span many sourcebooks, and almost every entry (metatype,
metavariant, quality, skill, ...) carries a `<source>` tag identifying which one. MVP restricts to
`source == "SR5"` uniformly — this is what "mundane... core-rulebook math" in the Project Overview
concretely means at the data layer, not just a metatype-specific rule. Verified counts:
`metatypes.xml` → 5 of 21 (`Metahuman` category base types: Human, Elf, Dwarf, Ork, Troll; this
also excludes every metavariant, since all of them are non-`SR5`-sourced); `qualities.xml` → 96 of
803; `skills.xml` → 76 of 76 (no filtering needed, already all core). Any WP whose loader offers a
list of choices to the player (metatypes, qualities, and by extension gear/priorities content
later) needs this filter; see the SR5-scope clauses in `spec/plan/phase-b-static-rules-data.md`
(WP3) and `spec/plan/phase-d-core-engine.md` (WP6).

**Quality `<bonus>` nodes are a mini-language, not a single field.** `qualities.xml` bonus nodes range
from trivial (`<ambidextrous/>`) to nested value-bearing tags, mirroring the general Improvement bonus
grammar the legacy engine parses. MVP does not implement that general parser — WP3/WP8 curate a small
supported subset (flat attribute/skill bonuses) and exclude qualities using anything else from the
MVP-offered quality list, rather than silently ignoring their mechanical effect. WP22
(`spec/plan/phase-h-content-expansions.md`) widens this subset with a precisely-verified list of what
else is safely offerable and what still isn't.

**Post-MVP scoping (Phase G/H) surfaced two hidden dependencies worth knowing before touching either
area.** Cyberware needs real Essence tracking as a prerequisite — today a hardcoded constant
(`chummer5.engine.derived.BASE_ESSENCE`) — not just new catalog content; adept magic needs unwinding
"Talent forced to E" across the web/session layers, not just engine data. Full detail in
`spec/decisions-log.md`'s 2026-07-18 entries and in `spec/plan/phase-h-content-expansions.md`'s own
intro. Neither blocks any WP currently on this list, which deliberately steers around both areas.

## Repo/package layout (established in WP1)

```
chummer5_py/
  legacy/            (unchanged)
  spec/
    Implementation Plan.md   (this file — index)
    Project Overview.md
    decisions-log.md
    plan/            # per-phase WP entries
    rulebooks/
      learnings.md    (index)
      learnings/      # per-phase rulebook-citation entries
      character_creation_chapter.md
    worklogs/         # per-WP retrospective detail
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

## Phases

| Phase | Focus | Status | File |
|---|---|---|---|
| A | Foundation | done (WP1) | [phase-a-foundation.md](plan/phase-a-foundation.md) |
| B | Static rules data | done (WP2-3) | [phase-b-static-rules-data.md](plan/phase-b-static-rules-data.md) |
| C | Regression fixture harness | done (WP4) | [phase-c-fixture-harness.md](plan/phase-c-fixture-harness.md) |
| D | Core engine (headless) | done (WP5-10) — **Headless MVP milestone** | [phase-d-core-engine.md](plan/phase-d-core-engine.md) |
| E | Save/load | done (WP11-12) | [phase-e-save-load.md](plan/phase-e-save-load.md) |
| F | FastAPI/HTMX UI | done (WP13-17) — **UI MVP milestone** | [phase-f-web-ui.md](plan/phase-f-web-ui.md) |
| G | Chargen state-model refinement | done (WP18-19) | [phase-g-state-refinement.md](plan/phase-g-state-refinement.md) |
| H | Smallest-scope content expansions | done (WP20-23) | [phase-h-content-expansions.md](plan/phase-h-content-expansions.md) |
| I | Magic (Magicians & Adepts) | done (WP24-29) | [phase-i-magic.md](plan/phase-i-magic.md) |
| J | Cyberware | done (WP30-35) | [phase-j-cyberware.md](plan/phase-j-cyberware.md) |
| K | Cyberware modifications (Capacity, subsystems, conditional bonuses) | in progress (WP36-40 done) — off hold as of 2026-07-29, WP41-42 not started | [phase-k-cyberware-mods.md](plan/phase-k-cyberware-mods.md) |
| L | Easy wins (Karma-to-Nuyen, Sum-to-Ten, Bioware) | done (WP43-45) | [phase-l-easy-wins.md](plan/phase-l-easy-wins.md) |
| M | Magic expansion (Bound Spirits, Foci, Mentor Spirits) | done (WP46-48) | [phase-m-magic-expansion.md](plan/phase-m-magic-expansion.md) |
| N | Expanded skill support (Knowledge/Language, specializations) | done (WP49-50) | [phase-n-skill-support.md](plan/phase-n-skill-support.md) |
| O | Karma-buying (chargen-time leftover-Karma spend) | done (WP51-56) | [phase-o-karma-buying.md](plan/phase-o-karma-buying.md) |
| P | Rigger support | research-intro only, no WPs assigned | [phase-p-rigger-support.md](plan/phase-p-rigger-support.md) |
| Q | Spec reorganization (phase-cut point) | done (WP57) | [phase-q-docs-reorg.md](plan/phase-q-docs-reorg.md) |
| R | Architecture cleanup / refactoring | done (WP58, WP62-63) | [phase-r-architecture-cleanup.md](plan/phase-r-architecture-cleanup.md) |
| S | Test fixture expansion | done (WP59, WP72-76) — fixture list complete | [phase-s-test-fixtures.md](plan/phase-s-test-fixtures.md) |
| T | UI bugfixes & skill-picker QoL | done (WP60-61) | [phase-t-ui-bugfixes.md](plan/phase-t-ui-bugfixes.md) |
| U | UI bugfixes round 2 | done (WP64-66) | [phase-u-ui-bugfixes-2.md](plan/phase-u-ui-bugfixes-2.md) |
| V | UI improvement requests | scoped, WP67-71 not started | [phase-v-ui-improvements.md](plan/phase-v-ui-improvements.md) |

Next unclaimed WP number: **WP77** (see Phase P's own file for why WP57-59 were claimed; Phase T
claimed WP60-61 on 2026-07-24; Phase R's own WP58 audit claimed WP62-63 on 2026-07-27; Phase U/V
claimed WP64-71 on 2026-07-27 from a second manual-testing pass — see those phase files for scope;
Phase S's WP59 research pass claimed WP72-76 on 2026-07-29 for its synthetic-fixture WP list).
