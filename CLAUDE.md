# Agent instructions

This project runs almost entirely on agent-executed work packages (WPs) — see
`spec/Implementation Plan.md`. Read in this order for a fresh conversation picking up a WP, and stop
as soon as you have what you need rather than reading everything:

1. `spec/Implementation Plan.md` — index only: "How to use this plan," the cross-cutting notes, and
   the phase table. Find your WP's phase row.
2. `spec/plan/phase-<letter>-<slug>.md` — the phase file the table points at. This has your WP's
   actual goal/deliverables/acceptance criteria, plus the phase's own intro context.
3. `spec/Project Overview.md` — architecture, stack, and design decisions. Skim once per
   conversation; you likely don't need to re-read it if you already have it from earlier in the
   session.
4. Only if your WP's phase file points at one: `spec/decisions-log.md` (dated scoping rulings),
   `spec/rulebooks/learnings.md` (index into `spec/rulebooks/learnings/phase-<letter>.md` — rulebook
   citations already extracted, grouped by phase), or `spec/worklogs/WP<n>.md` (a specific prior WP's
   retrospective detail).

Don't read every phase file or every worklog "just in case" — that defeats the point of the split.
Each phase file's own "Depends on" lines tell you when you genuinely need another phase's content.

## Rulebook lookups: chapter extraction before the PDF

`spec/rulebooks/character_creation_chapter.md` is "Creating a Shadowrunner" (core rulebook pp. 62-104,
Steps One-Nine — metatype, priorities, attributes, skills, qualities, contacts, resources, lifestyle,
chargen-time Karma spend) already extracted verbatim, with its own cross-reference index for pages it
points at elsewhere in the book. **Check this file first for anything in that scope.**

**Everything under `spec/rulebooks/` is gitignored and local-only** — the PDF, the chapter
extractions, and `learnings.md` + `learnings/` all reproduce copyrighted rulebook text. Read and
update them freely, but never commit them, never `git add -f` them, and never copy rulebook prose
into tracked files (code, tests, worklogs, decisions-log, commit messages). Tracked files cite a
page number and paraphrase; the verbatim text stays in `spec/rulebooks/`. Only open
`spec/rulebooks/Shadowrun_Fifth_Edition_Core_Rulebook.pdf` (via `pdftotext -layout`, not a raw read —
see existing worklogs for the pattern) when the chapter extraction doesn't cover it, or when a citation's
exact page/wording still needs pinning down for `learnings.md`.

## Closing out a WP

- One WP per commit, message `WPn: short description` (see `git log` for the existing style).
- Tick the checkbox in the WP's phase file as part of that commit.
- If the WP resolved a rulebook question via the PDF, record the citation in the relevant
  `spec/rulebooks/learnings/phase-<letter>.md` (create the phase file if the phase doesn't have one
  yet, and add it to `learnings.md`'s index table). These files are gitignored — the update stays
  local and is not part of the commit.
- If the WP surfaced a scoping decision, correction, or cross-phase finding, add a dated entry to
  `spec/decisions-log.md`.
- `spec/worklogs/WP<n>.md` — write a retrospective entry for non-trivial WPs, matching the existing
  worklogs' depth (research done, decisions made, traps hit).
