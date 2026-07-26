[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase Q — Post-MVP: Spec reorganization (the phase-cut point)

**Why this phase exists.** By the end of Phase O (WP56), `Implementation Plan.md` had grown to ~1940
lines and `rulebooks/learnings.md` to ~1428 lines — both append-only logs that every fresh WP
conversation was implicitly expected to read in full per this plan's own "How to use this plan"
section, even though the overwhelming majority of that content is finished-phase history irrelevant
to whatever WP a given conversation is actually executing. `Project Overview.md`'s "Open questions"
section had grown the same way — a dated decision log masquerading as part of the evergreen
architecture reference. This phase is a deliberate pause to fix the *shape* of the project's own
documentation before continuing content work, the same instinct that produced Phase G's `Character`
fold: restructure once the accumulated shape stops paying for itself, rather than patching around it
WP after WP.

- [x] **WP57 — Split the plan, the learnings log, and the decision log into an index + per-phase/
  per-topic files; add the PDF-vs-chapter-extraction rule for fresh agent conversations.**
  Goal: cut the token cost of orienting a fresh WP conversation, without losing any existing content
  or breaking any existing cross-reference.
  Deliverables:
  - `spec/Implementation Plan.md` keeps the "How to use this plan," "Notes that shape the plan," and
    "Repo/package layout" sections (genuinely cross-cutting, cheap to read) plus a new phase-index
    table; each phase's own WP entries move verbatim into `spec/plan/phase-<letter>-<slug>.md`
    (Phases A-P, plus this phase's own file and Phases R/S below).
  - `spec/rulebooks/learnings.md` keeps its short intro and becomes an index; each phase's citation
    entries move verbatim into `spec/rulebooks/learnings/phase-<letter>.md`, grouped by which WP's
    plan-entry they support (not by original chronological position — e.g. the "Pre-Phase-K research"
    entry, written between WP32 and WP35's own entries, moves into `phase-k.md` since it's Phase K
    content, not Phase J).
  - `spec/Project Overview.md`'s dated "Open questions" section (11 entries, 2026-07-18 through
    2026-07-24) moves verbatim to a new `spec/decisions-log.md`; `Project Overview.md` itself keeps
    only current-state architecture, goals, scope, and design-decision content — no dated entries.
  - New root `CLAUDE.md`: states the doc-reading order for a fresh conversation (this plan's index,
    then the relevant phase file, then `Project Overview.md`), and explicitly directs agents to
    `spec/rulebooks/character_creation_chapter.md` **before** opening
    `Shadowrun_Fifth_Edition_Core_Rulebook.pdf` for anything covered by Steps One-Nine — the PDF stays
    the authority for whatever the chapter extraction doesn't cover (later chapters, tables the
    extraction's own cross-reference index points at).
  - Every internal cross-reference updated to the new paths (e.g. `Implementation Plan.md`'s own
    "Notes that shape the plan" pointer to Project Overview's Open Questions section now points at
    `decisions-log.md`; Phase P's "next WP number" note updated for Phases Q/R/S claiming WP57-59).
  - `spec/worklogs/` is left untouched — already the right per-WP granularity this reorg extends to
    the other three documents, nothing to fix there.
  Depends on: nothing new (pure documentation restructuring, zero source/test changes).
  Acceptance: every phase's WP entries and every learnings entry accounted for (line-count spot
  checks against the pre-split originals); no dangling relative link; `pytest`/`ruff`/`mypy` untouched
  and green (this WP touches no `src/`/`tests/` files at all).
