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

- [x] **WP37 — Cyberware Capacity/subsystem data loader.**
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

  **Landed 2026-07-29** as `chummer5.data.cyberware_subsystems` (a new module, following WP36's own
  precedent — see its docstring for every decision below in one place), with 19 tests in
  `tests/unit/test_cyberware_subsystems.py`. Public API: `load_cyberware_entries() ->
  tuple[CyberwareEntry, ...]`, **all 87 SR5 rows** (not just the 27 WP31 excludes — a single wider
  catalog beats two partial ones). `chummer5.data.cyberware.load_cyberware()` is byte-for-byte
  unchanged; the only edit to that module is `_classify_bonus` → public `classify_bonus`, which the
  new loader reuses verbatim rather than re-implementing. What WP38-42 need to know:
  - **A sibling type, `CyberwareEntry`, not a widened `Cyberware`** — forced, not preferred:
    `Cyberware.cost` is an `int` and a rating-scaled row has no single value for it. Cost, Essence,
    Capacity budget and Capacity cost are all `CyberwareFormula` (WP36), **parsed at load, resolved
    per purchase** (the other question WP37's entry left open). An unrecognized formula raises
    `UnsupportedCyberwareFormulaError` at load — data drift fails loudly, no row is silently dropped.
  - **The intro's parent split is exact**: 29 parents = 16 Cyberlimb + 2 Cybereyes/Cyberears + 11
    Cyber Implant Weapon. Also now pinned: 50 plugins (bracketed `<capacity>`), 19 standalone-only
    rows, and the 11 weapons are the only rows that are *both*.
  - **The Cyber Implant Weapon → Accessory two-level case should be cut explicitly in WP38.** No
    fixture exercises it (every depth-2/3 chain in all 34 `.chum5` files is a Chrome Flesh modular-
    limb chain, out of SR5 scope), and the data gives a weapon no budget to spend: its `<capacity>`
    is bracketed, which per legacy `CapacityRemaining` means a budget of zero. Its 3 accessories
    instead carry `<addtoparentcapacity>`/`<addtoparentess>` — a fold-into-the-parent mechanic, a
    different thing. Both flags are captured (`adds_to_parent_capacity`/`adds_to_parent_essence`) so
    WP38 can decide from data.
  - **Bundled-free is two signals, and the pre-Phase-K reading of it was incomplete.** `[*]`
    (`bundled_free`) means "costs no Capacity as a plugin"; a parent's `<subsystems>` list
    (`bundled_subsystem_names`) means "these come with it automatically" — and there are **3** of
    those, not 2: the third is **Control Rig → Datajack**, which carries neither `[*]` nor
    `<allowsubsystems>` and *is* real fixture content (`Mittens Chargen.chum5`). See
    `spec/rulebooks/learnings/phase-k.md`'s WP37 entry.
  - **`requires_parent` (9 rows, from `<requireparent>`) is the answer to half of WP38's
    Essence-vs-Capacity dual-costing question**: Ocular Drone, Armor, Customized/Enhanced
    Strength/Agility, Cyber Holster, Cyberarm Slide, Large Smuggling Compartment have no standalone
    mode at all, so no choice exists for them.
  - `{AGIMaximum}`/`{AGIMinimum}+1` bounds are kept **raw alongside** parsed ints (`raw_max_rating`
    / `max_rating`, both `None` when attribute-derived; `has_resolvable_rating_bounds` is false for
    exactly Customized Agility and Customized Strength) — WP38 resolves them against a character.
  - Deliberately **not** captured, listed in the module docstring: `<limbslot>`/`<blocksmounts>`/
    `<limit>` (limb-count mechanic), `<allowgear>` (25 rows can hold gear children), `<selectside>`,
    `<pairbonus>`/`<pairinclude>`, `<required>`/`<forbidden>`, `<addweapon>`, `<avail>`.

- [x] **WP38 — Purchase tree & Capacity budget validation.**
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

  **Landed 2026-07-30** as `chummer5.engine.cyberware_subsystems` (a new module, mirroring WP37's
  data-layer sibling exactly — `data.cyberware`↔`engine.cyberware` is the WP31/32 flat pair,
  `data.cyberware_subsystems`↔`engine.cyberware_subsystems` the WP37/38 tree pair), with 30 tests in
  `tests/unit/test_cyberware_tree.py` and 6 in `tests/integration/test_cyberware_tree_fixtures.py`.
  Public API: `CyberwarePurchaseRequest` (nested request: item id + rating + plugin requests),
  `create_cyberware_tree_selection(requests, catalog, nuyen_budget, *, attribute_maximums=None,
  other_essence_spent=Decimal(0)) -> CyberwareTreeSelection`, `PurchasedCyberware` (validated node),
  `Installation`, and `cyberlimb_attribute_maximums(character)`. What WP40-42 need to know:
  - **It sits alongside `CyberwareSelection`, it does not replace it** — the compatibility decision
    the entry above flagged as real. `create_cyberware_selection` is typed on WP31's `Cyberware` out
    through `io.save_format`, `io.legacy_import`, `web.routes.cyberware` and five test modules; a
    tree node needs WP37's `CyberwareEntry`. **WP41 owns that call-site migration** (it has to touch
    save/load and legacy import anyway). `CyberwareTreeSelection` deliberately reuses
    `nuyen_budget`/`nuyen_spent`/`essence_spent` verbatim so the swap is mechanical.
  - **Nothing consumes this module yet, deliberately** — no `Character` field, no Improvements, no
    UI, exactly as WP36/WP37 added no behaviour. A `Character` must never carry both selection
    shapes; today there is no field for this one, so it can't happen by accident.
  - **Dual costing confirmed from three directions, not just the p. 29103 citation the entry names.**
    The sharpest is p. 456's Bodyware narrative — "Bodyware cannot be installed into cyberlimbs
    unless it has a Capacity cost [in brackets]. Bodyware with a Capacity cost can be installed in
    cyberlimbs, **costing capacity rather than Essence**" — plus legacy `Cyberware.cs`'s
    `GetCalculatedESSPrototypeInvariantCoreAsync`, whose first line is `if (Parent != null &&
    !AddToParentESS) return 0;`. Nuyen *is* charged either way (same file: "Add in the cost of all
    child components"). So a plugin charges Capacity + nuyen and **zero** Essence.
  - **`[*]` bundled items are always auto-attached, and free in all three currencies.** The fixture
    check the entry asked for: 8 of 8 `<subsystems>`-bearing purchases across all 34 `.chum5` files
    carry their bundled child (5 Cybereyes, 2 Cyberears, 1 Control Rig) — never skipped, so the
    simpler always-attached model is the right one. Free is from legacy `Cyberware.Create`'s
    `objSubsystem.Cost = "0"`, corroborated by every fixture storing `<cost>0` for a bundled item.
    An *explicit* request for a bundled name resolves to the same free node rather than erroring,
    so WP41's legacy import (whose `<children>` does list `Image Link`) needs no special case.
    Bundled auto-attach bypasses the parent-eligibility/category/Capacity-price checks entirely —
    forced by Control Rig → Datajack, which satisfies none of the three.
  - **Two validation rules beyond the entry's deliverable list, both from p. 456.** A limb holds at
    most one `Cyberlimb Enhancement` of each type ("you can't stack two Strength 3 enhancements in
    the same cyberarm"), and a customization may not exceed the character's natural maximum for that
    attribute ("you can't use the cyberlimb (so don't overdo it)") — which is what
    `{AGIMaximum}`/`{STRMaximum}` resolve to. `{AGIMinimum}`/`{STRMinimum}` resolve to the *limb's*
    floor of 3 (`CYBERLIMB_BASE_ATTRIBUTE`), not the character's, so `{AGIMinimum}+1` is 4.
  - **The third nesting level is cut, as ruled.** A plugin holding a plugin raises, naming the
    Cyber Implant Weapon Accessory fold-into-parent mechanic. A cyber implant weapon itself installs
    into a limb normally.
  - **`Customized`/`Enhanced Agility`/`Strength` are purchasable and correctly priced but
    mechanically inert** — they carry no `<bonus>` at all; their real effect is a *per-limb* STR/AGI
    attribute this engine has no representation of. Registered in the Project Overview's "Unmodeled
    real effects" table rather than silently dropped.

- [x] **WP39 — Conditional Improvements: a new engine primitive.**
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

  **Landed 2026-07-29**, entirely inside `chummer5.engine.improvements` (no other module touched),
  with 12 tests appended to `tests/unit/test_improvements.py`. What WP40-42 need to know:
  - **`Improvement.condition: ImprovementCondition | None = None`**, plus a new
    `ResolutionContext` enum and a keyword-only `context` parameter on `ImprovementIndex.resolve`.
    **Purely additive** — the signature change the WP entry anticipated turned out not to be
    needed: `context=None` resolves the plain unconditional value, which is exactly what every
    pre-WP39 call site already computed, so **zero call sites changed**. `condition=None` is a true
    no-op; an unconditional Improvement counts in every resolution, with or without a context.
  - **A `Condition` is an `Enum`** (not a closure, not a tagged union): `Improvement` must stay
    `frozen`, hashable and value-comparable, which a closure breaks, and every confirmed real shape
    is unparameterized. The condition is compiled at construction, never a string re-read at
    resolve time.
  - **A condition maps to a *set* of `ResolutionContext`s.** Forced by a fourth real bonus this
    WP's own entry doesn't name: **Hydraulic Jacks** (Physical limit, "Only for Gymnastics
    (Jumping) *and* Running (Sprinting)") — one condition, two unrelated activities. It is real
    fixture content (`Barrett.chum5` has two), so WP40 should wire **four** items, not three.
  - **No subsumption between conditions is modeled**, deliberately — Spatial Recognizer's "find the
    source of a sound" does *not* satisfy a hearing-Perception resolution. See
    `spec/rulebooks/learnings/phase-k.md`'s WP39 entry: the legacy engine never evaluates these
    conditions at all (it displays the condition string as a player-applied note), so there is **no
    oracle** for that call; making one is a fresh decision needing its own citation.
  - Condition filtering runs **before** the `unique_name` dedup pass, so an inapplicable conditional
    bonus can't win a dedup group it isn't competing in. `resolve_essence()` takes no context and
    *raises* on a conditional `ESSENCE` improvement rather than silently counting or skipping it.
  - The enum is `ResolutionContext`, not the more natural `TestContext`, only because pytest
    collects any importable class named `Test*`. Don't rename it back.

- [x] **WP40 — Wire real conditional-bonus subsystem items.**
  Goal: reclassify Vision Enhancement, Audio Enhancement, and Spatial Recognizer from
  `NOT_YET_SUPPORTED`/excluded to real, condition-gated Improvements, using WP39's new primitive.

  **Corrected by WP39 (2026-07-29): there are four such items, not three.** The fourth is
  **Hydraulic Jacks** (`Cyberlimb Accessory`) — `<limitmodifier><limit>Physical</limit>
  <value>Rating</value><condition>LimitCondition_CyberwareHydraulicJacks</condition>`, "Only for
  Gymnastics (Jumping) and Running (Sprinting)". It targets `PHYSICAL_LIMIT` where the other three
  target `MENTAL_LIMIT`, it is the reason WP39 models a condition as a *set* of contexts (one
  condition, two activities), and it is real fixture content (`Barrett.chum5` carries two). All four
  conditions already have an `ImprovementCondition` member and their English text is transcribed in
  `spec/rulebooks/learnings/phase-k.md`'s WP39 entry — so the `pdftotext` pass this WP's deliverables
  ask for is already done; re-confirm rather than re-derive.
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

  **Landed 2026-07-30**, spread across the four modules the four items actually touch rather than
  in a new one (the first Phase K WP with no new module), plus 17 tests. What WP41/WP42 need to
  know:
  - **`BonusSupport.CONDITIONAL_BONUS` went into `chummer5.data.cyberware`'s *shared* classifier**,
    settling the open call WP38's follow-up left. Both catalogs read the same rows of the same file,
    so a second classifier would be a copy. Deliberate consequence: **`load_cyberware()`
    reclassifies Spatial Recognizer** from `NOT_YET_SUPPORTED`, and `Cyberware`/`CyberwareEntry`
    each gain a `conditional_bonuses` tuple. WP37's "WP31's loader is completely unchanged" pin is
    narrowed, not broken — same 60 rows, same costs.
  - **A `CyberwareConditionalBonus` carries the verbatim legacy `<condition>` string**, not an
    engine enum; `chummer5.engine.cyberware._CONDITION_KEY_TO_CONDITION` maps it, mirroring
    `CyberwareFlatBonus.target_kind`'s existing string→`ImprovementType` split. A test pins the two
    whitelists to each other so neither can grow alone. `value=None` means "the purchased Rating"
    (`resolve_value(rating)`); the flat catalog *raises* on one rather than applying it as +1.
  - **`apply_cyberware_tree_improvements` (in `chummer5.engine.cyberware_subsystems`) is the tree's
    Improvement applier**, which WP38 explicitly deferred here. It reuses the shared
    `chummer5.engine.cyberware.cyberware_bonus_improvements`. Still nothing consumes it — no
    `Character` field until WP41 — so this remains proven-in-isolation plumbing.
  - **Hydraulic Jacks is a matched *pair*: one jack grants nothing, a pair grants `+Rating` once**
    (p. 457, quoted in `spec/rulebooks/learnings/phase-k.md`'s WP40 entry). No `<pairbonus>` exists
    on the row and the legacy engine never evaluates these conditions, so a per-node application
    would have silently produced `+2 x Rating` for `Barrett.chum5`. Modeled as a named rule; the
    pair test is "two of equal Rating in **distinct** parents," since no `<required>` data is loaded
    to check leg-ness.
  - **`derived.physical_limit`/`mental_limit` gained a keyword-only `context`** (purely additive;
    `social_limit` deliberately did not — no conditional Social bonus exists). This is the first
    place the project distinguishes the character sheet's headline figure from a specific test's,
    which WP42 needs when it shows "why a bonus applies only sometimes."
  - The **Wireless** halves of all four items (a dice-pool modifier of the same size) and Hydraulic
    Jacks' jump-distance/falling-damage clauses are unmodeled and now registered in the Project
    Overview's "Unmodeled real effects" table.

- [x] **WP41 — Cyberware modification save/load + legacy import.**
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

  **Landed 2026-07-31**, spread across the io + engine + web layers with no new module, plus 12 new
  tests (1107 total). This is the WP that **finished** WP38's deferred call-site migration:
  `Character.cyberware_selection` is a `CyberwareTreeSelection` now, and every purchase path
  resolves against WP37's full 87-row `CyberwareEntry` catalog. What WP42 needs to know:
  - **WP32's `CyberwareSelection`/`create_cyberware_selection`/`apply_cyberware_improvements` are
    retired**, not left in place — a second selection builder whose output can no longer be attached
    to a `Character` is a trap, and the tree engine enforces a strict superset of its rules.
    `chummer5.engine.cyberware` survives as the shared `<bonus>` → `Improvement` translator only
    (`cyberware_bonus_improvements` + the two string→enum maps); its tests moved to
    `tests/unit/test_cyberware_bonus.py`. `chummer5.data.cyberware.load_cyberware()` is **not**
    retired — the UI picker still lists its 60 flat rows.
  - **`CharacterSave.cyberware_item_ids` → `cyberware_purchases: tuple[CyberwarePurchaseRequest,
    ...]`.** `CyberwarePurchaseRequest` is reused verbatim as the persisted shape (the same reason
    `Contact` already is), with a new `CyberwareTreeSelection.to_requests()` as the inverse —
    bundled nodes omitted, since `create_cyberware_tree_selection` re-attaches them on load.
    A pre-WP41 save still loads: `_dict_to_save` falls back to the old key, mapping each id to a
    zero-plugin rating-1 request, which is exact (WP31's ids ⊂ WP37's; every WP31 row is unrated).
    `FORMAT_VERSION` is unchanged.
  - **The web layer is retyped but the picker is untouched, deliberately** — `_parse_cyberware`
    still yields flat ids, wrapped by a one-line `_purchase_requests` adapter, so every tree the
    browser builds is zero-plugin leaves at rating 1. Verified safe rather than assumed: no
    `CYBERWARE` row carries a `<rating>` tag, and none of the three `<subsystems>`-bearing parents
    (Cybereyes, Cyberears, Control Rig) is in `CYBERWARE`, so bundled auto-attach cannot fire from
    the picker. **WP42 owns rating selection and plugin installation.**
  - **Legacy import widened its catalog, not just its recursion.** "Rating-scaled" is no longer a
    rejection reason at any level (that was Phase K's whole point); non-SR5 source and non-Standard
    grade still are, and each nested item's reason names its parent. A **nested Bioware entry is
    rejected** (real SR5 allows it — p. 456 — but `chummer5.data.bioware` has no Capacity data, and
    zero fixture entries exercise it). Structural rules (category eligibility, Capacity budget,
    rating bounds) are deliberately *not* re-implemented in `_blocking_reasons`; they surface from
    `create_cyberware_tree_selection` at build time, the same place an over-budget nuyen spend
    always has.
  - **A consequence worth watching:** widening the import catalog also widens the pre-existing gap
    WP38's worklog flagged — `NOT_YET_SUPPORTED`-bonus cyberware is offered/imported with its bonus
    unmodeled and is absent from the Project Overview's "Unmodeled real effects" registry. WP41 did
    not backfill it; see `spec/decisions-log.md`, 2026-07-31.

**WP77-WP81 are numbered after WP42 but sequenced *before* it** — they were claimed on 2026-07-31,
once WP41 had already been written. WP41's own follow-up is why: WP42 is the WP that puts the widest
augmentation catalog this project has ever offered in front of a player, and it should not do that
while 15 rows in that catalog are purchasable, priced, and mechanically silent with no record of the
fact. WP77 (audit + registry), WP78 (model the computable ones), WP79 (show the notes) and WP80
(`Reflex Recorder`'s player choice) have landed — so WP42's hard prerequisite among them is met, and
no augmentation row is offered-and-inert any more. WP81 (natural vs. augmented attribute maximum)
and WP82 (the same for skills, claimed by WP80) landed on 2026-08-01 — neither gated WP42, but both
change what WP42's own picker and character sheet will be rendering: an attribute reads
`natural (augmented)` and a skill reads `bought (with bonuses)`, so any new augmentation display
WP42 adds should match those two conventions rather than inventing a third. **WP42 landed on
2026-08-01 and closed this phase.**

- [x] **WP77 — Augmentation `<bonus>` coverage audit + "Unmodeled real effects" backfill.**
  Goal: close the gap WP38's worklog first flagged and WP41's widening made larger — every
  `BonusSupport.NOT_YET_SUPPORTED` cyberware/bioware row is offered for purchase, charged in full,
  and grants *nothing*, and none of them appears in the Project Overview's "Unmodeled real effects"
  registry. That registry is the project's one place to look up "what does this offered aspect
  actually not do," and augmentation content has never been entered in it. **Documentation and
  classification only — no engine or catalog change** (see WP78 for the half that needs code).

  **This session's audit, to be re-confirmed rather than re-derived** (run over all 87 SR5
  `cyberware.xml` rows via `load_cyberware_entries()` plus all 6 `load_bioware()` rows; the counts
  below are exact as of 2026-07-31 but a WP that trusts them without re-running the classifier is
  doing it wrong). **15 rows classify as `NOT_YET_SUPPORTED`: 14 cyberware + 1 bioware.** They split
  into two genuinely different buckets, and the whole point of this WP is that they are *not* one
  bucket:

  **Bucket B — genuinely outside this engine's scope. These 10 are this WP's registry rows:**
  | Row | In WP31's flat 60 (offered today)? | `<bonus>` | Why unmodeled |
  |---|---|---|---|
  | Bone Lacing (Plastic / Aluminum / Titanium) | **yes**, all 3 | `<armor>`, `<damageresistance>`, `<unarmeddv>` | no character-level Armor total, no damage-resistance or unarmed-combat system |
  | Smartlink | **yes** | `<smartlink>2` | +2 dice on ranged attacks — no test resolution, no wireless state |
  | Damper | **yes** | `<sonicresist>2` | no sonic/damage-resistance subsystem |
  | Dermal Plating | no | `<armor>Rating` | same as Bone Lacing's armor half |
  | Armor (Cyberlimb Enhancement) | no | `<armor>Rating` | same |
  | Internal Air Tank | no | `<toxininhalationimmune/>`, `<pathogeninhalationimmune/>` | the same toxin/pathogen bucket Natural Immunity and Resistance to Pathogens/Toxins are already registered in |
  | Skillwires | no | `<skillwire>Rating` | no skillsoft subsystem |
  | Skilljack | no | `<skillsoftaccess>Rating` | no skillsoft subsystem |

  **Bucket A — computable by this engine today, and therefore *not* registry material.** Each of
  these 5 has a `<bonus>` whose effect maps onto an `ImprovementType` that already exists
  (`ATTRIBUTE`, `SKILL`, `INITIATIVE_DICE`), so under the Project Overview's 2026-07-24 policy —
  "every *computed, chargen-time* effect … must be modeled in full, or the aspect stays excluded" —
  registering them would be the wrong remedy. They are a **live policy violation**, not an accepted
  gap. This WP's job is to *name* them as one and hand them to WP78, not to fix or exclude them:
  | Row | Offered today? | `<bonus>` | Maps to |
  |---|---|---|---|
  | Reaction Enhancers | via legacy import only (WP41) | `<specificattribute>` REA +Rating | `ImprovementType.ATTRIBUTE` |
  | Wired Reflexes | via legacy import only | REA +Rating **and** `<initiativepass>Rating` | `ATTRIBUTE` + `INITIATIVE_DICE` |
  | Muscle Replacement | via legacy import only | AGI +Rating and STR +Rating | `ATTRIBUTE` |
  | Voice Modulator | via legacy import only | `<specificskill>` Impersonation +Rating | `SKILL` |
  | **Reflex Recorder** (bioware) | **yes — in the shipped UI since WP45** | `<selectskill limittoattribute="BOD,AGI,REA,STR">` +1 | `SKILL`, plus a player choice |

  Deliverables:
  - Re-run the classification over both catalogs; confirm (or correct, and say so) the 15/10/5 split
    and the per-row table above. Treat a mismatch as the finding, not as a reason to stop.
  - Add the 10 Bucket B rows to the Project Overview's "Unmodeled real effects" table, in that
    table's existing column shape, sourced `WP77`. Note in the `Kind` column which are offered by
    today's UI (5) versus reachable only through WP41's legacy import (5) — a player-visible gap and
    an import-only one are not the same severity, and the registry currently has no way to tell them
    apart for any aspect.
  - **Re-confirm each Bucket B "why unmodeled" against the code before writing it down**, rather than
    trusting this table. The armor rows are the one to be careful with: `chummer5.engine.resources
    .StarterGearItem.armor_rating` *does* exist (WP21), so "no armor at all" is wrong — what's
    missing is a character-level Armor total for anything to add to. Get that sentence right.
  - Record the Bucket A finding in `spec/decisions-log.md` as a dated entry: these 5 are offered and
    inert, that is a departure from the 2026-07-24 policy, WP78 is the fix, and they are deliberately
    **not** being excluded in the meantime (excluding `Reflex Recorder` would remove shipped
    functionality and break `Barrett.chum5`'s import positive case on the way to fixing it properly).
  Depends on: nothing new. **Should land before WP42.**
  Acceptance: the registry gains 10 rows; a test (or a documented one-off check — decide which, and
  say why) that pins "every `NOT_YET_SUPPORTED` augmentation row is either in the registry or named
  in WP78's scope," so this can't silently regrow the next time a catalog widens. No behavioural
  change: `pytest` count and every existing assertion unchanged.

  **Landed 2026-07-31**, documentation-only as scoped: no `src/` file changed, every pre-existing
  assertion untouched, +5 tests (1112 total). What WP78 and WP42 need to know:
  - **The audit re-ran exact.** 15 `NOT_YET_SUPPORTED` rows (14 cyberware + 1 bioware), splitting
    10 registry / 5 Bucket A, per row and per count. The entry's own table needed no correction.
  - **The 10 are in the Project Overview's registry** as 8 table rows (Bone Lacing's 3 variants
    share one, differing only in magnitude — the existing `Customized Agility / Customized
    Strength` grouping). Printed effects and citations: `spec/rulebooks/learnings/phase-k.md`'s
    WP77 entry.
  - **One correction to this entry's own table: Smartlink's printed effect is +2 *Accuracy*, not
    +2 dice** (p. 433 via p. 444/453). The legacy engine *does* apply `<smartlink>2` as a
    wireless-gated dice-pool modifier, so the table described the code, not the book. Both are
    equally unmodeled here; the registry row says both.
  - **`tests/unit/test_augmentation_unmodeled_registry.py` is the pin** — a test, not a one-off
    check, since the failure mode is a *future* catalog widening. It holds both bucket name-lists
    literally (the WP56 posture: the markdown registry is never read at runtime), so **WP78 must
    move each row it models out of `WP78_SCOPE`**, which is exactly the check WP78's own acceptance
    criteria ask for.
  - **The registry's `Kind` column now records reachability** (offered by today's UI vs. legacy
    import only) — 5 and 5 among these rows. Pre-WP77 rows are not retro-labelled.
  - **A gap found while writing the rows, now WP79:** nothing *shows* any of this to a player.
    WP56's `unmodeled_effect_note` mechanism exists and `derived.unmodeled_effect_notes` already
    walks cyberware/bioware for it, but no augmentation catalog populates the field.

- [x] **WP78 — Model the computable augmentation bonuses.**
  Goal: fix WP77's Bucket A — make the 5 rows whose real SR5 effect this engine *can* compute
  actually compute it, so they stop being offered-but-inert. This is the first time the augmentation
  `<bonus>` grammar grows since WP31 defined it, and it is deliberately its own WP for the same
  reason WP39 was: it changes a shared classifier both cyberware catalogs and (partly) the bioware
  one read, so it gets proven against synthetic data before real content depends on it.
  Deliverables:
  - Extend `chummer5.data.cyberware.classify_bonus`'s whitelist with the confirmed shapes:
    `<specificattribute>` (name + `Rating`-or-literal value), `<initiativepass>`, `<specificskill>`
    (name + value). Keep the "classify known, named shapes" posture — a whitelist, not a general
    `<bonus>` interpreter (WP22/WP25/WP27/WP36's shared precedent).
  - `CyberwareFlatBonus` carries `target_kind` + `value` and every producer passes `_GLOBAL_TARGET`
    today, because every modeled bonus so far has been a single character-wide total. An attribute or
    skill bonus needs a **real target** (`"REA"`, a skill id). Decide & document whether that is a new
    field on `CyberwareFlatBonus` or a sibling type, and how a skill *name* in the XML resolves to a
    skill id (`Impersonation` is an SR5 active skill — confirm).
  - Wire them through `chummer5.engine.cyberware.cyberware_bonus_improvements`, which both the flat
    and tree appliers already share, so neither path needs its own change.
  - **`<disablequality>` is deliberately out of scope** — `Wired Reflexes` and `Muscle Replacement`
    both carry one, and neither target is in the SR5 quality catalog (`Celerity` is not; the other is
    a raw guid — resolve it and confirm before relying on this). If either turns out to name a real
    SR5 quality, it does *not* get half-modeled: register it in the "Unmodeled real effects" table
    the way WP77 registered Bucket B, and say so.
  - **`Reflex Recorder`'s `<selectskill>` is a player choice, and is the one row that may not fit
    this WP.** It needs a chosen skill persisted (`CharacterSave`), re-validated on load, and picked
    in the UI — structurally the same problem WP55 solved for `SELECT_TEXT` qualities, and a real
    increment on top of the other four. Decide early whether it belongs here or as its own WP, and
    record the decision either way rather than letting it quietly determine the WP's size.
  Depends on: WP77 (its audit is this WP's input).
  Acceptance: unit tests, synthetic data first, that a `Reaction Enhancers` purchase raises REA (and
  through it Initiative and the Physical limit, which is the point), that `Wired Reflexes` raises
  both REA and Initiative Dice, and that `Voice Modulator` raises exactly the Impersonation dice pool
  and no other skill's; hand-checked against pp. 452-455's own printed entries. Plus an integration
  check against a real fixture that owns one (`Reaction Enhancers`: `BLUE`, `Mittens Chargen`,
  `SCSi`; `Wired Reflexes`: `Fuzzy-chargen`, `SCSi`), and an explicit test that every row this WP
  reclassifies has been removed from WP77's registry rows or was never in them.

  **Landed 2026-07-31**, touching two `src/` modules (`chummer5.data.cyberware`,
  `chummer5.engine.cyberware`) and no others — no new module, no save-format or web change, +33
  tests (1145 total). Four of the five Bucket A rows are modeled; the fifth became WP80. What WP42
  and WP79-WP81 need to know:
  - **Four rows, not five: `Reflex Recorder` is now WP80**, decided early as the entry asked. Its
    `<selectskill>` is a purchase-time *player choice* needing a persisted pick, load-time
    re-validation, a legacy `<extra>` import path and a UI picker — WP55's four-layer shape, and
    strictly larger than the other four combined. See `spec/decisions-log.md`, 2026-07-31.
  - **`CyberwareFlatBonus` was widened, not siblinged** (the entry's open call). Two new fields,
    both defaulted so no existing construction site changed: `target_name` (`""` for the
    character-wide kinds, which is also the `_GLOBAL_TARGET` sentinel — so
    `target=flat_bonus.target_name` covers both cases in one expression) and `unique_name`. `value`
    became `int | None`, `None` meaning "the purchased Rating," mirroring
    `CyberwareConditionalBonus` exactly; read it via `resolve_value(rating)`.
  - **A skill *name* is the target, not an id.** No id resolution is needed at all —
    `ImprovementType.SKILL` already resolves against `skill.name` everywhere in this engine
    (`chummer5.engine.skills.skill_rating`). `Impersonation` confirmed present in `skills.xml`.
  - **`precedence`/`unique` are the load-bearing part, and they are why the fixtures agree.**
    `precedence="0"` on a `<bonus>` child becomes `unique_name="precedence0"`; a `<bonus
    unique="...">` attribute becomes the default for children that don't override it. Without this,
    `SCSi.chum5` (Wired Reflexes 1 + Reaction Enhancers 1 over a natural REA of 2) would compute
    REA 4 against the legacy oracle's 3. p. 455 states the non-stacking rule outright, twice.
  - **`<disablequality>` stayed out of scope, as directed, and the guid resolved.**
    `3564b678-7721-4a8d-ac79-1600cf92dc14` is **Lightning Reflexes**, `source == "RF"` — so, like
    `Celerity`, it is absent from the SR5 quality catalog and unreachable by any character this
    engine builds. Nothing to register; a test pins the resolution so it can't rot.
  - **Two engine gaps found, deliberately not closed, both now dated entries in
    `spec/decisions-log.md`:** an attribute Improvement is capped at the *natural* maximum rather
    than SR5's augmented (+4) one — pre-existing since WP27's `Improved Physical Attribute`, now
    reachable from a second direction, and scoped as **WP81** because the fix requires a
    natural-vs-augmented split that `create_karma_attribute_selection`'s "only one at its natural
    maximum" rule also depends on; and legacy's `precedence0` *suppresses* unmarked bonuses where
    this engine adds them, reachable only for an adept who takes Improved Physical Attribute (REA)
    and also buys one of these implants.
  - `tests/unit/test_augmentation_unmodeled_registry.py`'s `WP78_SCOPE` is renamed
    `MODELED_BUT_UNCLASSIFIED` and holds one row (`Reflex Recorder`). WP79's "WP78's rows must have
    **no** note" invariant is unchanged and still pinned there.

- [x] **WP79 — Surface augmentation unmodeled-effect notes on the character sheet.**
  Goal: make WP77's 8 registry rows visible where a player can act on them. WP56 built the whole
  mechanism for qualities — `Quality.unmodeled_effect_note`, mirrored by hand from the Project
  Overview's table into `chummer5.data.qualities._UNMODELED_EFFECT_NOTES`, collected by
  `chummer5.engine.derived.unmodeled_effect_notes` and rendered as the character sheet's "Unmodeled
  real effects" disclosure. That collector **already walks `cyberware_selection.walk()` and
  `bioware_selection.items`** with a kind-agnostic `getattr(item, "unmodeled_effect_note", None)`
  (WP56 wrote it that way on purpose, and has a test pinning "walks them, contributes nothing").
  So this is a data-layer WP: populate the field, and the sheet lights up with no engine or template
  change. Claimed 2026-07-31 by WP77, which found the gap while writing rows nobody can see.
  Deliverables:
  - An `unmodeled_effect_note` field on `chummer5.data.cyberware.Cyberware`,
    `chummer5.data.cyberware_subsystems.CyberwareEntry` and `chummer5.data.bioware.Bioware`,
    populated from a by-name dict per module, mirroring `_UNMODELED_EFFECT_NOTES` exactly (default
    `None`, so no caller/test changes).
  - Notes for WP77's 8 registry rows **plus the 6 augmentation rows already in the registry from
    WP38/WP40** (Customized/Enhanced Agility/Strength, Vision/Audio Enhancement, Spatial
    Recognizer, Hydraulic Jacks) — those have a *partly* modeled effect, so their note is the
    unmodeled remainder, not "this does nothing." Check the wording carries that.
  - Decide whether the two catalogs' dicts are one shared constant or two: `Cyberware` and
    `CyberwareEntry` load the same rows from the same file, and only the second reaches a
    `Character` today.
  Depends on: WP77 (the rows). Independent of WP78 — but if WP78 lands first, its 5 rows must have
  **no** note, which is the same invariant `tests/unit/test_augmentation_unmodeled_registry.py`
  already pins. **Should land before WP42**, which is what puts the widest catalog in front of a
  player.
  Acceptance: a web test that a character owning Bone Lacing (Titanium) renders a non-empty
  "Unmodeled real effects" row for it (mirroring WP56's own quality-side test), and a data test that
  every name in that file's `REGISTERED_UNMODELED` resolves to a note in both cyberware catalogs.

  **Landed 2026-07-31**, data-layer only as scoped: three `src/chummer5/data` modules gained a
  defaulted field, `chummer5.engine.derived` gained only a docstring correction, and no template,
  route, engine or save-format code changed at all. +6 tests (1151 total). What WP42 and WP80-81
  need to know:
  - **The prediction held exactly: populate the field, and the sheet lights up.** WP56's
    `getattr(item, "unmodeled_effect_note", None)` collector needed no change, and neither did
    `_character_sheet.html`. Buying Bone Lacing (Titanium) now renders a real row where WP77 left
    an empty section.
  - **One shared constant, not two** (the entry's open call): `chummer5.data.cyberware
    .UNMODELED_EFFECT_NOTES` is public and imported by `chummer5.data.cyberware_subsystems`
    alongside `classify_bonus`. Two views of the same rows of the same file would otherwise be two
    mirrors of one registry table, free to drift while both looked maintained. `chummer5.data
    .bioware` keeps its own (different file) — and it is **empty**, deliberately: no bioware row is
    registry material, and `Reflex Recorder` specifically must not become one (that would launder
    WP77's Bucket A policy violation into an accepted gap; WP80 models it instead).
  - **16 names carry notes, not 10.** WP77's 10 registry names plus the 6 pre-existing WP38/WP40
    rows as 8 names (Customized/Enhanced Agility *and* Strength are 4 separate catalog rows). The
    partly-modeled 8 each end with a sentence saying what *is* applied, and a test asserts the
    word "modeled" appears in each — the cheapest available proxy for "this reads as a remainder,
    not as 'this does nothing'".
  - **The correspondence is pinned in both directions.** Every registered row resolves to a note in
    both cyberware catalogs, *and* no unregistered row carries one — the second being what keeps
    WP78's four modeled rows out of a table they must not be in. A future WP that models a
    registered row must delete its note in the same commit, or that test fails.
  - **Still not pinned: the note *wording* against the markdown table.** Closing that needs parsing
    `Project Overview.md` at test time, which WP56 rejected and this WP did not reopen. The
    Project Overview's registry preamble now states the hand-mirror obligation explicitly instead.

- [x] **WP80 — `Reflex Recorder`: a purchase-time skill choice on an augmentation.**
  Goal: finish WP77's Bucket A. `Reflex Recorder` (bioware, `source == "SR5"`, in the shipped
  picker since WP45) carries `<bonus><selectskill limittoattribute="BOD,AGI,REA,STR"><val>1</val>
  </selectskill></bonus>` — "+1 to one active skill linked to a physical attribute, chosen at
  purchase." It is the **last** augmentation row that is offered, charged in full, and mechanically
  silent, and it is a live departure from the Project Overview's 2026-07-24 "model it in full or
  exclude it" policy for as long as it stays that way. Claimed 2026-07-31 by WP78, which modeled the
  other four Bucket A rows and ruled this one out of its own scope because it is a different kind of
  problem, not a fifth instance of the same one.
  Deliverables:
  - A `<selectskill>` classification in `chummer5.data.bioware._classify_bonus` carrying the
    `limittoattribute` filter, *not* a resolved skill — the pick belongs to the purchase, not the
    catalog. Mirrors `chummer5.data.qualities`' `SELECT_TEXT` split (WP55) rather than
    `BiowareFlatBonus`'s fixed-name shape.
  - A per-purchase chosen skill on the bioware selection, validated against the filter (an active
    skill whose linked attribute is one of BOD/AGI/REA/STR — confirm the filter's semantics against
    `chummer5.data.skills` before hardcoding, the same way WP55 confirmed its own), persisted in
    `CharacterSave`, and re-validated on load.
  - Legacy import: the chosen skill is the item's `<extra>` element (`Barrett.chum5` stores
    `<extra>Longarms</extra>` — real fixture content, and the same fixture whose import positive
    case must keep passing). An unresolvable `<extra>` should be itemized the way WP41 itemizes
    every other blocking reason, not silently dropped.
  - A browser picker, mirroring WP55's own quality-detail control.
  - **Decide & document two things WP78 deliberately left open.** (a) Is the bonus applied as
    `ImprovementType.SKILL` (this engine's established route, which folds it into the skill
    *rating* and so caps at `MAX_SKILL_RATING_CREATE`) or does it need a genuine dice-pool
    modifier? Legacy treats a `<specificskill>` without `<applytorating>` as a **pool** modifier,
    and `Barrett.chum5`'s own copy of this bonus carries the comment "Hero Lab says this is not RAW
    `<applytorating>True`" — so the distinction is live, and it applies equally to Voice Modulator
    (WP78), Enhanced Articulation (WP45) and every focus/mentor skill bonus already shipped. (b)
    `Reflex Recorder` carries `<pairinclude><name>Reflex Recorder</name></pairinclude>`; check
    against p. 460 whether a matched pair behaves differently, the way WP40 found Hydraulic Jacks
    does.
  Depends on: WP78 (its classifier work is the pattern; nothing of its code is required).
  Acceptance: a unit test that a purchase with a chosen skill raises exactly that skill's pool; a
  rejection test for a skill outside the `limittoattribute` filter; a save/load round-trip carrying
  the pick; an integration test that `Barrett.chum5` imports with `Longarms` chosen. Plus the check
  WP77's pin already stands ready for: the row leaves
  `tests/unit/test_augmentation_unmodeled_registry.py`'s `MODELED_BUT_UNCLASSIFIED`, emptying that
  bucket for the first time since WP77 created it.

  **Landed 2026-07-31**, across the data/engine/save/import/web layers as scoped (no new module;
  `chummer5.data.{bioware,cyberware}`, `chummer5.engine.bioware`, `chummer5.io.{save_format,
  legacy_chum5,legacy_import}`, `chummer5.web.routes.{cyberware,character,priorities}` +
  `_cyberware.html`), +22 tests (1173 total). What WP42 and WP81-82 need to know:
  - **Both open questions answered, and both by the printed entry (p. 460), not by the data.**
    (a) "The reflex recorder adds 1 to the **Rating** of a specific skill linked to a Physical
    attribute" — a rating bonus, so `ImprovementType.SKILL` (this engine's established route) is
    correct and no dice-pool primitive was needed. It settles this row only: Voice Modulator's own
    printed wording is "to your dice pool," so the wider question WP78's worklog raised stays open.
    (b) **There is no matched-pair rule, and no `<pairinclude>` in `bioware.xml`** — this entry's
    own claim was wrong. The element it saw is in `Barrett.chum5`'s saved character node, beside an
    empty `<pairbonus />`; the only two `<pairinclude>`s in the file belong to `Striking Callus
    (Hands)/(Feet)`, both `CF`. What the page *does* state is the opposite rule: "Multiple recorders
    may be taken for multiple skills, but you can't implant two reflex recorders for the same
    skill," now enforced per (item, skill).
  - **`SELECT_SKILL` is a 5th value on the shared `chummer5.data.cyberware.BonusSupport`**, not a
    bioware-local enum — the same shape `CONDITIONAL_BONUS` already has (present on the shared type,
    produced by only one of the two catalogs). Classified by *shape*, not name-gated the way
    qualities' `SELECT_TEXT` is: a `<selectskill>` with a `limittoattribute` filter and exactly one
    `<val>` has one unambiguous reading. Verified sole producer: no SR5 `cyberware.xml` row carries
    `<selectskill>` in its `<bonus>` at all.
  - **`create_bioware_selection` takes `Iterable[str | BiowarePurchaseRequest]`.** A bare id keeps
    meaning "this item, no player choice" — a total, well-defined meaning for 5 of the 6 offered
    rows, so ~20 pre-WP80 call sites stayed correct instead of being rewritten to carry a permanent
    `chosen_skill=None`. `BiowareSelection.purchases` is the new field; `items` survives as a
    property, so `derived.unmodeled_effect_notes` and the web layer's Improvement swap read
    unchanged.
  - **`CharacterSave.bioware_item_ids` → `bioware_purchases`**, with WP41's exact fallback shape.
    The fallback is exact for every row *except* `Reflex Recorder`, whose pick was never persisted:
    such a save now fails to build ("requires a chosen skill") rather than loading with the bonus
    silently dropped. `FORMAT_VERSION` unchanged.
  - **`LegacyCyberware` gained `extra`** (defaulted, so synthetic test constructions are unchanged);
    an `<extra>` that doesn't resolve to a skill passing the filter is an itemized blocking reason,
    while the duplicate-skill rule stays a build-time check — the same split WP41 drew between
    name/grade checks here and structural ones in `create_*`.
  - **The picker renders one `<select name="bioware_skill_{id}_{n}">` per bought unit**, and only
    for a bought row (an unbought row renders no dropdown at all). The section's existing live
    re-render on `change` is what keeps the count in step with the quantity box.
  - **A gap found, not closed, scoped as WP82:** `skill_rating` clamps to `MAX_SKILL_RATING_CREATE`
    (6), so this bonus does nothing on a skill already at 6 — the skill-side twin of WP81, reachable
    from today's shipped UI, and shared by every skill Improvement this project grants. See
    `spec/decisions-log.md`, 2026-07-31.

- [x] **WP81 — Natural vs. augmented attribute maximum.**
  Goal: let an Improvement raise an attribute above its metatype maximum, up to SR5's augmented
  maximum, without breaking the chargen rules that currently read `attribute_value` as the *natural*
  rating. Claimed 2026-07-31 by WP78; see `spec/decisions-log.md`'s entry of that date for the full
  finding.
  The problem, stated once: `Character.attribute_value` returns
  `min(minimum + points + karma + Σ improvements, attribute_range.maximum)`. SR5 caps the
  *augmented* total at `metatype maximum + 4` instead (legacy `CharacterAttrib.AttributeModifiers`
  clamps Σ attribute improvements to `MetatypeAugmentedMaximum - MetatypeMaximum`, and
  `CalculatedTotalValue` then clamps to `TotalAugmentedMaximum`). `AttributeRange.augmented` is
  already loaded by `chummer5.data.metatypes` and read nowhere.
  **This is not a one-line cap change**, which is the whole reason it is its own WP:
  `chummer5.engine.character.create_karma_attribute_selection` enforces SR5's "only one Mental or
  Physical attribute may sit at its natural maximum" rule via
  `candidate.attribute_value(code) >= candidate.attribute_range(code).maximum`, which becomes
  silently wrong the moment `attribute_value` can exceed that maximum. `chummer5.engine.derived`
  and the character sheet have the same natural-vs-augmented question.
  Deliverables:
  - A natural-vs-augmented split on `Character` (decide the shape: a second method, a named tuple,
    or an `augmented=` flag — and document why), with every existing caller audited for which one
    it actually wants.
  - The augmented clamp itself, both halves (per-improvement `+4` ceiling and total cap).
  - Character sheet display: an augmented attribute should read as such, not as a bare number
    (WP35's "reduced from N by Essence loss" display is the nearest precedent).
  Depends on: WP78 (its four rows are the second real producer of attribute Improvements, after
  WP27's `Improved Physical Attribute`).
  Acceptance: a test that a character at their natural REA maximum plus Reaction Enhancers 3 reaches
  maximum + 3, and that Reaction Enhancers on top of a `+4`-worth of bonuses clamps at maximum + 4;
  an explicit test that the "only one at its natural maximum" Karma rule still reads the *natural*
  rating; `tests/integration/test_character_fixtures.py`'s existing skip of augmented attributes
  revisited — some of what it skips should now be checkable.

  **Landed 2026-08-01**, across engine + web + templates with no new module
  (`chummer5.engine.{character,knowledge,resources}`, `chummer5.web.routes.{attributes,character,
  contacts}`, `_attribute_allocation.html`, `_character_sheet.html`), +10 tests (1183 total). What
  WP82 and WP42 need to know:
  - **A second method, not a flag or a tuple** (the shape call this entry left open).
    `Character.natural_attribute_value(code)` is the bought rating; `attribute_value(code)` keeps
    its name and becomes the *augmented* total; `attribute_augmented_maximum(code)` names the
    ceiling. Chosen on where the default should sit: ~40 existing call sites want the augmented
    number and exactly 3 want the natural one, so a flag would have made every call site restate a
    choice it doesn't care about and made "forgot to pass it" a silent wrong answer.
  - **The `+4` is never hardcoded.** `AttributeRange.augmented` (`metatypes.xml`'s `<bodaug>`/…,
    loaded since WP2 and read nowhere until now) *is* `maximum + 4` on all eight primary attributes
    of all five SR5-core metatypes, and exactly `maximum` on EDG/MAG/RES — so Edge and Magic are
    un-augmentable by construction, no special case. Both clamps (Σ improvements → headroom, then
    total → augmented maximum) mirror legacy `AttributeModifiers`/`CalculatedTotalValueCore`.
  - **Three callers moved to the natural rating, and p. 95 names all three**: free Knowledge points,
    free contact points (engine + the web layer's own mirror), and the "only one at its natural
    maximum" Karma rule. `chummer5.engine.derived` deliberately did *not* move — the same sentence
    says Initiative and the Inherent Limits *are* modified by augmentations. The first two are a
    no-op for every character buildable today (nothing augments CHA/INT/LOG) but no longer depend
    on that holding.
  - **Display is `natural (augmented)`, collapsing to a bare number when equal** — the book's own
    notation (p. 95, "Strength 4 (6)"), on both the sheet and the attribute form. **WP82 should
    mirror this if it renders a split at all**; see its own landed note for why it doesn't.
  - **A corpus finding: legacy's `+4` clamp does not bound a cyberlimb average.** The new oracle
    test finds 22 augmented rows in the mundane corpus; all 22 respect the augmented maximum, 17
    respect the `+4` headroom, and the 5 that don't are all AGI/STR on the three cyberlimbed
    fixtures — legacy *replaces* the clamped total with a per-limb average for those two attributes
    before its last clamp. Recorded in `spec/rulebooks/learnings/phase-k.md` and excluded from that
    half of the test rather than asserted as universal.
  - WP78's "Gap 2" (`precedence0` suppression) is untouched and neither more nor less reachable.

- [x] **WP82 — Natural vs. augmented skill rating.**
  Goal: WP81's question, asked of skills instead of attributes. `chummer5.engine.skills.skill_rating`
  returns `min(purchased points + Σ improvements, MAX_SKILL_RATING_CREATE)`, so an *augmentation's*
  bonus is silently swallowed once the purchased rating reaches 6 — a Reflex Recorder bought for a
  rating-6 skill costs 14,000¥ and 0.1 Essence and changes nothing. Claimed 2026-07-31 by WP80,
  which made it reachable at a magnitude where it bites; see `spec/decisions-log.md`'s entry of that
  date.
  **Smaller than WP81, and the difference is the point.** SR5's 6 is a cap on what you may *buy* at
  character creation (p. 131's Skill Rating Table: "the maximum skill level for starting player
  characters", with ratings 7-12 described right below it), and this project's two purchase-side
  validators — `create_skill_allocation` and `create_karma_skill_selection` — already read purchased
  points directly rather than going through `skill_rating`, so they are natural-only by construction
  and need no change. That is the opposite of WP81's situation, where
  `create_karma_attribute_selection` genuinely reads the augmented value.
  Deliverables:
  - The ceiling itself: establish what actually bounds an augmented skill rating (rulebook first,
    then legacy's `Skill.RatingMaximum`/`TotalBaseRating` split as the executable spec) rather than
    assuming it mirrors the attribute `+4` rule, and apply it in `skill_rating`.
  - An audit of `skill_rating`'s callers for which ones want the natural rating and which the
    augmented one — `dice_pool`, the character sheet's skill rows, and the skill picker's own
    "points spent" display are three different answers.
  - Character sheet display: a skill above its purchased rating should read as augmented, mirroring
    whatever WP81 settles on for attributes (and WP35's "reduced from N by Essence loss" precedent).
  Depends on: nothing of WP81's code, but landing them together (or WP81 first) keeps one display
  convention rather than two.
  Acceptance: a test that a rating-6 skill plus a Reflex Recorder reaches 7 while a rating-6 skill
  *purchase* is still rejected at buy time; a test that the "no skill above 6 at creation" Karma and
  priority-point rules still read the purchased rating; every existing dice-pool assertion unchanged
  for characters with no skill Improvement.

  **Landed 2026-08-01**, one engine module plus the two display call sites
  (`chummer5.engine.skills`, `chummer5.web.routes.{skills,character}`, `_skill_allocation.html`,
  `_character_sheet.html`), +7 tests (1190 total). What WP42 needs to know:
  - **The ceiling is `MAX_SKILL_RATING = 12`, and 6 was never a rating cap.** p. 131's Skill Rating
    Table calls 6 "the maximum skill level for starting player characters" and then describes
    ratings 7-13; p. 129 defines the scale as running to 12 (13 with Aptitude).
    `MAX_SKILL_RATING_CREATE` stays exactly where it was, on the two purchase-side validators.
    `natural_skill_rating` is the new public function for the purchased rating.
  - **Legacy clamps neither**, so the 12 is this project's own guard-rail rather than a port:
    `Skill.TotalBaseRating` is unclamped and only the purchased halves see `RatingMaximum`.
    Unreachable with today's catalogs; Aptitude's 13 is not modeled (no `Improvement.Maximum`
    field, and `Aptitude` is `NOT_YET_SUPPORTED`).
  - **The clamp was costing dice pools, not just hiding an unspent implant.** Two synthetic
    fixtures moved (Renata's Gymnastics/Running, Sabine's Counterspelling) — each rating 6 → 7 and
    each *pool* from a die short to correct. Every skill bonus this project grants was truncated
    whenever it landed on a skill at or near 6, not only augmentation ones. Their `expected` values
    and citations encoded the bug and were corrected.
  - **The display says "bonuses", not "augmented", and that is deliberate.** Sheet and picker render
    `bought (with bonuses)` — `3 (4)`, `0 (2)` for a Catlike-boosted Sneaking, `0 (4)` for a
    Talent-granted skill — under a "Rating (with bonuses)" header. WP81 can say "augmented" because
    every attribute contributor is one; `ImprovementType.SKILL` mixes a Talent *grant*, printed
    dice-pool modifiers and genuine rating augmentations, and calling the delta an augmentation
    would assert the rating-vs-pool classification WP80 left open. See `spec/decisions-log.md`,
    2026-08-01.
  - `chummer5.engine.knowledge` is untouched — its Knowledge/Language ratings have the same
    purchase cap and no Improvement producer at all, so nothing to split yet.

- [x] **WP42 — Cyberware modification/subsystem UI.**
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

  **Landed 2026-08-01**, across the web + template layers with two small public-surface changes in
  the data/engine layers and no new module (`chummer5.data.cyberware`,
  `chummer5.engine.cyberware_subsystems`, `chummer5.web.{catalogs, routes.cyberware,
  routes.priorities, routes.character}`, `_cyberware.html`, `_character_sheet.html`), +20 tests
  (1210 total) in a new `tests/unit/test_web_cyberware_subsystems.py`. **Phase K is complete.**
  What a later WP needs to know:
  - **The offered catalog widened from 60 rows to 76** (`chummer5.web.catalogs
    .CYBERWARE_STANDALONE`): WP37's full 87 SR5 rows, minus the 9 `<requireparent>` rows (offered
    inside a parent instead) and `Essence Hole`/`Essence Antihole`. The `<requireparent>` move is a
    **bug fix**, not a narrowing — four of those 9 were in WP34's flat 60, and the engine rejects
    every one of them bought standalone, so the shipped picker offered four controls that could only
    produce an error. See `spec/decisions-log.md`, 2026-08-01, and the learnings entry for why the
    two Essence Hole rows are engine bookkeeping despite `source == "SR5"`.
  - **The form stayed backward compatible on purpose.** `cyberware_{item_id}` still means "how many
    of this row," so all of WP34's `tests/unit/test_web_cyberware.py` passes unchanged; everything
    per-unit hangs off that count by index (`cyberware_rating_{id}_{n}`, `plugin_{id}_{n}_{plugin}`,
    `plugin_rating_{id}_{n}_{plugin}`), the shape WP80 established for bioware skill picks.
  - **"Live Capacity" needed no new JS.** The section already re-posts itself on `change`, so a
    ticked plugin checkbox re-renders the parent's `Capacity N of M remaining` line — the same
    mechanism WP15's remaining-points display uses.
  - **Two engine symbols were made public for the UI**: `cyberware_rating_bounds` (so the rating
    control offers exactly the range `_build_purchase` validates — a control that can produce a
    rejection is the one thing a rating picker must not be) and `PAIRED_BONUS_ITEM_NAMES` (so the
    sheet can say a Hydraulic Jack's bonus is granted once per matched pair). Plus a new
    `chummer5.data.cyberware.CONDITION_DESCRIPTIONS`, the four conditions' English text, mirrored
    from `en-us.xml` beside `UNMODELED_EFFECT_NOTES` and pinned to the same whitelist by a test.
  - **`_cyberware_context`'s third parameter changed shape** (flat ids → a `CyberwarePurchaseRequest`
    tree), and `chummer5.web.routes.priorities` passes `to_requests()`. That is what makes a
    committed limb's plugins survive a full-page re-render instead of being dropped by the next
    submission.
  - **The sheet's cyberware recap is nested and grouped**, one line per distinct top-level purchase
    (same row, same rating, same subsystems) with its plugins beneath it, each conditional bonus
    printed as `+N Mental limit — Only for Perception (Visual)`. The derived-stats table gained
    conditional limit rows (`Mental limit, visual Perception tests`), emitted only when they differ
    from the headline — **the first consumer of the `context=` parameter WP40 added to
    `derived.physical_limit`/`mental_limit` and left unused**.
  - **Display costs are resolved in the web layer, not read off the validated selection**, because
    the picker must render the rejected state (over budget, over capacity) where no selection
    exists. The same independent-tally shape WP34's subtotal column already had.
  - **A plugin is a checkbox, not a quantity box** — the one place this UI is narrower than the
    engine, with its one consequence (a legacy-imported duplicate plugin collapses on re-submit)
    recorded in the decisions log rather than hidden.
  - **Nine rows in the Project Overview's "Unmodeled real effects" registry changed reachability**
    (WP77's five import-only augmentation rows, WP38's four cyberlimb-enhancement rows), updated in
    the same commit; the registry preamble now states that a UI-widening WP owes that re-check.
  - **A follow-up nobody has claimed:** `chummer5.data.cyberware.load_cyberware()` and its
    `Cyberware` dataclass are now unused by `src/` outside tests/fixtures — WP41 kept them
    explicitly because the picker still listed them, and that reason is gone. See the decisions-log
    entry for the four test modules a retirement would touch.

