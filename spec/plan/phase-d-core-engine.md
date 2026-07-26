[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase D — Core engine (headless)

- [x] **WP5 — Improvement engine core.**
  Goal: the base+improvements composition mechanism, proven in isolation.
  Deliverables: `src/chummer5/engine/improvements.py` — `Improvement` dataclass (source type/id, target,
  value, rating, unique-name dedup group) + index (`dict[(type, target)] -> list[Improvement]`) +
  `resolve()` implementing sum + `UniqueName` dedup ("highest bonus wins").
  Depends on: WP1.
  Acceptance: unit tests using **synthetic** improvements only (no XML involved) — proves the resolution
  math before any real rules content touches it, including a stacking/dedup case.

- [x] **WP6 — Metatype selection & attribute allocation.**
  Goal: first real slice of chargen — pick a metatype, spend attribute points.
  Deliverables: `src/chummer5/engine/character.py` (`Character` aggregate, mundane fields only);
  metatype selection from a Heritage priority letter (via WP2 data), restricted to `metatypes.xml`
  entries with `source == "SR5"` (Human/Elf/Dwarf/Ork/Troll base types only — metavariants and
  non-core metatypes like Centaur/Sasquatch/A.I./Shapeshifters are excluded from MVP; see "MVP
  content scope" note above) when cross-referencing against a Heritage priority's metatype list;
  attribute point allocation from an Attributes priority letter within metatype min/max;
  `Attribute.Value = metatype minimum + points spent + Σ improvements` (via WP5).
  Depends on: WP2, WP5.
  Acceptance: tests against WP4's mundane fixture set (attribute totals) and specifically against
  `Yeti-#ffffff2.chum5` (allocation budget/spend logic).

- [x] **WP7 — Skill allocation & dice pools.**
  Goal: active skills, groups, specializations, and the dice pool formula.
  Deliverables: `src/chummer5/engine/skills.py` — Skills-priority-letter → point pools; dice pool =
  attribute + rating (+2 specialization).
  Depends on: WP3, WP6.
  Acceptance: tests against the fixture corpus.

- [x] **WP8 — Quality selection & minimal Improvement bonuses.**
  Goal: qualities affect karma and, for the supported subset, feed the Improvement engine.
  Deliverables: `src/chummer5/engine/qualities.py` — positive/negative quality picking, karma cost,
  negative-quality karma cap; only WP3's "MVP-supported" qualities produce `Improvement` records.
  Depends on: WP3, WP5, WP6.
  Acceptance: tests against fixtures restricted to MVP-supported qualities; an explicit test that an
  unsupported-bonus quality is excluded from the offered list rather than silently mis-applied.

- [x] **WP9 — Contacts & starting resources.**
  Goal: nuyen, contacts, and a minimal starting-gear stub.
  Deliverables: `src/chummer5/engine/resources.py` — Resources-priority-letter → starting nuyen;
  contacts (connection/loyalty, karma cost beyond free points); a deliberately minimal starter-gear
  purchase (flat nuyen deduction against a small curated list — explicitly not the full gear catalog).
  Depends on: WP6.
  Acceptance: tests against fixtures for nuyen/contact math.

- [x] **WP10 — Derived stats + full end-to-end regression. (Headless MVP milestone)**
  Goal: a complete, validated mundane priority-built character, computed headlessly end to end.
  Deliverables: `src/chummer5/engine/derived.py` — initiative, physical/mental/social limits, condition
  monitor boxes as pure functions of finalized attributes. Add the full-character regression test.
  Depends on: WP6, WP7, WP8, WP9.
  Acceptance: for every curated fixture, build the character end-to-end through the engine and diff every
  MVP-covered field against the legacy-computed values. **Headless MVP is complete when this passes.**

