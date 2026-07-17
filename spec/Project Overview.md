# Chummer5 Python — Project Overview

## What this is

A from-scratch Python reimplementation of [Chummer5a](https://github.com/chummer5a/chummer5a), the
Shadowrun 5E character creation and campaign management tool. The original is a mature (10+ year),
community-maintained WinForms/.NET Framework application, preserved in this repo under [legacy/](../legacy)
for reference. This is a personal project, not a contribution to the upstream Chummer5a project.

## Why

The legacy application is:
- **Windows-bound.** WinForms + .NET Framework 4.8 means Linux/macOS users are stuck with Wine, CrossOver,
  or a VM — none of which are attractive as a daily-driver setup.
- **Slow in ways that trace back to architecture, not just bugs.** See [Performance lessons](#performance-lessons-from-the-legacy-app)
  below — this isn't "needs a profiler pass," it's "several load-bearing design decisions fight performance
  by construction."

The goal is a tool that does the same job — build and manage an SR5 character — as a local web app that
runs anywhere Python and a browser run.

## Relationship to the legacy codebase

`legacy/` is kept, not deleted, because it's genuinely useful for three things:
1. **Rules reference.** When the new engine needs to know exactly how a derived stat is computed, the
   legacy C# is the executable spec.
2. **Game data.** `legacy/Chummer/data/*.xml` (+ matching `.xsd`) is the actual SR5 ruleset — metatypes,
   priorities, qualities, gear, etc. — already decoupled from code. The new project parses these files
   directly rather than re-entering rules content. These files span many sourcebooks; almost every
   entry carries a `<source>` tag identifying which book it's from (e.g. `SR5`, `RF`, `DT`). See
   "Core rulebook only" under MVP scope below for how this gates what MVP actually loads/offers.
3. **Regression oracle.** `legacy/Chummer.Tests/TestFiles/*.chum5` is a corpus of real, legacy-computed
   characters. The new engine's output gets diffed against these to catch silently-wrong rules logic —
   this matters more than it sounds like it should, because an AI-agent-assisted port of unfamiliar
   business logic will otherwise happily produce plausible-but-wrong numbers.

`spec/rulebooks/Shadowrun_Fifth_Edition_Core_Rulebook.pdf` is also kept as the authoritative rules
*text* — used to resolve cases where the data/code alone don't make intent obvious (e.g. which
direction a metatype/magic eligibility rule actually runs).

**License:** the legacy project is GPLv3. Because this project reuses its data files, rules logic, and
test fixtures, it is a derivative work and is GPLv3 too. Not a decision point — inherited.

## Goals

1. Priority-based character creation with correct SR5 core-rulebook math, verified against legacy output.
2. Cross-platform: no Windows, no Wine, no VM. Runs as a local web app.
3. Fast by construction — see the architectural lessons below, not a "fix it later" item.
4. Maintainable by one person with AI-agent assistance: favor explicit, small-surface-area, testable code
   over cleverness. Optimize for "an agent unfamiliar with this session can pick up a module and get it
   right," not for minimal line count.
5. English only for now, but structured so translation is an addition, not a retrofit.

## MVP scope

**In scope:**
- Priority-based chargen only: metatype priority, attribute priority, skill priority, resources priority.
- **Mundane characters only.** No magic/resonance priority (no adepts, mages, technomancers) in MVP —
  a mundane priority build already exercises the full engine shape end-to-end (priorities → attributes/
  skills/qualities → derived stats) without also requiring spell/program selection, tradition choice, or
  drain/fading. Magic/resonance is the first fast-follow after MVP, not a "someday".
  This means that, in order to obtain valid characters in MVP, the effect of "no magic/resonance priority" must be modeled as "magic/resonance priority forced to E (mundane)", i.e. the only available priorities for the other aspects are A, B, C, and D.
  (Rules note for that later work: metatype, not the other way around, governs Magic/Resonance
  eligibility — most metatypes are simply *eligible* to buy Magic via a Talent priority letter,
  a few are inherently magical and start with Magic forced ≥1 regardless of Talent choice, and a
  few can never access Magic at all. This only matters once magic/resonance chargen exists — every
  metatype in MVP's scope, per the "Core rulebook only" rule below, falls in the plain-eligible
  bucket, which is exactly why forcing Talent to E is sufficient to get mundane characters in MVP
  without needing any metatype-specific handling.)
- **Core rulebook (SR5) content only.** Beyond "mundane," MVP further restricts every data-driven
  choice (metatype, quality, ...) to entries sourced from the SR5 core rulebook — checked via each
  data file's per-entry `<source>` tag. Concretely: `metatypes.xml`'s `Metahuman` category has 5
  `source=SR5` base types (Human, Elf, Dwarf, Ork, Troll); every metavariant (Nartaki, Gnome, ...)
  and every non-`Metahuman` metatype (Centaur, Sasquatch, A.I., Shapeshifters, ...) is sourced from
  a later book and is out of MVP scope. `qualities.xml` similarly narrows from 803 entries to 96
  `source=SR5` ones. `skills.xml`'s 76 entries are all `source=SR5` already, so no filtering is
  needed there. This is a general MVP-scope filter every data loader should apply, not a
  metatype-specific rule.
- Attributes, active skills (+ specializations, skill groups), positive/negative qualities (karma cost
  and limits), contacts, starting nuyen/resources spent on a basic gear purchase.
- Derived stats needed to validate a freshly created character: attribute totals, skill dice pools,
  initiative, limits, condition monitors.
- A minimal subset of the Improvement mechanism — only what priority chargen actually triggers (metatype
  bonuses, quality bonuses, priority-derived bonuses). See [Improvement engine](#improvement-engine-design)
  below for why this can't be "zero."
- Save/load in a new, native format (see [Data & save format](#data--save-format)).
- Web UI (local, single-user, no auth) as the only supported interface.
- All user-facing strings routed through an i18n key layer from day one, even though only English ships.

**Explicitly out of scope for MVP (deferred, not abandoned):**
- The general-purpose Improvement engine (full type coverage — cyberware/bioware effects, vehicles,
  matrix rules, most of the ~100+ improvement types the legacy engine supports).
- Magic and Resonance (adepts, magicians, mystic adepts, technomancers) — see above.
- Cyberware, bioware, vehicles, drones, full gear catalog beyond a basic purchase flow.
- Career mode (post-chargen karma spending, character aging over time).
- Plugins.
- Localization content (structure only, per above).
- Multi-user / hosted deployment, anything resembling ChummerHub.

## Architecture & major design decisions

### Stack
- **Python**, targeting a recent 3.x (specifics TBD when scaffolding — low switching cost, not a blocking
  decision).
- **FastAPI + server-rendered HTML (Jinja2) + HTMX** for the UI. Chosen over a pure-Python UI library
  (binds you to that library's widget model) and over a full SPA (React/Svelte + TypeScript — doubles
  the language/toolchain surface for a solo, agent-assisted maintainer). Chargen is fundamentally a
  forms-and-computed-values app; HTMX's partial re-renders cover the dynamic bits (live totals, dependent
  dropdowns) without a JS build pipeline.
- **pytest** for testing, with the legacy `.chum5` corpus as golden-output fixtures.

### Rules engine first, UI last
Build and validate the domain/rules layer headless — driven by pytest against golden `.chum5` outputs —
before writing UI code. The UI is a thin layer over a rules engine that must already be correct on its own.

### Data & save format
- Game rules data (`data/*.xml`) is parsed once at startup from the legacy files into indexed Python
  structures. Not re-entered, not queried live via XPath per UI action.
- The new app uses its **own save format** (not legacy `.chum5`). Legacy `.chum5` files are supported as
  **read-only import** — enough to bring a character in and to use the test corpus directly as fixtures —
  but the app never needs to reproduce legacy XML schema quirks for features it hasn't built yet. This was
  a deliberate trade against full bidirectional compatibility, which would require schema fidelity for
  Improvements/cyberware/etc. this project doesn't have.

### Improvement engine design
The legacy model — confirmed by reading the C# — is: every derived value (`attribute.Value`,
`skill.Pool`, etc.) equals a base term plus the sum of whatever `Improvement` records currently target it.
Each `Improvement` carries: its source (what granted it, and that specific instance's id, so removing the
source cleanly removes its improvements), a target key (what aspect it affects), a value/rating, an
optional dedup group (`UniqueName`, for SR5's "highest bonus wins" stacking rules), and an optional
condition. The new engine keeps this shape but changes *how it's evaluated*, based directly on where the
legacy app's performance problems live:

- **Conditions compile to typed predicates once, at construction** — not re-parsed from a string
  (regex + reflection) on every read. This is the single biggest identified perf/complexity cause in the
  legacy engine (`ImprovementManager.ValueOf` has 465 call sites, each capable of re-triggering condition
  evaluation).
- **Improvements are stored in an index** — `dict[(ImprovementType, target)] -> list[Improvement]` —
  rebuilt on mutation. Resolving a value is a lookup + sum + dedup-by-`UniqueName`, not a scan.
- **No manual per-field cache invalidation.** The legacy app clears cache entries individually on every
  field mutation of every `Improvement`. The new design recomputes the (cheap, character-sized) index on
  add/remove instead. Add caching only if profiling actually shows it's needed — the legacy caching
  complexity exists to offset reflection/regex overhead that doesn't exist in this design to begin with.

### Performance lessons from the legacy app
Concrete, code-grounded findings (not general "Windows is slow" hand-waving) that this project deliberately
designs away from:
1. **Improvement conditions re-evaluated at read time via regex + reflection**, not resolved once —
   see Improvement engine design above.
2. **Fine-grained but scan-heavy caching**: any cache miss re-scans the character's full improvement list;
   every mutation independently invalidates cache entries. Death by a thousand small cuts rather than one
   bottleneck.
3. **UI-tree-walking localization**: every form load recursively walks the entire control tree
   (100+ controls on non-trivial forms) and reflects into each one to set translated text, marshaled
   through the UI thread. A web UI with a normal i18n library (dictionary lookup at render time) avoids
   this class of problem by construction — one of the reasons "web UI" isn't just a portability choice
   here, it's also a performance one.

### Development environment
Development happens inside a Podman-backed VS Code devcontainer (`.devcontainer/`), not directly on the
host. The host machine for this project is Bazzite, an immutable/atomic OS not meant for ad hoc package
installs — `pip install --break-system-packages` or similar host mutations are avoided by construction,
not by discipline. The devcontainer defines the actual toolchain (Python, `uv`); reopening the workspace
in it relocates the whole VS Code extension host — including agent sessions — into the container, so this
isn't just a CI convenience, it's how day-to-day (and agent-driven) development happens here.

**Stale `.venv` console scripts.** `.devcontainer/devcontainer.json` pins `workspaceFolder` to
`/workspace`. If a session ever ends up with the repo checked out at a *different* absolute path
(seen in some agent-harness sessions, not a real "Reopen in Container" flow), `.venv/bin/{pytest,
ruff,mypy}` — small scripts with a `#!/workspace/.venv/bin/python`-style shebang baked in at
`uv sync` time — fail with a misleading `No such file or directory` even though the file is right
there. Two fixes, in order of preference:
1. Invoke tools as `uv run python -m pytest` / `-m ruff` / `-m mypy` instead of the bare command —
   this runs the venv's `python` (a symlink, not a shebang script, so it isn't affected) with `-m`,
   sidestepping the stale shebang entirely. Prefer this form generally, since it's a strict superset
   of the bare-command case.
2. If something still doesn't work, regenerate the venv (`.venv/` is gitignored, so this is always
   safe): `rm -rf .venv && uv sync --group dev`.

### Testing strategy
- `legacy/Chummer.Tests/TestFiles/*.chum5` (34 real characters) used as golden-output regression fixtures:
  build the same character (metatype/priorities/qualities/skills) through the new engine, diff computed
  values against what's recorded in the legacy save.
- Legacy unit tests (`legacy/Chummer.Tests/*.cs`) ported as intent, not mechanically translated — they
  encode expected numeric outcomes for specific rules edge cases worth keeping as pytest equivalents.
- `legacy/` is kept buildable as a reference/oracle; it does not need to run day-to-day.

## Open questions

None blocking MVP start as of this writing — the three foundational calls (UI stack, save-format strategy,
MVP magic/resonance scope) are made above. Smaller implementation-level decisions (exact Python version
floor, dependency/packaging tool, pydantic vs. plain dataclasses for the domain model) are treated as
low-cost-to-change defaults to be set when scaffolding the project, not spec-level rulings.

Anything discovered during implementation that materially changes scope, data compatibility, or the
Improvement engine's shape gets raised as a new entry here before being acted on.
