[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase S — Post-MVP: Test fixture expansion (research-intro; WP60 onward pending its own strategy pass)

**Why now.** Raised in the same 2026-07-24 session as Phase Q. The project's regression oracle has
been the same fixed 34-file `legacy/Chummer.Tests/TestFiles/` corpus since WP4, and it is thin in a
way that's been re-flagged by nearly every phase since: only **3 of 34** fixtures are
`buildmethod = Priority` at all — `Yeti-#ffffff2.chum5` (mundane), `Miko.chum5` (Elf Magician),
`Wesson.chum5` (Human Adept) — and each backs exactly one phase's own content in isolation. No
fixture is simultaneously magic-enabled *and* cyberware-bearing (Phase J's WP35 note), none exercises
the Cyber Implant Weapon → Weapon Accessory two-level nesting case Phase K's own intro flags as
undecided, and Phase M/N/O's worklogs repeatedly fall back to "hand-verified, no fixture" for content
the corpus simply never happens to contain. The corpus can't grow on its own — it's a fixed snapshot
of real characters, not a generator — so more coverage has to come from somewhere else.

**Checked this session, load-bearing for how this phase should be scoped: no .NET toolchain is
available in this devcontainer.** `which dotnet mono` returns nothing, and
`legacy/Chummer.Tests/Chummer.Tests.csproj` is an old-style `packages.config` project (pre-SDK-style),
making a from-scratch build meaningfully harder than a modern `dotnet build` even if a runtime were
installed. **This means "drive the actual legacy engine to generate new golden `.chum5` fixtures for
hand-designed synthetic characters" — the highest-fidelity option, since it would produce real
legacy-computed truth instead of hand-computed truth — is very likely not viable here**, though this
needs confirming (not just inferring from a missing binary) before being ruled out, since a
prior-session environment might differ. If it's genuinely not viable, the realistic path is
hand-authored synthetic fixtures cross-checked directly against the rulebook (the same rigor this
project already applies to "hand-authored cases checked directly against `priorities.xml`" for WP6,
and to every `pdftotext -layout`-sourced formula in `learnings.md`) rather than against legacy output.

- [x] **WP59 — Fixture-strategy research pass: confirm the legacy-toolchain question, inventory real
  coverage gaps, and decide a fixture-authoring mechanism before writing any new fixtures.**
  Goal: settle *how* new fixtures get created (legacy-engine-generated vs. hand-authored-and-cited)
  and *what* they should cover, before committing engine-content WPs to either path.
  Deliverables:
  - Definitively confirm whether any environment available to this project (this devcontainer, or a
    documented one-off outside it) can build and run `Chummer.Tests` headlessly to produce a new
    `.chum5` for a synthetic character definition. If yes, prototype the smallest possible case (one
    new mundane character) end to end before assuming the path scales. If no, document why concretely
    (missing runtime confirmed, or a real build failure — not just "seems unlikely").
  - Inventory concrete coverage gaps by phase, cross-checking the "hand-verified, no fixture" and
    "no fixture exercises X" call-outs already scattered across `Implementation Plan.md`'s phase files
    and `learnings.md` (e.g. Phase K's two-level cyberware nesting, Phase J's Essence+Magic
    interaction now covered by WP35 but only via hand-derived cases, any Sum-to-Ten build combined
    with magic or cyberware) rather than guessing at what's missing from scratch.
  - Decide and document the fixture format for whichever mechanism wins: a new `.chum5`-shaped file
    (if legacy-generated) slotting into the existing `tests/fixtures/` + `mundane_chum5.py`-style
    registry, or a lighter synthetic-input format (e.g. a small dataclass/JSON literal plus its
    hand-derived expected values and rulebook citations) if hand-authored — mirroring how synthetic
    data already proves engine primitives in isolation (WP5's Improvement resolution tests, WP30's
    Essence tests) before this phase decides whether that pattern extends to whole-character fixtures
    or stays primitive-scoped.
  - Produce the resulting fixture-authoring WP list (numbers, scope, which gaps each closes) as an
    addition to this phase file, the same way Phase K's own intro was scoped before WP36-42 were
    written.
  Depends on: nothing new.
  Acceptance: `pytest`/`ruff`/`mypy` untouched and green (research only, no source/fixture changes
  yet); this phase file updated with a concrete WP60+ breakdown, the legacy-toolchain question
  answered definitively (not left open), and each proposed new fixture tied to a specific,
  currently-real gap rather than speculative future-proofing.

---

## WP59 findings (2026-07-29)

Full retrospective in `spec/worklogs/WP59.md`; the load-bearing conclusions and the resulting WP
breakdown are recorded here so a future WP can act on them without re-deriving.

### 1. Legacy-toolchain question — answered definitively: **not viable, for two independent reasons.**

The 2026-07-24 intro above hedged this as "very likely not viable ... needs confirming." It is now
confirmed, and one of the intro's premises turned out to be wrong in a way that doesn't change the
verdict:

- **The environment has no .NET/Mono toolchain and can't easily get one.** `dotnet`, `mono`,
  `msbuild`, `nuget`, `curl`, and `wget` are all absent. The `~/.dotnet/corefx` directory the intro
  didn't know about is a red herring — it holds only a cryptography CRL cache
  (`~/.dotnet/corefx/cryptography/crls/*.crl`), not a runtime. Network *is* reachable
  (`urllib` reaches `download.mono-project.com`), but `apt-get install mono-complete` fails with
  "Unable to locate package" — Mono isn't in the configured repos, so installing it would mean adding
  a third-party repo + GPG key by hand, for a runtime whose WinForms support is incomplete anyway.
- **Correction to the intro: `Chummer.Tests.csproj` is SDK-style, not `packages.config`-era.** It
  opens with `<Project Sdk="Microsoft.NET.Sdk">`. But this doesn't help: it targets `net48` with
  `<UseWindowsForms>true</UseWindowsForms>`, references `WindowsBase`, and — the real blocker —
  `<ProjectReference Include="$(SolutionDir)Chummer\Chummer.csproj" />`, i.e. it pulls in the **entire
  WinForms Chummer application**. The .NET SDK on Linux cannot build a `net48` + WinForms target; that
  needs Windows or Mono, and Mono building the full 100+-form Chummer app headlessly is a long shot
  even with a runtime installed.
- **Even if it built, it would not produce new golden fixtures.** This is the finding that closes the
  door regardless of toolchain: `ChummerTest.cs`'s tests (`Test02_LoadCharacters`,
  `Test03_SaveAsChum5lz`, `Test04_LoadThenSaveIsDeterministic`, `Test05_LoadThenPrint`) only
  **load and round-trip the existing `.chum5` files** in `TestFiles/`. There is no code path that
  takes a synthetic chargen definition (metatype + priorities + skill/quality/gear picks) and *emits*
  a computed character. Producing a genuinely new legacy-computed character requires driving the
  actual WinForms chargen forms interactively (realistically Windows-only) or writing fresh C# harness
  code against the chargen engine — reverse-engineering the very WinForms codebase this project exists
  to avoid. So "legacy-engine-generated fixtures" is off the table on the merits, not just for want of
  a compiler.

**Consequence for the format decision:** hand-authoring fake `.chum5` files is *rejected* — a `.chum5`
whose derived values were hand-computed (not legacy-computed) is strictly worse than an honest
synthetic fixture, because it wears the costume of legacy ground truth while being exactly as
hand-derived. New fixtures are hand-authored **in a native synthetic format** (below), cross-checked
against the rulebook/`priorities.xml`/legacy C# with the same rigor already applied to every
`pdftotext`-sourced formula in `learnings.md`.

### 2. Coverage-gap inventory (each tied to an existing, currently-real call-out)

The corpus's structural thinness (3 of 34 Priority-built; only `Yeti-#ffffff2` mundane-Priority) means
every *interaction between subsystems* is untested by real fixtures — the unit tests exercise each
mechanism in isolation, but no whole-character fixture combines them. Concrete gaps, with their source
call-out:

| # | Gap (interaction no real fixture exercises) | Currently-real call-out |
|---|---|---|
| G1 | Priority-built character bearing **cyberware** — Essence computed from real implants in a priority build | `phase-j-cyberware.md:150` (WP33 acceptance), Phase J WP35 |
| G2 | **Cyberware + bioware** Essence costs stacking against the one shared pool | `phase-l-easy-wins.md:119` (WP45); `learnings/phase-l.md:143` |
| G3 | **Magic-enabled + cyberware** together: Essence loss reducing Magic rating | `phase-j-cyberware.md:45-47` (phase intro) |
| G4 | Step-Seven **leftover-Karma** spend on skills/groups (group-breaking) + specializations | `learnings/phase-o.md:152`; `phase-o-karma-buying.md:134` (WP53) |
| G5 | Step-Seven leftover-Karma spend on **extra spells** beyond the free Talent budget | `learnings/phase-o.md:186` (WP52) |
| G6 | **Bound Spirits / Foci / Mentor Spirits** on a magician build | `phase-m-magic-expansion.md:54,96,132` (WP46/47/48) |
| G7 | **Sum-to-Ten** allocation logic combined with a magic or cyberware layer | `phase-l-easy-wins.md:77`; `learnings/phase-l.md:118` (WP44) |

Explicitly **not** given a fixture WP here: Phase K's Cyber Implant Weapon → Weapon Accessory
two-level nesting (Phase K is on hold, WP36-42 unstarted — no engine code to test against yet). It
stays on this list as blocked-on-K, not scheduled.

### 3. Fixture-authoring mechanism & format (decided)

**Mechanism: a synthetic whole-character fixture harness that drives the real engine.** Each fixture is
a Python literal describing the full chargen input, fed through the actual public engine API
(`create_character()` + the skill/quality/cyberware/bioware/magic/karma selection functions the web
routes already call), with a companion table of **hand-derived expected derived values, each carrying
an inline rulebook/`priorities.xml`/legacy-C# citation**. This is the WP5/WP30 synthetic-primitive
pattern (`test_improvements.py`, Essence unit tests) extended from "one mechanism in isolation" to
"one whole character exercising an interaction," which is exactly the axis the real `.chum5` corpus
can't cover. It lives beside the existing `.chum5` registry under `tests/fixtures/`, not in place of it
— the 11-file legacy corpus stays the ground truth for build-method-agnostic derived-stat formulas;
synthetic fixtures cover interactions the corpus structurally lacks.

**Format:** a small frozen `SyntheticCharacter` dataclass (priorities, metatype, attribute allocation,
skill/group allocation, qualities, cyberware, bioware, magic selections, karma spend — all optional so
a fixture declares only what it exercises) plus an `expected: dict[str, <value>]` of hand-derived
targets and a `citations: dict[str, str]` mapping each expected key to its source. **Not** a fake
`.chum5` (see §1). The harness `build_synthetic(fixture) -> Character` runs it through the real engine;
tests assert `Character`-derived values against `expected`, and the citations make every magic number
auditable — the same honesty standard the worklogs' "hand-verified" caveats already hold themselves to,
but now executable and regression-guarded instead of prose-only.

### 4. Resulting fixture-authoring WP list (WP72+)

Next unclaimed WP number is **WP72** (WP60-71 already claimed by Phases T/R/U/V — see the Implementation
Plan index's tail note). Each WP below closes named gaps from §2 and follows the §3 format.

- [x] **WP72 — Synthetic whole-character fixture harness + one reference fixture.** Infrastructure
  first, mirroring how WP4 established the `.chum5` harness before any test consumed it. Deliver the
  `SyntheticCharacter` dataclass, `build_synthetic()` helper, and the expected/citations convention
  under `tests/fixtures/` (+ a README section), proven end-to-end by **one** reference fixture: a full
  mundane **Priority** build (metatype + all four A-D priorities + attribute/skill allocation +
  a positive/negative quality pair), asserting attribute totals, skill dice pools, initiative, limits,
  and condition monitors against hand-derived values cited to `learnings.md`/`priorities.xml`. Closes no
  §2 gap on its own — it's the substrate the rest depend on. Depends on: nothing new.
- [x] **WP73 — Priority-built cyberware + bioware Essence-stacking fixture.** Closes G1, G2. A mundane
  Priority build carrying ≥1 cyberware and ≥1 bioware item, asserting the shared-pool Essence total and
  the resulting Essence-derived stats. Depends on: WP72; Phase J (WP30-33), Phase L (WP45).
  **Team role (see §5): the Street Samurai** — the muscle. Ork or Troll, combat-augmented (e.g. wired
  reflexes cyber + muscle toner bio), which is exactly the cyberware+bioware Essence stacking this WP
  must test anyway.
  Landed as `STREET_SAMURAI_FIXTURE` — Dražen "Rebar" Kovač, an Ork samurai (Attributes A / Heritage B
  / Resources C / Skills D). Carries 5 cyberware (Obvious Full Arm, Bone Lacing (Titanium), Spurs,
  Datajack, Smartlink — Essence 3.1) + 2 bioware (Enhanced Articulation, Platelet Factories —
  Essence 0.5), stacking to Essence 6 − 3.6 = **2.4** in one shared pool; asserts the per-source
  `cyberware:*`/`bioware:*` splits, the combined `essence`, the Cyberlimb +1 Physical CM, and the
  Enhanced Articulation +1 Physical Limit / +1 Escape Artist bonuses. *Note the team-role blurb's
  "wired reflexes + muscle toner" example is illustrative only — both are rating-scaled, hence
  excluded from the flat WP31/WP45 catalogs, so the fixture uses flat equivalents.* No PDF/decisions
  entry needed: every figure is `cyberware.xml`/`bioware.xml`/`priorities.xml` data or an already-
  extracted `learnings/phase-d.md` formula. See `spec/worklogs/WP73.md`.
- [x] **WP74 — Priority-built magician + cyberware fixture (Essence→Magic loss), with foci/mentor.**
  Closes G3, and G6 to the extent a single magician build naturally carries a focus and a mentor
  spirit. A Priority magic build with enough cyberware to drop Essence below a whole point, asserting
  the reduced Magic rating and any focus/mentor-granted Improvements. Depends on: WP72; Phase I (WP25),
  Phase J (WP30), Phase M (WP47-48).
  **Team role (see §5): the Combat Mage** — the artillery/astral. A **Hermetic** (Logic-based)
  magician with a power focus + mentor spirit and just enough cyberware (e.g. cybereyes + datajack) to
  drop below a whole Essence point, which is the Essence→Magic-loss interaction this WP must test.
  Landed as `COMBAT_MAGE_FIXTURE` — Sabine "Cinder" Aumann, a Human Hermetic magician (Talent A /
  Attributes B / Skills C / Resources D / Heritage E — a magic build now assigns Talent a real A-D
  letter instead of the mundane-only forced E). Carries a datajack + a pair of cybereyes (Image Link
  + Vision Magnification), Essence 6 − 0.3 = 5.7; that sub-1.0 loss reduces Magic 6 → **5** (p.278
  "point or fraction thereof"), and the fixture asserts that reduced 5 flows into the spell cap, the
  foci count/Force caps, and every MAG-linked dice pool — not just the headline rating. Mentor Spirit
  (Mountain) grants +2 Survival (General) and +2 Counterspelling (Magician) as FLAT_BONUS
  Improvements — the latter grant-5 + mentor-2 capping at the chargen 6 — and a Power Focus (Force 2,
  cost-only, its bonus unmodeled) closes the foci half of G6. Drain Resistance (Hermetic LOG + WIL)
  and `power_points = 0` (Magician ≠ Adept) are asserted too. No PDF/decisions entry needed: every
  figure is `priorities.xml`/`cyberware.xml`/`foci.xml`/`mentors.xml`/`traditions.xml` data or an
  already-extracted `learnings/phase-d.md`/`phase-i.md`/`phase-m.md` formula. See
  `spec/worklogs/WP74.md`.
- [ ] **WP75 — Step-Seven leftover-Karma spend fixture.** Closes G4, G5. A completed Priority build that
  spends leftover Karma on an extra skill rank that breaks a skill group, a specialization, and an
  extra spell beyond the free Talent budget — asserting the Karma ledger and the resulting
  pool/spell-count changes against the WP52/WP53 cost formulas. Depends on: WP72; Phase O (WP52-53).
  **Team role (see §5): the Face** — the social engine. Because the mechanic forces a magic user (it
  spends leftover Karma on *an extra spell*), make this the team's **Shaman** (Charisma-based
  magician): high social skills, so the leftover-Karma spend that breaks a skill group naturally lands
  in the Influence/Acting group and the extra spell is a manipulation/illusion spell. Distinct from
  WP74's Hermetic combat mage in both attribute base (CHA vs LOG) and role (social vs artillery), so
  the two magic users don't overlap.
- [ ] **WP76 — Sum-to-Ten whole-character fixture.** Closes G7. A Sum-to-Ten build (the sibling build
  method WP44 landed but no fixture exercises end-to-end) combined with a cyberware or magic layer,
  asserting the Sum-to-Ten letter-assignment validation plus the layered subsystem's derived values.
  Depends on: WP72; Phase L (WP44).
  **Team role (see §5): the Decker** — the Matrix specialist (the one role Cheshire explicitly can't
  cover — she has Simsense Vertigo). Take the "cyberware layer" option (datajack + cerebral booster),
  which doubles as a decker's own augmentation, over Cracking/Electronics skills and high LOG.

## 5. Team roster — the fixtures mesh as one shadowrunning team

The five synthetic fixtures are deliberately authored as **one coherent runner team**, not five
unrelated characters. This costs nothing in coverage — each character's archetype is chosen to *fit*
the mechanic its WP already has to test (a cyberware+bioware build is naturally a Street Samurai; an
Essence-losing magician is a Combat Mage; a leftover-Karma-on-a-spell build is a second, social
magician; a Sum-to-Ten cyberware build is a Decker) — while making the set legible and fun to pick up
as a table-ready party. A future reader who wants "a team" has one; a WP author who wants "the fixture
that tests X" still has that too.

| Fixture | Runner | Metatype (suggested) | Role | Covers |
|---|---|---|---|---|
| WP72 | Renata "Cheshire" Vance | Human | Infiltrator / B&E | Stealth, locks, legwork (Perception), backup pistols |
| WP73 | *(the Street Samurai)* | Ork / Troll | Muscle | Frontline combat, soak, physical intimidation |
| WP74 | *(the Combat Mage)* | Elf / Human | Artillery / Astral | Combat spells, astral recon, magical defense, healing |
| WP75 | *(the Shaman Face)* | Elf / Human | Face / secondary magic | Negotiation/Con/Etiquette, manipulation spells |
| WP76 | *(the Decker)* | Dwarf / Human | Matrix | Hacking, Matrix overwatch, data search, electronic B&E |

**Role coverage check.** Combat: Sam (primary) + Mage (spells) + Cheshire (backup pistols 12-dice).
Stealth/infiltration: Cheshire. Matrix: Decker (fills Cheshire's deliberate gap — she has Simsense
Vertigo). Magic/astral/healing: Combat Mage + Shaman. Social/Face: Shaman-Face (fills Cheshire's
CHA-2 gap). Legwork/Perception: Cheshire + Decker. Two magic users is normal for a Shadowrun team and
they don't overlap (Hermetic artillery vs Shamanic Face). **Known gap: no Rigger** — deliberate,
since rigger support (Phase P) isn't built, so there's no vehicle/drone subsystem for such a fixture
to exercise; not a hole to plug until Phase P lands.

**Complementary attribute/skill spread (not just roles).** Cheshire is AGI/INT-heavy and CHA-2 (no
Face) and LOG-3 (no decker) *on purpose* — those gaps are exactly what the Face and Decker fill, so
the fixtures were designed against each other, not in isolation. When authoring WP73-76, sanity-check
the new runner against this table so the team stays balanced (e.g. don't also make the Decker a
climber, or the Sam a second face).
