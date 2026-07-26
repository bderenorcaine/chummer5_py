[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase R — Post-MVP: Architecture cleanup (research-intro; WP59 onward pending its own audit)

**Why now.** Raised in the same 2026-07-24 session as Phase Q, after 56 WPs of incremental,
mostly-additive design. This project's own discipline holds up well under a quick audit — a repo-wide
grep for `TODO`/`FIXME`/`XXX`/`hack` across `src/` returns **zero hits**, and nearly every
"deliberately not X" comment found (`grep -rn "deliberately not\|not an oversight"` across `src/`)
is a documented, considered scope boundary, not silent debt. So this phase is *not* "pay down a pile
of hacks" — it's two narrower, concretely-grounded things surfaced this session, plus a proper audit
pass before committing to more than that.

**Finding 1 — `chummer5.web.app` is a single 4,397-line file** (largest in the repo by ~4.5x; next is
`io/save_format.py` at 962, then `io/legacy_import.py` at 795). Every chargen route and every
context-builder for every phase (metatype/attributes/skills/qualities/contacts/resources/lifestyle,
then magic, cyberware, bioware, spirits, foci, mentors, karma-buying) lives in this one module,
accreted one WP at a time with no phase ever owning a split. Worth a real look at whether it
naturally decomposes along chargen-step boundaries (mirroring `engine/`'s own per-aspect module
split) — but this needs an actual read of the file's route/context-builder boundaries before
committing to a specific split, not a guess from its size alone.

**Finding 2 — the `submit_attributes`-vs-`submit_priorities` asymmetry `Project Overview.md` already
flags** ("Character as the single aggregate" section): attribute-point edits still call
`create_character()` fresh instead of `dataclasses.replace()`, unlike every other post-WP18 mutation
path. Documented there as "a real, intentional asymmetry... left for a future WP to unify if it's
ever worth it, not an oversight" — this phase is the candidate for that "if it's ever worth it" call,
not an automatic yes.

**Everything else is genuinely unknown until audited.** Unlike Phase K/P, this phase's own candidate
list wasn't built from a systematic read of `src/` — only from what surfaced incidentally while
scoping Phase Q. Do the audit before assuming these two findings are the whole scope.

- [ ] **WP58 — Architecture audit: confirm/extend this phase's candidate list before splitting into
  cleanup WPs.**
  Goal: a real, systematic pass — not the incidental grep above — over `src/chummer5/` for
  consolidation/split candidates, producing the actual WP breakdown for the rest of this phase.
  Deliverables:
  - A structural read of `web/app.py`: enumerate its route/context-builder groups, confirm whether a
    per-chargen-step split (e.g. `web/routes/{metatype,attributes,skills,...}.py`) is clean or whether
    shared session/context-builder helpers make a different boundary more natural; decide and document
    a target shape (or explicitly decide the file is fine as-is and retire this finding).
  - Confirm or retire the `submit_attributes`/`replace()` asymmetry as worth fixing — check whether
    any real bug traces back to it (the same "keep everything except the one field that changed"
    argument WP18/WP19 made for the other mutation paths) or whether it's genuinely inert.
  - A second pass over `io/save_format.py` and `io/legacy_import.py` (962 and 795 lines respectively,
    each having grown by one mechanical addition per WP since WP18/WP20) for the same
    accretion-without-a-split pattern `web/app.py` shows more acutely — confirm whether either has
    reached a size worth splitting or is still proportionate to its actual job.
  - Produce the resulting cleanup WP list (numbers, scope, dependencies) as an addition to this phase
    file, the same way Phase K's own intro was scoped before WP36-42 were written.
  Depends on: nothing new.
  Acceptance: `pytest`/`ruff`/`mypy` untouched and green (audit only, no source changes); this phase
  file updated with a concrete WP59+ breakdown or an explicit "nothing here is worth the churn"
  verdict per candidate, not left as an open question.
