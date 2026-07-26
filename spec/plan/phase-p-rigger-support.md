[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase P — Post-MVP: Rigger support (research-intro only; no WPs assigned yet)

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

No WP numbers are assigned yet; the next work package after this research pass lands should continue
from WP60 (WP55-56 were claimed by Phase O's own SINner/unmodeled-effects-disclosure WPs; WP57-59
were claimed by Phases Q/R/S — the spec reorganization, architecture-cleanup audit, and
fixture-strategy research pass added 2026-07-24, after Phase P's own research-intro section was
written).
