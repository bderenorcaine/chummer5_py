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
