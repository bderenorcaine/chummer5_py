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

- [x] **WP58 — Architecture audit: confirm/extend this phase's candidate list before splitting into
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

## Audit results (WP58, 2026-07-27)

**Finding 1, confirmed and scoped — `web/app.py` decomposes cleanly along chargen-step boundaries.**
A full structural read (every `def`/`@app.` line, not just the size) shows the file is already
internally organized this way, just not physically split: for nearly every chargen step (metatype/
priorities, attributes, talent, skills, knowledge, spells, powers, spirits, qualities, contacts,
resources, lifestyle, cyberware+bioware, foci) the same four pieces exist and are grep-adjacent —
one or more `_parse_*` form helpers, zero or more `_relink_*`/`_replace_committed_*` Improvement-
carry-forward helpers, one `_*_context` builder, and that step's own `@app.post("/ui/...")` route
(all 21 routes live as closures inside one `create_app()` factory, lines 3319-4499). Two pieces are
genuine cross-cutting aggregators, not step-scoped: `_character_sheet_context` (2484-2813, ~330
lines) reads every committed selection off `Character` for the read-only summary page, and
`_chargen_body_context` (3065-3319, ~250 lines) composes every step's own context builder into one
dict for the full-page/full-body render (`index` and `submit_priorities` are the only two routes
that need it — every other `submit_*` route re-renders only its own single-section fragment).

Two structural facts make the split mechanically low-risk, not just plausible: (1) `templates`
(`Jinja2Templates`) and `resolve_session` are both created *inside* `create_app()` today, but neither
actually closes over anything `create_app()`-local — `resolve_session` only reads
`request.app.state.sessions`, and `templates` only needs `TEMPLATES_DIR`, a module constant already
computed at import time. Both can move to plain module-level definitions with zero behavior change,
which is what makes route functions extractable into separate `APIRouter`-based modules at all. (2)
The 15 test files that import from `chummer5.web.app` directly (`grep -rl` count) import either
`create_app` (14 of 15 — stays put, it's the one thing that doesn't move) or a handful of module-level
catalog constants (`LIFESTYLES`, `CYBERWARE`, `BIOWARE`, `MAX_CONTACT_ROWS`, `MVP_QUALITIES`,
`MUNDANE_SKILL_GROUPS`, `MUNDANE_SKILLS` — 7 names total, across 6 files) — a real but small,
enumerable migration cost, not an open-ended one.

Target shape (WP62's own job to execute, not fully pre-designed here — per this file's own Phase K
precedent, "decide and document a target shape," not hand-place every line before implementation
starts):
- `web/catalogs.py` — every `load_*()` call currently at `app.py` module scope (`METATYPES`,
  `PRIORITIES`, `SKILLS`, `QUALITIES`, `CYBERWARE`, `BIOWARE`, ... ) plus the small number of
  catalog-derived constants nearly every step needs (`MVP_QUALITIES`, `MUNDANE_SKILLS`, ...).
- `web/forms.py` — the genuinely generic `_parse_*` helpers used by 2+ steps (`_parse_points`,
  `_parse_specializations`); step-specific parsers (`_parse_contacts`, `_parse_bound_spirits`, ...)
  move with their own step module instead.
- `web/routes/{priorities,attributes,talent,skills,knowledge,spells,powers,spirits,qualities,
  contacts,resources,lifestyle,cyberware,foci}.py` — each an `APIRouter` plus that step's own parse/
  relink/context-builder helpers. `metatype_options_fragment`/`talent_options_fragment` (small GET
  fragment routes) travel with `priorities.py`/`talent.py` respectively, the steps they refresh.
  `resolve_session` and the two aggregator context builders need a home too; simplest option is a
  shared `web/routes/priorities.py` (since `index`/`submit_priorities` are their only two callers) —
  decide at implementation time whether `_character_sheet_context` instead travels with a new
  `web/routes/character.py` (housing `character_sheet`/`download_save`/`load_save`/
  `import_chum5_route`, its own natural home) — no other step module needs to import it, so either
  placement is import-cycle-safe.
- `web/app.py` shrinks to `create_app()` itself: construct the `FastAPI`/`SessionStore`/static mount/
  `Jinja2Templates`, `app.include_router(...)` once per step module, and (for the 6 catalog-constant
  test imports above) re-export the handful of names those tests still expect from `chummer5.web.app`
  rather than editing 6 test files' imports — cheaper and just as correct.

No import cycle risk identified: route modules depend downward on `catalogs.py`/`forms.py`/
`chummer5.engine.*`/`chummer5.data.*` only; only the priorities/character aggregator modules depend
sideways on every other step module's context-builder function, and nothing depends back on them.

**Finding 2, confirmed as worth fixing, not inert.** Read both `submit_priorities` (3403-3535) and
`submit_attributes` (3536-3670) side by side. `submit_priorities` (post-WP19) needs exactly two
relink calls after its `dataclasses.replace(previous, ...)` — `_relink_metatype_qualities` (metatype
may have changed) and `_relink_contact_selection` (CHA may have changed) — both substantive, not
asymmetry artifacts. `submit_attributes`, still on its pre-WP19 `create_character()`-fresh shape,
needs **seven**: `_relink_quality_improvements`, `_relink_metatype_qualities`, `_relink_contact_
selection`, `_relink_magic_selection`, `_relink_cyberware_selection`, `_relink_bioware_selection`,
`_relink_foci_selection`, plus an 8-field explicit carry-forward (`skill_allocation`,
`resources_selection`, `lifestyle_selection`, `bound_spirit_selection`, `knowledge_selection`,
`karma_skill_selection`, `karma_knowledge_selection`, plus the two Karma/magic points it computes
itself) inside one `replace()` call at the end. Every one of WP23/29/34/45/47/49/53 had to add a new
line to this specific function as its own new Character-level selection shipped — a real, repeating
"remember to update this one function too" tax `submit_priorities` doesn't pay, and a real latent-bug
shape (a future WP that forgets the new relink line silently drops that selection's Improvements on
the next attribute edit — the exact class of bug WP18/19 already fixed once for `submit_priorities`
itself). Worth fixing. Note for whoever implements it: unlike `submit_priorities`'s metatype-unchanged
case, `submit_attributes` can change CHA and (when magic-active) MAG directly, so `_relink_contact_
selection`'s CHA-recompute and the route's own separate MAG-points handling both stay
needed after the switch — only the sheer count of *Improvement re-landing* calls collapses.

**`io/save_format.py`'s `build_character` (607-962, ~355 lines) — retired as a split candidate.**
Read in full: unlike `web/app.py`'s independent per-step chunks, this is one genuinely sequential
9-stage pipeline (metatype/quality → knowledge → skills/contacts/lifestyle/resources → cyberware →
bioware → magic/spells/powers → karma-attribute → karma-skill/knowledge → spells(Karma) → bound
spirits → foci) where each stage's `create_*` call reads `character.karma_remaining` or an attribute
value that only holds its correct value because every earlier stage already ran and was folded in via
`replace()`. The function's own inline comments already document *why* each stage sits exactly where
it does (a fixed evaluation order, cited stage-by-stage) — splitting it into per-stage helper functions
would mean passing an ever-growing bag of already-computed values into each one, trading one linear,
already-well-commented read for several smaller functions with wider parameter lists and no
independent reuse. Proportionate to its actual job; not a cleanup candidate.

**`io/legacy_import.py`'s `import_legacy_character` (435-765, ~330 lines) — considered, retired.**
Structurally different from `build_character`: its per-aspect chunks (attributes, skills,
specializations, knowledge, qualities, contacts, talent/magic, spells, powers) are each independent —
every chunk reads only from the `legacy` argument and the static catalogs, writes a local variable,
and none reads another chunk's output; they only converge at the single closing `create_character_
save(...)` call. This makes it a *legitimate* split candidate, unlike `build_character`, on structure
alone. Retired anyway: each chunk is used exactly once, several hundred words of the file's existing
per-field commentary explain legacy-format quirks specific to that exact call site (e.g. the
`qualitysource=Metatype` disambiguation, the native-language 0-cost carve-out), and extracting them
into same-file-adjacent private functions would mean threading the same catalog parameters into each
without eliminating any duplication or enabling any reuse — the Project Overview's own "don't add
abstractions beyond what the task requires" / "three similar lines is better than a premature
abstraction" standard argues against this split, not for it. `io/save_format.py` and
`io/legacy_import.py` are both left as-is; neither gets a cleanup WP.

**Resulting cleanup WP list** (numbers continue from WP61, the last one claimed — Phase S's own WP59
is untouched by this list):

- [ ] **WP62 — Split `web/app.py` into per-chargen-step route modules.**
  Goal: execute the target shape decided above — no behavior change, pure move/re-organization.
  Deliverables:
  - `web/catalogs.py`, `web/forms.py`, `web/routes/{14 step modules + character.py}` per the shape
    above; `web/app.py` shrinks to `create_app()` plus re-exports of the ~7 catalog names the existing
    test suite imports from it directly (`LIFESTYLES`, `CYBERWARE`, `BIOWARE`, `MAX_CONTACT_ROWS`,
    `MVP_QUALITIES`, `MUNDANE_SKILL_GROUPS`, `MUNDANE_SKILLS`).
  - Decide, when it's actually in front of you, the one placement question this audit left open:
    which module hosts `_character_sheet_context` vs. `_chargen_body_context` (both plausible homes
    listed above; either is import-cycle-safe).
  - No template changes needed — URL paths (`/ui/attributes`, etc.) are unchanged; only which Python
    module registers each route moves.
  Depends on: nothing new.
  Acceptance: `pytest`/`ruff`/`mypy` green with zero test edits beyond what the catalog re-export
  above avoids (if any test needs an import path fixed anyway, that's fine, just keep the list short);
  a manual `uvicorn` smoke pass through at least one full chargen (mirrors WP61's own verification
  style) confirming no route regressed; `web/app.py`'s own line count drops to a small fraction of
  today's 4,499.

- [ ] **WP63 — Unify `submit_attributes` onto the `dataclasses.replace()` shape.**
  Goal: give `submit_attributes` the same WP19 treatment `submit_priorities` already has, retiring
  the relink-call accretion Finding 2 documents.
  Deliverables:
  - `submit_attributes` builds its new `Character` via `dataclasses.replace(previous, ...)` instead
    of a fresh `create_character()` call, the same shape `submit_priorities` uses.
  - Remove `_relink_quality_improvements`, `_relink_magic_selection`, `_relink_cyberware_selection`,
    `_relink_bioware_selection`, `_relink_foci_selection` calls from this route once `replace()` makes
    them redundant (their `Improvement`s already sit in the carried-forward `previous.improvements`
    index); confirm whether any of these five helpers becomes fully dead code (no other call site) and
    delete it if so, rather than leaving an unused helper behind.
  - Keep `_relink_metatype_qualities` (harmless/needed either way, metatype is unchanged on this route
    so this may already be a no-op — confirm) and `_relink_contact_selection` (CHA can genuinely
    change here) — both stay, per this audit's own note above.
  - Existing tests (`test_web_attribute_skill_allocation.py` and any test exercising a magic/
    cyberware/bioware/foci character across an attribute edit) must still pass unchanged in behavior,
    only in implementation.
  Depends on: WP62 only in the sense that `submit_attributes` will live in a different file by then —
  either ordering is functionally fine; doing WP62 first avoids editing this logic twice in two
  different modules.
  Acceptance: `pytest`/`ruff`/`mypy` green; a new or updated test proving the specific bug class this
  fixes is now structurally impossible — e.g. a synthetic case with an Adept's power selection,
  cyberware, and bioware all committed, then an attribute edit, confirming every Improvement survives
  without any relink call for that selection type existing in the route at all.
