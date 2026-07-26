[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase E — Save/load

- [x] **WP11 — Native save format.**
  Goal: persist and reload a character in the project's own format.
  Deliverables: `src/chummer5/io/save_format.py` — JSON format mirroring the domain model.
  Depends on: WP10.
  Acceptance: round-trip tests (build → save → load → equal).

- [x] **WP12 — Legacy `.chum5` import.**
  Goal: bring a real legacy character into the new engine, for MVP-covered content only.
  Deliverables: extends WP4's parser into a real import path for mundane, priority-built,
  MVP-feature-only legacy saves.
  Depends on: WP4, WP10.
  Acceptance: successfully imports `Yeti-#ffffff2.chum5`; imports of saves with out-of-scope content
  (magic, cyberware, etc.) fail with a specific, itemized error rather than silently dropping data.

