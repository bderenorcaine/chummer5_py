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

**A gap found after MVP shipped, not a deliberate cut:** Lifestyle selection — SR5's mandatory
"Step Six" line item (core rulebook, p.369: "A character must select one of the lifestyles below to
be their primary Lifestyle"), paid from the same Resources-priority nuyen pool the bullet above
already claims as in scope — is absent from what MVP actually built. It wasn't excluded by any
decision recorded in this document; it was simply missed, discovered during post-MVP scoping. See
Implementation Plan's WP20.

**Explicitly out of scope for MVP (deferred, not abandoned):**
- The general-purpose Improvement engine (full type coverage — cyberware/bioware effects, vehicles,
  matrix rules, most of the ~100+ improvement types the legacy engine supports).
- Magic and Resonance (adepts, magicians, mystic adepts, technomancers) — see above. Magicians and
  physical Adepts are scoped as Implementation Plan's Phase I. Technomancers/A.I. (Resonance) remain
  out of scope indefinitely, not just for MVP; **Mystic Adepts are excluded from Phase I too, by
  explicit product decision (2026-07-19)** rather than deferred smallest-scope pragmatism like every
  other cut on this page — not currently planned at all, not just "later."
- Cyberware, bioware, vehicles, drones, full gear catalog beyond a basic purchase flow. (Cyberware/
  bioware specifically need real Essence tracking as a prerequisite, not just new catalog content —
  see Open Questions below.) Cyberware itself is scoped as Implementation Plan's Phase J (Standard
  grade, flat-cost/flat-essence items only); bioware, vehicles, drones, and non-Standard cyberware
  grades remain deferred past that phase too.
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

**Why `ImprovementIndex` is the one genuinely mutable object in an otherwise-frozen domain model.**
`Character` and every other engine dataclass are `frozen=True` — no field of an existing instance is
ever reassigned. `ImprovementIndex` is the deliberate exception (`add`/`remove_source` mutate
`self._improvements`/`self._index` directly). The line holds up on its own logic, not just as a
mirror of the legacy shape: fields with a *joint, shared-budget constraint* — attribute points
collectively bounded by one priority budget, each individually bounded by a metatype range — belong
in "reconstruct wholesale to validate," since checking one requires knowing the others
simultaneously. Independently-scoped, per-source deltas (a quality's flat bonus, eventually a
cyberware's) don't share that constraint — each is addable/removable on its own, with no reference to
any other Improvement — so a mutable, per-source collection is the right shape there, and making it
immutable too would buy nothing. This is the same "no manual per-field cache invalidation" principle
above, generalized: keep the mutable surface exactly as large as the actual mutation-shaped problem,
and reconstruct everything else. "Frozen," though, doesn't mean "always rebuilt from nothing" — see
the next section for how a `frozen` `Character` actually advances one stage at a time.

### Character as the single aggregate

`Character` (`chummer5.engine.character`) is the one object representing an in-progress character:
metatype and attributes, plus — once each stage is committed — `skill_allocation`,
`quality_selection`, `contact_selection`, and `resources_selection`, all as fields on the same
instance. This wasn't the original shape. Attributes arrived first (WP6), the only thing `Character`
needed to hold at the time; skills, qualities, contacts, and resources (WP7-WP9) each rode in
afterward as independent `ChargenSession` siblings, reunited only ad hoc — for save/load and legacy
import — by a since-retired `BuiltCharacter` wrapper. A design discussion held after the UI MVP
milestone found this split had no rules justification, only a build-order one (nothing about a
quality is conceptually outside "the character"), and WP18 folded everything back onto `Character`
directly. `ChargenSession` (`chummer5.web.session`) now holds only `character` plus the handful of
state that genuinely predates having one — the 4 priority letters, before a metatype is even chosen.

Advancing a committed `Character` one stage — spending more attribute points, picking a quality — is
`dataclasses.replace(character, field=new_value)` wherever the change doesn't require re-deriving
anything else about the character, not always a fresh `create_character()` call. This is more than a
convenience. `replace()` copies every untouched field *by reference*, so a `Character`'s
already-populated `ImprovementIndex` and already-committed selections simply survive a `replace()`
call with nothing to re-link — the "re-apply a quality's Improvement onto a freshly-rebuilt, empty
index" workaround this design needed before WP18/WP19 is now only necessary where a route still
deliberately calls `create_character()` fresh (currently just attribute-point edits — a real,
intentional asymmetry with metatype/priority edits, left for a future WP to unify if it's ever worth
it, not an oversight). Second: `Character` has no `__post_init__` validation — every invariant
(attribute points fit their budget, values fit the metatype's range) is enforced only by
`create_character`'s own checks at construction time — so `replace()`-ing old, now-out-of-budget
values onto a newly reconfirmed metatype/priority selection simply succeeds rather than raising.
Validity is instead re-derived at render time, by re-running the same `create_*` validators that
already exist and reading their error message rather than raising it — a stale selection surfaces a
specific "no longer fits" diagnostic next to the affected section and clears itself automatically the
moment the player edits it back into range, rather than being discarded the moment a priority letter
changes.

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
Improvement engine's shape gets raised as a new entry here before being acted on. The MVP itself
(Phases A-F) shipped without hitting any such entry — everything below was raised afterward, during
a design discussion scoping what comes next (see Implementation Plan's Phase G/H). None of it
blocked or reversed anything already shipped; all three are prerequisites/corrections for work still
ahead.

### 2026-07-18 — Essence is a hardcoded constant; cyberware/bioware need real tracking first, not just new catalog content

`chummer5.engine.derived.BASE_ESSENCE` is a fixed `6`, read in exactly one place (`social_limit`) —
correct for MVP, since nothing in MVP's scope ever reduces Essence (see that module's own docstring
for the full Yeti-fixture trace that led here). Surfaced while scoping cyberware as a candidate
post-MVP expansion: real Essence tracking (a `Character` field plus a `6 - Σ(cyberware/bioware
essence cost)` formula) is a genuine prerequisite for cyberware, not a side effect of adding a
catalog — and it isn't the only one. `chummer5.io.legacy_import` currently hard-*rejects* any
`.chum5` import containing cyberware/bioware specifically because of this gap (tested explicitly),
so that rejection path has to be unwound in the same piece of work, not routed around. Neither is
difficult in isolation, but a cyberware WP needs to land both *before* cyberware content itself, not
alongside it.

### 2026-07-18 — "Talent forced to E" is real plumbing in the web layer, not just an engine default

Confirmed while scoping adept-first magic as a candidate post-MVP expansion. The rules/data side is
close to ready: Adept-eligible Talent letters (B/C/D) already parse cleanly out of `priorities.xml`
with zero changes needed to `chummer5.data.priorities`, and for pure Adepts, Power Points equal the
Magic rating 1:1 (no separate formula to derive). What isn't ready is the assumption, threaded
through `chummer5.web.session`'s letter constants and `chummer5.web.app`'s priority-validation logic
(not just the engine layer), that Talent sits outside the 4 player-chosen priority categories.
Making Talent a real 5th choice touches more existing plumbing than any other post-MVP candidate
surveyed — this is why adept magic, despite having the best-scoped *content* of any candidate (only
6 of 28 SR5 Adept Powers even need new Improvement handling), isn't scoped as the smallest next step.
See Implementation Plan's Phase H intro.

*(A third entry — whether `Character`'s frozen shape should hold every committed selection, not just
attributes — was raised here 2026-07-18 and resolved the same day by WP18/WP19. See "Character as the
single aggregate" under Architecture below for the settled design; entries here stay only while
genuinely open.)*

### 2026-07-19 — Metatype-granted free qualities (Low-Light Vision, Thermographic Vision, Resistance to Pathogens/Toxins) were never modeled

Surfaced by a user question while reviewing WP22. Confirmed via the raw data: `legacy/Chummer/data/
metatypes.xml` grants specific SR5-core qualities for free at character creation via a
`<metatype><qualities><positive>/<negative>` block — Elf and Ork both get Low-Light Vision, Dwarf
gets Thermographic Vision **and** Resistance to Pathogens/Toxins, Troll gets Thermographic Vision;
Human gets none. The legacy engine has a dedicated mechanism for this (`QualitySource.Metatype` —
auto-granted, zero karma cost, excluded from the karma cap, auto-removed if the metatype changes;
`Character.cs` ~line 44348). None of this exists in the new engine: `chummer5.data.metatypes
.Metatype` never parses the base `<qualities>` block at all (only `Metavariant` does, and
metavariants are entirely out of MVP scope), so an Elf/Dwarf/Ork/Troll character built through this
engine today silently gets none of their racial qualities. This also connects to WP22 concretely:
Low-Light Vision/Thermographic Vision are now in the *purchasable* catalog (WP22's `NO_EFFECT`
tranche) with no check preventing a non-Human character from spending karma on something they
should already have for free, and (confirmed separately) `chummer5.io.legacy_chum5.LegacyQuality`
doesn't capture `<qualitysource>` at all, so importing a real Elf/Dwarf/Ork/Troll `.chum5` (5 of the
11 curated mundane fixtures: `BLUE`/Ork, `Blindfire`/Elf, `Gentle Earthquake`/Troll, `Monomax
(approved) 3`/Troll, `Rez0luti0n2.0`/Dwarf) would now misreport their free racial quality as a
karma-costing player pick. Scoped as WP23, next on the Implementation Plan — see that entry for the
fix.

### 2026-07-19 — Magic scoping: two rulings (Mystic Adept out, free-skill grant in), plus the
research each one resolved or required

Surfaced while scoping Phase I (Magicians & physical Adepts) against real data, then settled by two
explicit product decisions the same day.

**Ruling 1 — Mystic Adept is out of scope entirely**, not deferred for size/research-cost reasons
like every other cut in this phase, but simply not being built. This has a convenient technical side
effect: it retires the one piece of research that would otherwise have blocked WP25 outright — a
Mystic Adept's Power Point split (flagged unresolved on 2026-07-18) is a Mystic-Adept-only wrinkle; a
pure Adept's PP is a plain 1:1 Magic-rating grant with nothing to split.

**Ruling 2 — the Talent free-skill grant (`skillqty`/`skillval`/`skilltype`) is in scope**, reversing
WP2's original "out of MVP scope" framing (written when Talent wasn't a real player choice at all).
Reading `SelectMetatypePriority.cs` directly (the legacy form that actually applies this grant) shows
the two `skilltype` values this phase's offered Talent options ever produce are both plain
category/field filters, not a general expression language: `"magic"` (Magician) means "any skill with
`category` in `{Magical Active, Pseudo-Magical Active}`"; `"xpath"` (Adept, letter B only) carries one
specific literal expression — `not(attribute = 'RES' or attribute = 'DEP') and (not(category =
'Magical Active') or skillgroup = '' or not(skillgroup))` — expressible as a plain predicate over
`chummer5.data.skills.Skill`'s existing `attribute`/`category`/`skill_group` fields. Both are
implementable as named, hardcoded predicates (mirroring WP3/WP22's "classify known shapes" method);
no general XPath evaluator is needed for what this phase actually offers. See Implementation Plan's
Phase I intro and WP25 for the full detail, including why neither of the phase's own two real
fixtures can be used to verify the grant's *exact numbers* (Miko's `.chum5` commingles free-grant
points with regular Skills-priority spend in one `<base>` field; Wesson's Talent letter, C, grants no
free skill at all) — the mechanism is verified against the traced legacy C# directly instead.

Unrelated to either ruling, still true and unchanged: confirmed against both of the corpus's only
magic-capable `buildmethod = Priority` fixtures (`Miko.chum5`, an Elf Magician; `Wesson.chum5`, a
Human Adept), the Magic rating is **not** funded from a priority-derived points budget the way EDG
is — the chosen Talent option's `magic` field (`chummer5.data.priorities.TalentOption.magic`) *is*
the finished MAG rating outright. Adding `"MAG"` to
`chummer5.engine.character.SPECIAL_ATTRIBUTES` (EDG's shape) would silently misimplement this.

### 2026-07-19 — Cyberware scoping: 8 of the 11 curated "mundane" fixtures already carry real
cyberware, and their stored Essence costs are usually unresolved rating formulas, not numbers

Surfaced while scoping Phase J (Cyberware) against real data. `tests/fixtures/README.md`'s definition
of "mundane" has only ever been `<magenabled>False</magenabled>` — never "augmentation-free." Checked
directly: `BLUE`, `Barrett`, `Bastion`, `Blindfire`, `Fuzzy-chargen`, `Gentle Earthquake`,
`Monomax (approved) 3`, and `SCSi` (8 of the 11 WP4-curated fixtures) each carry between 3 and 16 real
`<cyberwares>` entries. This is not a latent bug — every derived-stat test that exists today already
worked around it correctly rather than by accident (`test_cross_corpus_attribute_value_matches_when_
unaugmented` explicitly skips cyberware-boosted attributes; `social_limit`, the one Essence-dependent
derived stat, is only ever asserted against real fixture data via `Yeti-#ffffff2.chum5` specifically,
which has zero cyberware) — but it means Phase J inherits real, ready-to-use fixture coverage for
Essence math well beyond what a from-scratch catalog WP would normally get.

That coverage comes with a caveat, though: a fixture's per-item `<ess>` field is frequently the source
catalog's *unresolved* rating formula (e.g. `Rating * 0.3`, `FixedValues(2,3,5)`), not a resolved
number — the legacy engine evaluates it at read time rather than storing a resolved value per
purchase. Only a modest, specific subset of real purchases across these 8 fixtures (Datajack, the
Cyberlimb variants, Smartlink, Bone Lacing (Titanium)) are flat-cost/flat-essence items unaffected by
this. See Implementation Plan's Phase J intro and WP31-33 for the resulting catalog cut and its
honest acceptance-criteria caveat (full `<totaless>` reproduction against these fixtures is not a
realistic bar for Phase J alone).

### 2026-07-19 — Essence-driven Magic loss is a real interaction between Phase I and Phase J, deferred
to a dedicated WP because neither phase's fixtures can exercise it

SR5 reduces a magically active character's Magic (or Resonance) rating as Essence is lost to
cyberware/bioware. This connects Phase I (Magicians & physical Adepts) and Phase J (Cyberware)
directly, but no fixture in the 34-file corpus is simultaneously Priority-built, magic-enabled, and
cyberware-bearing, so the interaction can't be validated against real data from either phase alone.
Scoped as Phase J's WP35, deliberately sequenced after both phases' own engine work rather than
folded into whichever phase happens to land first.

### 2026-07-19 — Adept Drain is real: Drain Resistance is not Magician-only, and one Adept Power
(Attribute Boost) was nearly misclassified as a permanent flat bonus

A user question ("adepts might have to roll drain, since several adept powers are active rather than
passive, e.g. Attribute Boost") caught a wrong assumption already written into Phase I before any
code existed. Checked directly against the rulebook via `pdftotext -layout` (p.309): "Adept Drain:
Some powers cause Drain. The Drain from adept powers is Stun unless specified in the description, and
is resisted with Body + Willpower" — a real, named rule, structurally different from a Magician's
tradition-dependent Drain (which resists with a tradition-chosen attribute pair instead). Two of the
28 SR5 Adept Powers actually trigger it: Adrenaline Boost and Attribute Boost, both `NOT_YET_SUPPORTED`
in Phase I's classifier (their effects require in-play test resolution this engine's combat-free scope
doesn't model) — but Drain Resistance itself is still a real, cheaply-computable derived stat for any
Adept, using the fixed BOD+WIL formula, independent of which specific powers were bought (the same way
Physical/Mental/Social Limit are shown regardless of build specifics). Corrected in Implementation
Plan's WP28.

The same check surfaced a second, sharper find: `cyberware.xml`-style raw-XML inspection showed
Attribute Boost's `<bonus><selectattribute>` node has the *identical* child tag as Improved Physical
Attribute's — but no `<val>` child, because Attribute Boost's real magnitude comes from an in-play
Magic + Rating Test, not a fixed formula. A classifier keyed on "`selectattribute` bonus == flat
attribute bonus" (a direct, reasonable-looking generalization of `chummer5.data.qualities`'s own
`_is_flat_attribute_bonus` shape) would have silently applied Attribute Boost as a permanent stat
increase. Caught before any code was written; see Implementation Plan's WP27 for the corrected
classifier rule (presence of a `<val>` child is the real discriminator) and the broader finding it
led to — every Adept Power's bonus value is the literal token `"Rating"`, not a hardcoded int the way
every quality's `FlatBonus` value already is, so WP27's applier needs a rating-resolution step
`chummer5.data.qualities` never needed.
