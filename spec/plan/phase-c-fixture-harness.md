[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase C — Regression fixture harness

- [x] **WP4 — Legacy `.chum5` fixture parser & golden corpus.**
  Goal: turn legacy save files into comparable ground truth.
  Deliverables: `src/chummer5/io/legacy_chum5.py` (or `tests/fixtures/` helper) extracting MVP-relevant
  fields (metatype, priority selections, attributes, skills, qualities, karma, nuyen) from a `.chum5`
  file. Curate the fixture set per the corpus note above: copy/reference all 11 mundane fixtures from
  `legacy/Chummer.Tests/TestFiles/` for derived-stat comparisons, flag `Yeti-#ffffff2.chum5` specifically
  for priority-allocation comparisons. Document the split in `tests/fixtures/README.md`.
  Depends on: WP1.
  Acceptance: parser round-trips known raw fields for all 11 curated fixtures; `tests/fixtures/README.md`
  lists which fixture backs which kind of assertion.

