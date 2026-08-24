[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase P — Post-MVP: Rigger support (research pass done, WP90; WP91-96 scoped)

**Deliberately scoped down before any WP breakdown is written** — raised during the same 2026-07-21
session as Phases L-O, but confirmed to be a materially different size than any of them: vehicles and
drones are their own rulebook chapter (not part of "Creating a Shadowrunner" at all — only referenced
via Step Six's Gear Checklist sidebar, "Vehicle(s), p. 461 / Drones..., p. 461") with their own stat
block (Body/Armor/Speed/Handling/Acceleration/Sensor/Pilot) and **multiple separate per-category
modification-slot pools** (Cosmetic/Powertrain/Protection/Weapons, each sized differently per vehicle) —
mechanically similar in *spirit* to cyberware's Capacity system but not the same shape (one Capacity
number vs. several named slot pools). An RCC (Rigger Command Console) and control rigs also drag in the
Matrix device-rating stat block (Attack/Sleaze/Data Processing/Firewall) this project has never modeled
for *anything* — no commlinks, no cyberdecks, no Matrix rules at all exist in `chummer5_py` today, and
Project Overview has always listed "matrix rules" among the general Improvement engine's excluded scope.

**Ruling, 2026-07-21: modifications are excluded from this phase's eventual scope.** No vehicle mods, no
drone mods, no RCC/cyberdeck upgrades — characters may buy stock/unmodified vehicles, drones, RCCs, and
cyberdecks only. This removes the per-category modification-slot system and most of the Matrix-adjacent
complexity from what this phase actually needs to build (a stock RCC/cyberdeck still needs its own
Attack/Sleaze/Data Processing/Firewall stat block *displayed*, since those are inherent ratings of the
item itself, but nothing needs to *change* them via installed programs/mods).

**Before any WP breakdown is written, this phase needs its own research pass** (mirroring Phase K's own
"Pre-Phase-K research" entry in `spec/rulebooks/learnings.md`, done ahead of scoping):
- Confirm the exact `vehicles.xml` (or equivalent) shape: which fields are flat vs. rating-scaled, how
  many SR5-core, flat-cost entries exist across vehicles/drones/RCCs/cyberdecks (mirroring WP21/31's own
  catalog-size research before committing to a filter rule), and whether Availability filtering (per this
  project's 2026-07-21 ruling — exclude Availability > 12 items) meaningfully shrinks the offerable list.
- Confirm whether any curated `.chum5` fixture (mundane or magic corpus) carries a vehicle/drone/RCC
  purchase at all, to know upfront whether this phase can lean on real fixture data or will need the same
  "hand-verified, no fixture" honesty standard Phase M's WPs already anticipate.
- Confirm the rulebook's own page range for the Vehicles/Rigger chapter (not yet extracted into any
  chapter file in this project) and extract the purchase-relevant subset the same way
  `character_creation_chapter.md` did for character creation, before writing WPs against it secondhand.
- Decide whether a stock RCC/cyberdeck's Matrix stat block needs any new `Character`-level concept at
  all, or whether (given no Matrix rules exist to consume those numbers) it's sufficient to record and
  display them without deriving anything further from them — the same "don't build machinery nothing
  downstream needs yet" discipline WP27 applied to Adept Powers whose effects fall outside this engine's
  current scope.

*(The "continue from WP62" note that stood here is stale — WP62-89 were claimed by Phases R/S/T/U/V/O
between 2026-07-27 and 2026-08-01, while this phase sat unstarted. The research pass below is
**WP90**, and it claims WP91-96 for the phase's implementation work.)*

- [x] **WP90 — Rigger-support research pass: answer the four questions above, extract the chapter,
  and emit the WP breakdown.** Research only, no `src/`/`tests/` changes.
  Depends on: nothing new.
  Acceptance: `pytest`/`ruff`/`mypy` untouched and green; each of the four intro bullets answered
  concretely (not left open); the rulebook extract committed; this phase file carrying a WP
  breakdown whose every entry is tied to a currently-real finding.

---

## WP90 findings (2026-08-01)

Full retrospective in `spec/worklogs/WP90.md`; rulebook citations in
`spec/rulebooks/learnings/phase-p.md`; the purchase-relevant chapter extract in
`spec/rulebooks/vehicles_and_riggers_chapter.md`. The load-bearing conclusions and the resulting WP
breakdown are recorded here so a future WP can act on them without re-deriving.

### 1. The intro's central premise about modification slots was wrong — and the ruling is cheaper than it looks

`powertrain`, `modification slot` and `mod slot` appear **nowhere** in the SR5 core rulebook (checked
over a full 489-page `pdftotext` dump). The per-category slot pools this phase's intro described —
"Cosmetic/Powertrain/Protection/Weapons, each sized differently per vehicle" — are **Rigger 5.0**
(`source=R5`) content that `vehicles.xml` carries because Chummer supports every book. Of that file's
197 `<mods>` rows, **170 are `R5` and exactly 2 are `SR5`** (Rigger Interface, Manual Operation),
plus 7 SR5 weapon-mount rows.

The complete SR5-core vehicle-modification system is one four-row table (p. 461: Rigger interface
1,000¥/Avail 4, Standard weapon mount 2,500¥/8F, Heavy weapon mount 5,000¥/14F, Manual operation
+500¥/+1) and one sizing rule ("weapon mounts equal to their unaugmented Body ÷ 3, round down").

**The 2026-07-21 no-modifications ruling stands** — nothing here argues for reopening it — but its
cost is now known precisely rather than feared: it excludes 2 purchasable modifications, not a
system. One of the two matters:

**Drones ship rigger-ready; vehicles do not.** p. 265: "Drones are designed for use by riggers, and
have been designed with the rigger interface built in. Nearly all vehicles need to have the interface
added as an after-factory option." `vehicles.xml` agrees exactly — all **13** SR5 drone rows carry a
bundled `Rigger Interface` in their `<mods>`, and **none** of the 29 vehicle rows do. So under the
no-mods ruling a player can buy a drone that a rigger can actually use, and a *vehicle* that no
rigger can jump into. That is a documented gap (§5's registry rows), not a reason to reverse the
ruling — but it is the single most consequential thing the ruling costs, and it was invisible before
this pass.

### 2. `vehicles.xml` shape: flat, small, and already book-verified

- **42 SR5-sourced `<vehicle>` rows** out of 380 (`R5` 158, `SAG` 37, `2050` 32, `SS` 27, …).
  29 vehicles + 13 drones.
- **Every field a purchase needs is a flat literal.** `<cost>`, `<avail>`, `<body>`, `<armor>`,
  `<pilot>`, `<sensor>`, `<accel>`, `<seats>` are bare integers; `<handling>`/`<speed>` are either a
  bare integer or the printed `on-road/off-road` pair (`4/3`, `3/4`). **No `Rating * N`, no
  `FixedValues(...)`, no `Variable(...)` anywhere in the SR5 set** — so this phase needs *nothing*
  like `chummer5.data.cyberware_formula`. This is the WP21-shaped "flat literal" case, not the
  WP36-shaped one.
- **All four printed tables agree with the XML stat-for-stat**, transcribed from the PDF before being
  compared (see the chapter extract §6 and `learnings/phase-p.md`). No corrections needed.
- **Two XML rows are not printed anywhere** and should be excluded, mirroring WP42's
  `_UNPURCHASABLE_CYBERWARE_NAMES` precedent exactly:
  - `Horizon Flying Eye w/Flash-Pak and Grenade (Minidrone)` — a 2,500¥ Chummer convenience bundle
    of the 2,000¥ printed drone plus two pieces of gear.
  - `Ocular Drone` — `<page>453</page>`, `<cost>0</cost>`: the *cyberware* ocular drone, which this
    project already carries in its cyberware catalog as a `requires_parent` plugin. It exists as a
    vehicle row only so the legacy app can give that implant a vehicle stat block.

**Availability ≤ 12 (the 2026-07-21 ruling) removes 5 of 42** — a real but modest filter, and it
removes exactly the rows that had no business in a starting build:

| Excluded | Avail | Cost |
|---|---|---|
| Eurocar Westwind 3000 (Luxury Sports Car) | 13 | 110,000¥ |
| Mitsubishi Nightsky (Limousine) | 16 | 320,000¥ |
| Morgan Cutlass (Patrol Boat) | 14R | 96,000¥ |
| Nissan Hound (Transport Helicopter) | 13R | 425,000¥ |
| GMC Banshee (Thunderbird) | 24F | 2,500,000¥ |

**Offerable catalog: 42 − 5 (Availability) − 2 (unprinted) = 35 rows** (24 vehicles + 11 drones).
Every one of the 35 is affordable within Resources A's 450,000¥, so no second cost filter is needed.

### 3. RCCs, cyberdecks and commlinks are **already purchasable today** — with their entire stat block discarded

This is the finding that most changes what this phase should build. `chummer5.engine.resources
.STARTER_GEAR_CATALOG` already offers, as ordinary flat-cost gear:

- **11 Rigger Command Consoles** (Scratch-Built Junk 1,400¥ … Triox UberMensch 140,000¥)
- **9 Cyberdecks** (Erika MCD-1 49,500¥ … Fairlight Excalibur 823,250¥)
- **7 Commlinks**, 6 Autosofts, 26 Programs, 2 Sensor rows

`StarterGearItem` carries `(name, cost, category, armor_rating, cost_per_rating, max_rating, rating)`
— so `<devicerating>`, `<attack>`, `<sleaze>`, `<dataprocessing>`, `<firewall>`, `<programs>` and
`<attributearray>` are read by nobody and shown nowhere. A player can buy a Fairlight Excalibur and
the character sheet will show a line item and a price.

Two consequences, both scoped below rather than assumed away:
- **Nothing needs to be *built* for a rigger to buy an RCC.** WP94 is a display/verification WP, not
  a new-subsystem WP.
- **The Availability ≤ 12 ruling has never been applied to flat-cost gear at all** (only WP66's
  Rating-priced half enforces it). For these three categories that means 3 of 11 RCCs (14R/16R/18R),
  2 of 9 cyberdecks (15R/18R) and 1 of 7 commlinks (Fairlight Caliban, 14) are offered against the
  ruling. Project Overview already flags the general gap ("no WP currently scheduled to backfill
  that"); WP94 closes the rigger-adjacent slice of it and nothing more.

### 4. `Control Rig` is offered by today's UI, and its effect is 100% unmodeled with no registry row

`Control Rig` (Headware, SR5 p. 452, `<ess>Rating * 1`, `<cost>FixedValues(43000,97000,208000)`,
`<avail>(Rating * 5)R`, ratings 1-3) is in `CYBERWARE_ENTRIES` and in `CYBERWARE_STANDALONE` — it
became UI-reachable with WP42's full-catalog picker, the same commit that made five of WP77's rows
reachable. It carries **no** `unmodeled_effect_note`.

Its entire printed mechanical payload (p. 266) is: "When you're jumped into a vehicle, drone, or
other device, the limits of that device are increased by the rating of your control rig. This
includes vehicle and drone Sensor, Speed, and Handling, and the Accuracy of mounted weapons when used
by the rigger." There is no character-level term in it at all. So a player can spend 43,000¥ and a
**full point of Essence** on an implant this engine models as pure cost — which is exactly the
situation the 2026-07-24 unmodeled-effects policy says is *fine to offer* provided the gap is
recorded. It isn't recorded. WP95 fixes that.

Its rating-3 availability is `15R`, over the cap, which today's cyberware picker does not enforce
either — part of the same unscheduled backfill as §3's, sized in `spec/decisions-log.md`.

### 5. Do stock Matrix stat blocks need a new `Character`-level concept? **No. One vehicle number does.**

Every RCC/cyberdeck/commlink number (Device Rating, Attack, Sleaze, Data Processing, Firewall,
Programs, Attribute Array) is a printed constant of the item, read by nothing downstream because no
Matrix rules exist. **Record and display; derive nothing** — the same discipline WP27 applied to
Adept Powers whose effects fall outside this engine.

The one genuine exception, and the only computed number this whole phase adds:

> Vehicle **Condition Monitor = 12 + ⌈Body / 2⌉**; drone **Condition Monitor = 6 + ⌈Body / 2⌉**
> (p. 199).

Same `+ ⌈attribute / 2⌉` shape as the character-level Physical/Stun monitors `chummer5.engine
.derived` already computes, with a different constant and a vehicle-vs-drone split. It is worth
deriving because it is the one printed-page number a player can't read off the catalog table.

Everything else about a vehicle purchase (Handling, Speed, Acceleration, Body, Armor, Pilot, Sensor,
Seating) is a constant carried through from the catalog row.

### 6. Fixtures: one Priority-built SR5 vehicle exists, and it can validate a stat block but not a ledger

Checked all 34 corpus files. 14 carry a `<vehicles>` node; among the 13 curated ones (11 mundane +
2 magic-Priority):

| Fixture | Build method | SR5-sourced vehicles |
|---|---|---|
| `Wesson.chum5` (Human Adept) | **Priority** | Harley-Davidson Scorpion (Chopper), 12,000¥ — **with 7 mods, all `R5`** |
| `Miko.chum5` (Elf Magician) | Priority | none (its Festo Pigeon 2.0 is `R5`) |
| `Yeti-#ffffff2.chum5` (the one mundane Priority build) | Priority | **none** |
| `BLUE`, `Fuzzy-chargen`, `Serpent` | SumtoTen | 2× MCT Fly-Spy; MCT Fly-Spy; Fly-Spy ×2 + Steel Lynx + Kanmushi + Roto-drone |
| `Monomax`, `Rez0luti0n2.0`, `SCSi` | SumtoTen | none (all `R5`/`TCT`) |

So: real legacy-computed stat blocks for stock SR5 vehicles **do** exist (Wesson's Scorpion matches
both the XML and the printed table exactly), which is enough to validate a loader. What does **not**
exist is a reconstructable *nuyen ledger*: Wesson's bike carries 7 `R5` mods (Metahuman Adjustment,
Anti-Theft System, Spoof Chips, GridLink, GridLink Override, Morphing License Plate, Off-Road
Suspension) whose cost this project will never model, so his ¥3,965 remaining can't be reproduced
from a stock purchase. This is moot for import in any case — `chummer5.io.legacy_import` passes
`gear_names=()` and imports no Step Six gear at all, so vehicles were never going to arrive that way.

**Conclusion:** this phase gets the same honesty standard Phase M's WPs already anticipate —
hand-verified against the printed tables — with Wesson's Scorpion as the one piece of real
legacy-computed corroboration, and a synthetic whole-character fixture (WP96) as the regression
guard. That fixture also closes Phase S §5's own explicitly-recorded roster gap ("**Known gap: no
Rigger** — deliberate, since rigger support (Phase P) isn't built … not a hole to plug until Phase P
lands").

---

## 7. The WPs (WP91-96)

Next unclaimed WP number after this block is **WP97**.

- [x] **WP91 — `chummer5.data.vehicles`: load the SR5 vehicle/drone catalog.** Closes nothing on its
  own; it's the substrate, mirroring how WP21's loader preceded WP9's purchase flow.
  Goal: a literal XML→frozen-dataclass pass over `legacy/Chummer/data/vehicles.xml`, restricted to
  `source == "SR5"`, in the shape `chummer5.data.gear` established.
  Deliverables: a `Vehicle` dataclass carrying `id`, `name`, `category`, `cost`, `availability`
  (magnitude + `R`/`F` marker, parsed the way `chummer5.data.gear`'s `_AVAIL_RESTRICTION_RE` already
  does), `handling`/`handling_offroad`, `speed`/`speed_offroad`, `acceleration`, `body`, `armor`,
  `pilot`, `sensor`, `seats` (`None` for drones), `is_drone` (derived from the `Drones: *`
  categories), `page`; a `load_vehicles()` returning all 42 SR5 rows literally (so the count is
  testable), with the Availability cap and the 2 unprinted exclusions living one layer up, exactly
  as `chummer5.data.gear` splits loader-vs-policy today.
  Notes and traps: **there are no formulas in this file's SR5 set** (§2) — if the loader ever needs
  to parse one, something upstream changed and it should fail closed rather than guess. The
  `on-road/off-road` pair is a *string* in the XML (`4/3`) and two elements in `.chum5`
  (`<handling>`/`<offroadhandling>`); split it in the loader, don't propagate the string.
  Depends on: nothing new.
  Acceptance: `pytest`/`ruff`/`mypy` green; a test pinning **42** SR5 rows and the 29/13
  vehicle/drone split; every row's stats asserted against the printed tables transcribed in
  `spec/rulebooks/vehicles_and_riggers_chapter.md` §6 for at least one row per printed table, plus
  the full Harley-Davidson Scorpion row cross-checked against `Wesson.chum5`'s own legacy-computed
  `<vehicle>` node (§6).
  Landed as `chummer5.data.vehicles` (`Vehicle` + `load_vehicles()`), 42 rows / 29 vehicles + 13
  drones. Acceptance was met past its own bar: rather than one row per printed table,
  `tests/unit/test_vehicles.py` transcribes **all four tables in full** and asserts every one of the
  40 printed rows stat-by-stat. Two payoffs. First, the printed tables cover exactly 40 of the 42
  rows and the 2 they miss are precisely §2's unprintable pair, so WP92's exclusion list is
  *derived* by a test rather than asserted. Second, it found a real data error — `vehicles.xml`
  gives the Renault-Fiat Fokker Tundra-9 Handling **2** where p. 465 prints **3**, correcting WP90
  §2's "all four printed tables agree with the XML stat-for-stat." The loader stays literal;
  **WP92 must apply the printed 3 in its catalog builder**, per the 2026-08-01 ruling in
  `spec/decisions-log.md`. See `spec/worklogs/WP91.md`.

- [x] **WP92 — Engine: `VehicleSelection`, the Condition Monitor, and save/load.**
  Goal: make a stock vehicle/drone purchase a real, budget-checked part of a `Character`.
  Deliverables: `chummer5.engine.vehicles` with a `build_vehicle_catalog()` applying the two policy
  filters (Availability ≤ 12; the 2 unprinted names) to reach the 35-row offerable set, a frozen
  `VehicleSelection` carrying the purchased rows and `nuyen_cost`, and a `create_vehicle_selection()`
  validator; `Character.vehicle_selection`; `vehicle_cost` threaded into
  `create_resources_selection` as one more `*_cost` kwarg exactly as `cyberware_cost`/`bioware_cost`/
  `foci_cost` already are; the **Condition Monitor** (`12 + ⌈Body/2⌉`, drones `6 + ⌈Body/2⌉`) as the
  one derived value; save-format fields + round-trip.
  Notes and traps: repeats are legal (a rigger buys four Fly-Spies) — follow `gear_names`' "repeats
  allowed" precedent, not the qualities/foci "can't pick twice" one. `io/save_format.build_character`
  resolves the shared nuyen ledger in a fixed sequence; add vehicles to that sequence rather than
  inventing one (the same instruction WP87 was given). Nothing needs to touch
  `chummer5.io.legacy_import` — it imports no Step Six gear at all (§6) — but say so in the module
  docstring rather than leaving it as a silent omission.
  Depends on: WP91.
  Acceptance: `pytest`/`ruff`/`mypy` green; the offerable catalog is exactly **35**; the 5
  Availability-excluded and 2 unprinted rows are each asserted absent *by name*; a purchase that
  overruns the shared nuyen pool is rejected with the same diagnostic shape cyberware's already
  produces; save → `to_json` → `from_json` round-trips a multi-vehicle selection unchanged.
  Landed as `chummer5.engine.vehicles` (`build_vehicle_catalog`/`VEHICLE_CATALOG` = **35** rows,
  `VehicleSelection`, `create_vehicle_selection`, `condition_monitor`), `Character
  .vehicle_selection`, `ResourcesSelection.vehicle_cost`, and `CharacterSave.vehicle_ids`. Three
  things worth carrying forward: purchases are keyed by **catalog id**, not name (gear is
  name-keyed only because `StarterGearItem` is a synthesized cross-file catalog with no id — every
  other catalog since WP21 uses ids); `build_character` resolves vehicles **third** among the
  shared-pool spenders (cyberware → bioware → vehicles) and folds `vehicle_cost` into the same
  re-call that already folds the other two; and `build_character`'s new `vehicles` parameter
  defaults to the real `VEHICLE_CATALOG` rather than `()`, unlike every other optional catalog,
  because `()` would silently reject every id. WP91's Tundra-9 Handling correction is applied here,
  in `_PRINTED_HANDLING_CORRECTIONS`. See `spec/worklogs/WP92.md`.

- [x] **WP93 — Web UI: the vehicle/drone picker and the character-sheet stat block.**
  Goal: reach the player. A `_vehicles.html` partial + `routes/vehicles.py` following
  `_cyberware.html`/`routes/cyberware.py`'s category-grouped `<details>` shape, and a character-sheet
  section rendering each purchased vehicle's full stat block (Handling on-road/off-road, Speed,
  Accel, Body, Armor, Pilot, Sensor, Seats, **Condition Monitor**) plus the running nuyen total.
  Notes and traps: WP83/WP84's chargen-section layout conventions are current — match them rather
  than the older partials. **Re-check the `Kind` column of every Project Overview registry row this
  WP makes newly UI-reachable**, per that file's own WP77 instruction; this WP is exactly the kind of
  "a UI WP moves the line" event that clause exists for.
  Depends on: WP92.
  Acceptance: `pytest`/`ruff`/`mypy` green; an integration test buying a drone and a vehicle through
  the routes and asserting both stat blocks and the budget on the rendered sheet; the two-value
  Handling/Speed rendered as printed (`4/3`), not silently collapsed to one number.
  Landed as `chummer5.web.routes.vehicles` (`POST /ui/vehicles`) + `_vehicles.html`, a peer section
  after cyberware in `_chargen_body.html`, plus a character-sheet stat-block table. The picker and
  the sheet share one `vehicle_stat_block()` helper, so they cannot disagree about notation.
  **Registry re-check (the WP77 clause): nothing changed.** This WP offers a catalog that has no
  registry rows yet (WP95 writes them) and makes no existing quality/cyberware row newly reachable
  — `Control Rig` was already UI-reachable via WP42's full-catalog picker, as WP90 §4 records.
  Threading `vehicle_cost` through the five sibling sections surfaced a **pre-existing bug**:
  `submit_resources`/`submit_lifestyle` displayed `foci_cost` in their budget warnings but never
  passed it to the `create_resources_selection` call that actually accepts a submission, so gear or
  a Lifestyle could be committed over budget against bonded foci. Fixed in the same lines
  (2026-08-01 decisions-log entry). See `spec/worklogs/WP93.md`.

- [ ] **WP94 — Surface the Matrix stat block on gear already being sold, and cap its Availability.**
  Goal: close §3. No new purchase flow — these items are already in `STARTER_GEAR_CATALOG`; what's
  missing is that their entire printed stat block is discarded at load time and that the
  Availability ≤ 12 ruling was never applied to flat-cost gear.
  Deliverables: `chummer5.data.gear.load_gear` reads `<devicerating>`, `<attack>`, `<sleaze>`,
  `<dataprocessing>`, `<firewall>`, `<programs>`, `<attributearray>` into optional fields;
  `StarterGearItem` carries them; the character sheet renders them for the Commlinks / Cyberdecks /
  Rigger Command Consoles categories; `build_starter_gear_catalog` applies the Availability ≤ 12 cap
  **to those three categories only**, with a comment saying plainly that the general flat-gear
  backfill is a separate, unscheduled job (see `spec/decisions-log.md`).
  Notes and traps: `<attributearray>` is `"4,3,2,1"` — an *assignable* set of four Matrix attributes
  in descending order (p. 439), not four labelled columns. Render it as the book does (one array),
  or the display asserts a fixed assignment the rules don't make. `Living Persona` is `<hide/>` and
  `Custom Commlink` is formula-priced; neither is in the catalog today and neither should arrive.
  Depends on: nothing new (independent of WP91-93 — may land first).
  Acceptance: `pytest`/`ruff`/`mypy` green; the three categories drop to **8 RCCs / 7 cyberdecks /
  6 commlinks**, each removed row asserted absent by name; every retained row's stat block asserted
  against the tables in `vehicles_and_riggers_chapter.md` §6; the total catalog count in
  `chummer5.data.gear`'s docstring updated rather than left stale.

- [ ] **WP95 — Unmodeled-effect registry: the rigger surface.** Closes §4 and the display half of
  §1's rigger-interface gap.
  Goal: every rigger-reachable aspect this project offers gets a row in Project Overview's registry
  *and* an `unmodeled_effect_note` the player actually sees, per that table's own hand-kept-mirror
  rule.
  Deliverables: an `unmodeled_effect_note` for `Control Rig` in
  `chummer5.data.cyberware.UNMODELED_EFFECT_NOTES` (mechanism already exists); a new
  `unmodeled_effect_note` field on `StarterGearItem` plus a `_UNMODELED_EFFECT_NOTES` dict in
  `chummer5.data.gear` (mechanism does **not** exist for gear today — `engine.derived
  .unmodeled_effect_notes` already walks `resources_selection.gear` via `getattr`, so only the
  catalog side is missing), covering RCCs, cyberdecks, commlinks and the 6 autosofts; a note on the
  `Vehicle` dataclass covering "every printed stat feeds Vehicle Tests/Vehicle Combat, which don't
  exist here" **and** the rigger-interface gap ("a vehicle bought here cannot be jumped into: p. 265's
  1,000¥ Rigger Interface is a modification, excluded from this phase by the 2026-07-21 ruling;
  drones ship with it built in"); the matching rows in `Project Overview.md`'s table, with the `Kind`
  column stating UI-reachability per WP77's rule.
  Notes and traps: the registry table and the catalog dicts must move **in the same commit** — that's
  the standing rule in Project Overview's own preamble. `tests/unit/test_augmentation_unmodeled_
  registry.py` pins which augmentation rows must have a note; adding `Control Rig` means updating it.
  Depends on: WP91 (for the `Vehicle` dataclass to hang a note on); WP94 (for the gear stat block the
  notes describe). Independent of WP93.
  Acceptance: `pytest`/`ruff`/`mypy` green; a character holding a Control Rig, an RCC and a drone
  renders three distinct notes in the sheet's "Unmodeled real effects" section; the registry table
  and the catalog dicts agree row-for-row.

- [ ] **WP96 — The Rigger synthetic fixture.** Closes Phase S §5's recorded "Known gap: no Rigger."
  Goal: a whole-character `RIGGER_FIXTURE` in `tests/fixtures/synthetic_fixtures.py` with the full
  hand-derived `expected`/`citations` treatment WP72-76/WP88 established, and a seventh row on Phase
  S §5's roster table.
  Notes and traps: **design him against §5's table, as every fixture except WP88's was** — the team
  is currently Human infiltrator / Ork muscle / Human hermetic / Elf face / Dwarf decker / Human
  wetwork, so pick attributes and a metatype that don't duplicate a peak. He needs a Control Rig
  (a full Essence point at rating 1, or two at rating 2 — an Essence interaction none of the existing
  fixtures has in that shape), Pilot/Gunnery skills, at least one **drone** and one **vehicle** (so
  both Condition Monitor formulas are asserted), and an RCC (so §3's stat block is asserted on a real
  character, not only in a catalog test). Requires new `SyntheticCharacter` fields and
  `resolve_metric` keys for the vehicle side — follow WP86/WP87's precedent of widening the harness
  without touching the existing fixtures' literals.
  Depends on: WP92, WP93, WP94, WP95.
  Acceptance: `pytest`/`ruff`/`mypy` green with the six existing fixtures' literals **unchanged**;
  `assert_fixture` passes with every `expected` key carrying a citation; both Condition Monitor
  formulas asserted; Phase S §5's roster table and its role-coverage/attribute-spread paragraphs
  updated to seven runners **and its "Known gap: no Rigger" sentence retired**;
  `spec/worklogs/WP96.md` written.

**Explicitly out of this phase, each for a stated reason:**
- **Vehicle/drone modifications** — the 2026-07-21 ruling, unchanged by §1. Its one real cost (a
  bought vehicle can't be rigged) becomes a registry row in WP95 rather than a reversal.
- **Vehicle combat, Vehicle Tests, drone combat, jumping in** — no test-resolution subsystem exists;
  Project Overview has excluded Matrix rules since MVP.
- **The general flat-gear and cyberware Availability backfill** — sized concretely in
  `spec/decisions-log.md`'s 2026-08-01 entry (7 flat cyberware rows over the cap, plus 17
  rating-scaled rows whose top ratings exceed it, plus every non-rigger flat-gear category). WP94
  closes only the three rigger-adjacent gear categories. Still unscheduled, now with numbers.
- **The general gear unmodeled-effect backfill** — WP95 adds the *mechanism* to `StarterGearItem`
  and uses it for the rigger surface only. The other ~50 gear categories stay unannotated, the same
  way WP79 annotated cyberware without claiming every catalog.
