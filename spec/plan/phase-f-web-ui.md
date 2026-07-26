[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase F — FastAPI/HTMX UI

- [x] **WP13 — Web app skeleton.**
  Goal: the UI stack runs end to end, doing nothing yet.
  Deliverables: `src/chummer5/web/app.py` (FastAPI app factory), Jinja2 base layout, HTMX vendored
  locally (not CDN-loaded, to keep the app fully offline/local-first), `uvicorn` dev-run instructions,
  one trivial page.
  Depends on: WP1.
  Acceptance: `uvicorn chummer5.web.app:app` serves the trivial page; an HTMX-driven interaction on that
  page round-trips through the server.

- [x] **WP14 — Priority & metatype selection UI.**
  Goal: first real chargen screen.
  Deliverables: assign priority letters to the 4 MVP categories (Talent forced to E, not offered as a
  choice) and pick a metatype; server-side in-memory character-in-progress state keyed by a session
  cookie.
  Depends on: WP6, WP13.
  Acceptance: manual walkthrough creates a metatype+priority selection that matches what WP6's engine
  would produce for the same inputs.

- [x] **WP15 — Attribute & skill allocation UI.**
  Goal: spend attribute/skill points through the browser.
  Deliverables: point-spend forms with HTMX-driven live remaining-points and dice-pool preview.
  Depends on: WP7, WP14.
  Acceptance: manual walkthrough; values match engine output for the same inputs.

- [x] **WP16 — Qualities, contacts & resources UI.**
  Goal: round out chargen inputs.
  Deliverables: quality picker (MVP-supported catalog only), contacts editor, nuyen spend screen.
  Depends on: WP8, WP9, WP15.
  Acceptance: manual walkthrough; values match engine output for the same inputs.

- [x] **WP17 — Character sheet + save/load UI. (UI MVP milestone)**
  Goal: finish and persist a character through the browser, start to finish.
  Deliverables: read-only finished-character view (derived stats), save/download (native format via
  WP11), load/upload (native format + legacy `.chum5` import via WP12).
  Depends on: WP10, WP11, WP12, WP16.
  Acceptance: full manual walkthrough — create a mundane priority character in the browser end to end,
  save it, reload it, and (separately) import `Yeti-#ffffff2.chum5` — all producing correct values.
  **UI MVP is complete when this passes.**

