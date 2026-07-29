[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase K — Post-MVP: Cyberware modifications (Capacity, subsystems, conditional bonuses)

**Taken off hold 2026-07-29** at the user's direction, with WP36 landing that day. The hold below is
kept as written for the record; WP37-42 remain as scoped, and the phase intro's own catalog survey
should still be re-confirmed per WP by whoever picks the next one up — WP36 did exactly that for the
formula-shape half of it and found the count slightly off (see WP36's landed note).

**On hold, deliberately, as of 2026-07-21 — scoped now, started later.** Raised by a user question
after WP33 shipped: cyberlimbs, cybereyes, and cyberears can be upgraded with plugin-type subitems
in real SR5 (e.g. a cybereye taking a "Vision Enhancement" plugin), a mechanic WP31/32/33
deliberately excluded (both modules' own docstrings flag nested `<children>`/rating-scaled items as
out of scope, and `tests/integration/test_cyberware_fixtures.py` documents "top-level only" as a
considered choice, not an oversight). This phase is that mechanic, scoped and researched ahead of
time so a future conversation can pick it up cold — see `spec/rulebooks/learnings.md`'s "Pre-Phase-K
research" entry for the rulebook citations (the Capacity rule itself, p. 29100-29106; the
Essence-vs-Capacity dual-costing footnote, p. 453) this intro's own catalog research builds on.

**Four separable primitives, none of which Phase J's flat-item scope needed — this is why Phase K
is its own phase, not a Phase J add-on:**
1. **A rating-scaled formula resolver.** WP31 excluded every cyberware item whose `<cost>`/`<ess>`
   wasn't a bare literal (27 of 87 SR5 entries) precisely because nothing resolves `Rating * N`-style
   formulas yet.
2. **A purchase *tree*, not a flat list.** A limb with plugins installed into it needs parent/child
   structure; `CyberwareSelection.items` (WP32) is a flat tuple today, and legacy import (WP33)
   explicitly does not parse `<children>` at all.
3. **A second, per-purchase budget (Capacity)**, independent of the shared nuyen/Essence budgets
   Phase J already built, plus the Essence-vs-Capacity dual-costing choice at purchase time (same
   catalog row, two different cost modes depending on where it's installed).
4. **Conditional Improvements.** Checked directly: `chummer5.engine.improvements.Improvement` (WP5)
   has no `condition` field at all — every Improvement this engine has ever produced is
   unconditional by construction. At least one real subsystem bonus (Vision Enhancement's Mental
   limit bonus, "only on visual Perception tests") needs one. This is the single biggest, most
   foundational piece of this phase — a new engine primitive, not new catalog content.

**Catalog research (this session, via a one-off `xml.etree.ElementTree` read over all 87 SR5
`cyberware.xml` entries — re-confirm against the full file during implementation, this was an
exploratory pass, not an exhaustive audit the way WP21/31's own counts were).** Of the 27 SR5
entries WP31 excluded as non-flat, `<cost>`/`<ess>` reduce to only **6 distinct formula shapes**:
`Rating * N` (19 occurrences), a plain literal that failed only the *other* field's flatness check
(2), `FixedValues(N,N,N)` (2), `(Rating - MinRating + N) * N` (2), plus two one-off named formulas
(`Cybereyes Basic System`'s and `Cyberears`' own `<cost>`, each a unique small arithmetic expression
not shared by any other item). `<capacity>` (checked across all 87 SR5 entries, not just the
non-flat 27) reduces to **7 shapes**: a bare integer or bare `Rating`-formula (a parent's *budget*),
or the same shapes bracketed (`[N]`, `[Rating]`, `[Rating * N]` — a plugin's *cost*), plus a literal
`[*]` marker (2 occurrences: `Image Link`, `Sound Link` — bundled free with their parent, not a
player pick, see the learnings.md entry's own caveat about confirming this reading). **29 of the 87
SR5 entries carry `<allowsubsystems>` (i.e., are parents):** 16 are the Cyberlimb variants already in
WP31's flat catalog (their Capacity budget is already a bare int, e.g. `Synthetic Full Arm` → `8`);
2 are Cybereyes/Cyberears (rating-formula cost, currently excluded entirely); 11 are "Cyber Implant
Weapon"-category items (Grenade Launcher, Hand Blade, Heavy Pistol, ...) which are *themselves*
plugins into a limb (bracketed Capacity cost) **and** parents for a further "Cyber Implant Weapon
Accessory" subsystem layer — a genuine two-level nesting case; confirm whether any curated fixture
actually exercises it before deciding whether to support that third level or cut it explicitly.

**Sequencing rationale.** The formula resolver (WP36) and expanded data loader (WP37) are pure,
side-effect-free groundwork — proven/loaded before any purchase logic touches them, mirroring
WP5→WP6 and WP30→WP31's own "prove the primitive, then build on it" precedent. Conditional
Improvements (WP39) is scoped as its own isolated WP for the identical reason WP5 itself was: it's a
core-engine primitive change (touches `resolve()`'s call sites, not just cyberware), so it gets
proven with synthetic data before real content depends on it — deliberately sequenced independently
of WP37/38 (no data dependency either way) so it can be picked up first if that turns out to be the
more useful order. WP40-41 wire real content through the now-complete primitive set; WP42 (UI) is
last and deliberately excluded from this phase's own scope until WP36-41 are solid — this
conversation's own request not to build placeholder UI that gets thrown away applies here directly.

- [x] **WP36 — Cyberware rating-formula resolver.**
  Goal: a small, tested, whitelisted evaluator for the rating-scaled cost/Essence/Capacity formula
  shapes `cyberware.xml` actually uses — proven against synthetic formula strings before any real
  catalog data touches it (mirrors WP5/WP30's "prove the mechanism in isolation first" precedent).
  Deliverables:
  - A resolver, e.g. `resolve_cyberware_formula(formula: str, *, rating: int, min_rating: int = 0)
    -> Decimal`, location TBD at implementation time (a new `chummer5.data.cyberware_formula` module,
    or a private helper inside `chummer5.data.cyberware` — decide and document).
  - Re-confirm this session's shape survey (see this phase's own intro) against the *complete* 87-
    entry SR5 set before finalizing which shapes to support — enumerate and hand-verify each rather
    than building a general arithmetic-expression parser (mirrors WP22/WP25/WP27's "classify known,
    named shapes" precedent, not a general expression/XPath evaluator). Decide, and document the
    decision: hardcode the two one-off named formulas (`Cybereyes Basic System`, `Cyberears`) by
    item name rather than generalizing a parser to cover them, since nothing else shares their shape.
  - Decide & document: is a bracketed value (`[N]`, `[Rating]`) parsed by this same resolver (stripping
    brackets first) or treated as a distinct concern from WP37's loader? Keep the resolver itself
    agnostic to "is this a budget or a cost" — that's a WP37/38 concern, not this one's.
  - Decide & document: is `[*]` (Image Link, Sound Link) a resolver concern at all, or purely a
    WP37/38 "bundled free" special case with nothing to resolve? (Current read: the latter — see
    learnings.md.)
  Depends on: nothing new.
  Acceptance: unit tests for every distinct shape confirmed present, each hand-checked against a
  real rulebook-table value (e.g. Vision Enhancement Rating 2 → Capacity cost 2, Essence 0.1, nuyen
  cost 8000; Cybereyes Basic System Rating 3 → nuyen cost 10000, Essence 0.4 — both already
  transcribed from the p. 453 table in this session's research, see learnings.md — WP36 re-verified
  the page: those numbers are printed on p. **454**, since a Chummer `<page>` tag names where an
  item's narrative section starts, not the table its numbers live in).

  **Landed 2026-07-29** as `chummer5.data.cyberware_formula` (a new module, not a private helper inside
  `chummer5.data.cyberware` — see its docstring for all six "decide & document" calls in one place),
  with 35 tests in `tests/unit/test_cyberware_formula.py`. Public API:
  `parse_cyberware_formula(text) -> CyberwareFormula | None` (parse once, resolve many — WP37 can use
  the `None` as its inclusion filter) plus `resolve_cyberware_formula(text, *, rating,
  min_rating=None) -> Decimal` (raises `UnsupportedCyberwareFormulaError`). What the next WPs need to
  know:
  - **The shape survey came out at 8 resolvable shapes, not this intro's 6.** Re-derived over all 87
    SR5 entries and all three fields (this intro's pass looked at the 27 WP31-excluded entries and
    mostly at `<cost>`): the two extras are a bare `Rating` (only ever seen bracketed, `[Rating]`) and
    `(Rating * A) + B` — the `<ess>` **shared** by Cybereyes Basic System and Cyberears, which this
    intro folded into those items' "two one-off named formulas" when only their `<cost>` is genuinely
    one-off. Everything else in the intro's survey held up exactly, including the `<capacity>` shape
    list and the 29-parent split (that half is WP37's to re-confirm).
  - **Brackets are the caller's to strip, by decision.** `[2]`/`[Rating]`/`[Rating * 1]`/`[*]` are all
    rejected by the resolver, so WP37 owns bracket handling — that's where budget-vs-cost semantics
    belong, and it makes "resolved a plugin's Capacity cost as a parent's budget" impossible to do
    silently.
  - **`[*]` confirmed as a pure WP37/38 `bundled_free` flag**, not a resolver concern (p. 454's
    eyeware-table footnote, verified this WP).
  - **`{AGIMinimum}+1`/`{AGIMaximum}` bound placeholders and `<avail>` are out of scope** — the
    resolver takes already-resolved `rating`/`min_rating` ints. `min_rating` deliberately has no `0`
    default: omitting it for Customized Strength/Agility raises rather than silently overcharging.
  - The one-off formulas are keyed by verbatim formula text, not item name, so no item identity needs
    threading through WP37/38 call sites.

- [ ] **WP37 — Cyberware Capacity/subsystem data loader.**
  Goal: widen `chummer5.data.cyberware` to capture parent Capacity budgets, subsystem-category
  eligibility, and plugin Capacity cost — data layer only, no purchase logic yet (mirrors WP31's own
  sequencing relative to WP32).
  Deliverables:
  - Widen `Cyberware` (or a new sibling type — decide and document) with: a raw/resolved Capacity
    *budget* (parents only), a raw/resolved Capacity *cost* (plugins only, brackets stripped),
    `allowed_subsystem_categories: tuple[str, ...]` (parents only), and a `bundled_free: bool` (the
    `[*]` case).
  - **This WP must widen `load_cyberware()`'s own scope, not just its field set.** Today's loader
    only keeps items with a flat `<cost>` **and** flat `<ess>` (60 of 87 SR5 entries) — this whole
    phase's point is items *excluded* by that filter (Cybereyes, Cyberears, Customized/Enhanced
    Agility/Strength, the 11 Cyber Implant Weapons, ...). Add a second, explicitly-named loading path
    (e.g. `load_cyberware_subsystems()`, or a `include_rating_scaled: bool` parameter) rather than
    relaxing WP31's existing flat-only contract in place — several already-shipped WP31/32/33 tests
    depend on `load_cyberware()`'s current 60-item, flat-only behavior being unchanged.
  - Re-verify this phase's intro's "29 parents, 16 already-flat Cyberlimbs / 2 Cybereyes+Cyberears /
    11 Cyber Implant Weapons" split against the full data set; confirm whether any curated fixture
    exercises the Cyber Implant Weapon → Weapon Accessory two-level nesting case before deciding
    whether WP38 needs to support a third nesting level or can cut it explicitly (document either way).
  Depends on: WP36 (to store resolved, not just raw, Capacity values — decide whether this WP resolves
  eagerly at load time or keeps raw strings for WP38 to resolve per-purchase; document the choice).
  Acceptance: unit tests confirming the loader's new counts/fields against hand-checked
  `cyberware.xml` values; an explicit test that WP31's original `load_cyberware()` (60 flat items,
  existing field set, existing call sites) is completely unchanged — this WP must be additive to
  WP31/32/33, not a breaking change to already-shipped behavior.

- [ ] **WP38 — Purchase tree & Capacity budget validation.**
  Goal: let a cyberware purchase actually nest — a limb with plugins installed into it, validated
  against the parent's resolved Capacity budget.
  Deliverables:
  - `chummer5.engine.cyberware`: a purchase-tree type, e.g. `PurchasedCyberware(item, rating,
    installation: Literal["standalone", "subsystem"], plugins: tuple[PurchasedCyberware, ...])`.
    Decide & document whether this replaces `CyberwareSelection.items`'s current flat
    `tuple[Cyberware, ...]` outright (every existing purchase becomes a zero-plugin leaf) or sits
    alongside it — existing WP32/33 tests and the native save format both depend on today's flat
    shape, so this is a real compatibility decision, not a mechanical rename.
  - Capacity check: sum of each installed plugin's resolved Capacity cost (WP36/37) must not exceed
    the parent's resolved Capacity budget; category check: each plugin's category must be in the
    parent's `allowed_subsystem_categories`.
  - Essence-vs-Capacity dual costing: the same catalog item, bought standalone, still costs Essence
    exactly as today's engine already models; bought as a subsystem, it costs Capacity instead and
    contributes **zero** Essence — confirm this reading against `spec/rulebooks/learnings.md`'s own
    p. 29103 citation before implementing (already recorded, no new PDF pass needed for this part).
  - The `[*]` bundled-free case (Image Link, Sound Link): confirm via real fixture data whether any
    curated Cybereyes/Cyberears purchase ever appears *without* its bundled item before deciding
    whether to model it as always-auto-attached (simpler) or a skippable choice.
  Depends on: WP36, WP37.
  Acceptance: unit tests (synthetic data) for Capacity budget/category validation, including an
  over-capacity rejection and a wrong-category rejection; an integration test against a real
  fixture's actual limb+plugin combination (e.g. `Barrett.chum5`'s own `Synthetic Full Arm` +
  `Customized Agility` + `Enhanced Agility` + `Cyberlimb Optimization`, already dumped during this
  session's WP33 research) confirming the resolved Capacity spend matches what the limb's own
  Capacity budget allows.

- [ ] **WP39 — Conditional Improvements: a new engine primitive.**
  Goal: give `Improvement` (WP5) a real, typed condition mechanism — the one genuinely new,
  foundational engine primitive this phase needs, proven with synthetic data before any cyberware
  content uses it (mirrors WP5's own "prove in isolation" methodology, applied to itself).
  Deliverables:
  - `chummer5.engine.improvements`: `Improvement` gains an optional `condition` field — a typed
    predicate compiled once at construction (the Project Overview's own long-stated design intent
    for this, never yet implemented; confirmed this session that no `condition` field exists at all
    today). Keep it a named, hardcoded predicate per confirmed real shape (mirrors WP25's xpath-
    predicate precedent) — do not build a general expression/condition-string interpreter; nothing
    in this phase's own scope needs one.
  - `resolve()` needs additional call-site context to evaluate a condition against (e.g. "is the
    dice pool being resolved a visual Perception test") — this is a real signature change to
    `resolve()`'s call sites, not just an additive field. Scope the *smallest* context shape this
    phase's own real conditional bonuses (Vision Enhancement/Audio Enhancement/Spatial Recognizer,
    all "only on a specific test category") actually need, not a general "arbitrary game-state
    predicate" system.
  - Decide & document: is a `Condition` a closure/callable, a small tagged-union dataclass, or an
    Enum + parameters?
  Depends on: nothing new (touches only `engine/improvements.py`, mirrors WP5/WP30's isolation from
  real catalog content).
  Acceptance: unit tests with synthetic conditional improvements (a condition that's met and one
  that isn't, evaluated against the same target) proving `resolve()` only includes the met one;
  explicit test that every existing unconditional Improvement (all of WP5-WP35's content) is
  completely unaffected — `condition=None` must be a true no-op, zero behavioral drift for every
  character this engine builds today.

- [ ] **WP40 — Wire real conditional-bonus subsystem items.**
  Goal: reclassify Vision Enhancement, Audio Enhancement, and Spatial Recognizer from
  `NOT_YET_SUPPORTED`/excluded to real, condition-gated Improvements, using WP39's new primitive.
  Deliverables:
  - Extend `chummer5.data.cyberware`'s bonus classifier with a new `BonusSupport` value for
    "conditional flat bonus." Confirm each item's exact condition semantics via `pdftotext -layout`
    (their in-fiction test-category wording, e.g. Vision Enhancement's visual-Perception-only
    condition already identified this session) before hardcoding a predicate; record each citation
    in `spec/rulebooks/learnings.md`.
  - `chummer5.engine.cyberware`: apply these as conditional `Improvement`s (WP39) targeting the
    existing `MENTAL_LIMIT` improvement type (per the raw XML's own `<limitmodifier><limit>Mental
    </limit>`), gated by the appropriate new condition.
  Depends on: WP38, WP39.
  Acceptance: unit tests confirming the Mental limit bonus applies when resolving a visual-
  Perception-flagged dice pool and does not apply otherwise; explicit test that a non-visual Mental
  limit resolution (e.g. a Memory test) is unaffected by an installed Vision Enhancement.

- [ ] **WP41 — Cyberware modification save/load + legacy import.**
  Goal: thread the purchase tree (WP38) through native save/load and legacy import, which currently
  discards `<children>` entirely (a deliberate, documented WP31/33 scope cut, not an oversight).
  Deliverables:
  - `chummer5.io.save_format`: extend `CharacterSave`'s cyberware representation to carry the tree
    shape (parent + nested plugin picks), not just a flat id list.
  - `chummer5.io.legacy_chum5`: parse `<children>` recursively — reopens WP33's own "top-level only"
    decision now that there's an engine shape to receive the nested data; extend `LegacyCyberware`
    with a `children: tuple[LegacyCyberware, ...]` field.
  - `chummer5.io.legacy_import`: real per-plugin importability checks (each nested item independently
    resolved against WP37's subsystem catalog, itemized the same way WP33 itemizes top-level items)
    rather than continuing to ignore `<children>` wholesale.
  Depends on: WP38, WP40 (a saved/imported character may carry a conditional-bonus item).
  Acceptance: integration tests against real fixtures' actual nested purchases (e.g. `Barrett.chum5`'s
  `Synthetic Full Arm` + its 6 real children, already dumped during this session's WP33 research)
  confirming each resolvable child imports with the correct Capacity/Essence math, and non-resolvable
  ones (most of them, per WP33's own finding that most nested items are non-SR5-sourced or
  rating-scaled beyond what WP36/37 cover) are itemized, not silently dropped.

- [ ] **WP42 — Cyberware modification/subsystem UI.**
  Goal: expose subsystem/plugin purchase through the browser. Deliberately last, and deliberately
  out of scope until WP36-41 are solid — this project's own "rules engine first, UI last" principle,
  applied here specifically because a placeholder UI built against an incomplete engine shape would
  be throwaway work once the real shape lands.
  Deliverables:
  - A picker UI for "install a plugin into this limb/cybereye/cyberear," showing remaining Capacity
    live (mirrors WP15's live remaining-points precedent).
  - `_character_sheet_context`: show installed subsystems nested under their parent, and any
    conditional bonus's condition text alongside its value (so a player can see *why* a bonus applies
    only sometimes).
  Depends on: WP41.
  Acceptance: manual walkthrough — install a Cybereyes system, buy a Vision Enhancement plugin into
  it, confirm Capacity remaining updates live and the Mental limit bonus is visibly conditional on
  the character sheet.

