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

*(2026-08-01 update: Phase K closed with WP42, so that blocker is gone — `Cyber Implant Weapon
Accessory` is a real catalog category and Hand Blade/Spurs really do declare it in their
`allowed_subsystem_categories`. §6's own gap list picks up the general parent→plugin nesting case;
the weapon-accessory variant specifically is still unscheduled, because §6's fixture happens to
carry implanted weapons with no accessory on them.)*

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
- [x] **WP75 — Step-Seven leftover-Karma spend fixture.** Closes G4, G5. A completed Priority build that
  spends leftover Karma on an extra skill rank that breaks a skill group, a specialization, and an
  extra spell beyond the free Talent budget — asserting the Karma ledger and the resulting
  pool/spell-count changes against the WP52/WP53 cost formulas. Depends on: WP72; Phase O (WP52-53).
  **Team role (see §5): the Face** — the social engine. Because the mechanic forces a magic user (it
  spends leftover Karma on *an extra spell*), make this the team's **Shaman** (Charisma-based
  magician): high social skills, so the leftover-Karma spend that breaks a skill group naturally lands
  in the Influence/Acting group and the extra spell is a manipulation/illusion spell. Distinct from
  WP74's Hermetic combat mage in both attribute base (CHA vs LOG) and role (social vs artillery), so
  the two magic users don't overlap.
  Landed as `SHAMAN_FACE_FIXTURE` — Yseult "Wren" Marchetti, an Elf Shamanic magician (Attributes A /
  Skills B / Talent C / Heritage D / Resources E). Talent C's Magician option is the first fixture to
  exercise a Talent row with **no free-skill grant** (`skill_qty` unset), and Heritage D/Elf is the
  first with a **0 special-attribute-point** budget — so Edge starts at the Elf floor of 1 and only
  Step Seven Karma lifts it. Her Karma pool is 42, not 25 (Positive 8 = Indomitable (Social);
  Negative 25 = Codeblock 10 + SINner (Corporate Limited) 15, hitting the Negative cap exactly), and
  **all 25 net Karma is spent, `karma_remaining` 0**: EDG 1→2 (10), Negotiation 4→5 (10, which breaks
  the priority-bought Influence group — Etiquette/Leadership stay at 4), a Karma specialization on
  Negotiation ("Bargaining", 7 flat — the second, independent group-breaking trigger), the Conjuring
  group 1→2 raised *as a group* with Karma (10, legal because nothing broke that group), and a 6th
  spell beyond the free 5-spell budget (5), landing exactly on the Magic 3 x 2 known-spells cap. The
  fixture asserts the per-selection Karma costs, the broken-group set, both specialization kinds'
  +2 pools (one skill-point-funded, one Karma-funded) and the full derived-stat set. No PDF pass
  needed: every formula was already extracted in `learnings/phase-o.md` (WP51-54). See
  `spec/worklogs/WP75.md`.
- [x] **WP76 — Sum-to-Ten whole-character fixture.** Closes G7. A Sum-to-Ten build (the sibling build
  method WP44 landed but no fixture exercises end-to-end) combined with a cyberware or magic layer,
  asserting the Sum-to-Ten letter-assignment validation plus the layered subsystem's derived values.
  Depends on: WP72; Phase L (WP44).
  **Team role (see §5): the Decker** — the Matrix specialist (the one role Cheshire explicitly can't
  cover — she has Simsense Vertigo). Take the "cyberware layer" option (datajack + cerebral booster),
  which doubles as a decker's own augmentation, over Cracking/Electronics skills and high LOG.
  Landed as `DECKER_FIXTURE` — Bakari "Nullsec" Osei, a Dwarf decker built **Sum-to-Ten** with
  Heritage B / Skills B / Attributes C / Resources C / Talent E = 3+3+2+2+0 = exactly 10. Two
  repeated letters, so the same assignment is *illegal* under the Priority bijection every other
  fixture uses — the test asserts that rejection directly, which is the whole engine-visible content
  of the build-method difference (`Character` has no `build_method` field; both methods read the same
  `priorities.xml` rows, so the harness needed a `build_method` input field but no new metric key).
  Carries a 4-item implanted rig (Cyberdeck, Datajack, Image Link, Sound Link — Essence 6 − 0.7 =
  5.3) as the layered subsystem, plus two boundary cases the set lacked: the Negative-quality cap hit
  by a *single* quality (SINner (Corporate) 25, the catalog's largest) and a Dwarf REA deliberately
  held at 4 because Dwarf is the only SR5-core metatype whose REA maximum is 5, not 6. Its Step Seven
  spend (WIL 4→5 for 25, a Hacking specialization for 7 = the full 32-Karma pool) also covers the
  *complement* of WP75's group-breaking case: a Karma specialization on a skill whose group was never
  group-bought breaks nothing. *Note the team-role blurb's "cerebral booster" is illustrative only —
  Cerebral Booster is rating-scaled bioware, hence outside WP45's flat catalog, the same mismatch
  WP73's "wired reflexes" blurb hit.* No PDF/decisions entry needed: Sum-to-Ten's point table and
  exact-equality target are legacy-C#-sourced (WP44, `learnings.md`) and every other figure is
  `priorities.xml`/`metatypes.xml`/`cyberware.xml` data or an already-extracted
  `learnings/phase-d.md`/`phase-o.md` formula. See `spec/worklogs/WP76.md`.

**Phase S's fixture list is complete with WP76** — the harness (WP72) plus all five gap-closing
fixtures (WP73-76 covering G1-G7) have landed. Two mechanics remain without *whole-character*
coverage, both deliberate and both unit-tested: WP53's Knowledge/Language Karma spend (no synthetic
fixture declares a Knowledge roster, so the harness has no `karma_knowledge_points` field) and WP43's
Karma-to-Nuyen conversion. Phase K's two-level cyberware nesting stays blocked on Phase K itself.

*(Superseded 2026-08-01: **§6 reopens the phase with WP85-88.** Both "deliberate" gaps above, and
several more the §2 inventory never knew to look for, turned out to be closable at once by a
player-authored character that arrived from outside the plan — see §6.)*

## 5. Team roster — the fixtures mesh as one shadowrunning team

The five synthetic fixtures are deliberately authored as **one coherent runner team**, not five
unrelated characters. This costs nothing in coverage — each character's archetype is chosen to *fit*
the mechanic its WP already has to test (a cyberware+bioware build is naturally a Street Samurai; an
Essence-losing magician is a Combat Mage; a leftover-Karma-on-a-spell build is a second, social
magician; a Sum-to-Ten cyberware build is a Decker) — while making the set legible and fun to pick up
as a table-ready party. A future reader who wants "a team" has one; a WP author who wants "the fixture
that tests X" still has that too.

All five are now authored, so the "Metatype" column below records what each fixture actually took.

| Fixture | Runner | Metatype | Role | Covers |
|---|---|---|---|---|
| WP72 | Renata "Cheshire" Vance | Human | Infiltrator / B&E | Stealth, locks, legwork (Perception), backup pistols |
| WP73 | Dražen "Rebar" Kovač | Ork | Muscle | Frontline combat, soak, physical intimidation |
| WP74 | Sabine "Cinder" Aumann | Human | Artillery / Astral | Combat spells, astral recon, magical defense, healing |
| WP75 | Yseult "Wren" Marchetti | Elf | Face / secondary magic | Negotiation/Con/Etiquette, manipulation spells |
| WP76 | Bakari "Nullsec" Osei | Dwarf | Matrix | Hacking, Matrix overwatch, data search, electronic B&E |

**Role coverage check.** Combat: Sam (primary) + Mage (spells) + Cheshire (backup pistols 12-dice).
Stealth/infiltration: Cheshire. Matrix: Decker (fills Cheshire's deliberate gap — she has Simsense
Vertigo). Magic/astral/healing: Combat Mage + Shaman. Social/Face: Shaman-Face (fills Cheshire's
CHA-2 gap). Legwork/Perception: Cheshire + Decker. Two magic users is normal for a Shadowrun team and
they don't overlap (Hermetic artillery vs Shamanic Face). **Known gap: no Rigger** — deliberate,
since rigger support (Phase P) isn't built, so there's no vehicle/drone subsystem for such a fixture
to exercise; not a hole to plug until Phase P lands.

**Complementary attribute/skill spread (not just roles).** Cheshire is AGI/INT-heavy and CHA-2 (no
Face) and LOG-3 (no decker) *on purpose* — those gaps are exactly what the Face and Decker fill, so
the fixtures were designed against each other, not in isolation. Each of WP73-76 was sanity-checked
against this table as it was authored so the team stayed balanced (e.g. the Decker is AGI 2 / CHA 2,
not a second climber or a second face); any *future* fixture WP should do the same.

---

## 6. Second gap pass (2026-08-01) — importing a player-authored character, WP85-88

### What arrived, and why it reopened a phase marked complete

A player-built character turned up as a **save file in this project's own format**
(`format_version: 1`), authored in the web UI rather than derived from the plan. It loads clean
through `POST /character/load` today — no engine change is needed to accept it. What makes it worth
a WP block is that it was built by someone shopping for a *character*, not for coverage, and it
therefore walks straight through several things §2's inventory never thought to enumerate, because
§2 was written by reasoning about which *subsystems* had no fixture rather than about which
*inputs* the harness could not express.

The build (letters E/B/A/B/E — Sum-to-Ten, 0+3+4+3+0 = 10):

- **Chromed to Essence 0.10.** 5.90 of 6.00 spent. `create_cyberware_tree_selection` rejects at
  `>= BASE_ESSENCE`, so this passes with 0.10 of headroom — the tightest legal margin any fixture
  has ever put on that validator. It is also load-bearing downstream, not just a big number:
  Social Limit reads `ceil(Essence)`, so 0.10 → 1 and the limit lands on 5, where a flat 0 would
  give 4.
- **A real purchase *tree*.** Wired Reflexes 2, Bone Lacing (Titanium), Hand Blade, Shock Hand,
  Datajack, plus Cyberears 3 and Cybereyes Basic System 3 each carrying four plugins and one
  bundled freebie (Sound Link / Image Link). Both parents' Capacity comes out **exactly** full at
  12/12 (`Rating * 4` with Rating 3).
- **An augmentation that moves an attribute.** Wired Reflexes 2 → natural REA 4, augmented REA 6,
  and `initiative_dice` 3.
- **Three conditional Improvements.** Audio Enhancement 3, Spatial Recognizer, and Vision
  Enhancement 3 land `MENTAL_LIMIT` bonuses gated on `PERCEPTION_HEARING_ONLY` /
  `PERCEPTION_SOUND_SOURCE_ONLY` / `PERCEPTION_VISUAL_ONLY`.
- **A skill pushed past the chargen maximum by an Improvement.** Stealth group 5 + Catlike's +2
  puts Sneaking at rating **7**, above `MAX_SKILL_RATING_CREATE`.
- **Every budget except Karma spent to the pin.** 20/20 attribute points, 1/1 special (EDG, off
  Human-at-E's single point), 46/46 skill points (43 + 3 specializations), 10/10 group points,
  12/12 Knowledge points, and ¥282,420 of ¥283,000 — a total that only reaches ¥283,000 because
  4 Karma were converted to nuyen. It leaves 19 Karma unspent, the one axis where it is *not* a
  fully-spent build (see WP88 on what to do about that).

### 6a. Second-pass gap inventory

Same rule as §2 — each gap is tied to something currently real, not speculative.

| # | Gap (nothing in `SYNTHETIC_FIXTURES` exercises it) | Currently-real call-out |
|---|---|---|
| G8 | Cyberware bought as a **tree**: rating > 1, plugins, Capacity budget, bundled subsystems | `tests/fixtures/synthetic.py`: "Each name is bought as a zero-plugin purchase tree at rating 1 (WP41); no synthetic fixture installs a plugin yet"; Phase K WP38/WP42 |
| G9 | A build sitting at the **Essence floor**, where `ceil(Essence)` is load-bearing | `engine/cyberware_subsystems.py:650` (the `>= BASE_ESSENCE` reject); the deepest existing fixture is Rebar at 2.4 |
| G10 | An **augmentation that raises an attribute** (natural vs. augmented, WP81) and adds Initiative Dice | every existing fixture asserts `initiative_dice: 1` and cites its `attr:REA` as "metatype min + points"; no fixture's cyberware has a non-empty `flat_bonuses` targeting an attribute |
| G11 | **Conditional Improvements** (WP39/WP40) on a finished character | `engine/improvements.py` `ImprovementCondition`; every existing fixture's cyberware has `conditional_bonuses` empty. `resolve_metric` has no key for a conditional limit either |
| G12 | The **spend side** of the nuyen/Karma/point budgets: gear, Rating-priced gear, Lifestyle, contacts, Knowledge/Language, Karma-to-Nuyen | `SyntheticCharacter` declares no field for any of them; §4's own closing note already flagged the last two as deliberate holes (WP43, WP49/WP53) |
| G13 | A **skill rating pushed past `MAX_SKILL_RATING_CREATE`** by an Improvement, at whole-character level | WP82 (unit-tested only); the closest fixture is Cheshire, whose Catlike-boosted Sneaking lands at 5 |

Still **not** scheduled: the Cyber Implant Weapon → Weapon Accessory nesting (§2's note). WP86
makes it expressible for the first time, but this character's Hand Blade and Shock Hand carry no
accessory and he has ¥580 left to buy one with, so closing it means a *different* fixture, not this
one.

### 6b. The WPs

Next unclaimed WP number is **WP85** (Phase V claimed WP83-84 on 2026-08-01 — see the Implementation
Plan index's tail note). WP85 lands the input; WP86/WP87 widen the harness on two independent axes;
WP88 authors the fixture on top of all three.

- [x] **WP85 — Land the save file as the project's first on-disk save-format fixture.**
  Goal: get the character into the repo as *data* — and get a regression guard on the save format
  itself, which has never had one.
  Notes: the file is already committed at `tests/fixtures/saves/razorboy.json` (added with this
  planning entry, precisely so WP86-88 can be executed cold from the repo rather than from a chat
  transcript); nothing references it yet. Everything the round-trip needs already exists —
  `from_json` / `build_character` / `create_character_save` / `to_json`.
  Deliverables:
  - A registry entry beside `mundane_chum5.py`'s (name → path under `tests/fixtures/saves/`),
    following that module's own "referenced, not copied" shape — except these files *are* ours, so
    they live under `tests/fixtures/` rather than pointing into `legacy/`.
  - An integration test that loads the file, builds it, and asserts the headline results this
    section states above (Essence `Decimal("0.10")`, `initiative_dice` 3, augmented REA 6, Sneaking
    7, nuyen remaining 580, both Capacity budgets exactly full), plus `save → to_json → from_json`
    equality — i.e. that a `format_version: 1` file written by the UI keeps loading unchanged.
  - A `tests/fixtures/README.md` section for the new directory, matching the depth of the two
    already there.
  Depends on: nothing new.
  Acceptance: `pytest`/`ruff`/`mypy` green; the test fails loudly (not silently skips) if the file
  is missing or stops loading; no engine or `io` change is needed to make it pass — if one turns
  out to be, stop and log it, because it means the format regressed at some point since WP41.

- [ ] **WP86 — Harness: express a cyberware purchase *tree*.** Closes the harness half of G8.
  Goal: `SyntheticCharacter.cyberware` is a flat `tuple[str, ...]` that `build_synthetic()` turns
  into rating-1, plugin-free `CyberwarePurchaseRequest`s. Widen it so a fixture can declare
  ratings and nested plugins, which is what WP38/WP41/WP42 actually built.
  Notes: keep the name-keyed authoring convention (`build_synthetic()` resolves names to ids and
  raises clearly on an unknown one) and keep the existing four fixtures' literals working —
  a bare `"Datajack"` must stay legal alongside a rated/plugged entry, the same way WP73-76 each
  extended the dataclass without rewriting their predecessors. Bundled subsystems
  (`bundled_subsystem_names`) are resolved *by the engine*, not declared by the fixture; a fixture
  that lists one explicitly should be an error, not a silent duplicate.
  Deliverables: the widened `cyberware` field + `build_synthetic()` wiring; new `resolve_metric`
  keys for the Capacity side (per-purchase `capacity_cost`/`capacity_budget`, so "exactly full" is
  assertable rather than merely "not rejected"); the `tests/fixtures/README.md` paragraph.
  Depends on: WP72 (harness), Phase K (WP38 tree/Capacity, WP41 save shape, WP42 the UI that
  produced this file). Independent of WP87 — either may land first.
  Acceptance: `pytest`/`ruff`/`mypy` green with the four existing fixtures' literals **unchanged**;
  a round-trip check that the widened field can express `razorboy.json`'s `cyberware_purchases`
  exactly (same Essence, same nuyen, same Capacity per parent).

- [ ] **WP87 — Harness: express the spend side of the budgets.** Closes the harness half of G12.
  Goal: add the `SyntheticCharacter` fields for everything a character *buys* that isn't
  cyberware/bioware/foci — gear, Rating-priced gear, Lifestyle, contacts, Knowledge skills,
  languages, and Karma-to-Nuyen conversion — so a fixture can assert that a build's budgets balance,
  not just that its dice pools are right.
  Notes: every one of these already has an engine function `build_synthetic()` simply doesn't call
  (`create_resources_selection` with `rating_gear`/`lifestyle_cost`/`karma_converted`,
  `create_contact_selection`, `create_knowledge_selection`). Follow `io/save_format.build_character`'s
  own evaluation order rather than inventing one — it already resolves these against a shared
  ledger in a fixed sequence, and a fixture that disagrees with the save path is a fixture that
  proves nothing. Note that free Contact points (`CHA x 3`) and free Knowledge points
  (`(INT + LOG) x 2`) read **`natural_attribute_value`**, not the augmented one (p. 95) — that
  distinction is exactly the kind of thing this fixture should pin down.
  Deliverables: the new fields + wiring; `resolve_metric` keys for `nuyen:remaining` /
  `nuyen:available`, the contact and knowledge point budgets, and knowledge dice pools; README.
  Depends on: WP72; Phase H (WP20 Lifestyle), Phase L (WP43 Karma-to-Nuyen), Phase N (WP49
  Knowledge/Language), WP66 (Rating-priced gear). Independent of WP86.
  Acceptance: `pytest`/`ruff`/`mypy` green with the four existing fixtures' literals **unchanged**
  (all four decline every new field, and their `expected` tables must not shift); the new metric
  keys reproduce `razorboy.json`'s own ¥580 remaining and 12/12 Knowledge points.

- [ ] **WP88 — The fixture: Jacob "Tithe" Smith, the wetwork specialist.** Closes G8-G13.
  Goal: author `WETWORK_FIXTURE` in `synthetic_fixtures.py` from the save file, with the full
  hand-derived `expected`/`citations` treatment WP72-76 established, and add him to §5's roster.
  **Naming (decided here so WP88 doesn't re-litigate it):** the character's SINner (National)
  quality text already names him *Jacob Smith*, which is his real, legal, government-registered
  identity — he is a SINner, not a nobody, and the Rating-4 Fake SIN is the alias, not the other way
  round. Handle: **"Tithe"** — what he has left, one tenth. Team role: close-quarters wetwork and
  the rooftop approach (Blades 6 spec'd "Implanted" for 12 dice, Gymnastics/Climbing 11, Sneaking
  11), which is a third lane beside Rebar's guns-and-soak muscle and Cheshire's infiltration rather
  than a duplicate of either.
  Notes and traps:
  - **Spend the leftover 19 Karma.** Every other fixture is fully spent on every axis, and §5's own
    rationale is that a fully-spent budget hits the validators at their exact limits. 19 Karma
    is enough for a meaningful Step Seven spend (WIL 3→4 costs 20 — just out of reach; BOD 3→4 costs
    20 likewise; a Karma specialization is 7, an active skill step is `new Rating x 2`). Pick a
    spend that fits *and* says something, and record what changed from the player's original file
    — the save is the input of record, so any divergence from it must be deliberate and written
    down, not quietly absorbed.
  - Do **not** carry the Karma-to-Nuyen figure over uncritically: WP89 changes what 4 converted
    Karma costs the ledger. Sequence this after WP89 or re-derive `karma_remaining` once it lands.
  - `resolve_metric` needs a conditional-limit key for G11, or the three conditional Improvements
    are present-but-unasserted, which is the "hand-verified, no fixture" failure mode this whole
    phase exists to end.
  - Assert `natural` *and* augmented REA separately (G10), and Sneaking's 7 against
    `MAX_SKILL_RATING_CREATE` (G13), or neither gap is actually closed by having the numbers pass.
  Depends on: WP85, WP86, WP87; and see the WP89 note above.
  Acceptance: `pytest`/`ruff`/`mypy` green; `assert_fixture` passes with every `expected` key
  carrying a citation (a magic number with no cited source is a test failure — WP72's standard);
  §5's roster table and its role-coverage/attribute-spread paragraphs updated to six runners;
  `spec/worklogs/WP88.md` written, and any figure that needed the PDF recorded in
  `spec/rulebooks/learnings/phase-s.md`.
