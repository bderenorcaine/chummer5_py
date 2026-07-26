[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase B — Static rules data

- [x] **WP2 — Metatype & priority data loader.**
  Goal: load metatype and priority-table rules data as typed Python structures.
  Deliverables: `src/chummer5/data/metatypes.py` parsing `legacy/Chummer/data/metatypes.xml` (attribute
  min/max/aug per metatype + metavariants) into frozen dataclasses; `src/chummer5/data/priorities.py`
  parsing `legacy/Chummer/data/priorities.xml`, **Standard table only** (Heritage/Attributes/Skills/
  Resources categories; Talent category loaded but MVP only consumes its "E - mundane" entry).
  Depends on: WP1.
  Acceptance: unit tests assert known hand-checked values (e.g. Human attribute ranges from
  `metatypes.xml`; priority-A Heritage karma/value table from `priorities.xml`).

- [x] **WP3 — Quality & skill data loader.**
  Goal: load quality and skill rules data.
  Deliverables: `src/chummer5/data/qualities.py` parsing `legacy/Chummer/data/qualities.xml` (id, name,
  category, karma cost, limit, raw bonus node); `src/chummer5/data/skills.py` parsing skill definitions
  (name, linked attribute, category/group). Restrict the loaded/offered quality catalog to
  `source == "SR5"` (96 of 803 entries — see "MVP content scope" note above) before applying the
  bonus-node classification below; `skills.xml`'s 76 entries are already all `source == "SR5"`, so
  no equivalent filtering is needed there. Classify each in-scope quality's bonus node as
  "MVP-supported" (flat attribute/skill bonus) or "not yet supported" — this classification is what
  WP8 filters on.
  Depends on: WP1.
  Acceptance: unit tests cover at least one supported and one unsupported bonus-node shape; loader
  reports counts of each so the split is visible.

