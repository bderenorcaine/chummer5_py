# Decisions log

Dated entries recording scoping decisions, corrections, and cross-phase findings discovered during
implementation — split out of `Project Overview.md`'s former "Open questions" section as of WP57
(Phase Q) so the Overview itself stays a compact, current-state reference rather than growing
indefinitely as a changelog. Anything discovered during implementation that materially changes scope,
data compatibility, or the Improvement engine's shape gets raised as a new dated entry here before
being acted on, the same standing rule the old section stated.

None blocking MVP start as of the original writing — the three foundational calls (UI stack,
save-format strategy, MVP magic/resonance scope) are made in `Project Overview.md` itself. Smaller
implementation-level decisions (exact Python version floor, dependency/packaging tool, pydantic vs.
plain dataclasses for the domain model) are treated as low-cost-to-change defaults set when
scaffolding the project, not spec-level rulings.

The MVP itself (Phases A-F) shipped without hitting any entry below — everything here was raised
afterward, during design discussions scoping what came next. None of it blocked or reversed anything
already shipped; each is a prerequisite, correction, or ruling for work still ahead of it at the time.

### 2026-07-18 — Essence is a hardcoded constant; cyberware/bioware need real tracking first, not just new catalog content

`chummer5.engine.derived.BASE_ESSENCE` is a fixed `6`, read in exactly one place (`social_limit`) —
correct for MVP, since nothing in MVP's scope ever reduces Essence (see that module's own docstring
for the full Yeti-fixture trace that led here). Surfaced while scoping cyberware as a candidate
post-MVP expansion: real Essence tracking (a `Character` field plus a `6 - Σ(cyberware/bioware
essence cost)` formula) is a genuine prerequisite for cyberware, not a side effect of adding a
catalog — and it isn't the only one. `chummer5.io.legacy_import` currently hard-*rejects* any
`.chum5` import containing cyberware/bioware specifically because of this gap (tested explicitly),
so that rejection path has to be unwound in the same piece of work, not routed around. Neither is
difficult in isolation, but a cyberware WP needs to land both *before* cyberware content itself, not
alongside it.

### 2026-07-18 — "Talent forced to E" is real plumbing in the web layer, not just an engine default

Confirmed while scoping adept-first magic as a candidate post-MVP expansion. The rules/data side is
close to ready: Adept-eligible Talent letters (B/C/D) already parse cleanly out of `priorities.xml`
with zero changes needed to `chummer5.data.priorities`, and for pure Adepts, Power Points equal the
Magic rating 1:1 (no separate formula to derive). What isn't ready is the assumption, threaded
through `chummer5.web.session`'s letter constants and `chummer5.web.app`'s priority-validation logic
(not just the engine layer), that Talent sits outside the 4 player-chosen priority categories.
Making Talent a real 5th choice touches more existing plumbing than any other post-MVP candidate
surveyed — this is why adept magic, despite having the best-scoped *content* of any candidate (only
6 of 28 SR5 Adept Powers even need new Improvement handling), isn't scoped as the smallest next step.
See Implementation Plan's Phase H intro.

*(A third entry — whether `Character`'s frozen shape should hold every committed selection, not just
attributes — was raised here 2026-07-18 and resolved the same day by WP18/WP19. See "Character as the
single aggregate" under Architecture below for the settled design; entries here stay only while
genuinely open.)*

### 2026-07-19 — Metatype-granted free qualities (Low-Light Vision, Thermographic Vision, Resistance to Pathogens/Toxins) were never modeled

Surfaced by a user question while reviewing WP22. Confirmed via the raw data: `legacy/Chummer/data/
metatypes.xml` grants specific SR5-core qualities for free at character creation via a
`<metatype><qualities><positive>/<negative>` block — Elf and Ork both get Low-Light Vision, Dwarf
gets Thermographic Vision **and** Resistance to Pathogens/Toxins, Troll gets Thermographic Vision;
Human gets none. The legacy engine has a dedicated mechanism for this (`QualitySource.Metatype` —
auto-granted, zero karma cost, excluded from the karma cap, auto-removed if the metatype changes;
`Character.cs` ~line 44348). None of this exists in the new engine: `chummer5.data.metatypes
.Metatype` never parses the base `<qualities>` block at all (only `Metavariant` does, and
metavariants are entirely out of MVP scope), so an Elf/Dwarf/Ork/Troll character built through this
engine today silently gets none of their racial qualities. This also connects to WP22 concretely:
Low-Light Vision/Thermographic Vision are now in the *purchasable* catalog (WP22's `NO_EFFECT`
tranche) with no check preventing a non-Human character from spending karma on something they
should already have for free, and (confirmed separately) `chummer5.io.legacy_chum5.LegacyQuality`
doesn't capture `<qualitysource>` at all, so importing a real Elf/Dwarf/Ork/Troll `.chum5` (5 of the
11 curated mundane fixtures: `BLUE`/Ork, `Blindfire`/Elf, `Gentle Earthquake`/Troll, `Monomax
(approved) 3`/Troll, `Rez0luti0n2.0`/Dwarf) would now misreport their free racial quality as a
karma-costing player pick. Scoped as WP23, next on the Implementation Plan — see that entry for the
fix.

### 2026-07-19 — Magic scoping: two rulings (Mystic Adept out, free-skill grant in), plus the
research each one resolved or required

Surfaced while scoping Phase I (Magicians & physical Adepts) against real data, then settled by two
explicit product decisions the same day.

**Ruling 1 — Mystic Adept is out of scope entirely**, not deferred for size/research-cost reasons
like every other cut in this phase, but simply not being built. This has a convenient technical side
effect: it retires the one piece of research that would otherwise have blocked WP25 outright — a
Mystic Adept's Power Point split (flagged unresolved on 2026-07-18) is a Mystic-Adept-only wrinkle; a
pure Adept's PP is a plain 1:1 Magic-rating grant with nothing to split.

**Ruling 2 — the Talent free-skill grant (`skillqty`/`skillval`/`skilltype`) is in scope**, reversing
WP2's original "out of MVP scope" framing (written when Talent wasn't a real player choice at all).
Reading `SelectMetatypePriority.cs` directly (the legacy form that actually applies this grant) shows
the two `skilltype` values this phase's offered Talent options ever produce are both plain
category/field filters, not a general expression language: `"magic"` (Magician) means "any skill with
`category` in `{Magical Active, Pseudo-Magical Active}`"; `"xpath"` (Adept, letter B only) carries one
specific literal expression — `not(attribute = 'RES' or attribute = 'DEP') and (not(category =
'Magical Active') or skillgroup = '' or not(skillgroup))` — expressible as a plain predicate over
`chummer5.data.skills.Skill`'s existing `attribute`/`category`/`skill_group` fields. Both are
implementable as named, hardcoded predicates (mirroring WP3/WP22's "classify known shapes" method);
no general XPath evaluator is needed for what this phase actually offers. See Implementation Plan's
Phase I intro and WP25 for the full detail, including why neither of the phase's own two real
fixtures can be used to verify the grant's *exact numbers* (Miko's `.chum5` commingles free-grant
points with regular Skills-priority spend in one `<base>` field; Wesson's Talent letter, C, grants no
free skill at all) — the mechanism is verified against the traced legacy C# directly instead.

Unrelated to either ruling, still true and unchanged: confirmed against both of the corpus's only
magic-capable `buildmethod = Priority` fixtures (`Miko.chum5`, an Elf Magician; `Wesson.chum5`, a
Human Adept), the Magic rating is **not** funded from a priority-derived points budget the way EDG
is — the chosen Talent option's `magic` field (`chummer5.data.priorities.TalentOption.magic`) *is*
the finished MAG rating outright. Adding `"MAG"` to
`chummer5.engine.character.SPECIAL_ATTRIBUTES` (EDG's shape) would silently misimplement this.

### 2026-07-19 — Cyberware scoping: 8 of the 11 curated "mundane" fixtures already carry real
cyberware, and their stored Essence costs are usually unresolved rating formulas, not numbers

Surfaced while scoping Phase J (Cyberware) against real data. `tests/fixtures/README.md`'s definition
of "mundane" has only ever been `<magenabled>False</magenabled>` — never "augmentation-free." Checked
directly: `BLUE`, `Barrett`, `Bastion`, `Blindfire`, `Fuzzy-chargen`, `Gentle Earthquake`,
`Monomax (approved) 3`, and `SCSi` (8 of the 11 WP4-curated fixtures) each carry between 3 and 16 real
`<cyberwares>` entries. This is not a latent bug — every derived-stat test that exists today already
worked around it correctly rather than by accident (`test_cross_corpus_attribute_value_matches_when_
unaugmented` explicitly skips cyberware-boosted attributes; `social_limit`, the one Essence-dependent
derived stat, is only ever asserted against real fixture data via `Yeti-#ffffff2.chum5` specifically,
which has zero cyberware) — but it means Phase J inherits real, ready-to-use fixture coverage for
Essence math well beyond what a from-scratch catalog WP would normally get.

That coverage comes with a caveat, though: a fixture's per-item `<ess>` field is frequently the source
catalog's *unresolved* rating formula (e.g. `Rating * 0.3`, `FixedValues(2,3,5)`), not a resolved
number — the legacy engine evaluates it at read time rather than storing a resolved value per
purchase. Only a modest, specific subset of real purchases across these 8 fixtures (Datajack, the
Cyberlimb variants, Smartlink, Bone Lacing (Titanium)) are flat-cost/flat-essence items unaffected by
this. See Implementation Plan's Phase J intro and WP31-33 for the resulting catalog cut and its
honest acceptance-criteria caveat (full `<totaless>` reproduction against these fixtures is not a
realistic bar for Phase J alone).

### 2026-07-19 — Essence-driven Magic loss is a real interaction between Phase I and Phase J, deferred
to a dedicated WP because neither phase's fixtures can exercise it

SR5 reduces a magically active character's Magic (or Resonance) rating as Essence is lost to
cyberware/bioware. This connects Phase I (Magicians & physical Adepts) and Phase J (Cyberware)
directly, but no fixture in the 34-file corpus is simultaneously Priority-built, magic-enabled, and
cyberware-bearing, so the interaction can't be validated against real data from either phase alone.
Scoped as Phase J's WP35, deliberately sequenced after both phases' own engine work rather than
folded into whichever phase happens to land first.

### 2026-07-19 — Adept Drain is real: Drain Resistance is not Magician-only, and one Adept Power
(Attribute Boost) was nearly misclassified as a permanent flat bonus

A user question ("adepts might have to roll drain, since several adept powers are active rather than
passive, e.g. Attribute Boost") caught a wrong assumption already written into Phase I before any
code existed. Checked directly against the rulebook via `pdftotext -layout` (p.309): "Adept Drain:
Some powers cause Drain. The Drain from adept powers is Stun unless specified in the description, and
is resisted with Body + Willpower" — a real, named rule, structurally different from a Magician's
tradition-dependent Drain (which resists with a tradition-chosen attribute pair instead). Two of the
28 SR5 Adept Powers actually trigger it: Adrenaline Boost and Attribute Boost, both `NOT_YET_SUPPORTED`
in Phase I's classifier (their effects require in-play test resolution this engine's combat-free scope
doesn't model) — but Drain Resistance itself is still a real, cheaply-computable derived stat for any
Adept, using the fixed BOD+WIL formula, independent of which specific powers were bought (the same way
Physical/Mental/Social Limit are shown regardless of build specifics). Corrected in Implementation
Plan's WP28.

The same check surfaced a second, sharper find: `cyberware.xml`-style raw-XML inspection showed
Attribute Boost's `<bonus><selectattribute>` node has the *identical* child tag as Improved Physical
Attribute's — but no `<val>` child, because Attribute Boost's real magnitude comes from an in-play
Magic + Rating Test, not a fixed formula. A classifier keyed on "`selectattribute` bonus == flat
attribute bonus" (a direct, reasonable-looking generalization of `chummer5.data.qualities`'s own
`_is_flat_attribute_bonus` shape) would have silently applied Attribute Boost as a permanent stat
increase. Caught before any code was written; see Implementation Plan's WP27 for the corrected
classifier rule (presence of a `<val>` child is the real discriminator) and the broader finding it
led to — every Adept Power's bonus value is the literal token `"Rating"`, not a hardcoded int the way
every quality's `FlatBonus` value already is, so WP27's applier needs a rating-resolution step
`chummer5.data.qualities` never needed.

### 2026-07-19 — Karma-bought attribute points at character creation were never modeled, a general
legacy-import gap, not a magic-specific one

Surfaced while pursuing WP28's own acceptance criterion (importing `Wesson.chum5` end to end).
`chummer5.io.legacy_import.import_legacy_character`'s `attribute_points` formula has read
`legacy.attributes[code].base + legacy.attributes[code].karma` since WP12 — combining
priority-derived points (`base`) with points bought afterward with Karma, beyond the priority
budget (`karma`), into one number, then validating that combined total against `create_character`'s
priority-budget-only check. This was never actually exercised with a nonzero `karma` value before
WP28: Yeti (the sole Priority-built fixture among the curated mundane 11) has `karma == 0` on every
allocatable attribute. Wesson does not — his real `<attribute name="EDG"><base>1</base>
<karma>1</karma></attribute>` against Heritage E's 1-point special-attribute-points budget for
Human means he spent 1 Karma-bought EDG point beyond that budget, a real, standard SR5
chargen-time Karma-for-attribute-points purchase this engine has never modeled at all. Not
magic-specific — any future Priority-built fixture with nonzero attribute `karma` would hit the
same gap regardless of Talent. Fixed in WP28 by rejecting it as a new, itemized legacy-import
blocking reason (mirroring cyberware/metavariant), not by implementing the underlying mechanic —
modeling real Karma-for-attribute-points spend at chargen (which would need a tracked
starting-Karma budget this engine has no concept of at all) remains out of scope, unraised as its
own candidate WP for now since nothing currently blocks on it. See Implementation Plan's WP28 and
`spec/worklogs/WP28.md` for the full research.

### 2026-07-21 — Five post-MVP phases scoped (Phases L-O + a Phase P research intro), three explicit
"won't build" rulings, and a note on the chapter extraction that fed this scoping session

A user request to survey what's still needed for full rulebook chargen support led first to extracting
the "Creating a Shadowrunner" chapter (rulebook pp. 62-104) verbatim into
`spec/rulebooks/character_creation_chapter.md` (Steps One-Nine, every quality, every table, with a
cross-reference index of every later-chapter page citation — deliberately excluding the
"Character Advancement"/career-mode section and the "Character Archetypes" pre-gen NPC appendix), then a
gap survey against it, then this scoping session. Five new phases came out of that survey:

- **Phase L — easy wins**: Karma-to-Nuyen conversion, the Sum-to-Ten build method, and Bioware.
- **Phase M — magic expansion**: Bound Spirits (roster + Karma budget only, no spirit stat-block/power
  modeling — deliberately deferred, see Phase M's own intro), Foci (bonding + a gear-catalog entry), and
  Mentor Spirits (a WP22/WP27-sized classification pass over ~20+ archetypes, each granting 3 distinct
  bonuses).
- **Phase N — expanded skill support**: Knowledge/Language skills (currently entirely absent — confirmed
  via `chummer5.data.skills`'s own docstring) and wiring up skill specializations for real (the +2
  dice-pool formula already exists in `chummer5.engine.skills`, but there was no purchase mechanism, no
  point cost, and no UI at all before this phase — confirmed via `grep` finding zero hits in `web/`).
- **Phase O — Karma-buying (chargen-time only, not career mode)**: a unified "leftover Karma" ledger on
  `Character` (today, qualities (WP8) and contacts (WP9) each spend Karma via independent one-shot
  checks that don't share a running total with anything else), then Karma-funded attribute increases,
  skill/skill-group increases (including the "buying a Karma-funded specialization breaks an existing
  skill group" case the rulebook restricts to this step specifically, not Step Five), and extra
  spells/complex forms beyond a Talent option's free grant. **Correction to earlier scoping**: this
  project previously treated the "Character Advancement" section (rulebook pp. 103-107) as pure
  career-mode content and excluded it wholesale from the chapter extraction above — it turns out Step
  Seven's own text explicitly says to reuse those exact Karma-cost formulas (new Rating x 5 for
  attributes, x 2 for skills, x 5 for skill groups, x 1 for Knowledge/Language) for **chargen-time**
  leftover-Karma spend, not just for post-creation advancement. Phase O needs those specific formulas
  even though the section they're printed in was correctly excluded as a whole.
- **Phase P — rigger support (research-intro only, no WPs assigned yet)**: vehicles, drones, RCCs, and
  control rigs. Confirmed during scoping that this is not sized like the other four phases — vehicles/
  drones are their own rulebook chapter with their own stat block and **multiple separate
  modification-slot pools per vehicle** (not the single Capacity number cyberware has), and an RCC drags
  in the Matrix device-rating stat block (Attack/Sleaze/Data Processing/Firewall) this project has never
  modeled for anything. **Ruling: modifications (vehicle mods, drone mods, RCC/cyberdeck upgrades) are
  excluded for now** — the phase is scoped down to buying stock/unmodified vehicles, drones, RCCs, and
  cyberdecks only. Still needs its own research pass (mirroring Phase K's own pre-scoping research
  entry in `spec/rulebooks/learnings.md`) before a WP breakdown is written.

**Three explicit "not now" rulings that came out of the same session, recorded here so they aren't
re-litigated by a future WP:**
1. **The Availability-cap mechanic stays unbuilt.** Simplification agreed instead: any catalog (gear,
   cyberware, bioware, foci, eventual vehicle gear) should simply exclude Availability > 12 items from
   what it offers. This does not retroactively fix WP21's gear catalog or WP31's cyberware catalog,
   neither of which filters by Availability today — flagged, not scheduled.
2. **The Karma-based build method** (`CharacterBuildMethod.Karma` in the legacy engine — buying an
   entire character from a large Karma pool instead of Priority or Sum-to-Ten) **stays out of scope.**
   Worth distinguishing by name from Phase O above ("Karma-buying") — Phase O is chargen-time leftover-
   Karma spend *within* Priority/Sum-to-Ten chargen, not this alternate whole-character build method.
3. **Technomancers/Resonance** reaffirmed out of scope (no change — already excluded per the MVP scope
   section above; recorded again since it came up in the same ruling as the other two).

See Implementation Plan's Phases L-P for the resulting work packages (WP43 onward).

### 2026-07-23 — WP52 confirms `create_character`'s pure-priority-point path has never enforced
SR5's "only one Mental/Physical attribute at natural maximum" rule, and surfaces a second,
unrelated Karma-ledger gap (an excluded quality's Karma credit silently lost)

Two findings while implementing Phase O's WP52 (Karma-funded attribute increases), neither blocking
that WP but both worth recording so a future WP doesn't rediscover them from scratch.

**Finding 1**: the core rulebook restricts character creation to at most one Mental or Physical
attribute sitting at its own natural (metatype) maximum — stated at Step Two (p.99) and explicitly
restated at Step Seven for Karma spend specifically (p.100: "These rules still apply to when you are
spending Karma"). This engine's `chummer5.engine.character.create_character` (WP6) has never
enforced it for ordinary priority-point spend — confirmed by `grep`, and confirmed harmless so far
only because the one priority-build regression fixture (`Yeti-#ffffff2.chum5`) never happens to
reach a metatype maximum on more than one primary attribute. WP52 enforces the rule for its own new
Karma-funded spend (`chummer5.engine.character.create_karma_attribute_points`) but deliberately does
not retrofit `create_character` itself — a different function, a different WP's job if it's ever
worth doing. See `spec/rulebooks/learnings.md`'s WP52 entry and that function's own "Scope note"
docstring paragraph for the full detail, including a real implementation trap this surfaced (the web
layer calls the new validator on *every* attribute-form submission, not just Karma-spending ones, so
the check has to fire only when the submission itself touches a Mental/Physical attribute — otherwise
a legal pure-priority spend that happens to hit two maxima would be rejected on the next unrelated
edit).

**Finding 2**: `Wesson.chum5` (this project's one real Adept fixture) was expected, per WP52's own
Implementation Plan entry, to finally reach a clean `import_chum5()` round-trip once Karma-bought
attribute points were modeled — it doesn't. His real EDG Karma-buy (rating 3 → 4) legitimately costs
20 Karma (confirmed against the legacy engine's own `UpgradeKarmaCost` formula), affordable in the
real character only because his real `SINner (Corporate Limited)` quality carries a +15 Karma
credit — a quality this project has never offered (WP22's own scoping ruling, unmodeled
background-check/social-consequence narrative weight) and still doesn't. Every unsupported quality a
legacy import drops was already silently losing its Karma-cost side effect before this WP (WP8's
"excluded, not silently mis-applied" rule already implied this); WP52 is simply the first WP whose
own Karma-spending consumer is expensive enough for that loss to matter. Not fixed here — fixing it
would mean reopening WP22's own SINner exclusion, out of scope for a Phase O attribute-spend WP. See
`chummer5.io.legacy_import`'s own WP52 docstring paragraph and `spec/worklogs/WP52.md` for the full
arithmetic and the tests that pin down the corrected (still-blocked, but for a new and different
reason) behavior.

### 2026-07-24 — WP55 closes the SINner gap WP52 found, generalizes quality mutual-exclusion
parsing, and reaffirms the "significance" judgment call framing this WP itself retires

Built the free-text ("`<selecttext>`") quality-selection mechanism WP22 flagged as missing, and used
it to offer the 9 qualities WP22's own research had already fully characterized as needing only that
mechanism (SINner ×4, Code of Honor, Codeblock, Social Stress, Natural Immunity ×2) — see this
section's own table above for what's modeled vs. not per quality. Two findings worth recording:

**`Wesson.chum5` finally reaches a full end-to-end `import_chum5()` round-trip** — the first WP to
get there, after WP28 (blocked on Talent/tradition scope) and WP52 (blocked on this exact SINner
gap) both fell short. His real `SINner (Corporate Limited)` pick's `<extra>` ("Lone Star Security
Services") resolves directly into `QualitySelection.quality_text` via the same field
`LegacyPower.extra` already threads through for select-attribute Adept powers — no new legacy-import
parsing was needed beyond reading a field this project already had.

**`Quality.forbidden_names` (parsed from `<forbidden><oneof><quality>`) was built generally, for
every SR5 quality, not just this WP's own 9** — it costs nothing extra (a uniform, single-shape
parse confirmed across all 31 SR5 qualities carrying a `<forbidden>` block), so WP22's two
"deliberately deferred" mutually-exclusive pairs (Insomnia (Basic)/(Full); Distinctive Style/
Blandness) get correct exclusion enforcement for free whenever a future WP offers either — no new
work needed on `create_quality_selection`'s side when that happens.

This WP also finishes the retroactive reversal this section's own policy note above (settled the
same day) started: WP22's original "significance" judgment call — excluding SINner/Code of Honor/
Codeblock/Social Stress/Natural Immunity specifically, rather than offering them with a documented
gap — no longer reflects this project's policy. All 9 are now offered in full, karma charged/
credited correctly, with every unmodeled consequence recorded in the table above rather than used as
a reason to withhold the quality.

### 2026-07-25 — WP60/WP61 (Phase T): first real hands-on browser testing since the UI shipped
surfaced two bugs and one previously-undiscovered latent gap

Raised directly from manual browser use, not a design-discussion scoping session like every entry
above — worth recording anyway since two of the three findings weren't obvious from the code alone.

**Bug 1 (WP60)**: the Attributes and Skills sections' "Karma remaining" numbers went wrong on any
full-page reload after a Karma-funded spend — reported as a qualities-triggered recompute bug, but
actually a Python dict-key collision: `_attribute_allocation_context`/`_skill_allocation_context`/
`_knowledge_selection_context` all returned the identically-named generic `"karma_budget"`/
`"karma_remaining"` keys, and `_chargen_body_context`'s dict-spread merge let whichever was applied
last (Knowledge) silently clobber the other two for the whole merged page render. Underlying
`Character`/session state was correct throughout — confirmed by direct `TestClient` +
`app.state.sessions` introspection before touching any code. Fixed by prefixing all three (matching
`_spell_selection_context`/`_spirit_selection_context`/`_foci_selection_context`'s existing
convention). See `spec/worklogs/WP60.md`.

**Bug 2 (WP61)**: a Magician/Adept couldn't spend regular Skill-priority points or leftover Karma on
Spellcasting or any other Magical Active skill — only their Talent free-grant ever raised one, a gap
WP29 (2026-07-19) had already found and deliberately deferred pending a decision on which subset of
Magical Active skills to offer. Resolved by reusing `chummer5.engine.magic
.MAGICAL_SKILL_CATEGORIES` (the exact category filter WP25 already verified for the free-grant
itself) rather than commissioning new rules research — SR5 doesn't restrict regular skill-point
spend by magic type or tradition, only the free grant is restricted.

**Previously-undiscovered latent gap, surfaced (not caused) by WP61's own skill-category grouping**:
`MUNDANE_SKILLS`'s exclusion had been attribute-based (`attribute not in ("MAG", "RES")`) since WP2,
not category-based — a plausible but wrong proxy. 3 of the 12 Magical/Pseudo-Magical Active skills
(Assensing/INT, Astral Combat/WIL, Arcana/LOG) use a non-MAG linked attribute despite requiring
Awakened status to use at all, so a strictly Mundane character could always buy all three. Fixed
alongside WP61's main widening — the exclusion is now `Skill.category not in
(MAGICAL_SKILL_CATEGORIES | {"Resonance Active"})`. See `spec/worklogs/WP61.md` for the full trace
of how the category-grouping work made this visible.

## 2026-07-27 — Second manual-testing pass: five bugs verified (Phase U), five QoL requests recorded (Phase V)

A second hands-on browser-testing pass over the shipped chargen UI (first since Phase T) reported
five defects and five feature requests. All five defects were verified against the current
templates/routes before any WP was written; scoped into Phase U (WP64-66) and Phase V (WP67-71).

**On "the accordion lets more than one section open at once — was this intended?":** *partly.* The
one-section-at-a-time behavior is server-driven (`ChargenSession.open_section`); native client-side
exclusivity via a shared `<details name>` was **deliberately removed after WP61** because it raced
with htmx's `outerHTML` swap and collapsed the section a player had just used (documented in
`chummer5.web.session.ChargenSession`'s "Post-WP61 fix" docstring). Consequence: manually clicking
several `<summary>` bars open — with no server round-trip — leaves them all open. So it is not a
regression, but it is a real gap for anyone who expects click-to-open exclusivity. **Ruled 2026-07-27: restore
exclusivity** — WP64 does this via a client-side toggle listener that closes sibling sections and
survives the next htmx swap, *not* by re-adding a shared `<details name>` (which would bring back the
WP61 race).

**Bug root causes (all verified, not just reported):** the skill sub-category re-expanding
(`_skill_allocation.html:87-91` renders `<details open>` from server-derived "has active rows",
overriding a manual collapse on every swap) and the text-input focus loss (`hx-trigger="change,
input delay:400ms"` + `hx-swap="outerHTML"` rebuilds the focused field mid-typing) share the same
root as the accordion: an `outerHTML` section swap discards client-only DOM state — WP64/WP65 fix
these. The specialization-pool display shows only the specialized value because `dice_pool` folds
the +2 `SPECIALIZATION_BONUS` into the single rendered number (WP65 splits it into `X (Y)`). The
missing gear (fake SINs, AR glasses/goggles/contacts, earbuds, headphones) is the WP21 flat-cost
filter excluding every `Rating * N`-priced entry — a documented MVP cut, not a regression; WP66 adds
Rating-priced gear support (the one non-trivial fix, since it introduces a per-item rating
dimension). **Ruled 2026-07-27: cap the offered rating** so each Rating-priced item's computed
`<avail>` stays ≤ 12 (Fake SIN `(Rating*3)F` → max offered rating 4), making WP66 the first place
the gear catalog enforces the 2026-07-21 Availability ≤ 12 line — scoped to the new Rating-priced
items only, not a retroactive re-filter of WP21's flat-cost catalog.

### 2026-07-29 — WP66: Rating-priced gear scope — Foci/Formulae excluded, availability cap parses the `<avail>` formula, one flat/rating name collision resolved

Recorded while implementing WP66 (Rating-priced starter gear). Three sub-decisions, all made at the
`chummer5.engine.resources.build_starter_gear_catalog` policy layer rather than the
`chummer5.data.gear.load_rating_gear` loader (which stays a literal XML→dataclass translation):

- **Foci and Formulae categories are excluded from the gear catalog.** Of the 120 SR5-sourced
  `Rating * N` gear entries, 64 are the `Foci`/`Formulae` categories — the same items the dedicated
  Foci bonding system (`chummer5.data.foci`/`chummer5.engine.foci`, WP47) already models with real
  Force/Karma-bonding semantics and magic-gating. Offering them as plain rating-priced gear would
  duplicate and misrepresent them (a focus must be bonded with Karma to function, and a mundane
  character can't use one at all), so they're dropped. This is a deviation from the WP's literal
  "load the rest of the catalog" wording, made deliberately. Note: the *flat-cost* `Spell Formula, X`
  entries (also `Formulae` category, but a different thing — spell formulae, offered since WP21) are
  untouched; the exclusion is scoped to rating-priced items only. Net offered after all filters: 51
  Rating-priced items.

- **The Availability ≤ 12 cap parses each item's `<avail>` formula into `slope*rating + intercept`**
  (`chummer5.data.gear.parse_rating_availability`) and clamps the selectable rating range to the
  highest rating that stays ≤ 12 (Fake SIN `(Rating*3)F` → offered max rating 4, even though its
  `<rating>` is 6). An item over the cap even at rating 1 (Plastic Explosive, flat `16F`) is dropped
  entirely. A leading `+` in `<avail>` marks an accessory added to a *parent's* availability (Vision
  Enhancement, Audio Enhancement, etc.) — excluded, mirroring `load_gear`'s existing `+`-cost
  accessory exclusion. This implements the 2026-07-27 ruling above and is the first place the gear
  catalog enforces the project's 2026-07-21 Availability line at all; per that ruling it is **not**
  retroactively applied to WP21's flat-cost catalog.

- **One flat/rating name collision (`Camera`) is resolved in favor of the rating item.** `Camera`
  exists as both a 0-cost `Sensor Functions` component (flat) and the real `Rating * 100` `Vision
  Devices` item. The name-keyed catalog can't hold both; the rating-priced one wins, via the same
  "0 is never a real standalone price" tie-break the existing flat-collision handling uses.

Data-model shape: a Rating-priced purchase carries a chosen rating separately from flat gear — a new
`ResourcesSelection.gear` item field (`rating`, `cost_per_rating`, `max_rating` on `StarterGearItem`)
and a new `CharacterSave.rating_gear_picks` `(name, rating)` list, persisted alongside `gear_names`.
Carry-forward sites (priority reconfirm, Lifestyle/cyberware re-validation, save building) use the
new `resources_gear_args` helper to split a committed selection back into `(gear_names, rating_gear)`
so a rating item's chosen rating survives re-validation instead of collapsing to a bare name.

### 2026-07-29 — WP70: bound-spirit chargen cost is a flat 1 Karma/service, NOT Force-scaled (the WP note's own guess, corrected against the rulebook)

WP70 (Phase V) lets a Magician bind a spirit at a Force below their Magic rating (previously pinned
to exactly Magic and never stored). The WP's own note in `phase-v-ui-improvements.md` guessed the
chargen binding cost "scales with Force (Force × Karma per service)" — and explicitly instructed
verifying that against the rulebook before implementing. **Verified: the guess is wrong.** Step
Seven's "Additional Purchases & Restrictions" table (core rulebook p. 98) gives a flat **1 Karma
per service**; its parenthetical "Force = character's Magic rating" is the *default* Force, not a
cost multiplier (full citation in `spec/rulebooks/learnings/phase-m.md`'s WP70 entry). So
`chummer5.engine.spirits.KARMA_PER_SERVICE` stays `1`; WP70 changes only which binds are *legal*,
never the per-service cost. Force cap at chargen is the Magic rating (`1 ≤ force ≤ Magic`) — the
general Summoning rule's Magic × 2 cap (p. 300) is the looser, post-chargen number, the same
"chargen number is the tighter one" pattern WP47 hit for Foci.

Data-model/compat shape: each `CharacterSave.bound_spirit_picks` entry widens from a `(spirit_type,
services)` pair to a `(spirit_type, force, services)` triple, where `force` is `int | None`. A
persisted integer is the player's chosen Force; `None` — and, on read, the *absence* of a `"force"`
key in a pre-WP70 save — means "default to the live Magic rating", exactly the pre-WP70 behavior.
So every pre-WP70 save round-trips unchanged (WP46's "Force is never stored, always live Magic"
design is preserved as the `None` default rather than removed). This retires the WP46 module-docstring
claim that a bound spirit's Force "is always exactly the caster's current Magic rating (not
player-chosen)".

### 2026-07-29 — WP59 (Phase S): legacy-engine-generated fixtures ruled out permanently; new fixtures are native synthetic, not fake `.chum5`

WP59's fixture-strategy research pass settled the question Phase S was created to answer. Two findings,
the second decisive on its own:
- **No usable .NET/Mono toolchain, and `Chummer.Tests` targets `net48` + WinForms and project-references
  the entire WinForms Chummer app** — unbuildable on Linux by the .NET SDK, a long shot under Mono
  (which isn't installed or in the apt repos anyway). Corrects the Phase S intro's claim that the csproj
  is "pre-SDK-style `packages.config`": it's actually `<Project Sdk="Microsoft.NET.Sdk">`, but that
  doesn't change the verdict.
- **Toolchain-independent blocker:** `ChummerTest.cs` only *loads and round-trips* the existing
  `TestFiles/*.chum5`; no test path takes a synthetic chargen definition and *emits* a computed
  character. So even a working build could not generate a new golden fixture for a hand-designed
  character — that needs the interactive WinForms chargen forms or fresh C# harness code.

**Ruled:** legacy-engine-generated fixtures are off the table permanently (not "deferred until a
toolchain exists" — the round-trip-only finding is toolchain-independent). New fixtures are hand-authored
in a **native synthetic format** — a `SyntheticCharacter` input literal driven through the real engine
plus a hand-derived, rulebook-cited `expected` table — **never a fake `.chum5`**, since a `.chum5` with
hand-computed derived values only impersonates legacy ground truth. Full reasoning, the seven-gap
coverage inventory (G1-G7), and the resulting WP list (WP72-76) live in
`spec/plan/phase-s-test-fixtures.md`'s "WP59 findings" section; retrospective in `spec/worklogs/WP59.md`.

### 2026-07-29 — Phase K taken off hold; its formula-shape survey corrected (8 shapes, not 6), and a PDF page-offset finding that affects every future rulebook citation

Phase K ("Cyberware modifications") was parked on hold on 2026-07-21, scoped but deliberately unstarted.
**Off hold as of this date**, at the user's direction; WP36 (the rating-formula resolver) landed the same
day. Nothing about the phase's scope or sequencing changed — WP37-42 stand exactly as scoped.

Two corrections came out of WP36's mandated re-confirmation pass, both worth recording because they
apply beyond the WP that found them:

- **The Phase K intro's "6 distinct formula shapes" is 8.** That survey was an exploratory pass over the
  27 entries WP31 excluded, weighted toward `<cost>`; re-derived over all 87 SR5 entries and all three
  formula-bearing fields it becomes 8. The additions are a bare `Rating` (only ever seen bracketed, in
  `<capacity>`) and `(Rating * A) + B` — the `<ess>` **shared** by Cybereyes Basic System and Cyberears,
  which the intro had folded into those two items' "one-off named formulas" when in fact only their
  `<cost>` is one-off. The rest of the intro's survey (the `<capacity>` shape list, the 29-parent split)
  held up; the parent/plugin half is still WP37's to re-confirm.
- **`spec/rulebooks/Shadowrun_Fifth_Edition_Core_Rulebook.pdf`: physical page = printed book page + 2,
  and a Chummer `<page>` tag names an item's *narrative section* start, not the table its numbers are
  printed in.** Both verified by reading each page's own printed folio out of its footer. Concretely,
  every Eyeware/Earware item carries `<page>453</page>` while the Eyeware/Earware *tables* are on
  p. 454 (PDF p. 456) — p. 453 holds the Headware table and the eyeware narrative. This retroactively
  corrects the "p. 453 (Eyeware/Earware tables)" citation in `learnings/phase-k.md`'s pre-Phase-K entry
  (the quoted mechanic there is unaffected — only the page number for the tables). Future WPs citing
  this PDF should derive the offset from a footer rather than trusting an XML `<page>` tag or the
  `-f N` page number.

## 2026-07-29 — Phase K, WP37/WP39: cut the cyberware third nesting level; this engine evaluates
conditional bonuses the legacy engine only displays

Two findings from WP37 and WP39 that reach past the WPs that found them.

**WP37 — the Cyber Implant Weapon → Weapon Accessory layer should be cut explicitly in WP38, not
supported.** The Phase K intro flagged it as "a genuine two-level nesting case; confirm whether any
curated fixture actually exercises it before deciding whether to support that third level or cut it
explicitly." Confirmed, both ways: no fixture exercises it (every depth-2/3 nested purchase across
all 34 `.chum5` files is a Chrome Flesh modular-limb chain, out of SR5 scope — the two cyber implant
weapons that appear at all are childless), and the data gives such a weapon no budget to spend (its
`<capacity>` is bracketed, and legacy `Cyberware.CapacityRemaining` returns 0 for a purely-bracketed
Capacity, matching neither of its two branches). The 3 SR5 accessories instead carry
`<addtoparentcapacity>`/`<addtoparentess>` — their cost folds into the *weapon's* cost against the
*grandparent limb*, which is a different mechanic, not one more level of the same one. Recorded as a
scoping ruling rather than left in a docstring because it decides what WP38 builds. Both flags are
captured in `chummer5.data.cyberware_subsystems` regardless, so WP38 can revisit from data.

**WP37 — a correction to the pre-Phase-K bundled-free reading, which that entry itself flagged as
needing confirmation.** Auto-inclusion is driven by a parent's `<subsystems>` element, not by the
`[*]` Capacity marker, and the SR5 set has **three** instances, not two: the third is
`Control Rig` → `Datajack`, which carries neither `[*]` nor `<allowsubsystems>` and *is* real fixture
content (`Mittens Chargen.chum5`). The two signals mean different things and both are needed.
Recorded here because "there are exactly two bundled items, both marked `[*]`" had already been
written down twice (the pre-Phase-K learnings entry and the Phase K intro) and would otherwise keep
propagating.

**WP39 — this engine evaluates conditional Improvements; the legacy engine does not, so for this one
mechanic there is no regression oracle.** Legacy Chummer builds a `LimitModifier` object carrying a
condition *string* and displays it on the character sheet as a note for the player to apply by hand;
it never adjusts the limit total. This project's stated testing strategy leans on the legacy engine
as the oracle for "silently-wrong rules logic," so it matters to record where that oracle simply
isn't there. Consequence already acted on: WP39 models **no subsumption** between related conditions
(Spatial Recognizer's "Perception to find the source of a sound" does not satisfy a
Perception-(Hearing) resolution), because nothing establishes the containment as a rule rather than a
reading and there is nothing to diff against. Any later WP wanting a hierarchy is making a fresh
ruling, not restoring a lost one.

**WP39 — the SR5 conditional-bonus catalog is four items, not the three both WP39's and WP40's plan
entries name.** The fourth is Hydraulic Jacks ("Only for Gymnastics (Jumping) and Running
(Sprinting)", a Physical rather than Mental limit modifier, present twice in `Barrett.chum5`). It is
the reason an `ImprovementCondition` maps to a *set* of `ResolutionContext`s rather than to one.
WP40's entry has been annotated accordingly.

## 2026-07-30 — Phase K, WP38: the tree selection sits alongside the flat one (WP41 migrates);
bundled subsystems are always auto-attached; cyberlimb attributes are an unmodeled mechanic

Three findings from WP38 that reach past the WP that found them.

**The purchase tree does not replace `CyberwareSelection` — WP41 does that.** WP38's plan entry
called this out as "a real compatibility decision, not a mechanical rename," and the decision is:
alongside. `chummer5.engine.cyberware.create_cyberware_selection` is typed on WP31's flat
`Cyberware` all the way out through `io.save_format`, `io.legacy_import`, `web.routes.cyberware` and
five test modules, while a tree node necessarily holds WP37's `CyberwareEntry` (a rating-scaled row
has no single cost until a rating is chosen). Retyping every call site *and* introducing the nesting
mechanic in one WP would bundle a mechanical migration into a rules change — the same split WP37
already declined to make. **WP41 owns the migration**, which is natural since it has to touch
save/load and legacy import anyway; `CyberwareTreeSelection` reuses
`nuyen_budget`/`nuyen_spent`/`essence_spent` verbatim so the swap stays mechanical. Consequence worth
stating explicitly: until WP41, a `Character` has no field for a tree selection at all, so the
"two selection shapes both charging Essence" hazard cannot arise by accident.

**Bundled subsystems (`<subsystems>`) are always auto-attached and free, and bundling bypasses every
eligibility check.** WP38's entry asked for the fixture check before choosing between
"always-auto-attached (simpler)" and "a skippable choice." Checked: **8 of 8** `<subsystems>`-bearing
purchases across all 34 `.chum5` fixtures carry their bundled child (5 Cybereyes Basic System, 2
Cyberears, 1 Control Rig), never skipped — so always-attached it is. "Free" means all three
currencies: 0 nuyen (legacy `Cyberware.Create` forces `objSubsystem.Cost = "0"`, and every fixture
stores `<cost>0` for a bundled item), 0 Essence (any child contributes zero), 0 Capacity. The
bypass matters beyond tidiness: `Control Rig` → `Datajack` satisfies *none* of the three eligibility
tests a normal plugin must pass (no `<allowsubsystems>` on the parent, wrong category, and a bare
rather than bracketed `<capacity>`), so treating a bundled item as an ordinary plugin would reject
real fixture content. An explicit request for a bundled name resolves to the same free node instead
of erroring, so WP41's legacy import needs no special case for `<children>` listing `Image Link`.

**Cyberlimb attributes are a mechanic this engine has no representation of, and WP38 makes four
items purchasable on that basis.** `Customized Agility`, `Customized Strength`, `Enhanced Agility`
and `Enhanced Strength` carry **no `<bonus>` element at all** — their real effect is a *per-limb*
STR/AGI attribute ("Physical attribute enhancements add their Rating to the appropriate attribute of
the limb," p. 456; "All standard cyberlimbs come with Strength and Agility attributes of 3"), which
the legacy engine models as a whole parallel attribute system per limb and this project does not
model anywhere. Offered anyway, correctly priced in nuyen and Capacity, per the 2026-07-24 policy:
every *computable* chargen-time effect is applied in full, the unmodeled part is recorded in the
Project Overview's "Unmodeled real effects" registry. Flagged here rather than only in the registry
because a future cyberlimb-attribute WP would need to revisit both this and the `Cyberlimb`
condition-monitor bonus WP31 already models, and because it is the first *cyberware* content to enter
that registry — WP31/34's `NOT_YET_SUPPORTED` items (e.g. Smartlink) are still unregistered, which
is a gap someone should close.

## 2026-07-30 — Phase K, WP40: Hydraulic Jacks is a matched-pair implant; `BonusSupport` gains a
fourth value shared by both cyberware catalogs; the Improvement half of the tree lands here

**Hydraulic Jacks grants its bonus once per matched *pair*, not once per purchase — a rulebook rule
with no signal anywhere in the data.** p. 457: "This implant requires you to have two cyberlegs with
a hydraulic jack of identical Ratings in each leg. Each Rating point adds a +1 to your Physical
limit for jumping and sprinting." So a lone jack grants **nothing**, and a pair grants `+Rating`
**once**. The `cyberware.xml` row carries no `<pairbonus>`/`<pairinclude>` (both exist in the legacy
schema; WP37 deliberately captures neither), and the legacy engine never evaluates a conditional
limit modifier at all — so a per-purchase application would have silently produced `+2 x Rating` for
`Barrett.chum5`, an entirely ordinary real build that owns exactly two. Modeled as a named rule
(`_PAIRED_BONUS_ITEM_NAMES`), with the pair test being "two of equal Rating in **distinct** parents"
rather than "in two legs": the jacks' `<required><parentdetails>` leg restriction is real but WP37
loads no `<required>` data, so leg-ness is not something this engine can currently check. A later WP
that does load `<required>` should tighten it. Recorded here rather than only in the learnings file
because it is the first time this project has found a *pairing* mechanic at all, and `<pairbonus>`
items elsewhere in the catalog will hit the same shape.

**`BonusSupport.CONDITIONAL_BONUS` is added to `chummer5.data.cyberware`'s shared classifier, which
means WP31's flat catalog reclassifies one row.** WP38's follow-up flagged the "which module gains
the new value" call as open, since WP40's plan entry names `chummer5.data.cyberware` (WP31's frozen
flat catalog) while three of the four conditional items live only in WP37's wider
`cyberware_subsystems` catalog. Decision: extend the one shared `classify_bonus`, because the two
catalogs read the *same rows of the same file* and a second classifier would be a copy, not a
separation. The visible consequence is deliberate and is the point of the WP: **Spatial Recognizer
moves from `NOT_YET_SUPPORTED` to `CONDITIONAL_BONUS` in `load_cyberware()`**, so a purchase that is
already possible through today's shipped UI starts granting a real (conditional) +2 Mental limit.
WP37's "WP31's loader is completely unchanged" guarantee is narrowed accordingly: which rows load
and what they cost is still untouched; the `<bonus>` classification of one row, and the field set
(a new `conditional_bonuses` tuple), are not. Both pinning tests were updated with that note rather
than deleted.

**WP40 also brings the tree's Improvement application, which WP38 explicitly deferred to it.**
`apply_cyberware_tree_improvements` lives in `chummer5.engine.cyberware_subsystems` and reuses
`chummer5.engine.cyberware.cyberware_bonus_improvements` — the engine mirroring the data layer's own
single shared classifier. Still nothing *consumes* it: a `Character` has no tree-selection field
until WP41, so this remains proven-in-isolation plumbing exactly as WP36-38 were.

**`chummer5.engine.derived.physical_limit`/`mental_limit` gain a keyword-only `context`.** Purely
additive (WP39's `resolve(context=None)` is the pre-existing behaviour), and deliberately not added
to `social_limit`: no aspect this engine offers carries a conditional Social limit bonus, and WP39's
rule is to add a context only where a real bonus needs one. This is also the first API in the
project that distinguishes "the character sheet's headline figure" from "the figure for one specific
test" — worth knowing before WP42 designs how to display it.

## 2026-07-31 — Phase K, WP41: the flat cyberware selection is retired (not deprecated in place);
legacy import's cyberware catalog widens from 60 rows to 87; nested Bioware is refused

**WP32's `CyberwareSelection`/`create_cyberware_selection`/`apply_cyberware_improvements` are
deleted, and this was WP38's question to answer here.** WP38 shipped the purchase tree "alongside"
the flat selection precisely so that a mechanical call-site migration wouldn't ride along with a
rules change, and handed the survives-or-not call to WP41 ("the WP that decides whether
`CyberwareSelection` survives at all or becomes a thin wrapper over a zero-plugin tree"). Decision:
delete. Once `Character.cyberware_selection` is typed on `CyberwareTreeSelection`, the flat builder
has no constructor path and no consumer — a second selection builder whose output can never be
attached to a character is a trap for the next agent, not a convenience, and the tree engine already
enforces a strict superset of its rules (unknown ids, nuyen budget, the strictly-positive Essence
floor shared via `other_essence_spent`, duplicates legal). Nothing was lost in coverage:
`tests/unit/test_cyberware_selection.py` became `tests/unit/test_cyberware_bonus.py`, keeping the
`<bonus>` → `Improvement` translation tests plus the data/engine condition-whitelist pin, because
every selection/apply test it held already has a counterpart in `tests/unit/test_cyberware_tree.py`.
`chummer5.data.cyberware.load_cyberware()` is **not** retired — the web picker still lists its 60
flat rows until WP42 widens the UI, so "the flat catalog" and "the flat selection engine" had
genuinely different fates.

**`chummer5.io.legacy_import` now resolves cyberware against WP37's 87-row `CyberwareEntry`
catalog, at every nesting level.** WP41's plan entry only asks for nested items to resolve against
that catalog, but keeping top-level items on WP31's flat 60 would have made a `Cybereyes Basic
System` unimportable and therefore its children unreachable — the exact content the WP exists to
import. Consequence, deliberate: **"rating-scaled" stops being a rejection reason at all** (Phase K
built a formula resolver so that it wouldn't be), and a stored `<rating>` is now imported. Non-SR5
source and non-Standard grade remain blocking at both levels, unchanged. `LegacyCyberware` gains
`rating` (stored as literal `0` for an unrated item in the legacy format — resolved to this engine's
floor of 1 in `legacy_import`, not silently normalised in the parser) and `children`.

**A gap this widening makes bigger, and did not fix.** WP38's worklog already flagged that WP31/34's
`NOT_YET_SUPPORTED`-bonus cyberware (Smartlink and friends) is offered with its bonus unmodeled and
is absent from the Project Overview's "Unmodeled real effects" registry. Widening the import catalog
extends that to every rating-scaled `NOT_YET_SUPPORTED` row too (e.g. `Wired Reflexes`, now
importable, whose Initiative/Reaction bonus this engine does not model). Not fixed here — it is a
registry backfill spanning WP31/34's own content, not something WP41 introduced — but it is now
larger than when it was first flagged, and it should be closed before WP42 puts a wider catalog in
front of a player. **Scoped the same day as Phase K's WP77** (the registry backfill) **and WP78**
(the part that turned out not to be a registry problem at all) — an audit run while writing those
found that of the 15 `NOT_YET_SUPPORTED` augmentation rows, 5 have a `<bonus>` this engine *can*
compute (attribute, Initiative Dice and skill bonuses on `Reaction Enhancers`, `Wired Reflexes`,
`Muscle Replacement`, `Voice Modulator`, and the bioware `Reflex Recorder`). Those 5 are a
departure from the 2026-07-24 "model it in full or exclude it" policy rather than an acceptable
documented gap, and one of them (`Reflex Recorder`) is offered by the shipped UI today. See
`spec/plan/phase-k-cyberware-mods.md` for the full per-row split.

**A nested Bioware entry is refused rather than half-costed.** Real SR5 allows Capacity-priced
bodyware inside a cyberlimb (p. 456's "Bodyware with a Capacity cost can be installed in cyberlimbs,
costing capacity rather than Essence" — the same sentence WP38 cited for dual costing), but
`chummer5.data.bioware` carries no Capacity data at all, so there is nothing to charge the parent.
Checked before deciding: **zero** nested `<cyberware>` entries across all 34 fixtures carry
`improvementsource == "Bioware"`, so this refuses a case the corpus never exercises rather than
blocking real content. A future bioware-Capacity WP would lift it.

**Structural validation stays in the engine, not duplicated into `_blocking_reasons`.** The itemized
import checks cover name/source/grade (what can be decided per item, with no character); category
eligibility, the parent's Capacity budget and rating bounds all surface from
`create_cyberware_tree_selection` during `build_character` as a plain `ValueError` — exactly where an
over-budget nuyen spend has surfaced from since WP33. Re-implementing them in the import module
would be a second copy of rules that can drift.

## 2026-07-31 — Phase K, WP77: five offered augmentations are a live policy violation, not a
registry gap; the registry gains a reachability marker; the notes are written but not yet shown

**The audit re-run, and it holds.** WP41's entry stated 15 `NOT_YET_SUPPORTED` augmentation rows
(14 cyberware + 1 bioware), splitting 10/5. Re-derived from scratch over `load_cyberware_entries()`'s
87 SR5 rows and `load_bioware()`'s 6: **exact**, per row and per count. No correction needed, which
is worth recording because the WP entry explicitly asked for the counts to be re-run rather than
trusted.

**The 10 that belong in the registry are now in it** (as 8 table rows — Bone Lacing's 3 variants
share one, differing only in magnitude, matching the registry's existing `Customized Agility /
Customized Strength` grouping). Each names the printed effect and the specific missing subsystem;
see `spec/rulebooks/learnings/phase-k.md`'s WP77 entry for the citations.

**The other 5 are *not* registered, deliberately.** `Reaction Enhancers`, `Wired Reflexes`,
`Muscle Replacement`, `Voice Modulator` (all cyberware) and `Reflex Recorder` (bioware) carry a
`<bonus>` that maps onto an `ImprovementType` this engine already has — `ATTRIBUTE`,
`INITIATIVE_DICE`, `SKILL`. Under the 2026-07-24 policy ("every *computed, chargen-time* effect …
must be modeled in full, or the aspect stays excluded") these are a **departure from the policy**,
not an accepted gap, and registering them would launder one into the other. They stay offered and
inert in the meantime rather than being excluded: `Reflex Recorder` has been in the shipped bioware
picker since WP45 and is real content in `Barrett.chum5`'s import positive case, so excluding it
would remove working functionality *and* break a passing test on the way to fixing it properly.
WP78 is the fix. `tests/unit/test_augmentation_unmodeled_registry.py` pins the split so a future
catalog widening cannot quietly add a row to either bucket — a test rather than the one-off check
WP77's entry allowed, because the failure mode is a future change, which no one-off check catches.

**The registry's `Kind` column now records reachability.** Half of WP77's 10 rows (Bone Lacing ×3,
Smartlink, Damper) are purchasable from the browser today; the other half (Dermal Plating, Armor,
Internal Air Tank, Skillwires, Skilljack) are rating-scaled and so reachable only by importing a
legacy `.chum5` — WP41 widened import to all 87 rows while the picker stayed on WP31's flat 60. A
player-visible gap and an import-only one are not the same severity and the registry previously had
no way to say so. Rows predating WP77 were **not** retro-labelled: doing it right needs a
per-catalog reachability check this WP only ran over its own 10, and a wrong label is worse than
none.

**Correction carried into the registry: Smartlink's printed effect is +2 *Accuracy*, not +2 dice.**
WP77's own scoping entry said "+2 dice on ranged attacks." The book (p. 433, via p. 444/453) says
the smartgun system "increases the gun's Accuracy by 2" when you have a smartlink — a Limit, not a
dice pool. The legacy engine does apply `<smartlink>2` as a wireless-gated dice-pool modifier
(`Weapon.cs`), so the WP entry described the *code* accurately and the *book* inaccurately. Nothing
turns on it here — both readings are equally unmodeled — but the registry states both rather than
repeating the half that is wrong about SR5.

**A gap this WP documents and cannot close: none of these notes are shown to a player.** WP56 built
exactly the mechanism for it — `Quality.unmodeled_effect_note`, surfaced on the character sheet's
"Unmodeled real effects" disclosure via `chummer5.engine.derived.unmodeled_effect_notes`, which
*already walks cyberware and bioware* looking for that field. No augmentation catalog populates it,
so a player who buys Bone Lacing (Titanium) sees an empty section where a Low-Light Vision quality
would show a note. WP77 is documentation-only by its own scope and WP78's is the 5 computable rows,
so neither covers this. **Scoped as WP79** (Phase K, before WP42) rather than left as worklog prose.

## 2026-07-31 — Phase K, WP78: four of WP77's five policy-violating rows are fixed; `Reflex
Recorder` becomes WP80; two engine gaps this WP surfaced and deliberately did *not* close

**Four of the five are modeled, and WP77's Bucket A is nearly empty.** `Reaction Enhancers`,
`Wired Reflexes`, `Muscle Replacement` and `Voice Modulator` now classify `FLAT_BONUS` and grant
real `ATTRIBUTE`/`INITIATIVE_DICE`/`SKILL` Improvements, so the 2026-07-24 "model it in full or
exclude it" policy holds for them again. `chummer5.data.cyberware.classify_bonus`'s whitelist grew
by three shapes (`<specificattribute>`, `<initiativepass>`, `<specificskill>`); the 60-row flat
catalog's classification is byte-for-byte unchanged, because all four rows are rating-scaled and so
live only in WP37's wider 87-row catalog.

**`Reflex Recorder` is deferred to WP80 rather than stretched into this WP.** WP78's own entry asked
for this call to be made early and recorded either way. It is the only Bucket A row whose `<bonus>`
is a *player choice* — `<selectskill limittoattribute="BOD,AGI,REA,STR"><val>1</val></selectskill>`,
i.e. "+1 to one active skill linked to a physical attribute, chosen at purchase." Modeling it needs
a chosen skill persisted in `CharacterSave`, re-validated on load, imported from a legacy
`<extra>` field (`Barrett.chum5` stores `<extra>Longarms</extra>`) and picked in the browser — the
same four-layer increment WP55 needed for `SELECT_TEXT` qualities, and a strictly larger job than
the four fixed-bonus rows put together. It stays offered and inert in the meantime for exactly the
reason WP77 recorded: excluding it would remove shipped functionality and break a passing import
test on the way to fixing it properly. `tests/unit/test_augmentation_unmodeled_registry.py`'s
`WP78_SCOPE` is renamed `MODELED_BUT_UNCLASSIFIED` and now holds this one row.

**Gap 1, not closed: an attribute Improvement is capped at the *natural* maximum, not the augmented
one.** SR5 allows an augmented attribute to exceed its metatype maximum by up to +4 (legacy:
`CharacterAttrib.AttributeModifiers` clamps Σ attribute improvements to `MetatypeAugmentedMaximum -
MetatypeMaximum`, then `CalculatedTotalValue` clamps the total to `TotalAugmentedMaximum`). This
engine's `Character.attribute_value` caps `base + points + Σ improvements` at
`attribute_range.maximum` — the natural one — and `AttributeRange.augmented` is loaded but read
nowhere. So a character at REA 6 buying Reaction Enhancers 3 gets 6 here and 9 in SR5.

This is **pre-existing, not introduced by WP78**: WP27's `Improved Physical Attribute` adept power
has produced `ImprovementType.ATTRIBUTE` improvements since Phase I and hits the same ceiling. WP78
makes it reachable from a second direction, which is why it is being written down now. It is
deliberately out of this WP's scope because the fix is not a one-line cap change: `create_karma_
attribute_selection`'s "only one Mental or Physical attribute may sit at its natural maximum" rule
reads `attribute_value(code) >= attribute_range(code).maximum`, which silently becomes wrong the
moment `attribute_value` can exceed the natural maximum. Closing it properly means introducing a
natural-vs-augmented split across `Character`, `chummer5.engine.derived` and the character sheet —
scoped as **WP81**. None of the three fixtures WP78 checks against reaches the boundary (BLUE 3/6,
SCSi 3/6, Fuzzy 6/6 — the last sits exactly *on* it), so the oracle has nothing to say about it
either way.

**Gap 2, not closed: `precedence0` suppression vs. plain addition.** Legacy's `ValueOf` treats a
`precedence0` dedup group as `max(Σ unmarked improvements, highest precedence0 + Σ precedence-1)`;
this engine's `ImprovementIndex.resolve` computes `Σ unmarked + highest per unique_name`. The two
agree whenever every competing bonus carries the marker — which covers the case the rulebook
actually names (reaction enhancers vs. wired reflexes, both `precedence="0"`, confirmed against
`SCSi.chum5`'s REA total of 3). They diverge only when an *unmarked* bonus to the same target
coexists: in this project's scope, an adept with `Improved Physical Attribute` (REA) who also buys
one of these implants. Closing it means teaching `resolve()` a magic `"precedence0"` string, i.e.
pushing a legacy serialization detail into the engine primitive WP5/WP39 deliberately kept clean —
so it is recorded here instead, with the modeled half being the one the book states outright.

## 2026-07-31 — Phase K, WP80: WP77's Bucket A is empty; a `<selectskill>` bonus is a Rating bonus, not a pool one; the skill-side twin of WP81 becomes WP82

**The policy violation WP77 named is closed.** `Reflex Recorder` classifies `SELECT_SKILL` (a new
value on the shared `chummer5.data.cyberware.BonusSupport`, mirroring
`chummer5.data.qualities.BonusSupport.SELECT_TEXT`) and grants a real `ImprovementType.SKILL`
Improvement against the player's own pick, so no augmentation row is offered-and-inert any more.
`tests/unit/test_augmentation_unmodeled_registry.py`'s `MODELED_BUT_UNCLASSIFIED` is empty for the
first time since WP77 created it, and stays as an empty frozenset — a future `NOT_YET_SUPPORTED` row
has to be put in one bucket or the other, deliberately, to pass that file.

**The rating-vs-pool question WP78's worklog raised is settled for this row, by the book, and only
for this row.** p. 460: "The reflex recorder adds 1 to the *Rating* of a specific skill linked to a
Physical attribute." So this engine's established `ImprovementType.SKILL` route (which folds into
`skill_rating`) is correct, and WP80 needed no new dice-pool primitive. That does **not** generalize:
Voice Modulator's own printed wording (p. 452) is "Add the Rating of the modulator to your *dice
pool* for Impersonation skill tests," so the two really are different bonuses that happen to share
one XML shape (`<specificskill>` with no `<applytorating>`, which legacy reads uniformly as a pool
modifier). Whether the *other* skill bonuses this project ships — Voice Modulator (WP78), Enhanced
Articulation (WP45), every focus (WP47) and Mentor Spirit (WP48) slot, Voice Control (WP27) — need a
genuine pool modifier is still open, and still not one WP's job to answer for all of them.

**A gap this WP surfaced and did not close, scoped as WP82: `skill_rating` clamps to
`MAX_SKILL_RATING_CREATE` (6), which swallows an augmented bonus.** SR5's 6 is a cap on what you may
*buy* at character creation, not on what an implant may add on top — the same natural-vs-augmented
distinction WP81 exists to draw for attributes. Today a Reflex Recorder bought for a skill already at
6 costs 14,000¥ and 0.1 Essence and changes nothing. This is reachable from today's shipped UI, and
it is not specific to WP80: every skill Improvement in this project (Enhanced Articulation, foci,
Mentor Spirits, Voice Modulator, Voice Control) hits the same clamp. Scoped as **WP82**, not fixed
here — but worth recording that it is a *smaller* job than WP81's attribute equivalent, and the
difference is instructive: the two purchase-side validators (`create_skill_allocation`,
`create_karma_skill_selection`) already read purchased points directly rather than going through
`skill_rating`, so they are natural-only by construction and need no change. What WP82 has to decide
is the ceiling itself — p. 131's Skill Rating Table calls 6 "the maximum skill level for starting
player characters" and goes on to describe ratings 7-12, so 6 is explicitly a *starting* cap, but
what bounds an augmented skill rating instead is a question WP82 has to answer against the rulebook
and legacy's own `Skill.RatingMaximum`, not one this WP guessed at — and what the character sheet
shows for a skill sitting above 6.

**Two smaller corrections, both to WP80's own entry, both found by re-checking rather than
trusting it.** (1) `Reflex Recorder` carries **no** `<pairinclude>` in `bioware.xml` — the entry
asked whether a matched pair behaves differently the way Hydraulic Jacks does, and the answer is
that there is no pair rule at all, in the data or in print; the element the entry saw lives in
`Barrett.chum5`'s saved character node next to an empty `<pairbonus />`. (2) p. 460's "Reflex
recorder bioware is incompatible with skillwires cyberware" is real and deliberately unenforced:
this engine has no cross-catalog incompatibility mechanism, the catalog row carries no `<forbidden>`
node (so legacy doesn't enforce it either), and `Skillwires` grants nothing at all here (a WP77
registry row), so allowing both changes no derived number. Recorded in
`chummer5.data.bioware`'s docstring rather than in the "Unmodeled real effects" table, which is for
an offered aspect's own uncomputed *effects* — `Reflex Recorder`'s are now all computed, and adding
it there would launder the fix into an accepted gap.

**One backward-compatibility break, deliberate and narrow.** `CharacterSave.bioware_item_ids`
becomes `bioware_purchases` (WP41's `cyberware_purchases` precedent, same fallback shape), because a
bare id cannot carry a skill pick. A pre-WP80 save loads through the fallback exactly, *except* one
holding a `Reflex Recorder`: its pick was never persisted, so the save now fails to build with
"Reflex Recorder requires a chosen skill" instead of loading a character whose bonus is silently
dropped. Nothing is recoverable in that case — the pick was never written — and WP45-WP79 never
applied the bonus either, so the failure loses nothing but announces itself.

## 2026-08-01 — Phase K, WP81: the augmented attribute maximum lands; three formulas move to the
natural rating; the cyberlimb average is confirmed exempt from the `+4` clamp

**WP78's "Gap 1" is closed.** `Character.attribute_value` no longer clamps at the metatype
(natural) maximum. It is now the *augmented* total — natural rating plus Σ `ATTRIBUTE`
improvements, with the improvement sum clamped to the augmentation headroom
(`AttributeRange.augmented - AttributeRange.maximum`) and the result clamped to
`AttributeRange.augmented`. Both clamps mirror legacy `CharacterAttrib.AttributeModifiers` /
`CalculatedTotalValueCore` line for line, and both come out of `metatypes.xml`'s own `<bodaug>`/…
field (loaded since WP2, read nowhere until now) rather than a hardcoded `+ 4` — which is exactly
`maximum + 4` on all eight primary attributes of all five SR5-core metatypes, and exactly `maximum`
on EDG/MAG/RES, so Edge and Magic are un-augmentable by construction rather than by special case.
Core rulebook p. 94 is the rule; see `spec/rulebooks/learnings/phase-k.md`'s WP81 entry.

**A second method, not a flag or a tuple** (the shape question the WP entry left open).
`Character.natural_attribute_value(code)` is what the points actually bought;
`attribute_value(code)` keeps its name and becomes the augmented total. Chosen because the *default*
matters more than the symmetry: every one of the ~40 existing call sites that reads
`attribute_value` wants the augmented number (dice pools, Initiative, the Limits, the condition
monitors), and only three want the natural one. A flag or a tuple would have made every one of
those call sites re-state a choice it has no interest in, and would have made "forgot to pass the
flag" a silent wrong answer instead of an unwritten line. `attribute_augmented_maximum(code)` is a
third, trivial method so the ceiling has a name at its call sites.

**Three callers moved to the natural rating, and the rulebook names all three.** p. 95: "Attributes
boosted by cyberware or bioware do not affect the calculation for things such as points for
Knowledge skills or Contacts. However, other in-game mechanics such as Initiative and Inherent
Limits are modified by these augmentations." So `chummer5.engine.knowledge.free_knowledge_points`,
`chummer5.engine.resources.create_contact_selection` (plus the web layer's own mirror of the latter
in `chummer5.web.routes.contacts`) read `natural_attribute_value`; nothing in
`chummer5.engine.derived` changed. Both modules' docstrings already said this rule was real and
currently unobservable — no SR5 quality, power, cyberware or bioware row in any loaded catalog
grants a CHA/INT/LOG `ImprovementType.ATTRIBUTE` bonus — so this is a no-op for every buildable
character today, and simply no longer *depends* on that coincidence holding.

The fourth caller is the one the WP entry named as the reason this could not be a one-line cap
change: `create_karma_attribute_points`'s "only one Mental or Physical attribute may sit at its
natural maximum" rule (p. 99/100) now reads `natural_attribute_value`. Pre-WP81 the distinction was
invisible because the augmented value was itself clamped at the natural maximum; post-WP81, an
augmented REA of 8 on a natural 5 must not count as an attribute "at its natural maximum," and
without this change it silently would have.

**Display: `natural (augmented)`, from the book's own notation** (p. 95: "Record augmentation
ratings in parentheses next to the natural attribute rating (e.g. Strength 4 (6) …)"), on both the
character sheet and the attribute-allocation form, collapsing to a bare number when the two are
equal — which is every character with no attribute augmentation, so the common case is unchanged.
This is the WP35 "reduced from N by Essence loss" precedent applied in the other direction.

**A corpus finding worth recording: legacy's `+4` clamp does not bound a cyberlimb average.** The
new oracle test over the mundane corpus (`test_cross_corpus_augmented_totals_respect_the_augmented_
maximum`) finds 22 augmented attribute rows. All 22 respect the augmented maximum. **17 respect the
`+4` headroom and 5 do not — all AGI or STR, all on the three fixtures with cyberlimbs** (Bastion's
natural AGI 1 against a legacy total of 8). That is not a rules violation: legacy clamps Σ
improvements to `+4` inside `AttributeModifiers`, then `CalculatedTotalValueCore` *replaces* the
result with a per-limb weighted average for AGI/STR before the single remaining
`TotalAugmentedMaximum` clamp. This engine has no per-limb attribute system at all (already a WP38
row in the Project Overview's "Unmodeled real effects" table), so it cannot produce such a total;
the test excludes AGI/STR from that half of its check rather than asserting a rule that isn't
universal.

**Not closed, and not reopened: WP78's "Gap 2" (`precedence0` suppression vs. plain addition).**
Untouched by this WP — it lives in `ImprovementIndex.resolve`, one layer below where the clamp
sits, and nothing here made it more or less reachable.

## 2026-08-01 — Phase K, WP82: SR5's 6 caps purchases, not ratings; the clamp was costing real dice
pools; the skill display says "bonuses", not "augmented"

**The ceiling question the WP entry left open is answered by the book, and 6 is not the answer.**
p. 131's Skill Rating Table calls Rating 6 "the maximum skill level for starting player characters"
and then describes ratings 7 through 13; p. 129 defines the scale itself as "ranging from 1 … to 12
(or 13 with the Aptitude quality)". So `MAX_SKILL_RATING_CREATE` (6) is a *purchase* cap and stays
exactly where it already was — on `create_skill_allocation` and `create_karma_skill_selection`,
both of which read purchased points directly and needed no change — and `skill_rating` now clamps at
a new `MAX_SKILL_RATING` (12) instead. `natural_skill_rating` is the new public function for the
purchased rating, the skill-side twin of WP81's `natural_attribute_value`.

**Legacy clamps neither, and this project's 12 is a deliberate divergence.**
`Skill.RatingMaximum` (6 at creation) bounds `Base` and `Karma` individually; `TotalBaseRating` is
`LearnedRating + RatingModifiers(Attribute)` with no clamp at all, and `Rating` is
`Math.Max(CyberwareRating, TotalBaseRating)`, likewise unclamped. Bounding the augmented total at 12
is a guard-rail against a future catalog widening rather than a port or a live formula — nothing
today's catalogs can stack comes close, and it takes an artificial +20 improvement to see it in a
test. **Aptitude's 13 is not modeled**: legacy implements it as a per-skill `Improvement.Maximum`
folded into the *purchase* cap, this project has no such field, and `Aptitude` is
`NOT_YET_SUPPORTED` in the quality catalog anyway.

**The clamp was not merely hiding an unspent implant — it was costing dice pools.** WP80's finding
framed this as "a Reflex Recorder bought for a rating-6 skill changes nothing," which is true but
understates it. Lifting the clamp moved two synthetic fixtures: Renata's Gymnastics and Running
(Athletics group 5 + Natural Athlete +2) and Sabine's Counterspelling (Talent grant 5 + Mountain
mentor +2) each went from rating 6 to 7 — and each *pool* from a value that was a die short to the
correct one. Every skill bonus this project grants was being silently truncated whenever it landed
on a skill at or near 6, not just augmentation bonuses. Those fixtures' `expected` values and
citations encoded the bug and were corrected in this WP.

**The display mirrors WP81's notation but deliberately not its label.** The character sheet and the
skill picker now render `bought (with bonuses)` — `3 (4)` for a Longarms 3 with a Reflex Recorder,
`0 (2)` for a Catlike-boosted Sneaking nobody bought, `0 (4)` for a Talent-granted Spellcasting —
under a "Rating (with bonuses)" header. WP81's attribute equivalent says "augmented" because every
contributor there genuinely is an augmentation or an adept power. `ImprovementType.SKILL` is not
that clean: it currently carries the Magician/Adept Talent free-skill *grant* (a granted natural
rating that WP25 routed through the Improvement index purely for convenience), quality and Mentor
Spirit bonuses whose printed effect is a **dice-pool** modifier rather than a rating one, and
genuine rating augmentations (`Reflex Recorder`, p. 460). Calling that delta "augmentation" would
assert the classification WP80 explicitly recorded as still open and still nobody's WP; "bonuses" is
true of all three kinds. Recorded here because it is a judgment call, not an implementation detail —
whoever settles the rating-vs-pool question inherits this label along with it.

**Not in scope and not touched:** `chummer5.engine.knowledge`'s Knowledge/Language ratings, which
have their own `MAX_SKILL_RATING_CREATE` purchase cap and no Improvement producer at all, so the
same distinction has nothing to bite on there yet.

## 2026-08-01 — Phase K, WP42: what the widened picker offers and what it deliberately doesn't; a
`<requireparent>` bug WP34 shipped; and a now-unused flat catalog nobody has claimed retiring

**The picker's catalog is now WP37's full 87-row SR5 set, minus 11 rows, and each exclusion is a
different kind of decision.** WP34's picker offered `chummer5.data.cyberware.load_cyberware()`'s 60
flat-cost rows — a filter that was never about what a player should be able to buy, only about what
WP31 could price. Phase K's whole point was removing that limit, so `CYBERWARE_STANDALONE` starts
from all 87 and removes:

- **The 9 `<requireparent>` rows**, which are offered inside a parent instead. This is a **fix, not a
  narrowing**: `create_cyberware_tree_selection` rejects such an item bought standalone, and four of
  them (Ocular Drone, Cyber Holster, Cyberarm Slide, Large Smuggling Compartment) *were* in WP34's
  flat 60, so buying one from the shipped picker could only ever produce an error message. Nobody
  reported it because nobody had a reason to click them; it is fixed here rather than logged.
- **`Essence Hole` / `Essence Antihole`**, engine bookkeeping wearing an `SR5` source tag — see
  `spec/rulebooks/learnings/phase-k.md`'s WP42 entry for the negative rulebook finding and the
  legacy `Character.IncreaseEssenceHole` call site behind it. WP31's flatness filter excluded them
  by accident; stating the exclusion is what keeps that true.

Everything else WP34 offered is still offered, at the same field name (`cyberware_{id}`), which is
why every WP34 test passes unchanged.

**A plugin is a checkbox, not a quantity box — the one place this UI is narrower than the engine.**
`create_cyberware_tree_selection` accepts two of the same row in one parent outside the
`Cyberlimb Enhancement` category (where p. 456 forbids it and the engine enforces it). The form
offers at most one, because a quantity box would need a fourth index level (a rating per copy) to
stay coherent and nothing in the SR5 core set gains anything from a second copy in one limb. The
consequence, recorded rather than hidden: a legacy-imported character carrying two identical plugins
in one parent renders as one ticked box, so re-submitting the form drops the duplicate. No fixture in
the corpus does this.

**Display costs are resolved in the web layer, not read off the validated selection.** The picker has
to render the *rejected* state — an over-budget spend, an over-capacity limb — which is exactly when
no `CyberwareTreeSelection` exists to read numbers from. So `_cyberware_groups` resolves each node's
`CyberwareFormula` itself, the same independent-tally shape WP34's own subtotal column already had.
The one rule it restates rather than reads is dual costing (a plugin charges Capacity, a standalone
purchase charges Essence), which is one conditional; everything structural still comes from the
engine, and `cyberware_rating_bounds` was made public specifically so the form cannot offer a rating
`_build_purchase` would then reject.

**`chummer5.data.cyberware.load_cyberware()` is now unused by `src/` outside its own module's
classifier, and no WP has claimed retiring it.** WP41 kept it explicitly because "the UI picker still
lists its 60 flat rows"; that reason is gone. `chummer5.web.catalogs.CYBERWARE` survives only as the
WP31 flat view that several test modules and fixtures import. Retiring the loader and the `Cyberware`
dataclass would touch `tests/unit/test_cyberware.py`,
`tests/integration/test_cyberware_fixtures.py`, `tests/unit/test_augmentation_unmodeled_registry.py`
and `tests/unit/test_web_cyberware.py` — a mechanical but wide cleanup, deliberately not bundled into
a UI WP. Flagged here so it isn't rediscovered as a surprise. Note `chummer5.data.cyberware` itself
is *not* retirable regardless: it owns `classify_bonus`, `UNMODELED_EFFECT_NOTES`,
`CONDITION_DESCRIPTIONS` and both bonus dataclasses, all of which
`chummer5.data.cyberware_subsystems` imports.

**Reachability markers in the Project Overview's "Unmodeled real effects" registry are WP-scoped
facts, not permanent ones.** Widening the picker moved nine rows from "legacy import only" (WP77's
five) or "installable only into a cyberlimb" (WP38's four) to UI-reachable in one commit. The rows
were updated in the same commit and the registry preamble now says a UI-widening WP owes that
re-check; nothing about the underlying gaps changed.

## 2026-08-01 — Phases S/O, planning pass: a player-authored save reopens two closed phases, and exposes a stale WP43 deferral

A character built in the web UI and handed over as a `format_version: 1` save file
(`tests/fixtures/saves/razorboy.json`) was assessed for fixture value. It loads clean through
`POST /character/load` with no engine change. Three rulings came out of that assessment.

**A fixture-gap inventory goes stale in a way its own authors can't see.** Phase S §2 enumerated
seven gaps by reasoning about which *subsystems* lacked a whole-character fixture, and §4 declared
the phase complete at WP76 with two named, deliberate holes. The imported character walks through
**six** gaps, only one of which (Knowledge/Language) §2 had ever named — because the others are
gaps in what `SyntheticCharacter` can *express*, not in which subsystem is covered: every fixture
buys cyberware flat, at rating 1, with no plugins, because the dataclass has no way to say
otherwise, and every fixture therefore reports `initiative_dice: 1` and an unaugmented REA. The
lesson recorded here, not just the fix: an input-format limitation reads as full coverage from
inside the coverage table, and the cheapest way to find one is to feed the system an artifact
authored by somebody who wasn't looking at the table. Scoped as WP85-88 in
`phase-s-test-fixtures.md` §6.

**Karma-to-Nuyen conversion has been free since WP51, and the deferral that made it free is
correctly documented.** `Character.karma_spent` sums eight selections' `karma_cost` and omits
`resources_selection.karma_converted`, so the imported character takes ¥8,000 for 4 Karma and still
reports 19 Karma remaining. `spec/worklogs/WP43.md` (2026-07-21) states the reasoning plainly —
Phase O hadn't landed, so there was no running total to double-spend against — and
`engine/resources.py`'s module docstring still carries it as a known, deliberate gap. Nothing was
missed at the time; WP51 silently satisfied the trigger condition three weeks later and no
mechanism existed to notice. **Ruling: a deferral whose stated trigger is another WP landing should
name that WP in the *depending* phase file, not only in the deferring WP's own worklog**, so the
landing WP's author sees it. Filed as WP89 in `phase-o-karma-buying.md`, which reopens Phase O.

**A player-authored save is worth committing as data before it is worth converting into a fixture.**
The synthetic-fixture format is a Python literal, so importing this character means hand-translating
it — three WPs' worth, given the harness extensions it needs first. The save file is therefore
committed as-is, unreferenced, in the same commit as the WP entries, so WP85-88 can be executed cold
from the repo rather than from a chat transcript. It also has standalone value the synthetic format
can't provide: it is the first real on-disk artifact of this project's *own* save format, and WP85
turns it into the regression guard that format has never had.

## 2026-08-01 — Phase O, WP89: converted Karma is spent Karma; the check lives in the ledger, not in `create_resources_selection`

**Direction, confirmed rather than assumed.** Core rulebook p. 94 (Step Six: Spend Your Resources):
"While nuyen from this step cannot be converted to Karma, players can convert some of their Karma to
nuyen if they need a little more to spend. They may convert up to 10 Karma at a rate of 2,000 nuyen
per Karma point for gear, which means they can have up to 20,000 extra nuyen." Two independent
confirmations that the Karma is *consumed*, not duplicated: the very next step is titled "Spending
Your Left Over Karma" (p. 98) — left over from Step Six, which the conversion is part of — and the
legacy engine's own `Character.CalculateKarmaValue` adds the converted amount to a character's total
Karma spend under the `Checkbox_CreatePACKSKit_StartingNuyen` line item rather than ignoring it. So
`Character.karma_spent` gains `resources_selection.karma_converted` as a ninth term, and every Step
Seven spend — each deriving its `karma_budget` from `karma_remaining` — sees the smaller pool for
free.

**Ruling on where the double-spend check lives: the aggregate ledger, not a new `karma_budget`
parameter on `create_resources_selection`.** WP89's own entry left this open as "either is
defensible, but say which and why." The deciding difference from every Karma-spending sibling that
*does* take a `karma_budget`: this function is **re-called several times inside one build** — once up
front, again once cyberware/bioware are resolved, again once foci are (`io/save_format
.build_character`) — and Step Seven's spends are resolved in between two of those calls. One
unchanged player choice would therefore have to be validated against three different budgets, which
is exactly the double-counting trap WP51's "add this section's own committed cost back in" idiom
exists to avoid. Making the conversion a *term of* the ledger instead is checked once, in one place,
and needs no new parameter at any call site.

**The consequence accepted with that ruling, stated rather than glossed:** an over-conversion is not
rejected at its own commit point. It drives `karma_remaining` negative and surfaces as every
subsequent Step Seven spend being refused, which is the same "validity is re-derived at render time
rather than enforced at construction" shape `Project Overview.md`'s "Character as the single
aggregate" section already describes for stale priority selections. `karma_to_nuyen` still enforces
the flat 0-10 rulebook cap, since that one is a property of the conversion alone and needs no ledger.

**One existing expected value moved, and it moved toward legacy.** `Wesson.chum5` carries
`<nuyenbp>1</nuyenbp>`, so `test_wesson_imports_end_to_end`'s `karma_remaining` drops 10 → 9. That is
the intended direction, not a regression: legacy's own `<karma>2</karma>` for the same character is
likewise net of the conversion. No other fixture or test shifted — the five synthetic fixtures all
convert 0.

## 2026-08-01 — Phase P, WP90: the rigger research pass, and three corrections it forced

**Correction: the modification-slot system Phase P was scoped around is Rigger 5.0, not SR5 core.**
Phase P's 2026-07-21 intro justified excluding vehicle modifications partly by their shape —
"multiple separate per-category modification-slot pools (Cosmetic/Powertrain/Protection/Weapons,
each sized differently per vehicle)." Searched the full 489-page core rulebook: `powertrain`,
`modification slot` and `mod slot` appear **nowhere**. That system is `source=R5`; `vehicles.xml`
carries it (`<modcategories>`, `<powertrainmodslots>`, …) because Chummer supports every book. Of
that file's 197 `<mods>` rows, 170 are `R5` and exactly **2** are `SR5` — Rigger Interface
(1,000¥/Avail 4) and Manual Operation (+500¥/+1) — plus 7 weapon-mount rows. **The ruling stands;
its premise doesn't.** Recorded because a future reader would otherwise reasonably conclude the
exclusion bought more than it did.

**The one thing that exclusion actually costs, now known:** p. 265 — "Drones are designed for use by
riggers, and have been designed with the rigger interface built in. Nearly all vehicles need to have
the interface added as an after-factory option." `vehicles.xml` agrees exactly (all 13 SR5 drone rows
bundle a `Rigger Interface`; none of the 29 vehicle rows do). So under the no-mods ruling a bought
*drone* is riggable and a bought *vehicle* is not. **Ruling: this becomes a documented registry row
(Phase P's WP95), not a carve-out.** Reversing it for one 1,000¥ item would reopen the whole
modification system for the sake of a flag no in-play subsystem reads.

**Finding, not a decision: Rigger Command Consoles and cyberdecks have been purchasable since WP21,
with their entire stat block discarded.** `STARTER_GEAR_CATALOG` already offers 11 RCCs, 9
cyberdecks and 7 commlinks as flat-cost gear; `StarterGearItem` has no field for `<devicerating>`,
`<attack>`, `<sleaze>`, `<dataprocessing>`, `<firewall>`, `<programs>` or `<attributearray>`, so
none of it is loaded or shown. This materially reshapes Phase P: the RCC/cyberdeck half of the phase
is a *display and verification* job (WP94), not a new-subsystem one, and the phase's only genuinely
new purchase flow is vehicles/drones.

**Ruling on what a stock Matrix device needs: record and display, derive nothing.** Every
RCC/cyberdeck/commlink number is a printed constant of the item, and no Matrix rules exist to consume
it — the same "don't build machinery nothing downstream needs yet" call WP27 made for Adept Powers.
**The one exception, and the only computed number the phase adds:** vehicle Condition Monitor
`12 + ⌈Body/2⌉`, drone `6 + ⌈Body/2⌉` (p. 199) — the one printed-page value a player can't read off
the catalog table.

**Finding: `Control Rig` is offered by today's UI with 100% of its effect unmodeled and no registry
row.** It entered the picker with WP42's full 87-row catalog (the same commit that made five of
WP77's rows reachable) and carries no `unmodeled_effect_note`. Its entire printed payload (p. 266) is
an in-play, jumped-in limit bonus to a *device*; there is no character-level term at all. Under the
2026-07-24 policy that is fine to offer — but only *with* the row, which is missing. Filed as WP95.

**The Availability ≤ 12 backfill, sized rather than re-flagged.** Project Overview has carried "no WP
currently scheduled to backfill that" since 2026-07-21 without numbers. Concretely, today:
`build_starter_gear_catalog` enforces the cap **only** on WP66's Rating-priced half — flat-cost gear
and the whole cyberware catalog are unfiltered. That leaves 3 of 11 RCCs, 2 of 9 cyberdecks and 1 of
7 commlinks over the cap, plus **7 flat cyberware rows** (Bone Lacing (Titanium) 16R, Cranial Bomb
- Area Bomb 20F, Cranial Bomb - Microbomb 16F, Grenade Launcher 20F, Obvious Skull 16, Retinal
Duplication 16F, Synthetic Skull 16) and **17 rating-scaled cyberware rows** whose top ratings exceed
it (Wired Reflexes r3 = 20R, Control Rig r3 = 15R, Muscle Replacement / Reaction Enhancers r3 = 15R,
Dermal Plating r4 = 16R, …). **Ruling: WP94 closes only the three rigger-adjacent gear categories**;
the rest stays unscheduled, on the same reasoning as before (it retroactively changes what existing
saves and fixtures contain), but is now costed instead of gestured at.

**Fixture honesty standard for this phase, decided up front:** the corpus has exactly one
Priority-built character carrying an SR5 vehicle (`Wesson.chum5`'s Harley-Davidson Scorpion), and its
7 mods are all `R5`, so it can corroborate a *stat block* but never a *nuyen ledger*. Phase P
therefore validates against the printed tables plus that one stat block, with a synthetic
whole-character fixture (WP96) as the regression guard — which also closes Phase S §5's own recorded
"Known gap: no Rigger."

**2026-08-01 (WP91, Phase P) — `vehicles.xml` gets one printed stat wrong; the book wins, at the
policy layer.** WP91 transcribed all four printed vehicle/drone catalog tables (pp. 462–466) and
asserted every one of the 40 printed rows against the loader stat-by-stat — the exhaustive version
of the comparison WP90 had done spot-check-shaped. 39 rows agree exactly. The `Renault-Fiat Fokker
Tundra-9 (Amphibious Jet)` does not: p. 465 prints Handling **3**, `vehicles.xml` says **2**, with
every other stat in the row (and the row's own `<page>464</page>`) matching the printed line. There
is exactly one Tundra-9 row in the file across all sourcebooks, so this isn't Chummer preferring a
later book's reprint — it's a transcription slip.

**Ruling: the printed value wins, and the correction lives in the engine's catalog builder, not the
loader.** `chummer5.data.vehicles` stays what every other `chummer5.data.*` module is — a literal
XML→dataclass pass that reports what the file says — and `chummer5.engine.vehicles` applies the fix
alongside the Availability≤12 cap and the two unprintable-row exclusions, which is where this
project already puts policy (cf. `build_starter_gear_catalog`, WP42's
`_UNPURCHASABLE_CYBERWARE_NAMES`). `test_vehicles.KNOWN_XML_DIVERGENCES` pins the pair in both
directions so the exemption cannot go stale: if a data drop ever fixes the XML, the test fails
loudly rather than letting the catalog silently double-correct.

**Scope note:** this is a one-row exemption, deliberately not a general "reconcile every catalog
against the printed tables" programme. No other catalog in this project (gear, cyberware, bioware,
qualities) has ever been checked exhaustively against its printed table, and doing so is not
scheduled — WP91 only did it here because a 40-row table is small enough to transcribe in full and
Phase P had the extract on hand.

**2026-08-01 (WP93, Phase P) — a pre-existing shared-budget hole, found by widening it.** Threading
`vehicle_cost` through the five sibling sections that share the Step Six nuyen pool made a bug in
the *existing* wiring visible: `chummer5.web.routes.resources.submit_resources` and
`chummer5.web.routes.lifestyle.submit_lifestyle` each passed `foci_cost` into their **context**
builder (so the "no longer fits" warning was right) but not into the `create_resources_selection`
call that actually **accepts** the submission. A character with bonded foci could therefore commit
gear or a Lifestyle that overran the real remaining budget; the character sheet, which recomputes
from the committed selections, would then show a negative `nuyen_remaining`.

Fixed in the same lines that gained `vehicle_cost`, rather than deferred: the omission and its fix
are one token apart, and leaving a known "the warning is right but the validator isn't" split in
place while adding a sixth spender to the same code would have been actively misleading to the next
WP. No other section had the gap (`cyberware`/`foci` both pass every sibling cost to their accepting
call). `tests/unit/test_web_vehicles.py::test_gear_bought_after_a_vehicle_is_checked_against_the_
remaining_budget` pins the vehicle half; the foci half stays covered only by the existing foci tests,
which is the same coverage it had before.

**Standing shape this confirms:** each shared-budget section must pass *every* sibling cost to both
its context re-validation and its accepting `create_resources_selection` call. Six spenders now
(gear, Lifestyle, cyberware, bioware, foci, vehicles); a seventh would touch the same six places.

**2026-08-24 (WP94, Phase P) — the Availability cap arrives in the flat-cost gear catalog, scoped
to three categories on purpose.** WP66 was the first place the gear catalog enforced the 2026-07-21
Availability≤12 ruling at all, and it only ever covered the *Rating-priced* half of `gear.xml`.
Every flat-cost row stayed uncapped, which is how this project came to sell a starting character a
Triox UberMensch (18R) and a Fairlight Excalibur (18R). WP94 caps **Commlinks, Cyberdecks and
Rigger Command Consoles** — removing 6 rows (Fairlight Caliban 14; Shiawase Cyber-5 15R, Fairlight
Excalibur 18R; Lone Star Remote Commander 14R, MCT Drone Web 16R, Triox UberMensch 18R) and taking
the purchasable catalog from 379 items to 373.

**The scoping is the decision, not an oversight.** Phase P's own WP list says WP94 "closes only the
three rigger-adjacent gear categories," and the general backfill (every other flat-gear category —
Certified Credstick Ebony at 20, Seven-7 at 20F, the Missile/Rocket ammunition rows at 22F — plus
the 7 flat and 17 rating-scaled cyberware rows the 2026-08-01 entry above sized) stays unscheduled.
Two things make that a defensible stopping point rather than a half-measure: the mechanism now
exists and widening it is one frozenset (`chummer5.engine.resources
._AVAILABILITY_CAPPED_GEAR_CATEGORIES`), and the categories left uncapped are, unlike these three,
not ones any Phase P WP puts in front of a player. Project Overview's "no WP currently scheduled to
backfill that" sentence is updated to say *partially*, rather than being left to read as if nothing
had happened.

**2026-08-24 (WP94, Phase P) — load a stat, don't display one the book never printed.** `gear.xml`
gives every Rigger Command Console a `<programs>` value equal to its Device Rating. The core
rulebook prints no program-slot count for an RCC anywhere: p. 267's table has no such column,
p. 269's sidebar establishes only that RCCs run programs and can't duplicate a type, and the one
printed slot *formula* in that neighbourhood ("half its Device Rating, rounded up") is explicitly a
**drone** rule. Cyberdecks do print a Programs column, so theirs is shown.

**Ruling:** `StarterGearItem.programs` is loaded for both (the loader stays literal, as always), and
`chummer5.web.routes.resources.matrix_stat_block` renders it for cyberdecks only. This is the same
line WP27 drew for Adept Powers and WP90 §5 drew for Matrix stat blocks generally — record what the
data says, display what the book says, derive nothing — applied one notch finer, to a single field
of a row this project does display. Worth stating as a rule because the tempting alternative
(render every field that happens to be populated) would have quietly published a Chummer-authored
number as an SR5 stat.

**2026-08-24 (WP95, Phase P) — the `getattr` indirection makes new catalogs free, not new
selections.** `chummer5.engine.derived.unmodeled_effect_notes` was written (WP56) to be
"aspect-kind-agnostic by construction": every aspect is read through a plain
`getattr(item, "unmodeled_effect_note", None)`, so adding the field to a new catalog dataclass needs
no change there. WP79 confirmed that for cyberware, and its docstring says so.

WP95 found the other half. The function can only read selections it actually **walks**, and its walk
is a hand-written list of `Character` fields. `vehicle_selection` postdates the function (WP92) and
was never added, so a `Vehicle` note would have been silently invisible no matter how correctly the
catalog populated it. Recorded here, in that function's docstring, and in Project Overview's registry
preamble, because the trap is generic: **a WP that gives `Character` a new field holding catalog
objects owes this function a loop.** `Power`/`Focus`/`LifestyleTier`/`Spell` are walked already and
populate nothing, which is why the omission looked like coverage.

**2026-08-24 (WP95, Phase P) — `NOT_YET_SUPPORTED` is not the same set as "unmodeled", and an audit
that conflates them has a blind spot.** WP77 audited augmentation content for unmodeled effects by
sweeping the `NOT_YET_SUPPORTED` bucket — rows whose `<bonus>` node the loader declined to classify.
`Control Rig` was not in it. It carries **no `<bonus>` node at all**, so it classifies `NO_EFFECT`,
alongside the many rows that genuinely have no mechanical effect to model. It is nonetheless one of
the most consequential unmodeled rows in the catalog: UI-reachable since WP42, a full point of
Essence at rating 1, and an entire printed payload (p. 266) that lives on a *vehicle* rather than on
the character.

**Ruling:** the row gets a registry entry and a note like any other, and
`tests/unit/test_augmentation_unmodeled_registry.py` gains a third bucket
(`FULLY_UNMODELED_WITHOUT_A_BONUS_NODE`) rather than being bent to fit it into one of the two — the
existing buckets' invariant (`NOT_YET_SUPPORTED == REGISTERED | MODELED_BUT_UNCLASSIFIED`) is
correct and must keep holding. The standing lesson, recorded in that file and in
`chummer5.data.cyberware`'s docstring: `bonus_support` classifies **parseability**, not
modelledness. A future unmodeled-effects audit has to enumerate `NO_EFFECT` rows against the book
too, and `NO_EFFECT` is a large bucket, so that is a genuinely bigger job than WP77's was.

**2026-08-24 (WP95, Phase P) — gear unmodeled-effect notes are keyed by category, not by name.**
Every other catalog's notes dict (`qualities`, `cyberware`, `bioware`) is keyed by item name,
because each row's gap is its own. Gear is different: every RCC has the same gap (the Matrix does
not exist here), every autosoft has the same gap (drone tests do not exist here). Keying by name
would have meant ~30 identical strings in `chummer5.data.gear._UNMODELED_EFFECT_NOTES` with 30
independent chances to drift from the registry table. Keyed by category it is 4 strings, and the
invariant a test can pin is stronger: **all or none of a category carries a note.** Vehicles take
the same shape one step further — two module-level strings split on `is_drone`, because the only
per-row difference in the whole catalog is the one thing that flag already records (p. 265's rigger
interface ships in every drone and no vehicle).

**2026-08-24 (WP96, Phase P) — the synthetic fixture harness never resolved metatype-granted
qualities, and it took a new metric key to notice.** `chummer5.io.save_format.build_character` has
resolved a metatype's free qualities (Elf/Ork Low-Light Vision, Dwarf/Troll Thermographic Vision,
Dwarf Resistance to Pathogens/Toxins) and applied them as `ImprovementSource.METATYPE` since WP23.
`tests/fixtures/synthetic.build_synthetic()` — which otherwise follows that function's evaluation
order deliberately and closely (WP87's own note: "a fixture that disagrees with the save path is a
fixture that proves nothing") — simply never did. It was invisible for six fixtures and four
released phases because **all four of those qualities are `NO_EFFECT` or `NOT_YET_SUPPORTED`**, so
they contribute zero Improvements and move no number a fixture asserts.

What made it visible is that they are not *inert*: each one is a row in the character sheet's
"Unmodeled real effects" section, so WP96's new `unmodeled_notes:names` metric would have quietly
under-reported against what a player actually sees. Fixed in the harness (no existing fixture's
literals moved — the fix is provably number-neutral, which is exactly why it went unnoticed).

**The generalisable point, and it is not about metatype qualities.** A harness that mirrors a
production code path only stays a mirror for the assertions someone has thought to write. Six
fixtures asserting dice pools and budgets could not have caught a divergence that affects neither.
The next such gap will be found the same way — by a new metric key reading something the harness
never populated — so a WP adding one should check what populates it in `build_character` before
assuming the harness already does.

**2026-09-24 (WP97, Phase W) — WP64's `<details>` store was half accordion, half not; only the
accordion half was deleted.** Phase W's Finding 2 says the ~70-line script in `base.html` existed
"solely" to make the stacked sections behave one-at-a-time, and WP97's entry says to delete it, not
port it. Reading it showed two jobs: (a) section-level exclusivity, which is accordion machinery and
went, and (b) remembering a *sub-category* `<details>`'s manual open/closed state (skill
categories, gear groups, cyberware slots, keyed on `data-details-key`) across an htmx swap. (b) is
the fix for a Phase U bug report — a collapsed skill category snapping open whenever any rating in
that step changed — and it has nothing to do with the accordion: a step's own fragment still swaps
itself on every change under the shell. Deleting it would have reintroduced that bug. It survives
as a ~20-line keyed store, now in `<head>` so a history-restore body swap cannot re-run it and
stack a second set of listeners, and now also survives a *page* swap (which is the WP's own
"window-level stores must survive a page swap" trap, applied to the store the trap did not list).

**2026-09-24 (WP97, Phase W) — the step nav re-fetches itself on a response header, instead of every
route re-rendering it.** A priorities change can make any step stale (WP19), and a player fixing a
step should see its ⚠ clear, so the nav has to refresh after every mutation. The two options were
an out-of-band nav in every step `POST`'s response (fifteen routes, each needing `chargen_context`
just to render the nav) or one `http` middleware adding `HX-Trigger: chargen-changed` to every
successful `POST`, with the nav doing `hx-get="/ui/nav" hx-trigger="chargen-changed from:body"`.
The second costs one extra `GET` per change and touches no step route. **WP99 should reuse the
event** for the resource panel rather than implement its entry's "out-of-band swap from every
step's `POST`" as written — the wording predates this and would re-do per route what the middleware
already does once. Page `GET`s still carry the nav out of band, because a nav click is not a
mutation but does move the current-step marker.

**2026-09-24 (WP97, Phase W) — found, not fixed: every step form's submit button does a native GET.**
Since WP65 at the latest, thirteen step forms carry an `hx-trigger` (`"change, input[...] delay:400ms"`, or just
`"change"` on Spells and Powers), which *replaces*
htmx's default `submit` trigger rather than adding to it. So each "Update skills"/"Update gear"/…
button (and Enter in a text field) is a plain HTML form submission — method GET, action the current
URL. Before WP97 that silently reloaded `/`; now it loads `/ui/page/<slug>?<every field>`, which
renders the same page (the query is ignored) but leaves the whole form in the address bar. Nothing
is lost that the `change` trigger had not already posted, which is why it went unnoticed, but the
buttons have never done what their labels say. The fix is adding `submit` to those thirteen
`hx-trigger` lists; it is a behaviour change to every step fragment, so it was left out of a WP whose
acceptance is "no step's contents change" — it belongs in its own small WP (or in WP98 if that WP is
open to it).

**2026-09-24 (WP98, Phase W) — the composite pages' intra-page pattern: server-rendered sub-tabs
over a page that still renders every fragment.** Phase W left this as the one open design call
(Skills, Magic, and Equipment each mount 2–5 of the old sections), to be made once and applied to all
three. The options were retained `<details>` groups — what WP97 already shipped as a placeholder,
every panel stacked and open — or sub-tabs. Tabs won, and the three constraints below settled *how*
they work:

1. **Every fragment has to stay in the page.** About 38 existing test requests `GET` a composite
   page and assert on one of its fragments. WP98's acceptance is that those assertions stay
   unchanged, and that each page renders all of its fragments. So a tab cannot be "the server renders
   only this section". Every section's fragment is rendered, and all but the current one get the
   `hidden` attribute on a `<section class="subpage">` wrapper owned by `_page.html`. The fragments
   themselves are untouched.
2. **A tab switch has to be a fresh render.** No step route re-renders a sibling fragment. Confirming
   Magician on the Talent tab swaps only `#talent-selection`, so the Spells fragment stays in the DOM
   with the empty output it rendered for a Mundane character. The same is true in the pre-WP97
   accordion, where Spells stayed empty until a full reload. A client-side tab toggle would
   uncover that stale fragment. A tab link that re-renders the page cannot. So a tab is WP97's nav
   mechanism one level down: `GET /ui/page/{slug}/{tab}` (htmx into `#page`, pushed to history,
   full shell when requested directly). It needs no JavaScript, and the cost is the same
   `chargen_context` a nav click already pays.
3. **The strip has to follow changes made on other tabs.** It re-fetches itself from
   `GET /ui/tabs/{slug}` on the same `chargen-changed` event as the nav (2026-09-24, WP97). That is
   how Spells un-disables the moment a Magician Talent is confirmed, and how a fixed section's ⚠
   clears.

**Availability is data, not a template guess.** A section's tab is disabled (a `<span>` with its
reason, the same form as the nav's Resonance/Bio) exactly when its fragment's own top-level
`{% if %}` renders nothing. The predicates on `PageSection.available` mirror those guards by hand,
and `test_magic_tab_availability_agrees_with_each_fragments_own_guard` pins the two together across
no-character/Mundane/Magician/Adept. Magic's designed empty state is the Talent tab, four
disabled tabs, and one `locked_note` line saying what opens them.

**Each page remembers its tab** (`ChargenSession.page_tabs`). A nav click reopens the tab the player
left, falling back to the first available tab if a Talent change took it away. An *explicit* tab URL
to an unavailable section shows that section's reason as an empty state rather than silently
showing a different tab at that URL.

**Deferred to WP99, deliberately: Equipment's shared nuyen line.** WP98's entry suggests one page-
level budget line, because gear, lifestyle, and vehicles all spend one pool. A line in `#page` would
go stale on every fragment `POST`, exactly as the nav would have without its self-refresh. Making it
refresh would rebuild WP99's resource panel inside one page. The panel will show the global nuyen
figure from every page, so a page-level copy would be redundant. The per-fragment "remaining" lines
stay as they are.

**2026-09-24 (WP99, Phase W) — the resource panel sits *above* the per-step "remaining" lines, and
nuyen gained a character-level total.** The WP99 entry asked for a deliberate decision on whether the
sidebar panel replaces the ten per-step remaining lines. It does not. The panel shows the global
pools. The per-step lines still answer "how much of this budget is left for what I'm doing here",
which the panel does not. For example, the Skills page's own Karma line is the Karma available to
*that* step's Karma spend, net of what that step already spent.

Two sourcing rules keep the panel from becoming a second accounting path:

- **Karma is `Character.karma_remaining`, verbatim.**
- **Nuyen needed one new engine term, `Character.nuyen_spent`,** which sums gear, lifestyle,
  cyberware, bioware, foci, and vehicles, as `karma_spent`'s counterpart. Until now the only way to
  that total was to thread the six costs through context-builder arguments. `chargen_context` does
  that six times over, and no one place summed them. The pool's size stays with
  `available_nuyen(letter, …)`, because the Resources letter lives on the session, not on
  `Character`.

The point pools (attribute, special, skill, skill-group, knowledge, free spells, Power Points) are
read off `chargen_context` by keys unique to one step context. They are the exact numbers each step
prints. The generic keys (`nuyen_remaining`, `free_points`, …) are merged over by several step
contexts, the same clobbering WP60 fixed for Karma. That is also why Contacts' free-point pool is not
in the panel yet: it is only exposed under the generic `free_points`.

**The WP99 entry's "out-of-band swap from every step's `POST`" was not built.** Per WP97's entry
above, the panel re-fetches itself on `chargen-changed`, the same as the nav and WP98's tab strip.
Its acceptance test asserts that event wiring instead of an OOB swap. After every change the browser
now makes three small `GET`s (nav, panel, and, on a composite page, tabs). Each measured about 3 ms
locally, which is not worth merging them into one endpoint while the app is local and single-user.

**2026-09-24 (WP100, Phase W) — `app.css` holds no token values; each theme is a complete token
set.** WP100's entry asked for per-theme stylesheets that "redefine only tokens". The obvious reading
keeps today's values as defaults in `app.css` and lets a theme override some of them. I did it the
stricter way: `app.css` defines no custom property at all, and every theme under `static/themes/`
defines every token `app.css` reads, for both colour schemes. The shipped themes are Classic (the
WP97-99 look) and Sketch (the hand-drawn layout).

The reason is what a test can then prove. With defaults in `app.css`, "Classic" would be an empty
file, and a typo in a theme's token name would silently leave the default showing. With complete
sets, `tests/unit/test_web_themes.py` checks three things mechanically:

- every `var(--x)` in `app.css` is declared by every theme;
- a theme's dark block only redefines tokens its light block already has;
- a theme file parses as exactly `:root {…}` plus one `prefers-color-scheme: dark` `:root {…}`,
  containing custom properties only. This last check is the entry's acceptance.

The cost is that a new token has to be added to every theme. With two themes that is cheap, and the
failing test names the missing token.

**Display preferences are not chargen changes.** Theme selection is `POST /ui/prefs/theme`, and
`chummer5.web.prefs` holds the theme list (the module exists so `session.py` can import the defaults
without a cycle through the shell). The WP97 `chargen-changed` middleware now skips `/ui/prefs/`.
Otherwise every preference change would make the nav, the panel, and the tabs re-fetch themselves
for nothing. The theme applies in place: the response is the new `<link id="theme-stylesheet">`,
swapped out of band into `<head>`. I checked in Chromium that htmx 2 swaps a `<head>` element by id
and that the link keeps its position ahead of `app.css`. **For WP101:** a language change cannot
work that way, because every string on the page changes. Its route should sit under the same
prefix and answer with `HX-Refresh: true`.

**2026-09-24 (WP101, Phase W) — the i18n mechanism: a dict-backed `_()` over XML catalogs in the
legacy schema, not Babel/gettext.** This was the one open call in Phase W. I chose the phase file's
recommended option, for these reasons:

- **Zero new dependencies.** gettext would add Babel as a dev dependency plus a `.pot`/`.po`/`.mo`
  extract-and-compile step. Every catalog here is read at runtime straight from XML.
- **One mechanism for chrome and game data.** WP103's `legacy/Chummer/lang/<locale>_data.xml` files
  are XML keyed by English name, and no gettext tooling reads them. The same loader shape
  (`chummer5.data.lang`) will serve both.
- **Inherited translations.** `legacy/Chummer/lang/<locale>.xml` carries 2,767 English keys and
  2,100-2,600 translated ones per locale (de-de, fr-fr, ja-jp, pt-br, zh-cn). A catalog in the same
  schema layers over them, so any reused legacy key arrives translated.

The trade is translator tooling: no PO editors or translation-memory platforms. That cost is
accepted, because the translators this project could realistically draw on are the legacy app's,
and they already work in this format.

**Shape.** A locale's catalog is the legacy file, normalised, with `src/chummer5/lang/<locale>.xml`
overlaid on it. Normalising strips WinForms mnemonics: `&File` → `File`, `&&` → `&`. The overlay
holds only `Web_`-prefixed keys, so a key's layer is visible from its name and the two layers can
never collide; a test enforces both. Lookup falls back from the session locale to English, and
then to a visible `⟦Key⟧` marker plus a logged warning, never blank. Project keys use named
placeholders, so translators can reorder them; legacy keys keep positional `{0}`, and `_()`
passes both through `str.format`. Catalog text is plain text and is HTML-escaped like any template
value. The full key rules are in `src/chummer5/lang/README.md`.

**Key vocabulary finding.** Legacy keys are WinForms control captions, so they fit this UI in
patches, not wholesale. `String_Karma`, `String_Qualities`, `String_Contacts`, `String_Export`,
`Tab_Skills`, and `Tab_Gear` match exactly. `Tab_Lifestyle` ("Lifestyles"), `Tab_Vehicles`
("Vehicles & Drones"), and `Tab_Magician` ("Spells & Spirits") are near misses. The rule is to reuse
only on an exact match of both text and role, and to add a `Web_` key otherwise. I never edited a
legacy text to make it fit. WP102 should expect most keys to be new.

**Only English is offered.** The loader reads the five legacy locales today, but WP102 has not
converted the pages, so any other locale would render almost entirely in its English fallback. A
locale is added to `prefs.LOCALES` when its coverage justifies it. The picker ships as a deliverable
anyway, with one entry. A language change answers `HX-Refresh`, because every string changes; the
theme's out-of-band `<link>` swap does not apply.

**2026-09-24 (WP102, Phase W) — where the chrome-string pass drew its line, and the mechanisms it
needed.** All 22 templates and every web-layer Python module now route user-facing text through
catalog keys: 327 `Web_*` keys plus reused legacy keys. Two tests enforce this from now on.
`test_no_template_has_bare_user_facing_text` covers text nodes plus `title`/`placeholder`/
`aria-label`/`alt`/button `value`. `test_no_web_python_module_builds_bare_user_facing_text` is an
AST scan of `web/*.py` and `web/routes/*.py` with a five-entry identifier allowlist. The decisions
worth knowing:

- **Context builders return `Message`, not strings.** A step's context builder takes a
  `Character`, not a session, so it cannot know the locale. Threading a locale through a dozen
  signatures was the alternative. Instead, the builder returns `Message.of(key, **params)`, or a
  `MessageJoin` for a list. The template renders it with `| tr`, in the request's locale. `| tr`
  passes a plain `str` through, which is how engine errors still display.
- **Engine exception texts stay English.** "No longer fits since…: {error}" is keyed; the
  `{error}` is a `ValueError` message from `chummer5.engine`. Translating the engine's messages
  means giving the rules layer message keys. That is a real project of its own, and it is out of
  this WP's scope (web layer only). The same applies to English authored in `chummer5.data`
  modules: `CONDITION_DESCRIPTIONS` and the unmodeled-effect notes, which the sheet shows verbatim.
  Neither is chrome, and neither is XML game data for WP103. They are a third category with no WP
  yet.
- **Inline markup survives through `Markup` arguments.** The template-side `_()` escapes the
  catalog text and then `Markup.format`s the arguments. A `<strong>` word the template builds is
  kept; everything else is escaped. So a sentence with emphasis stays one key and the catalog never
  holds a tag.
- **Plurals use `_n()` over `_One`/`_Other` keys**, which is enough for every locale the legacy
  catalogs ship; the limits are documented at `plural_key`. **Money uses one formatter** (`| nuyen`
  → `Web_Format_Nuyen`), so no template contains a `¥`. Digit grouping is *identified, not solved*:
  amounts stay ungrouped, as before. The one grouped literal (`2,000¥`) now reads `2000¥`, like
  every other amount, and comes from the engine's `KARMA_TO_NUYEN_RATE` rather than a hand-typed
  copy.
- **Legacy reuse changed a few English labels on purpose.** The sidebar panel and tab labels
  adopted legacy's Title Case ("Attribute Points", "Adept Powers", "Vehicles & Drones", "Free
  Spells") so they could reuse `String_*`/`Tab_*` keys with real translations. Attribute codes
  render through `String_Attribute<CODE>Short` (German `KON`, `GES`, …). Two raw codenames became
  words: the build method, where `SumtoTen` now reads "Sum-to-Ten", and the magic type.

**2026-09-24 (WP103, Phase W) — game-data names translate at display time, looked up by GUID
*and* name, because the legacy translation files reuse GUIDs.** `chummer5.data.lang.load_data_terms`
indexes `legacy/Chummer/lang/<locale>_data.xml`. Templates apply it only where a name is shown:
`{{ obj | dterm("file.xml") }}`, plus `{{ mentor | dtext("advantage") }}` for long texts.
Identity is never translated: form values, field names, ids, `data-details-key`, and saves stay
English/GUID. A test proves a German session's save is byte-for-byte the English one's.

**The GUID finding.** The phase file assumed lookup "keyed by the English name". Our catalogs
carry the legacy GUIDs, so lookup by id looked strictly better, until the German file turned out
to reuse ids. `adf31a50…` is the Pistols skill ("Pistolen") *and* an alternate "Handguns"
("Handfeuerwaffen"). de-de has 26 such ids, and fr/ja/pt/zh 4-5 each. A last-wins id index
silently showed "Handfeuerwaffen" for SR5's Pistols, and my own first test expectation encoded the
wrong answer. The index is now `{GUID: {English name: translation}}`. A lookup takes the entry
whose English matches the object's name, takes an id's sole entry when there is only one, and
otherwise falls back to the name within the given files. Names are also ambiguous *within* a file:
skills.xml's specialisations reuse skill names, so an item's own `<name>` outranks an
attribute-translated text with the same English.

**Display-name consequences.** The skill and gear filter scripts match the player's typing against
`data-*-name`, which now carries the *display* name, because a German player types German.
Sorting is still by English name, so a German list is not alphabetical; that is identified, not
solved. English authored in `chummer5.data` modules (knowledge-category examples,
`CONDITION_DESCRIPTIONS`, unmodeled-effect notes) has no legacy translation and stays English, as
the WP102 entry records. **No locale besides English is offered yet.** The machinery covers all
five legacy locales, but German chrome would still be mostly English fallback: 327 `Web_*` keys
exist only in English. Offering one is now a translation job plus one `prefs.LOCALES` line, not
engineering.

**2026-09-26 (WP104, Phase W) — the Shadowrun theme is the default, and the theme contract grew
rather than bent.** A new session now opens in the SR5-rulebook look, and Classic moves to second
in the picker. The theme needed shapes as well as colours: chamfered corners and a banner
heading. These went in as tokens (`--panel-clip`, `--page-heading-clip`, which hold `clip-path`
values), not as a theme-specific selector. So `app.css` stays the only structural CSS, and the
WP100 parser test still covers all three themes unchanged. One knowing stretch: the SR5 panel
colour tokens (`--section-bg-a`/`-b`) are full `background` values, a gradient layer that draws
the diagonal rule along the cut corner, and then the fill. That is legal because `app.css` only
ever uses those tokens in `background`. If a future rule reads them as a plain colour (`color:`,
`border-color:`), the SR5 theme breaks there, so split a `--section-fill` token first.

**2026-09-26 (WP105, Phase W) — table-row banding is a token pair.** The SR4 theme's alternating
green rows added `.page tbody tr:nth-child(odd|even) { background: var(--table-row-bg-a|b) }` to
`app.css`. The other themes set both tokens to `transparent`, so they are visually unchanged. The
known imperfection: striping counts filtered-out (`hidden`) rows. Fixing that would take either
JavaScript or selectors that know about the filters, and neither belongs in a theme mechanism.

**2026-09-26 (WP106, Phase W) — font family names are identifiers, not prose.** The WP102 guard
(`test_no_web_python_module_builds_bare_user_facing_text`) flags multi-word literals in web-layer
Python, and it flagged "Bebas Neue", "Source Sans 3" and the other suggested fonts. They are proper
names that the browser matches against installed fonts, and translating one would break it. So the
guard skips the arguments of `FontSuggestion(...)` calls, the same way it already skips
`HTTPException(detail=...)`. That is narrower than adding ten names to `ALLOWED_PYTHON_STRINGS`,
and it needs no upkeep when a theme's suggestions change. The role labels stay catalog keys
(`Web_Fonts_Role_*`), so translatable text still cannot hide in that call.

## 2026-09-26 — Phase X, planning pass: a second full-chapter gap survey, and the user's rulings on it

A gap survey walked every step of `spec/rulebooks/character_creation_chapter.md` against the code as
of WP106, the first since the 2026-07-21 survey that produced Phases L-P. It checked live catalogs and
validators, not documents. The user then ruled per step. The full ruling table and the resulting
WP107-135 are in `spec/plan/phase-x-rulebook-completeness.md`; what matters beyond that phase:

- **Rulings that stand past this phase.** Street-level/Prime Runner play is left alone for now.
  Mystic Adept, Technomancer, Resonance and Living Persona stay out. Vehicle modifications stay out.
  The per-contact 7-Karma cap stays unenforced (WP9's Yeti reason). Already-offered flat gear and
  cyberware over Availability 12 **stay offered by explicit ruling**. Only rating-scaled items get
  capped (WP126). This retires the Project Overview's "flagged, not scheduled" Availability-backfill
  note rather than scheduling it.
- **Two rulings are display caps, not rules the engine enforces.** The 5,000¥ nuyen carryover and the
  7-Karma carryover are shown capped on the character sheet (WP133), and the Lifestyle starting-nuyen
  roll is a notice, because it happens when play begins.
- **The phase-wide enforcement convention.** Per-action limits are rejected by `create_*` validators;
  whole-character "finish" rules are reported by a validation panel that never blocks saving (WP135).
  See the phase file's intro.
- **Every core quality is to be offered**, including ones whose whole effect is in play. The user was
  explicit that this project shouldn't only offer qualities that move a sheet number. This extends
  the 2026-07-24 registry policy from "permitted" to "the plan".
- **Three rulebook findings the survey itself got wrong or missed.** Used-grade implants are legal at
  creation (p. 451). The checklist's "dwarf/troll gear-cost modifiers" are the Lifestyle surcharge
  restated (p. 420), not a separate mechanic. Adepts have been offered magic-group skills since WP61,
  against p. 69. Details are in the phase file's Findings 1, 2 and 4.

## 2026-09-26 — WP107: the first save-format migration, and how legacy stores quality levels

- **`FORMAT_VERSION` is 2.** WP107 replaced `quality_ids` + `quality_text` with `quality_picks`.
  Every earlier shape change was additive and kept version 1. This one can't: an id list can't say
  "Focused Concentration 3" or "two Addictions". `from_json` reads versions 1 and 2
  (`READABLE_FORMAT_VERSIONS`), and `_quality_picks_from_dict` migrates version 1 exactly. Only
  version 2 is written. A later break should add its own per-field migration the same way, not a
  generic upgrade pass.
- **A `.chum5` quality has no rating field.** Legacy writes one `<quality>` node per level. Import
  therefore folds repeats of a rated quality into a rating, and the phase plan's "map `<rating>`"
  wording was wrong.
- **`<includeinlimit>` is parsed.** It is how the data says Indomitable's three rows share one
  3-level cap (p. 75). Any future catalog loader that offers rated items should check whether its
  file uses the same block.

## 2026-09-26 — WP111: Astral Initiative dice follow the 2D6 printing, pending a ruling

The core rulebook prints Astral Initiative's dice two ways. The Step Eight table and p. 159's chart
say 2D6. p. 314's Astral Attributes Table says "+2D6 (3D6 total)". The book's own sample characters
split between the two, and legacy defaults to 3. WP111 follows 2D6, the reading the Phase X plan
states, and puts it in one constant (`chummer5.engine.derived.ASTRAL_INITIATIVE_DICE`). **Open for
the user to rule on**: if 3D6 is preferred (legacy's choice, and possibly an erratum), changing that
constant and one test is the whole change.

## 2026-09-26 — Ruling: Astral Initiative is INT x 2 + 3D6

The user resolved WP111's open question: Astral Initiative uses **3D6**, following p. 314's Astral
Attributes Table ("+2D6 (3D6 total)") and legacy Chummer's default, over the 2D6 printed in the
Step Eight table and p. 159's chart. `chummer5.engine.derived.ASTRAL_INITIATIVE_DICE` is now 3.

## 2026-09-26 — WP115: prerequisites that live in later steps, and three rulebook-wins calls

- **Two quality prerequisites depend on steps resolved after qualities.** Loss of Confidence needs
  its skill at rating 4+ (p. 82). Scorched needs a BTL Addiction or being a decker (p. 83).
  `create_quality_selection` takes an optional `LaterStepFacts` (skill ratings, cyberdeck
  ownership). The web route passes them at pick time and on every re-render, so the WP19 "no
  longer fits" warning catches a later skill edit. A save or a legacy import resolves qualities
  before skills and gear, so it passes none and these two checks are skipped there. This matches
  the phase's "reported, never enforced" rule for imports. WP135's validator should re-run them.
  Consequence for the player: a skill must be bought before Loss of Confidence can be picked
  (the pick is rejected with the skill's current rating).
- **"Decker" means owning a cyberdeck**, as gear or as the implanted Cyberdeck. **A BTL Addiction**
  is an Addiction pick whose free text names BTLs ("BTL", "better-than-life"). The second half of
  the BTL branch, "possess the gear necessary to use BTLs", is not checked: the book names no
  specific item, and BTL chips themselves are out of the offered catalog.
- **Rulebook wins, three times.** (1) Addiction (Severe) gets −2 dice on Social Active skills. p. 78
  prints it, and the data has only Burnout's −3. (2) Weak Immune System is forbidden to Dwarfs. p. 87
  says it "cannot be combined with [...] Resistance to Pathogens/Toxins", and that is exactly the
  name of the Dwarf's racial row. The data's own forbidden list leaves the racial row out. (3)
  Scorched's pick is one of the five rows of p. 83's side-effects table, not the data's free text.
- **Two Burnout Addictions stack their −3.** The book is silent. Legacy stacks. A dedup group would
  keep the *highest* value, which for a penalty is the wrong one.
- **Legacy import now reads a choice from `<extra>`** for every choice-bearing quality (Exceptional
  Attribute, Codeslinger, Home Ground, Spirit Affinity, Spirit Bane, Scorched, Loss of Confidence).
  Before this, an imported choice quality reached `create_quality_selection` with no choice and
  would have raised. No curated fixture hit that path. An `<extra>` that doesn't resolve to an
  offered option now drops the quality, reported like any other.

## 2026-09-26 — WP117: how the purchase-rule qualities read, and the skill-purchase rules object

- **Uneducated doubles Karma, not priority points.** p. 87 says "the Karma cost", and the data has
  only Karma multipliers. The phase plan's "the same double cost" as Uncouth was loose. Uncouth's
  p. 85 wording says "the cost", and the data doubles both.
- **Uncouth makes unknown Social skills unaware, rulebook wins.** The data blocks defaulting only
  for Uneducated's categories. p. 85 says Uncouth characters are "unaware" in Social skills below
  rating 1.
- **Incompetent bans the group's member skills too, not just the group.** Otherwise "may not
  possess that skill group" is sidestepped one skill at a time.
- **`SkillPurchaseRules`** (`chummer5.engine.skills`) carries everything qualities change about
  buying skills: Aptitude's cap, cost percentages, and banned groups. `create_skill_allocation`
  takes it instead of a `Character`, as it did WP116's `maximum_bonus` map, which it replaces.
  `skill_purchase_rules(character)` builds it. A new quality that changes skill purchases should
  add a field here rather than a new parameter.
- **Sensitive System's ×2 is applied to each cyberware node's stored Essence cost.** Taking or
  dropping the quality re-costs a committed tree from the qualities page. If the doubled cost no
  longer fits the Essence floor, the tree is left alone and the cyberware page reports it stale.
  WP127's grade multipliers should compose with `essence_multiplier`, not replace it.
- **The pickers still list what a quality bans** (a Social group for an Uncouth character,
  Incompetent's group). Submitting one is rejected with the reason. Hiding the rows is a possible
  later UI improvement; it's not needed for correctness.

## 2026-09-26 — WP118: skill bans are one mechanism, and the pickers hide banned rows

- **`SkillPurchaseRules.banned_groups` / `banned_skills`** (group or skill → reason) replace WP117's
  `disabled_groups`. Incompetent's group, an Adept's Sorcery/Conjuring/Enchanting, and an Adept's
  Assensing (until the Astral Perception power's `SKILL_UNLOCKED`) all go through them. The engine
  rejects a purchase by points or Karma. That was the Finding 4 bug: WP61 had read p. 69 backwards.
- **The skill pickers now hide whatever the rules ban** (`offered_skills` / `offered_skill_groups`).
  This supersedes WP117's "the pickers still list what a quality bans". A committed spend that a
  later change made illegal is still flagged by the skills page's WP19 warning. Resubmitting the
  page drops it, because the form only reads rows it shows.
- **The save loader validates the skill spend after the Talent and powers**, not before. Nothing in
  between read the allocation, and the Adept rules need both.
- **An Adept's Talent grant may still name Assensing.** Rejecting it at the Talent step would fire
  before powers exist. WP135's whole-character check is to report it (added to that WP's check list).

## 2026-09-26 — WP119: power instances, and WP27's misreading of `<limit>`

- **`<limit>` counts instances; `<maxlevels>` and the Magic rating cap levels** (p. 308). WP27 used
  `<limit>` as the level cap, so every power with `<limit>1` (Enhanced Perception, Mystic Armor, ...)
  was stuck at level 1. `power_max_rating` now follows the book. A power that names nothing is bought
  once, whatever its `<limit>` (Voice Control's is 20).
- **`PowerPick.target` replaces `selected_attribute`.** A repeatable power is bought once per target.
  The save format writes `target` and still reads `selected_attribute`, so `FORMAT_VERSION` is
  unchanged, as with WP41's key rename.
- **Improved Ability's checks need the skill ratings**, which a save or import resolves *after*
  powers. As with WP115's `LaterStepFacts`, the web route passes them and the loader doesn't. The
  powers page re-checks the committed picks and warns when a skill edit breaks one. The learned
  rating is the bought rating plus the Talent's free skill.
- **Improved Reflexes' Reaction doesn't stack with implants either** (rulebook wins over the data,
  which puts only the dice in `precedence0`).
- **High Pain Tolerance ⟷ Pain Resistance is enforced from both sides.** `GateContext` gained
  `power_names` and the `power` condition kind. `create_power_selection` checks a power's
  `<forbidden>` qualities.

## 2026-09-26 — WP121: the Aspected Magician is offered

- **The aspect is its own field** (`Character.magic_aspect`, `CharacterSave.magic_aspect`), set by
  the Talent step. The free grant is derived from it: the aspect group's skills at the option's
  rating, through the same per-skill `TALENT` Improvements a Magician's grant uses. So a saved
  Aspected Magician stores no `granted_skill_ids`.
- **Capability helpers** replace `magic_type == "Magician"` checks: `uses_tradition`,
  `casts_spells` (Magician, or a Sorcery aspect) and `binds_spirits` (Magician, or a Conjuring
  aspect), in `chummer5.engine.magic`. The spell and spirit sections and routes gate on them. The
  free-spell budget reads the character's *own* Talent option rather than the letter's Magician
  row, so an Aspected Magician gets 0 free spells.
- **The other two groups are banned** through WP118's `SkillPurchaseRules.banned_groups`, with the
  aspect in the reason.
- **Legacy import still blocks an Aspected Magician.** No corpus file holds one, so where legacy
  records the aspect is unverified. The block is explicit ("its aspect isn't read"), not the old
  "not supported" catch-all.
- **Known gap:** Incompetent's choice list offers a Magician-type character all three magic groups.
  For an Aspected Magician, the two it can never learn are arguably "physically incapable" choices
  (p. 81), which the rulebook forbids. `choice_options` doesn't see the aspect. Left for WP135's
  whole-character check, where the full character is in view.
