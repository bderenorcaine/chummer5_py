[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase O — Post-MVP: Karma-buying (chargen-time leftover-Karma spend)

Scoped 2026-07-21. **Naming note, to avoid confusion with an explicitly-ruled-out feature**: this phase
is Step Seven's "leftover Karma" spend *within* Priority/Sum-to-Ten chargen — not the legacy engine's
separate **Karma-based build method** (`CharacterBuildMethod.Karma`, buying an entire character from a
large Karma pool instead of Priority), which this project's 2026-07-21 ruling keeps explicitly out of
scope (see Project Overview). The two are unrelated features that happen to share a word.

**A scope correction this phase's own scoping surfaced**: this project's chapter extraction
(`spec/rulebooks/character_creation_chapter.md`) deliberately excluded the rulebook's "Character
Advancement" section (pp. 103-107) as pure post-creation career-mode content. That's still the right call
for the section as a whole (training *time*, in-play Karma awards, career-mode qualities) — but Step
Seven's own text explicitly directs the player to "refer to the rules for improving the character in the
Character Advancement section (p. 103)" for the **Karma-cost formulas themselves** when spending leftover
Karma on attributes/skills at chargen. This phase needs those specific numbers even though the section
they're printed in was correctly excluded as a whole:

| Improvement | Karma cost |
|---|---|
| Attribute (any rating) | `new Rating x 5`, cumulative per rating step (Karma Advancement Table) |
| Active Skill | `new Rating x 2`, cumulative per rating step |
| Active Skill Group | `new Rating x 5`, cumulative per rating step |
| Knowledge/Language Skill | `new Rating x 1`, cumulative per rating step |

*(Re-verify this table directly via `pdftotext -layout` against the actual "Karma Advancement Table for
Attributes"/skill-cost prose on rulebook pp. 105-107 before implementing — transcribed here from this
session's own research pass for convenience, but the WPs below should confirm it themselves per this
project's "don't trust a secondhand transcription, re-extract" practice.)*

Today, qualities (WP8) and contacts (WP9) each spend Karma via **independent one-shot validation checks**
that don't share a running total with anything else or with each other beyond both drawing down the same
conceptual 25-Karma starting pool. **The foundational piece this phase needs first is a unified ledger**
— WP51 — that the later WPs (and, retroactively, qualities/contacts) draw from together.

**WP55 was added 2026-07-24**, after WP52 shipped and its own research surfaced a concrete, real gap
in the *quality* side of the Karma ledger rather than the attribute/skill side this phase was
originally scoped around: `Wesson.chum5`'s real `SINner (Corporate Limited)` quality is what makes
his real Karma-funded EDG purchase affordable, and this project has never been able to represent
that quality at all (a free-text quality-parameter mechanism this engine has never built — see
WP55's own entry below). Sequenced last in this phase since it depends on WP52's own finding, not on
WP53/WP54's skill/spell work.

**WP56 was added the same day, at the same time as a related policy ruling**: real but
out-of-engine-scope consequences (Notoriety, background checks, in-play test modifiers, ...) are no
longer, by themselves, a reason to exclude an otherwise-offerable aspect — they're tracked instead,
in Project Overview's new "Unmodeled real effects" section (which retroactively reversed WP55's own
original text, written earlier the same day, that had excluded SINner (Criminal) specifically for
its Notoriety bonus). WP56 gives that registry a player-facing home: a collapsible character-sheet
section listing, for whichever unmodeled-effect aspects the *current* character actually has, the
specific note from that registry — so a player looking at a finished character can see exactly what
isn't being computed, not just discover it by reading this document.

- [x] **WP51 — Unified Karma ledger.**
  Goal: give `Character` a single running "Karma remaining" value that every Karma-spending selection
  (qualities, contacts, and this phase's new attribute/skill/spell purchases) reads from and writes to
  together, replacing today's several independent one-shot checks — the same kind of foundational
  restructuring WP18 did for chargen selections generally, applied here specifically to Karma.
  Deliverables:
  - `chummer5.engine.character` (or a new `chummer5.engine.karma`): decide & document the representation
    — a computed property (`starting_karma - Σ every known Karma-spending selection's cost`) versus a
    genuinely stored, incrementally-updated field. Given `Character` is otherwise frozen and every
    selection is itself a frozen sub-object (WP18's own precedent), a **computed property** summing each
    present selection's already-known cost is likely the right shape (no new mutable state, consistent
    with "reconstruct wholesale to validate" for jointly-constrained values) — but confirm this holds
    once Phase M's Bound Spirits/Foci Karma costs and this phase's own new spend types are added, since
    the sum now spans more selection types than `Character` previously had to reason about jointly.
  - Retrofit `qualities.py`'s karma-cost accounting and `resources.py`'s contact-Karma accounting to
    report their cost through whatever shape this WP settles on, **without changing either's existing
    validation behavior** — this WP is a pure restructuring (WP18-style), not a behavior change; existing
    tests for both must pass unchanged.
  - Confirm the "starting Karma" figure itself: 25 at Step Four, but note it can arithmetically **exceed**
    25 by the time Step Seven begins if net Negative-Quality Karma exceeds net Positive-Quality Karma
    spent (confirmed in the rulebook's own worked examples — James ends Step Four with 26 Karma, not 25,
    having spent 19 on Positive Qualities and gained 20 from Negative ones). The ledger's "starting"
    value for Step Seven purposes is therefore **the post-Step-Four total**, not a fixed constant.
  Depends on: WP8, WP9 (retrofits both).
  Acceptance: `pytest`/`ruff`/`mypy` green; every existing WP8/WP9 test passes unchanged; a new test
  confirming the ledger's total matches the rulebook's own James/Rob/Kyra worked examples' arithmetic
  (25 → 26 / 25 / 26 respectively, per `character_creation_chapter.md`'s Step Four worked example) as a
  real, citable cross-check rather than only a synthetic one.

- [x] **WP52 — Karma-funded attribute increases.**
  Goal: let leftover Karma raise a Mental/Physical/Special attribute beyond its priority-derived budget,
  using the `new Rating x 5` formula. This is also the fix for the specific, previously-flagged gap in
  Project Overview's 2026-07-19 entry ("Karma-bought attribute points... never modeled... Wesson's own
  `<attribute name="EDG"><base>1</base><karma>1</karma></attribute>`") — that entry's own recommendation
  was to leave this unmodeled indefinitely "since nothing currently blocks on it"; this phase is the
  point at which something now does.
  Deliverables:
  - `chummer5.engine.character` (or wherever attribute resolution lives): a Karma-funded increment on top
    of `attribute_value`'s existing `metatype minimum + points spent + Σ improvements` formula, validated
    against WP51's ledger and the existing "only one Mental/Physical attribute may sit at natural maximum"
    rule (confirmed this restriction explicitly still applies to Karma-funded increases too, per the
    rulebook's own Step Seven text: "These rules still apply to when you are spending Karma").
  - `chummer5.io.legacy_import`: retire the itemized "nonzero-karma allocatable attribute" blocking
    reason WP28 added (confirm its exact current shape before removing/narrowing it) now that the
    underlying mechanic exists — re-attempt importing `Wesson.chum5` end to end as this WP's own
    acceptance case.
  - `chummer5.web`: extend the attribute allocation screen with a Karma-spend control once base points
    are exhausted, live-updating remaining Karma (WP15 precedent) via WP51's ledger.
  Depends on: WP51.
  Acceptance: unit tests for the `new Rating x 5` formula and the natural-maximum restriction under
  Karma spend specifically; integration test importing `Wesson.chum5` end to end (previously blocked,
  per WP28/Project Overview's own citation) confirming his Karma-bought EDG point resolves correctly —
  a real, existing fixture this phase directly unblocks, not a synthetic case.

- [x] **WP53 — Karma-funded skill/skill-group increases (including group-breaking).**
  Goal: let leftover Karma raise an Active skill (`new Rating x 2`), Active skill group
  (`new Rating x 5`), or Knowledge/Language skill (`new Rating x 1`) beyond its priority-derived budget,
  and implement the rulebook's specific Step Seven rule that **buying a Karma-funded specialization for a
  skill inside a purchased skill group breaks that group from that point forward** — explicitly called
  out as impossible in Step Five and only legal here (Step Five/Six text, `character_creation_chapter.md`:
  "This cannot happen in Step Five of character creation—you can only break up a skill group by buying a
  specialization for it in Step Seven").
  Deliverables:
  - `chummer5.engine.skills`: Karma-funded rating increases for individual skills/groups/Knowledge-
    Language skills, validated against WP51's ledger.
  - The group-breaking case specifically: buying a Karma-funded specialization (confirm the actual Karma
    cost for a chargen-time specialization purchase via `pdftotext -layout` over the Character Advancement
    pages before implementing — this session's own research pass found the *training-time* rule for
    specializations but did not resolve the Karma-cost figure; do not guess it) for a skill that's
    currently part of a group purchased via WP7's group-purchase path must: (a) charge the specialization
    cost from WP51's ledger, (b) "break" the group so each of its member skills becomes independently
    tracked from that point on (mirroring `SkillAllocation`'s existing group-vs-individual distinction,
    WP7's own shape), and (c) apply the specialization itself. Depends directly on WP50 (Step Five's
    specialization mechanism) existing first, since this is that same mechanism's Step-Seven/Karma-funded
    sibling, not a separate feature.
  Depends on: WP51, WP50.
  Acceptance: unit tests for all three Karma-cost formulas and the group-breaking transition (before:
  group intact at rating N; after specializing one member: that member specialized and independently
  rated, siblings still at rating N but now individually tracked). No real fixture is confirmed to
  exercise the group-breaking case specifically — flag as hand-verified if no fixture is found during
  implementation, per this phase's own honesty standard.

- [x] **WP54 — Karma-funded extra spells/complex forms.**
  Goal: let a Magician/Technomancer-equivalent... **note: Technomancer stays out of scope per this
  project's 2026-07-21 ruling, so this WP is Magician-only** — spend leftover Karma (5 Karma/spell, per
  the Additional Purchases table) on spells beyond a Talent option's free grant, extending WP26's
  existing `create_spell_selection` rather than replacing it.
  Deliverables:
  - `chummer5.engine.magic`: widen `create_spell_selection` (or add a sibling function) to accept an
    additional Karma-funded spell count on top of the Talent-granted budget, validated against WP51's
    ledger and the existing "max known = Magic Rating x 2" cap (Additional Purchases table) which already
    bounds the *combined* free+Karma-funded total, not just the free grant — confirm `create_spell_
    selection`'s existing cap check already reads this way or needs widening.
  - `chummer5.web`: extend the spell-picker screen (WP29) with a Karma-spend control once the free budget
    is exhausted.
  Depends on: WP51, WP26.
  Acceptance: unit test confirming a Karma-funded spell beyond the free budget is accepted up to the
  Magic-Rating-x-2 combined cap and rejected beyond it; no real fixture is confirmed to exercise
  Karma-funded extra spells specifically (both Miko/Wesson's own spell counts match their free grants
  exactly, per WP26's own acceptance notes) — hand-verified, documented as such.

- [x] **WP55 — SINner and the other selecttext-blocked-but-policy-eligible qualities (free-text
  quality-selection mechanism, 9 qualities offered).**
  Goal: offer SINner — surfaced as a real, concrete gap by WP52's own research, not a speculative
  addition: `Wesson.chum5`'s real `SINner (Corporate Limited)` pick is exactly what makes his real
  EDG Karma-buy affordable (its +15 Karma credit), and this project's inability to represent it is
  the specific, documented reason his `import_chum5()` still doesn't reach a full end-to-end
  success after WP52 (see `spec/worklogs/WP52.md` and Project Overview's matching 2026-07-23
  entry). **Widened 2026-07-24 (same day as the original entry) to cover every other quality WP22's
  own research already found blocked by the identical selecttext gap and nothing else** — not just
  SINner's 4 variants, but also Code of Honor, Codeblock, Social Stress, and Natural Immunity
  (Natural)/(Synthetic) — 5 more qualities, 9 total: WP22's own words for these 5 were "just as
  mechanically inert... as Tranche 2's 8 [`NO_EFFECT`] qualities... the only reason they weren't
  folded into `NO_EFFECT` alongside Tranche 2 is the missing free-text-selection mechanism." Once
  this WP builds that mechanism anyway (for SINner), leaving these on the table for a hypothetical
  future WP would just be re-paying the same research and re-derivation cost with nothing new to
  discover — they're already fully researched, right here.
  1. **The free-text-parameter gap (the shared, actual blocker for all 9).** Each carries a bare
     `<bonus><selecttext .../></bonus>` node — a free-text detail the player fills in (SINner:
     which SIN; Code of Honor: which protected group; Codeblock: which Matrix action; Social
     Stress: the cause/trigger of the stress; Natural Immunity: which disease or toxin) — and this
     engine has never built the general selecttext quality-parameter mechanism at all
     (`chummer5.data.qualities`'s bonus-node classifier has no case for `<selecttext>`; confirmed
     in WP22's own research, `spec/rulebooks/learnings.md`'s "selecttext-only" section). Building
     this — a free-text input on the quality picker, threaded through `QualitySelection`, the save
     format, and legacy import (`LegacyQuality`'s own recorded `<extra>` text) — is this WP's first
     real task, not a `_classify_bonus` tweak, and it's exactly the same mechanism regardless of
     which of the 9 qualities uses it (a plain string, stored and displayed, nothing more).
     **Still explicitly not extended to Home Ground or Prejudiced ×6** — both carry their own
     separate, non-trivial bonus logic on top of the free-text gap (Home Ground: a genuinely
     branching, 4-option bonus, at least one of which — Astral Acclimation — reduces a computed
     value this engine doesn't track at all; Prejudiced: a real dice-pool modifier for Social
     Tests) that needs its own research pass regardless of the selecttext mechanism's existence —
     flagged, not built here, mirroring this project's "flagged, not scheduled" precedent for other
     known-but-deferred gaps (e.g. the Availability cap).
  2. **The real, described narrative/mechanical weight (no longer blocking, now recorded).**
     Confirmed per-quality via `pdftotext -layout`, not assumed from WP22's own paraphrase:
     - **SINner ×4** (p. 84-85): background-check/arrest consequences across a full page for all 4
       variants; SINner (Criminal) additionally carries `<notoriety>1</notoriety>` (the wholly
       unmodeled Notoriety/reputation system this project shares with 18 other SR5 qualities).
       Karma: National -5, Corporate Limited -15, Criminal -10, Corporate -25 (the single
       largest-magnitude Negative quality in the SR5 core catalog).
     - **Code of Honor** (-15 karma, p. 79): an in-play, GM-adjudicated behavioral commitment to
       never kill/allow the killing of a chosen protected group — violating it costs Karma per
       adventure and raises Public Awareness; no test-resolution/reputation system to hang either
       consequence on.
     - **Codeblock** (-10 karma, p. 80): a chosen Matrix action always takes a -2 dice pool
       modifier — no Matrix rules exist in this engine at all.
     - **Social Stress** (-8 karma, p. 85): reduces the number of 1s required to glitch a
       Leadership or Etiquette test by 1 — no test-resolution/glitch system exists.
     - **Natural Immunity (Natural)** (4 karma, p. 76) / **(Synthetic)** (10 karma, p. 76): full
       immunity to one chosen disease or toxin — no toxin/pathogen subsystem exists (the same
       bucket Allergy's 8 SR5 variants and Resistance to Pathogens/Toxins are already in).
     Under the new policy, every one of these becomes a new row in Project Overview's "Unmodeled
     real effects" table — **this WP's own deliverables include adding all 9**, not just shipping
     the code. Karma cost/credit is applied in full for every one; only the listed consequence goes
     unmodeled.
  - **Mutual-exclusion validation, two independent instances.** SINner's own `<forbidden><oneof>`
    block (all 4 variants forbid each other) and Natural Immunity (Natural)/(Synthetic) each
    forbidding `Weak Immune System` (itself not offered, so this specific exclusion is practically
    unreachable today, but should still be implemented correctly, not skipped because it currently
    can't fire) both need *some* validation — WP22 already flagged "mutually exclusive quality" as
    a real, not-yet-built validation axis on `create_quality_selection` (its own "Deliberately
    deferred" list: Insomnia (Basic)/(Full), Distinctive Style/Blandness). Decide and document
    whether this WP builds that axis generally (letting those two deferred pairs ride along too) or
    scopes narrower checks just for what this WP's own 9 qualities need — either is acceptable, but
    the choice and its reasoning belong in this WP's worklog, not left implicit.
  - `chummer5.io.legacy_import`: resolve a legacy character's real picks among these 9 (name +
    `<extra>` free text) into the new selecttext-shaped selection instead of leaving them in
    `dropped_qualities`; re-attempt `Wesson.chum5` as this WP's own real acceptance case (his own
    worklog entry, `spec/worklogs/WP28.md`/`WP52.md`, already has the exact numbers: SINner
    (Corporate Limited), -15 Karma, needed on top of WP52's 20-Karma EDG purchase to reach 30
    available Karma against a 25-Karma-plus-quality-net budget).
  - `spec/Project Overview.md`: add all 9 qualities' rows to the "Unmodeled real effects" table,
    and remove that section's own "once WP55 ships" placeholder parenthetical.
  Depends on: WP52 (the concrete motivating case), WP22 (the research this WP extends).
  Acceptance: unit tests for the selecttext parameter round-tripping through `QualitySelection`/
  the save format; a test confirming SINner's 4-way mutual-exclusion is enforced; a test confirming
  Natural Immunity's exclusion against Weak Immune System is enforced (even though currently
  unreachable via the offered catalog); a test confirming all 9 qualities are offered and
  independently selectable at their correct karma cost; integration test importing `Wesson.chum5`
  end to end for the first time across WP28/WP52/this WP's combined fixes — the real cross-phase
  regression case this WP exists to close out.

- [x] **WP56 — Character sheet: unmodeled-effects disclosure section (aspect-kind-agnostic from the
  start).**
  Goal: give Project Overview's "Unmodeled real effects" registry a player-facing home — a
  collapsible section on the character sheet listing, for whichever unmodeled-effect aspects the
  *current* character actually has, the specific note from that registry. **Built generically
  across every aspect kind `Character` can hold from day one, not scoped to qualities and widened
  later** — even though qualities are the only kind with registry entries as of this WP (so
  qualities are the only thing that will actually render today), the collection mechanism itself
  must not be qualities-specific, so a future WP adding a Powers/cyberware/etc. registry row never
  has to touch this WP's own code, only the registry.
  Deliverables:
  - Decide and document the source-of-truth question this WP can't avoid: Project Overview's table
    is markdown, not something `src/` reads at runtime, so either (a) a new field lives on the
    relevant catalog dataclass per aspect kind (e.g. `Quality.unmodeled_effect_note: str | None`,
    populated at classification time in `chummer5.data.qualities`, mirroring how `BonusSupport` is
    already classified there — and, symmetrically, wherever a future WP adds a Powers/cyberware/etc.
    row, that catalog's own dataclass gains the identical field), with Project Overview's table
    treated as a hand-kept mirror, or (b) one small standalone `{aspect_name: note}` mapping module
    every catalog loader consults, keyed by name across all kinds rather than per-dataclass fields.
    Either is acceptable, but the two must not silently drift — whichever WP adds a new registry row
    has to update both, and this WP's own worklog should say which shape it chose and why.
  - `chummer5.web.app._character_sheet_context` (or a new small engine-layer helper it calls, if
    that reads cleaner): a generic `unmodeled_effect_notes` builder that walks *every* named aspect
    the character currently holds — not just `character.quality_selection.qualities` +
    `character.metatype_qualities`, but the same enumeration this WP should extend to
    `character.power_selection.picks`, `character.cyberware_selection.items`,
    `character.bioware_selection.items`, `character.foci_selection.picks`,
    `character.lifestyle_selection.tier`, and any other named, catalog-backed selection `Character`
    exposes — checks each one's name against the chosen source-of-truth from the decision above,
    and keeps only the hits, deduplicated (a character can't hold the same quality twice, but a
    metatype-granted and player-purchased instance of the identical quality, e.g. Low-Light Vision,
    should only produce one entry, not two). Returns a plain `(aspect name, note)` pair list — no
    `QualitySelection`-shaped or otherwise aspect-kind-specific return type — so the template needs
    no branching per kind either. Today this will only ever surface quality-sourced notes (nothing
    else has a registry entry yet), and that's fine — the point is that nothing about *how* the
    list is built assumes qualities are special, only that the registry currently happens to be
    quality-only.
  - `chummer5.web.templates._character_sheet.html`: a new `<details>` collapsible section (reusing
    the same widget `_resources.html`/`_cyberware.html`/`_foci_selection.html` already use for
    category grouping — no new UI pattern needed), closed by
    default, listing each note. Decide and document whether an empty list (a character with no
    unmodeled-effect aspects at all, e.g. a plain Human with none of the 8 `NO_EFFECT` qualities)
    hides the section entirely or shows it collapsed-and-empty with explanatory text — either is
    fine, but be explicit.
  Depends on: nothing technically blocking (every quality this WP can already surface today is
  already shipped), but sequenced after WP55 in this phase so its own manual walkthrough can
  exercise a SINner-holding character too, not just the pre-existing `NO_EFFECT` set.
  Acceptance: manual walkthrough — build an Elf (free Low-Light Vision) and confirm the section
  shows its note; add a purchased `NO_EFFECT` quality (e.g. Guts) and confirm its note also
  appears, not duplicated with Low-Light Vision's; build a plain Human with neither and confirm the
  documented empty-state behavior; build a character with real cyberware/bioware/powers/foci picks
  (none of which have registry entries yet) and confirm the walk across those selections doesn't
  crash and simply contributes nothing. Unit test for `unmodeled_effect_notes`'s own construction
  (dedup, correct notes, empty for a character with none, no crash on non-quality selections).


---

## Phase reopened 2026-08-01 — WP89

Phase S's second fixture-gap pass (see `phase-s-test-fixtures.md` §6) loaded a player-authored
character that converts 4 Karma to nuyen, and noticed that its Karma ledger doesn't move. This is
this phase's own construct that's wrong, so the fix is filed here rather than in Phase L or S.

- [x] **WP89 — Karma-to-Nuyen conversion must debit the unified Karma ledger.**
  Goal: `Character.karma_spent` (`engine/character.py:382`) sums every Karma-spending selection —
  qualities, contacts, bound spirits, foci, and the four Step Seven spends — but not
  `resources_selection.karma_converted`. So converting Karma to nuyen at Step Six currently costs
  nothing: a character can convert the maximum 10 Karma for ¥20,000 and still spend all 25 Karma
  on qualities, contacts, and Step Seven. The observed case: `tests/fixtures/saves/razorboy.json`
  converts 4 Karma, gets the ¥8,000 (the character sheet says so in as many words — "275000
  priority + 8000 from converting 4 Karma"), and still reports `karma_remaining: 19`, which is
  `25 - 3 qualities - 3 contacts` with the conversion simply absent.
  **This is a stale deferral, not an oversight.** `spec/worklogs/WP43.md` records the decision
  explicitly: *"Confirmed Phase O (the unified Karma ledger) hasn't landed — no code anywhere sums
  `quality_selection.karma_cost`/`contact_selection.karma_cost` into one running total today, so
  there is nothing yet for this conversion to double-spend against."* That was true on 2026-07-21
  and false from WP51 onward; the module docstring in `engine/resources.py` still documents the gap
  as deliberate. Nobody was wrong — the trigger condition just passed unnoticed.
  Notes and traps:
  - Confirm the direction against the rulebook before coding (p. 94, and Step Six/Step Seven's own
    ordering): the expectation is that converted Karma is spent Karma, but this WP should cite it
    rather than assume it, per this phase's own re-extraction practice.
  - `karma_spent` is a property read by `karma_remaining`, which is in turn what nearly every
    `create_*` function's `karma_budget` argument is derived from — including
    `create_foci_selection` and the four Step Seven spends. Adding a term to it therefore *shrinks*
    every downstream budget, and the "add back this section's own currently-committed cost" idiom
    (WP51) has to work for this term too or a resubmission will double-count it.
  - There is a genuine ordering question to settle and document: Karma-to-Nuyen is Step Six and the
    Karma spends are Step Seven, so a character who converts Karma and *then* overspends Step Seven
    should be rejected — but `create_resources_selection` currently validates only nuyen, and knows
    nothing about the Karma ledger. Decide whether it grows a `karma_budget` parameter like its
    siblings, or whether the check lives at the aggregate; either is defensible, but say which and
    why.
  - Existing saves/fixtures with a nonzero `karma_converted` will shift their `karma_remaining`.
    Check the four synthetic fixtures and the legacy-import path (`io/legacy_import.py:877` maps
    `<nuyenbp>` onto this field) before assuming nothing moves — `.chum5` characters with a nonzero
    `<nuyenbp>` are the interesting case, since their legacy-computed Karma total is ground truth
    for what the right answer looks like.
  - Remove the now-obsolete "known, deliberate gap" paragraph from `engine/resources.py`'s module
    docstring rather than leaving it to contradict the code.
  Depends on: WP51 (the ledger this adds a term to); WP43 (the conversion itself).
  Acceptance: `pytest`/`ruff`/`mypy` green; a unit test that converting Karma reduces
  `karma_remaining` by exactly the converted amount, and one that a Step Seven spend which was
  affordable *before* a conversion is rejected after it; `razorboy.json` reports `karma_remaining:
  15`; a dated entry in `spec/decisions-log.md` recording the ordering ruling; if the rulebook had
  to be opened, a citation in `spec/rulebooks/learnings/phase-o.md`.
