[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase N — Post-MVP: Expanded skill support (Knowledge/Language skills, specializations)

Scoped 2026-07-21. Confirmed both gaps directly rather than assumed: `chummer5.data.skills`'s own
docstring states "knowledge skills aren't [in scope]" (the original MVP scope decision, never revisited);
`chummer5.engine.skills` already has a `specialized: bool` parameter and the flat `SPECIALIZATION_BONUS`
(+2) dice-pool formula, but nothing calls it with a real, player-chosen value — no purchase/budget logic,
no UI (`grep -rln specializ src/chummer5/web/` returns nothing). So this phase is "finish a half-built
mechanic" (specializations) plus "build a genuinely new one" (Knowledge/Language skills), not two
from-scratch features.

**Real fixture coverage exists for both**, better than Phase M's three items: `Miko.chum5` has at least
one recorded Knowledge/Language skill (`<knoskills>` contains an English/Language entry) and a real
specialization (`<spec>Staves</spec>`) — both usable as acceptance-test ground truth, confirmed via
direct inspection of the fixture file rather than assumed present.

- [x] **WP49 — Knowledge & Language skills.**
  Goal: let a player spend the free Knowledge/Language point budget — `(Intuition + Logic) x 2` per the
  rulebook (Step Five, p. 89) — on freeform-named Knowledge skills (with a suggested/example list, not an
  enforced catalog, per the rulebook's own "Common Knowledge Skills in 2075"/"Knowledge Category
  Examples" sidebars) and Language skills (one free native language, `chummer5_py`'s existing Bilingual
  quality already grants a second free one per WP22's catalog — confirm this quality's Improvement
  actually feeds into this budget once it exists, since it was inert with respect to Knowledge/Language
  points before this WP).
  Deliverables:
  - `chummer5.data.skills` (or a new sibling module): a small **suggested-name list** per Knowledge
    category (Academic/Interests/Professional/Street, per the rulebook's own table,
    `spec/rulebooks/character_creation_chapter.md`'s Step Five section) — explicitly not an exhaustive or
    enforced catalog; the player must be able to type an arbitrary name, matching the rulebook's own "you
    do not need to understand all the nuances... just have a concept" posture for this specific
    mechanic (freeform Knowledge skills are a real, intentional rulebook design, not a gap this project
    is papering over with a stub list).
  - `chummer5.engine.skills` (or `chummer5.engine.knowledge`, decide & document): a
    `KnowledgeSkillSelection` (name, category, rating) + `LanguageSkillSelection` (name, rating, native:
    bool) pair, with `create_knowledge_selection(picks, character)` validating the free-point budget
    `(INT + LOG) * 2` and that exactly one (or two, with Bilingual) entry is marked native at rating
    implicitly "N"/uncosted.
  - `Character` gains `knowledge_selection: KnowledgeSelection | None`.
  - `chummer5.web`: a free-text-entry form (name + category dropdown + rating) with a running
    remaining-points display, mirroring WP15's live-budget precedent — this is the first chargen screen
    needing free-text player input rather than picking from a fixed list, flag any new UI pattern this
    requires.
  - `chummer5.io.save_format`/`legacy_import`: thread through normally; `legacy_chum5`'s `<knoskills>`
    parsing (confirmed present in real fixtures above) is the import source.
  Depends on: WP6 (attribute resolution, for INT/LOG).
  Acceptance: unit tests for the free-point budget formula and native-language handling; integration
  test against `Miko.chum5`'s own recorded Knowledge/Language entries (confirmed present via direct
  fixture inspection this session) rather than only hand-checked cases.

- [x] **WP50 — Skill specializations (Step Five: skill-point-funded).**
  Goal: let a player spend 1 skill point (from the same Skills-priority budget WP7 already tracks) to
  add one specialization to an individually-purchased skill, wiring up the dice-pool bonus that already
  exists in the engine. Scoped as **Step Five's mechanic specifically** (skill-point funded, no skill-
  group interaction) — the separate Step Seven case ("buying a Karma-funded specialization breaks an
  existing skill group") is Phase O's concern (WP53), not this WP's, since it's funded from leftover
  Karma rather than the Skills-priority point budget and depends on Phase O's ledger.
  Deliverables:
  - `chummer5.engine.skills`: extend `SkillAllocation` (or whatever the current type is named) with a
    `specializations: dict[skill_id, str]` (or equivalent), validating: 1 skill point per specialization,
    at most one specialization per skill, and — the group-purchase restriction the rulebook states
    explicitly (Step Five, p. 88-89) — **a skill that's part of a skill group purchased as a group cannot
    be specialized in this step at all** (only an individually-purchased skill can be). Confirm
    `create_skill_allocation`'s existing budget-check shape can extend to this cleanly rather than
    needing a parallel budget.
  - Wire the existing `dice_pool(..., specialized=...)` parameter to read from this new selection instead
    of always defaulting to `False`.
  - `chummer5.web`: a specialization checkbox/text-field per individually-purchased skill on the skill
    allocation screen (`_skill_allocation.html`), with the running skill-point-remaining display already
    built (WP15) now accounting for specialization spend too.
  - `chummer5.io.save_format`/`legacy_import`: thread through normally; `legacy_chum5`'s `<spec>` parsing
    (confirmed present in `Miko.chum5` as `<spec>Staves</spec>`) is the import source.
  Depends on: WP7 (Skills-priority budget/dice-pool formula).
  Acceptance: unit tests for the 1-point cost, one-per-skill limit, and group-purchased-skill rejection;
  integration test against `Miko.chum5`'s own `Staves` specialization (confirmed present via direct
  fixture inspection this session), confirming the resolved dice pool includes the +2 bonus.

