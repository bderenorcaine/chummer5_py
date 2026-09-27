# Chummer5 Python — Project Overview

## What this is

A from-scratch Python reimplementation of [Chummer5a](https://github.com/chummer5a/chummer5a), the
Shadowrun 5E character creation and campaign management tool. The original is a mature (10+ year),
community-maintained WinForms/.NET Framework application, preserved in this repo under [legacy/](../legacy)
for reference. This is a personal project, not a contribution to the upstream Chummer5a project.

## Why

The legacy application is:
- **Windows-bound.** WinForms + .NET Framework 4.8 means Linux/macOS users are stuck with Wine, CrossOver,
  or a VM — none of which are attractive as a daily-driver setup.
- **Slow in ways that trace back to architecture, not just bugs.** See [Performance lessons](#performance-lessons-from-the-legacy-app)
  below — this isn't "needs a profiler pass," it's "several load-bearing design decisions fight performance
  by construction."

The goal is a tool that does the same job — build and manage an SR5 character — as a local web app that
runs anywhere Python and a browser run.

## Relationship to the legacy codebase

`legacy/` is kept, not deleted, because it's genuinely useful for three things:
1. **Rules reference.** When the new engine needs to know exactly how a derived stat is computed, the
   legacy C# is the executable spec.
2. **Game data.** `legacy/Chummer/data/*.xml` (+ matching `.xsd`) is the actual SR5 ruleset — metatypes,
   priorities, qualities, gear, etc. — already decoupled from code. The new project parses these files
   directly rather than re-entering rules content. These files span many sourcebooks; almost every
   entry carries a `<source>` tag identifying which book it's from (e.g. `SR5`, `RF`, `DT`). See
   "Core rulebook only" under MVP scope below for how this gates what MVP actually loads/offers.
3. **Regression oracle.** `legacy/Chummer.Tests/TestFiles/*.chum5` is a corpus of real, legacy-computed
   characters. The new engine's output gets diffed against these to catch silently-wrong rules logic —
   this matters more than it sounds like it should, because an AI-agent-assisted port of unfamiliar
   business logic will otherwise happily produce plausible-but-wrong numbers.

`spec/rulebooks/Shadowrun_Fifth_Edition_Core_Rulebook.pdf` is also kept as the authoritative rules
*text* — used to resolve cases where the data/code alone don't make intent obvious (e.g. which
direction a metatype/magic eligibility rule actually runs).

**License:** the legacy project is GPLv3. Because this project reuses its data files, rules logic, and
test fixtures, it is a derivative work and is GPLv3 too. Not a decision point — inherited.

## Goals

1. Priority-based character creation with correct SR5 core-rulebook math, verified against legacy output.
2. Cross-platform: no Windows, no Wine, no VM. Runs as a local web app.
3. Fast by construction — see the architectural lessons below, not a "fix it later" item.
4. Maintainable by one person with AI-agent assistance: favor explicit, small-surface-area, testable code
   over cleverness. Optimize for "an agent unfamiliar with this session can pick up a module and get it
   right," not for minimal line count.
5. English only for now, but structured so translation is an addition, not a retrofit.

## MVP scope

**In scope:**
- Priority-based chargen only: metatype priority, attribute priority, skill priority, resources priority.
- **Mundane characters only.** No magic/resonance priority (no adepts, mages, technomancers) in MVP —
  a mundane priority build already exercises the full engine shape end-to-end (priorities → attributes/
  skills/qualities → derived stats) without also requiring spell/program selection, tradition choice, or
  drain/fading. Magic/resonance is the first fast-follow after MVP, not a "someday".
  This means that, in order to obtain valid characters in MVP, the effect of "no magic/resonance priority" must be modeled as "magic/resonance priority forced to E (mundane)", i.e. the only available priorities for the other aspects are A, B, C, and D.
  (Rules note for that later work: metatype, not the other way around, governs Magic/Resonance
  eligibility — most metatypes are simply *eligible* to buy Magic via a Talent priority letter,
  a few are inherently magical and start with Magic forced ≥1 regardless of Talent choice, and a
  few can never access Magic at all. This only matters once magic/resonance chargen exists — every
  metatype in MVP's scope, per the "Core rulebook only" rule below, falls in the plain-eligible
  bucket, which is exactly why forcing Talent to E is sufficient to get mundane characters in MVP
  without needing any metatype-specific handling.)
- **Core rulebook (SR5) content only.** Beyond "mundane," MVP further restricts every data-driven
  choice (metatype, quality, ...) to entries sourced from the SR5 core rulebook — checked via each
  data file's per-entry `<source>` tag. Concretely: `metatypes.xml`'s `Metahuman` category has 5
  `source=SR5` base types (Human, Elf, Dwarf, Ork, Troll); every metavariant (Nartaki, Gnome, ...)
  and every non-`Metahuman` metatype (Centaur, Sasquatch, A.I., Shapeshifters, ...) is sourced from
  a later book and is out of MVP scope. `qualities.xml` similarly narrows from 803 entries to 96
  `source=SR5` ones. `skills.xml`'s 76 entries are all `source=SR5` already, so no filtering is
  needed there. This is a general MVP-scope filter every data loader should apply, not a
  metatype-specific rule.
- Attributes, active skills (+ specializations, skill groups), positive/negative qualities (karma cost
  and limits), contacts, starting nuyen/resources spent on a basic gear purchase.
- Derived stats needed to validate a freshly created character: attribute totals, skill dice pools,
  initiative, limits, condition monitors.
- A minimal subset of the Improvement mechanism — only what priority chargen actually triggers (metatype
  bonuses, quality bonuses, priority-derived bonuses). See [Improvement engine](#improvement-engine-design)
  below for why this can't be "zero."
- Save/load in a new, native format (see [Data & save format](#data--save-format)).
- Web UI (local, single-user, no auth) as the only supported interface.
- ~~All user-facing strings routed through an i18n key layer from day one, even though only English
  ships.~~ **Corrected 2026-09-24 (WP101): this was never built during the MVP.** Every template and
  route message was plain English text until Phase W. The key layer itself landed in WP101: string
  catalogs in the legacy `lang/*.xml` schema, a `_()` template global, and a session locale (see
  `src/chummer5/lang/README.md` for the key rules). WP102 converted every template and web-layer
  string and made that property test-enforced. WP103 translates game-data names at display time
  from the legacy `<locale>_data.xml` files. So Goal 5's "translation is an addition" is now true
  of the pages: offering a language means translating the `Web_*` catalog and adding one
  `prefs.LOCALES` entry. Two things stay English by recorded decision (see `decisions-log.md`,
  2026-09-24): engine exception texts, and English authored in `chummer5.data` modules.

**A gap found after MVP shipped, not a deliberate cut:** Lifestyle selection — SR5's mandatory
"Step Six" line item (core rulebook, p.369: "A character must select one of the lifestyles below to
be their primary Lifestyle"), paid from the same Resources-priority nuyen pool the bullet above
already claims as in scope — is absent from what MVP actually built. It wasn't excluded by any
decision recorded in this document; it was simply missed, discovered during post-MVP scoping. See
Implementation Plan's WP20.

**Explicitly out of scope for MVP (deferred, not abandoned):**
- The general-purpose Improvement engine (full type coverage — cyberware/bioware effects, vehicles,
  matrix rules, most of the ~100+ improvement types the legacy engine supports).
- Magic and Resonance (adepts, magicians, mystic adepts, technomancers) — see above. Magicians and
  physical Adepts are scoped as Implementation Plan's Phase I. Technomancers/A.I. (Resonance) remain
  out of scope indefinitely, not just for MVP; **Mystic Adepts are excluded from Phase I too, by
  explicit product decision (2026-07-19)** rather than deferred smallest-scope pragmatism like every
  other cut on this page — not currently planned at all, not just "later." The **Aspected
  Magician** is in scope since Phase X's WP121.
- Cyberware, vehicles, drones, full gear catalog beyond a basic purchase flow. Cyberware itself is
  scoped as Implementation Plan's Phase J (Standard grade, flat-cost/flat-essence items only);
  non-Standard cyberware grades remain deferred past that phase. **Bioware is no longer on this list**
  as of the 2026-07-21 ruling below — it's scoped as Phase L (reuses Phase J's Essence mechanism
  directly, 8 flat SR5 entries, no new mechanism needed). **Vehicles/drones (rigger support) are
  targeted by a future phase**, deliberately scoped smaller than a full implementation per the same
  ruling: unmodified purchases only, no modification-slot system, no RCC/cyberdeck buildout beyond
  buying the stock item — see Implementation Plan's Phase P intro.
- Career mode (post-chargen karma spending, character aging over time) — **with one exception**: the
  2026-07-21 ruling scopes *character-creation-time* Karma spend on attributes/skills/spells (Step
  Seven's "leftover Karma," reusing the same cost formulas the Character Advancement section defines)
  as Implementation Plan's Phase O. This is chargen only — actual post-chargen play/advancement
  (career mode proper) remains out of scope.
- The Karma-based build method (`CharacterBuildMethod.Karma` in the legacy engine — buying the entire
  character from a large Karma pool instead of Priority or Sum-to-Ten) — **ruled out explicitly,
  2026-07-21**, not deferred. Sum-to-Ten (Priority's sibling build method — same Priority Table, same
  per-column meaning, just a different letter-assignment rule) **is** in scope, per that same ruling —
  see Implementation Plan's Phase L.
- SR5's Availability-cap mechanic (Restricted/Forbidden-availability purchases gated behind a
  Priority-derived Availability budget) — **ruled out explicitly, 2026-07-21**. The simplification
  agreed on: any new catalog (gear, cyberware, bioware, foci, eventual vehicle gear) should simply
  **exclude items with Availability > 12** from what it offers, rather than tracking an Availability
  budget as its own resource. Note this doesn't retroactively fix WP21's gear catalog or WP31's
  cyberware catalog, neither of which filtered by Availability at all when the ruling was made
  (WP21's own doc flags this as a deliberate, undone cut). **Partially backfilled since:** WP66
  capped the Rating-priced half of the gear catalog, and WP94 capped its Commlinks / Cyberdecks /
  Rigger Command Consoles categories (6 rows dropped, purchasable catalog 379 → 373). Every other
  flat-gear category and the whole cyberware catalog remained uncapped — sized concretely in
  `spec/decisions-log.md`'s 2026-08-01 and 2026-08-24 entries. **Settled by Phase X's Step Six
  ruling (WP126, 2026-09-27):** items whose Availability scales with their rating are capped (a new
  cyberware pick at the highest rating within 12; rated electronics at Device Rating 6), and flat
  items already over 12 stay offered, by ruling. No backfill remains.
- Technomancers/Resonance — reaffirmed out of scope, 2026-07-21 (already excluded per above; recorded
  again here since it came up explicitly in the same ruling as the items above).
- Plugins.
- Localization content (structure only, per above; the structure itself arrived late, in Phase W).
- Multi-user / hosted deployment, anything resembling ChummerHub.

## Unmodeled real effects

**A living registry, updated by whichever WP introduces or ships each row — do not let this drift
out of sync with `src/`.** This is the project's one place to look up "what does this offered
character aspect actually *not* do, mechanically" without re-deriving it from a worklog or the PDF.

**The policy this registry exists to support (settled 2026-07-24, refining WP3/WP8's original
"never partially apply" framing rather than replacing it):** every *computed, chargen-time* effect
of an offered aspect — a karma cost, a dice-pool/Limit/attribute bonus, anything this engine
actually derives a number from — must be modeled in full, or the aspect stays excluded. That part
of the original rule is unchanged. What's now explicit: an aspect whose real SR5 effect is
inherently an **in-play, GM-adjudicated, or otherwise out-of-this-engine's-scope** mechanic (a
combat-test dice-pool modifier, a Notoriety/reputation consequence, a background-check/arrest risk,
a subsystem like the Matrix or toxin/pathogen resistance this engine has zero representation of at
all) is fine to offer anyway — karma cost charged/credited in full, every *computable* part of it
applied — as long as the unmodeled part is recorded here, not silently dropped and not conflated
with "this aspect does nothing." The earlier, stricter reading (exclude anything with *any*
unmodeled effect, regardless of magnitude) is retired as of this ruling; WP22's own "significance"
judgment calls that led to excluding SINner/Prejudiced/etc. specifically (as opposed to offering
them with a documented gap) no longer apply going forward — see WP55's own entry in the
Implementation Plan for the first WP built under the new policy.

**Reachability is part of a row, not a footnote (WP77).** An aspect the browser UI offers today and
one reachable only by importing a legacy `.chum5` file are not the same severity of gap, so the
`Kind` column now says which. Rows predating WP77 carry no such marker — they were not
retro-labelled, because getting it right per row needs the same per-catalog reachability check WP77
only ran over its own 10. **A reachability marker is only true until a UI WP moves the line, so it
has to be re-checked by any WP that widens what the browser offers** — WP42 (Phase K's picker) did
exactly that, and all five of WP77's "legacy import only" augmentation rows plus WP38's four
cyberlimb-enhancement rows became UI-reachable in one commit. That is not a new gap; it is the same
gap in front of more players, which is precisely what the column exists to say.

**These rows also reach the player, not just this document.** A row whose aspect carries an
`unmodeled_effect_note` in its own catalog module — every Quality row (WP56) and every
cyberware row (WP79) below — renders in the character sheet's collapsible "Unmodeled real effects"
section for a character who actually holds it, collected by
`chummer5.engine.derived.unmodeled_effect_notes`. Those notes are a **hand-kept mirror** of this
table: runtime code never parses this file, so a WP that edits a row here must edit the matching
catalog dict (`chummer5.data.qualities._UNMODELED_EFFECT_NOTES`,
`chummer5.data.cyberware.UNMODELED_EFFECT_NOTES`, `chummer5.data.bioware._UNMODELED_EFFECT_NOTES`,
and — since WP95 — `chummer5.data.gear._UNMODELED_EFFECT_NOTES` (keyed by **category**, not by
item name: every row in a gear category here has the same gap) plus
`chummer5.data.vehicles.UNMODELED_EFFECT_NOTE_{VEHICLE,DRONE}` (two strings, split on `is_drone`
for the rigger-interface half)) in the same commit.
`tests/unit/test_augmentation_unmodeled_registry.py` pins *which* augmentation
rows must have a note and which must not; it cannot pin the wording against this table.

**One collector, but new *selections* aren't free (WP95).** `unmodeled_effect_notes` reads every
aspect through a plain `getattr`, so adding the field to a new *catalog* dataclass needs no change
there — but it can only read selections it actually walks, and `vehicle_selection` (WP92) was
simply never added to that walk. A WP that gives `Character` a new field holding catalog objects
has to add its own loop.

| Aspect | Kind | What's modeled | What's not (and why) | Source |
|---|---|---|---|---|
| Gearhead | Quality (Positive) | Karma cost only | Vehicle/drone Speed/Handling/dice-pool bonus during vehicle or chase combat (p. 74) — no vehicle/combat subsystem exists | WP22 |
| Guts | Quality (Positive) | Karma cost only | +2 dice pool resisting fear/intimidation tests, including magically induced (p. 74) — no test-resolution system exists | WP22 |
| Juryrigger | Quality (Positive) | Karma cost only | +2 dice pool for Mechanical Tests when juryrigging temporary repairs (p. 75) — no repair/test subsystem exists | WP22 |
| Natural Hardening | Quality (Positive) | Karma cost only | 1 point of natural biofeedback filtering vs. Matrix biofeedback damage (p. 76) — no Matrix rules exist | WP22 |
| Low-Light Vision | Quality (Positive); also metatype-granted (Elf, Ork) | Karma cost only (purchasable); free grant only (metatype-granted) | Negates low-light vision penalties on visual Perception (p. 444/446) — no lighting-condition Perception system exists | WP22 (purchasable), WP23 (metatype grant) |
| Thermographic Vision | Quality (Positive); also metatype-granted (Dwarf, Troll) | Karma cost only (purchasable); free grant only (metatype-granted) | Negates darkness/heat-pattern vision penalties (p. 446) — same, no lighting-condition Perception system | WP22 (purchasable), WP23 (metatype grant) |
| Simsense Vertigo | Quality (Negative) | Karma credit only | -2 dice pool to all AR/VR/simsense tests (p. 83) — no Matrix/AR test system exists | WP22 |
| Unsteady Hands | Quality (Negative) | Karma credit only | -2 dice pool for Agility-based tests, re-triggerable via an Agility+Body(4) test after a stressful encounter (p. 87) — no in-play test-resolution system exists | WP22 |
| Resistance to Pathogens/Toxins | Quality (Positive); metatype-granted only (Dwarf), not player-purchasable | Free grant only | The Dwarf racial trait: +2 dice on Resistance Tests against pathogens and toxins (Metatype Attribute Table, p. 66; the quality, p. 79) — no toxin/pathogen resistance subsystem exists | WP23, reworded by WP113 |
| Troll +1 Reach | Metatype (racial trait, Troll) | Shown on the character sheet (`Reach +1`) | Lengthens melee reach (p. 185) — no melee-combat resolution exists | WP113 |
| SINner (National) | Quality (Negative) | Karma credit + chosen SIN detail (free text) | Background-check/arrest consequences described across a full page (p. 84) — no background-check/arrest-risk subsystem exists | WP55 |
| SINner (Corporate Limited) | Quality (Negative) | Karma credit + chosen SIN detail (free text) | Same background-check/arrest consequences as National, p. 84 | WP55 |
| SINner (Criminal) | Quality (Negative) | Karma credit + chosen SIN detail (free text) + (since WP110) its +1 Notoriety | Same background-check/arrest consequences (p. 84-85) | WP55, narrowed by WP110 |
| SINner (Corporate) | Quality (Negative) | Karma credit + chosen SIN detail (free text) | Same background-check/arrest consequences, p. 85 — the single largest-magnitude Negative quality in the SR5 core catalog | WP55 |
| Code of Honor | Quality (Negative) | Karma credit + chosen protected-group detail (free text) | In-play Karma-loss/Public-Awareness consequences for violating the code (p. 79) — no in-play consequence-tracking subsystem exists | WP55 |
| Codeblock | Quality (Negative) | Karma credit + chosen Matrix-action detail (free text) | -2 dice pool modifier on the chosen Matrix action (p. 80) — no Matrix rules exist | WP55 |
| Social Stress | Quality (Negative) | Karma credit + chosen cause/trigger detail (free text) | Reduces the number of 1s required to glitch a Leadership/Etiquette test by 1 (p. 85) — no test-resolution/glitch system exists | WP55 |
| Natural Immunity (Natural) | Quality (Positive) | Karma cost + chosen disease/toxin detail (free text) | Full immunity to one chosen disease or toxin (p. 76) — no toxin/pathogen resistance subsystem exists (the same bucket Allergy's 8 SR5 variants are already in) | WP55 |
| Natural Immunity (Synthetic) | Quality (Positive) | Karma cost + chosen disease/toxin detail (free text) | Same as Natural, at the higher (synthetic) tier, p. 76 | WP55 |
| Ambidextrous | Quality (Positive); **offered by today's UI** | Karma cost | No -2 off-hand penalty on actions done solely with the off hand, such as firing a gun (p. 71) — no attack or off-hand action resolution exists. | WP114 |
| Analytical Mind | Quality (Positive); **offered by today's UI** | Karma cost | +2 dice to Logic Tests involving pattern recognition, evidence analysis, clue hunting or puzzles, and half the time to solve a problem (p. 72) — no test resolution exists. | WP114 |
| Astral Chameleon | Quality (Positive); **offered by today's UI** | Karma cost | Astral signatures last half as long and Assensing Tests against them take -2 dice (p. 72) — no astral-signature or Assensing resolution exists. | WP114 |
| Blandness | Quality (Positive); **offered by today's UI** | Karma cost + its −1 Notoriety (WP110) | +1 to the threshold to recall details about the character, and -2 dice to shadow or locate them by appearance in a crowd (p. 72); lost while they carry distinguishing features — no Memory-test or search resolution exists. (Its -1 Notoriety is applied.) | WP114 |
| First Impression | Quality (Positive); **offered by today's UI** | Karma cost + its −1 Notoriety (WP110) | +2 dice to relevant Social Tests at a first meeting only (p. 74) — no Social test resolution exists. (Its -1 Notoriety is applied.) | WP114 |
| Focused Concentration | Quality (Positive); **offered by today's UI** | Karma cost | Sustains one spell of Force up to the rating without the -2 per sustained spell penalty (p. 74) — no spell-sustaining or casting resolution exists. | WP114 |
| Human-Looking | Quality (Positive); **offered by today's UI** | Karma cost | Passes for human in most Social-test circumstances (p. 75) — no Social test resolution exists. | WP114 |
| Magic Resistance | Quality (Positive); **offered by today's UI** | Karma cost | +1 die per rating to Spell Resistance Tests, always on, and voluntary-subject spells always fail on the character (p. 76) — no spell resolution exists. | WP114 |
| Quick Healer | Quality (Positive); **offered by today's UI** | Karma cost | +2 dice to all Healing Tests made on, for or by the character, including magical healing (p. 77) — no healing resolution exists. | WP114 |
| Resistance to Pathogens | Quality (Positive); **offered by today's UI** | Karma cost | +1 die to Resistance Tests against pathogens (p. 77) — no toxin/pathogen resistance subsystem exists. | WP114 |
| Resistance to Toxins | Quality (Positive); **offered by today's UI** | Karma cost | +1 die to Resistance Tests against toxins (p. 77) — no toxin/pathogen resistance subsystem exists. | WP114 |
| Resistance to Pathogens and Toxins | Quality (Positive); **offered by today's UI** | Karma cost | +1 die to Resistance Tests against both pathogens and toxins (p. 77) — no toxin/pathogen resistance subsystem exists. | WP114 |
| Codeslinger | Quality (Positive); **offered by today's UI** | Karma cost + chosen Matrix action (a fixed list from `actions.xml`) | +2 dice on the chosen Matrix action (p. 72) — no Matrix test resolution exists. The chosen action is recorded. | WP114 |
| Home Ground | Quality (Positive); **offered by today's UI** | Karma cost + chosen bonus (one of 5; repeatable with a different bonus each time) | The chosen home-turf bonus (p. 74) — ignoring background count, local Street Cred, Matrix, Evasion or gang-Knowledge dice there -- none of those tests or locations exist here. The chosen bonus is recorded. | WP114 |
| Spirit Affinity | Quality (Positive); **offered by today's UI** | Karma cost + chosen spirit type (the 6 core types) | One extra service from each spirit of the chosen type, and +1 die to bind it (p. 77) — bound spirits' services are the player's own entry here and no Binding Test exists. The chosen type is recorded. | WP114 |
| Addiction (Mild) | Quality (Negative); **offered by today's UI** | Karma credit, the substance or habit (free text) and its +1 Notoriety (WP110) | Monthly cravings; a failed Withdrawal Test gives -2 dice to Mental- or Physical-based tests until the craving is satisfied (pp. 77-78, 414) — no craving or Withdrawal Test tracking exists. (Its +1 Notoriety is applied.) | WP115 |
| Addiction (Moderate) | Quality (Negative); **offered by today's UI** | Karma credit, the substance or habit (free text) and its +1 Notoriety (WP110) | Cravings every two weeks; a failed Withdrawal Test gives -4 dice to Mental- or Physical-based tests until the craving is satisfied (pp. 77-78, 414) — no craving or Withdrawal Test tracking exists. (Its +1 Notoriety is applied.) | WP115 |
| Addiction (Severe) | Quality (Negative); **offered by today's UI** | Karma credit, the substance or habit (free text), −2 dice on Social Active skills and its +1 Notoriety (WP110) | Weekly cravings; a failed Withdrawal Test gives -4 dice to Mental- or Physical-based tests until the craving is satisfied (pp. 77-78, 414) — no craving or Withdrawal Test tracking exists. (Its constant -2 dice on Social Tests and +1 Notoriety are applied.) | WP115 |
| Addiction (Burnout) | Quality (Negative); **offered by today's UI** | Karma credit, the substance or habit (free text), −3 dice on Social Active skills and its +1 Notoriety (WP110) | Daily cravings; a failed Withdrawal Test gives -6 dice to Mental- or Physical-based tests until the craving is satisfied (pp. 77-78, 414) — no craving or Withdrawal Test tracking exists. (Its constant -3 dice on Social Tests and +1 Notoriety are applied.) | WP115 |
| Allergy (Uncommon / Common, Mild) | Quality (Negative); **offered by today's UI** | Karma credit + the allergen (free text) | On contact with the allergen, -2 dice to Physical Tests while symptomatic; and 1 fewer die on Resistance Tests against attacks using it (p. 78) — no exposure, symptom or damage resolution exists. The allergen is recorded. | WP115 |
| Allergy (Uncommon / Common, Moderate) | Quality (Negative); **offered by today's UI** | Karma credit + the allergen (free text) | On contact with the allergen, -4 dice to all Physical Tests while symptomatic; and 2 fewer dice on Resistance Tests against attacks using it (p. 78) — no exposure, symptom or damage resolution exists. The allergen is recorded. | WP115 |
| Allergy (Uncommon / Common, Severe) | Quality (Negative); **offered by today's UI** | Karma credit + the allergen (free text) | On contact with the allergen, -4 dice to all tests while symptomatic, and 1 box of unresisted Physical damage per minute of exposure; and 3 fewer dice on Resistance Tests against attacks using it (p. 78) — no exposure, symptom or damage resolution exists. The allergen is recorded. | WP115 |
| Allergy (Uncommon / Common, Extreme) | Quality (Negative); **offered by today's UI** | Karma credit + the allergen (free text) | On contact with the allergen, anaphylactic shock: -6 dice to everything, and 1 box of unresisted Physical damage per 30 seconds of exposure; and 4 fewer dice on Resistance Tests against attacks using it (p. 78) — no exposure, symptom or damage resolution exists. The allergen is recorded. | WP115 |
| Prejudiced (Common / Specific, Biased) | Quality (Negative); **offered by today's UI** | Karma credit + the target group (free text) | -2 dice on all Social Tests when dealing with the target group, and +2 dice for them in negotiations with the character (p. 82) — no Social test resolution exists. The target group is recorded. | WP115 |
| Prejudiced (Common / Specific, Outspoken) | Quality (Negative); **offered by today's UI** | Karma credit + the target group (free text) | -4 dice on all Social Tests when dealing with the target group, and +4 dice for them in negotiations with the character (p. 82) — no Social test resolution exists. The target group is recorded. | WP115 |
| Prejudiced (Common / Specific, Radical) | Quality (Negative); **offered by today's UI** | Karma credit + the target group (free text) | -6 dice on all Social Tests when dealing with the target group, and +6 dice for them in negotiations with the character (p. 82) — no Social test resolution exists. The target group is recorded. | WP115 |
| Dependent (Nuisance) | Quality (Negative); **offered by today's UI** | Karma credit + +10% Lifestyle cost | Learning or improving a skill takes 50% longer, and so does any long-term project (p. 80) — no training-time tracking exists. (Its +10% Lifestyle cost is applied.) | WP115 |
| Dependent (Inconvenience) | Quality (Negative); **offered by today's UI** | Karma credit + +20% Lifestyle cost | Learning or improving a skill takes 50% longer, and so does any long-term project (p. 80) — no training-time tracking exists. (Its +20% Lifestyle cost is applied.) | WP115 |
| Dependent (Demanding) | Quality (Negative); **offered by today's UI** | Karma credit + +30% Lifestyle cost | Learning or improving a skill takes 50% longer, and so does any long-term project (p. 80) — no training-time tracking exists. (Its +30% Lifestyle cost is applied.) | WP115 |
| Astral Beacon | Quality (Negative); **offered by today's UI** | Karma credit | Its astral signature is highly visible and lasts twice as long, and Assensing Tests against it get -1 to the threshold (p. 78) — no astral-signature or Assensing resolution exists. | WP115 |
| Bad Luck | Quality (Negative); **offered by today's UI** | Karma credit + its +1 Notoriety (WP110) | Whenever Edge is spent, a 1 on 1D6 spends the point for the opposite effect, at most once per session (p. 79) — no Edge-spend resolution exists. (Its +1 Notoriety is applied.) | WP115 |
| Bad Rep | Quality (Negative); **offered by today's UI** | Karma credit + its Notoriety of 3 (WP110) | How NPCs react to the bad reputation, removable only by resolving its source and buying the quality off (p. 79) — no NPC-reaction or buy-off tracking exists. (Its Notoriety of 3 is applied.) | WP115 |
| Combat Paralysis | Quality (Negative); **offered by today's UI** | Karma credit + its +1 Notoriety (WP110) | The first Initiative Score of a combat is halved (rounded up), -3 dice on Surprise Tests, and +1 threshold on Composure Tests under fire (p. 80) — no combat, Surprise or Composure resolution exists. (Its +1 Notoriety is applied.) | WP115 |
| Distinctive Style | Quality (Negative); **offered by today's UI** | Karma credit | +2 dice for anyone trying to identify, trace or locate the character, and -1 to the threshold of NPC Memory Tests about them (p. 80) — no search or NPC Memory resolution exists. | WP115 |
| Elf Poser | Quality (Negative); **offered by today's UI** | Karma credit + its +1 Notoriety (WP110) | Passes as an elf; elves who discover the secret react with contempt or hostility (p. 81) — no Social-modifier resolution exists. (Its +1 Notoriety is applied.) | WP115 |
| Gremlins | Quality (Negative); **offered by today's UI** | Karma credit, rating 1-4 and its +1 Notoriety (WP110) | One fewer 1 is needed for a glitch per level when using a moderately sophisticated device (p. 81) — no test or glitch resolution exists. (Its +1 Notoriety is applied.) | WP115 |
| Insomnia (Basic) | Quality (Negative); **offered by today's UI** | Karma credit | An Intuition + Willpower (4) Test before each Stun recovery roll; failure doubles the recovery time and delays Edge refresh by up to 24 hours (pp. 81-82) — no healing or Edge-refresh resolution exists. | WP115 |
| Insomnia (Full) | Quality (Negative); **offered by today's UI** | Karma credit | An Intuition + Willpower (4) Test before each Stun recovery roll; failure negates that recovery attempt and delays Edge refresh by 24 hours (p. 82) — no healing or Edge-refresh resolution exists. | WP115 |
| Loss of Confidence | Quality (Negative); **offered by today's UI** | Karma credit + the chosen skill (rating 4+), its −2 dice and its lost specialization | Edge can't be used on tests with the chosen skill (p. 82) — no Edge-spend resolution exists. (Its -2 dice and the lost specialization are applied.) | WP115 |
| Ork Poser | Quality (Negative); **offered by today's UI** | Karma credit + its +1 Notoriety (WP110) | Passes as an ork; orks who discover the secret may turn hostile, and prejudiced humans or elves see a race traitor (p. 82) — no Social-modifier resolution exists. (Its +1 Notoriety is applied.) | WP115 |
| Scorched | Quality (Negative); **offered by today's UI** | Karma credit, the chosen side effect (one of 5) and its +1 Notoriety (WP110) | The chosen side effect, for 6 hours (24 on a glitch) after a failed Body + Willpower (4) Test on entering VR or slotting a BTL, plus a Willpower (3) Test to face Black or Psychotropic IC and -2 dice resisting its damage (p. 83) — no VR, BTL or IC resolution exists. The chosen effect is recorded. (Its +1 Notoriety is applied.) | WP115 |
| Spirit Bane | Quality (Negative); **offered by today's UI** | Karma credit, the chosen spirit type and its +1 Notoriety (WP110) | Spirits of the chosen type resent the character: -2 dice to summon or bind them, +2 dice for them to resist the character's banishing, and they single the character out in combat (p. 85) — no summoning, binding or spirit-combat resolution exists. The chosen type is recorded. (Its +1 Notoriety is applied.) | WP115 |
| Weak Immune System | Quality (Negative); **offered by today's UI** | Karma credit + its +1 Notoriety (WP110) | +2 to the Power of any disease the character resists (p. 87) — no toxin/pathogen resistance subsystem exists. (Its +1 Notoriety is applied.) | WP115 |
| Incompetent | Quality (Negative); **offered by today's UI** | Karma credit, the chosen skill group (never Sorcery/Conjuring/Enchanting for a non-Magician), the ban on buying the group or any of its skills, unawareness (no defaulting) in its skills, and its +1 Notoriety (WP110) | Gear that grants a bonus to, or needs, a skill of the group gives the character nothing, and the GM may call for Success Tests for ordinary tasks (p. 81) — no gear-skill or test resolution exists. | WP117 |
| Sensitive System | Quality (Negative); **offered by today's UI** | Karma credit, doubled cyberware Essence, and a character who can hold no bioware | For a magic user, a Willpower (2) Test before each Drain Test, with +2 Drain Value on a failure (p. 83) — no Drain resolution exists. | WP117 |
| Uncouth | Quality (Negative); **offered by today's UI** | Karma credit, double priority-point and Karma cost for Social Active skills, no Social skill groups, unawareness (no defaulting) in Social skills at rating 0, and its +1 Notoriety (WP110) | −2 dice on Social Tests to resist acting improperly or impulsively, and the GM may call for Success Tests in ordinary social situations (p. 85) — no Social test resolution exists. | WP117 |
| Uneducated | Quality (Negative); **offered by today's UI** | Karma credit, double Karma cost for Technical Active skills and groups and for Academic/Professional knowledge (and their specializations), unawareness (no defaulting) in Technical skills at rating 0, and its +1 Notoriety (WP110) | The GM may call for Success Tests for tasks most people take for granted, and may rule some skill groups of these categories out for good (p. 87) — no GM-adjudicated test exists. | WP117 |
| Astral Perception | Adept power; **offered by today's UI** | Power Point cost (1 PP), and it unlocks the Assensing skill for the Adept (p. 69) | Seeing into the astral plane while dual-natured, and so able to attack astral forms (p. 309; astral perception, p. 312) — no astral resolution exists. | WP118 |
| Critical Strike | Adept power; **offered by today's UI** | Power Point cost (0.5 PP) + the chosen melee skill (one of the five printed); repeatable, a different skill each time | +1 DV on attacks with the chosen melee skill (p. 309) — no attack or damage resolution exists. The chosen skill is recorded. | WP119 |
| Enhanced Accuracy (skill) | Adept power; **offered by today's UI** | Power Point cost (0.25 PP) + the chosen Combat skill (not Unarmed Combat); repeatable, a different skill each time | +1 Accuracy for weapons used with the chosen Combat skill (p. 309) — no weapon or Accuracy representation exists. The chosen skill is recorded. | WP119 |
| Killing Hands | Adept power; **offered by today's UI** | Power Point cost (0.5 PP) | Unarmed attacks may deal Physical instead of Stun damage, and count as magical against critters' magical defenses (p. 310) — no unarmed-combat or damage resolution exists. | WP119 |
| Mystic Armor | Adept power; **offered by today's UI** | Power Point cost (0.5 PP per level) + its +1 Armor per level, into the Armor total (WP109) | Its Armor also protects against damage in astral combat (p. 310) — no astral combat exists. | WP119 |
| Pain Resistance | Adept power; **offered by today's UI** | Power Point cost (0.5 PP per level) + one ignored wound box per level on both tracks; mutually exclusive with High Pain Tolerance | +2 dice per level on tests to withstand pain from torture, magic or illness (p. 311) — no such test exists. | WP119 |
| Adrenaline Boost | Adept power; **offered by today's UI** | Power Point cost (0.25 PP per level) | +2 Initiative Score per level for the current Combat Turn, then Drain equal to the level at the start of the next (p. 308) — no Initiative or Drain resolution exists. | WP120 |
| Attribute Boost | Adept power; **offered by today's UI** | Power Point cost (0.25 PP per level) + the chosen Physical attribute; repeatable, one per attribute | A Magic + level Test whose hits raise the chosen attribute's dice pools (not its limit or Initiative) for twice as many Combat Turns, then Drain equal to the level (p. 309) — no test or Drain resolution exists, so the attribute on the sheet is not raised. The chosen attribute is recorded. | WP120 |
| Combat Sense | Adept power; **offered by today's UI** | Power Point cost (0.5 PP per level) | +1 die per level on defense tests against ranged and melee attacks, and a Perception Test before a possible surprise (p. 309) — no combat or surprise resolution exists. | WP120 |
| Danger Sense | Adept power; **offered by today's UI** | Power Point cost (0.25 PP per level) | +1 die per level on Surprise Tests (p. 309) — no surprise resolution exists. | WP120 |
| Improved Sense | Adept power; **offered by today's UI** | Power Point cost (0.25 PP) + the chosen sense (free text); repeatable | The chosen sense improvement — low-light or thermographic vision, directional sense, improved tactile, perfect pitch, human scale, ... (p. 310) — no Perception or sensory resolution exists. The chosen sense is recorded. | WP120 |
| Kinesics | Adept power; **offered by today's UI** | Power Point cost (0.25 PP per level) | +1 die per level to resist Social Tests and tests to read the character's emotions, such as Judge Intentions (p. 310) — no Social test resolution exists. | WP120 |
| Light Body | Adept power; **offered by today's UI** | Power Point cost (0.25 PP per level) | Adds its level to Agility for jump distance, +1 die per level on the Gymnastics Test to jump, and shortens a fall by its level in meters (p. 310) — no movement or falling resolution exists. | WP120 |
| Missile Parry | Adept power; **offered by today's UI** | Power Point cost (0.25 PP per level) | +1 die per level to defend against thrown weapons and slow missiles, catching one on net hits (p. 310) — no combat resolution exists. | WP120 |
| Natural Immunity | Adept power; **offered by today's UI** | Power Point cost (0.25 PP per level) | +1 die per level on tests to resist toxins and disease (p. 311) — no toxin/pathogen resistance subsystem exists. | WP120 |
| Rapid Healing | Adept power; **offered by today's UI** | Power Point cost (0.5 PP per level) | +1 die per level to Body for Healing Tests, and to any test to heal the character (p. 311) — no healing resolution exists. | WP120 |
| Spell Resistance | Adept power; **offered by today's UI** | Power Point cost (0.5 PP per level) | +1 die per level on Resistance Tests against spells, rituals, alchemical preparations and Innate Spell (p. 311) — no spell resolution exists. | WP120 |
| Traceless Walk | Adept power; **offered by today's UI** | Power Point cost (1 PP) | Moving without visible traces or contact noise: -4 dice to hearing-based Perception against the character, no ground sensors tripped, -2 to Track Tests (p. 311) — no stealth or Perception resolution exists. | WP120 |
| Wall Running | Adept power; **offered by today's UI** | Power Point cost (0.5 PP) | A Running + Strength [Magic] Test to run up (or, with a Sprint, across) a wall (p. 311) — no movement resolution exists. | WP120 |
| Bear | Mentor spirit (archetype); **offered by today's UI** to magic users | Its General bonus, its Magician slot (flat dice, or a conditional pool shown on the sheet) or Adept slot (free power levels outside the Power Point budget) | Disadvantage: may go berserk for up to 3 turns after taking Physical damage in combat, resisted with a Charisma + Willpower Test, or when someone in their care is badly injured (p. 321) — no in-play test or consequence tracking exists. | WP122 |
| Cat | Mentor spirit (archetype); **offered by today's UI** to magic users | Its General bonus, its Magician slot (flat dice, or a conditional pool shown on the sheet) or Adept slot (free power levels outside the Power Point budget) | Disadvantage: can't make an incapacitating attack without a Charisma + Willpower (3) Test at the start of combat (p. 321) — no in-play test or consequence tracking exists. | WP122 |
| Dog | Mentor spirit (archetype); **offered by today's UI** to magic users | Its General bonus, its Magician slot (flat dice, or a conditional pool shown on the sheet) or Adept slot (free power levels outside the Power Point budget) | Disadvantage: can't leave someone behind or betray a comrade without a Charisma + Willpower (3) Test (p. 321) — no in-play test or consequence tracking exists. | WP122 |
| Dragonslayer | Mentor spirit (archetype); **offered by today's UI** to magic users | Its General bonus, its Magician slot (flat dice, or a conditional pool shown on the sheet) or Adept slot (free power levels outside the Power Point budget) | Disadvantage: -1 dice to all actions after breaking a promise, until it is made good (p. 321) — no in-play test or consequence tracking exists. | WP122 |
| Fire-Bringer | Mentor spirit (archetype); **offered by today's UI** to magic users | Its General bonus, its Magician slot (flat dice, or a conditional pool shown on the sheet) or Adept slot (free power levels outside the Power Point budget) | Disadvantage: can't refuse a sincere request for help without a Charisma + Willpower (3) Test (p. 322) — no in-play test or consequence tracking exists. | WP122 |
| Mountain | Mentor spirit (archetype); **offered by today's UI** to magic users | Its General bonus, its Magician slot (flat dice, or a conditional pool shown on the sheet) or Adept slot (free power levels outside the Power Point budget) | Disadvantage: abandoning a plan takes a Charisma + Willpower (3) Test (p. 322) — no in-play test or consequence tracking exists. | WP122 |
| Rat | Mentor spirit (archetype); **offered by today's UI** to magic users | Its General bonus, its Magician slot (flat dice, or a conditional pool shown on the sheet) or Adept slot (free power levels outside the Power Point budget) | Disadvantage: must flee or seek cover in combat unless a Charisma + Willpower (3) Test succeeds (p. 323) — no in-play test or consequence tracking exists. | WP122 |
| Raven | Mentor spirit (archetype); **offered by today's UI** to magic users | Its General bonus, its Magician slot (flat dice, or a conditional pool shown on the sheet) or Adept slot (free power levels outside the Power Point budget) | Disadvantage: a Charisma + Willpower (3) Test to resist exploiting someone's misfortune or pulling a prank (p. 323) — no in-play test or consequence tracking exists. | WP122 |
| Sea | Mentor spirit (archetype); **offered by today's UI** to magic users | Its General bonus, its Magician slot (flat dice, or a conditional pool shown on the sheet) or Adept slot (free power levels outside the Power Point budget) | Disadvantage: giving anything away takes a Charisma + Willpower (3) Test (p. 323) — no in-play test or consequence tracking exists. | WP122 |
| Seducer | Mentor spirit (archetype); **offered by today's UI** to magic users | Its General bonus, its Magician slot (flat dice, or a conditional pool shown on the sheet) or Adept slot (free power levels outside the Power Point budget) | Disadvantage: a Charisma + Willpower (3) Test to resist an available vice (p. 323) — no in-play test or consequence tracking exists. | WP122 |
| Shark | Mentor spirit (archetype); **offered by today's UI** to magic users | Its General bonus, its Magician slot (flat dice, or a conditional pool shown on the sheet) or Adept slot (free power levels outside the Power Point budget) | Disadvantage: may go berserk for up to 3 turns after taking Physical damage in combat, resisted with a Charisma + Willpower Test (p. 323) — no in-play test or consequence tracking exists. | WP122 |
| Snake | Mentor spirit (archetype); **offered by today's UI** to magic users | Its General bonus, its Magician slot (flat dice, or a conditional pool shown on the sheet) or Adept slot (free power levels outside the Power Point budget) | Disadvantage: a Charisma + Willpower (3) Test to resist chasing rare secrets (p. 324) — no in-play test or consequence tracking exists. | WP122 |
| Thunderbird | Mentor spirit (archetype); **offered by today's UI** to magic users | Its General bonus, its Magician slot (flat dice, or a conditional pool shown on the sheet) or Adept slot (free power levels outside the Power Point budget) | Disadvantage: a Charisma + Willpower (3) Test to avoid answering an insult in kind (p. 324) — no in-play test or consequence tracking exists. | WP122 |
| Wise Warrior | Mentor spirit (archetype); **offered by today's UI** to magic users | Its General bonus, its Magician slot (flat dice, or a conditional pool shown on the sheet) or Adept slot (free power levels outside the Power Point budget) | Disadvantage: -1 dice to all actions after acting dishonorably, until atoned for (p. 324) — no in-play test or consequence tracking exists. | WP122 |
| Wolf | Mentor spirit (archetype); **offered by today's UI** to magic users | Its General bonus, its Magician slot (flat dice, or a conditional pool shown on the sheet) or Adept slot (free power levels outside the Power Point budget) | Disadvantage: retreating from a fight takes a Charisma + Willpower (3) Test (p. 324) — no in-play test or consequence tracking exists. | WP122 |
| Customized Agility / Customized Strength | Cyberware (Cyberlimb Enhancement); installable only into a cyberlimb, **and installable there from today's UI** (WP42) | Nuyen cost (`(Rating - MinRating + 1) x 5,000¥`), zero Capacity cost, purchasable range capped at the character's natural maximum for that attribute | Raises the *limb's own* Strength/Agility above its base of 3 (p. 456) — cyberlimbs have a whole parallel per-limb attribute system this engine has no representation of, so nothing downstream (limb-specific tests, unarmed Damage Value) reads it | WP38 |
| Enhanced Agility / Enhanced Strength | Cyberware (Cyberlimb Enhancement); installable only into a cyberlimb, **and installable there from today's UI** (WP42) | Nuyen cost (`Rating x 6,500¥`) and Capacity cost (`Rating`) | Adds its Rating to the limb's Agility/Strength (p. 456) — same unmodeled per-limb attribute system as Customization above; carries no `<bonus>` element at all in the source data | WP38 |
| Vision Enhancement | Cyberware (Eyeware) | Nuyen/Essence/Capacity cost + **+Rating Mental limit, conditional on a visual Perception test** (p. 444) | Its Wireless clause's separate +Rating **dice pool** modifier on visual Perception tests (p. 444) — no wireless-state or test-resolution system exists | WP40 |
| Audio Enhancement | Cyberware (Earware) | Nuyen/Essence/Capacity cost + **+Rating Mental limit, conditional on a hearing Perception test** (p. 444) | Same Wireless dice-pool half, for audio Perception tests (p. 444) | WP40 |
| Spatial Recognizer | Cyberware (Earware) | Nuyen/Essence/Capacity cost + **+2 Mental limit, conditional on a Perception test to find a sound's source** (p. 444) | Same Wireless dice-pool half (p. 444) | WP40 |
| Hydraulic Jacks | Cyberware (Cyberlimb Accessory); installable only into a cyberleg | Nuyen/Capacity cost + **+Rating Physical limit for jumping/sprinting, granted once per matched pair** (p. 457) | The same sentence's other two clauses — +20% maximum jump distance and −2 m falling distance for falling-damage purposes (p. 457) — no movement or falling-damage system exists. Its "parent must be a leg" `<required>` is also unenforced (no `<required>` data is loaded); the pair check is "two of equal Rating in distinct parents" | WP40 |
| Bone Lacing (Plastic / Aluminum / Titanium) | Cyberware (Bodyware); **offered by today's UI**, all 3 | Nuyen + Essence cost; **since WP109, its +1/+2/+3 Armor (into the character's Armor total) and the same number of Body dice (into the Damage Resistance pool)** | Its unarmed Damage Value of (STR + N)P (p. 454) -- no unarmed-combat representation exists. The Body dice count only against Physical damage; the sheet's single Damage Resistance pool doesn't separate Physical from Stun | WP77, narrowed by WP109 |
| Smartlink | Cyberware (Eyeware); **offered by today's UI** | Nuyen + Essence cost only | +2 to a smartgun's Accuracy while you fire it (p. 433; the implant is the eyeware version of the p. 444 accessory) — no weapon, Accuracy or attack-test representation exists. The legacy engine reads the same `<smartlink>2` as a wireless-gated ranged **dice-pool** modifier rather than an Accuracy one; both readings are equally unmodeled here | WP77 |
| Damper | Cyberware (Earware); **offered by today's UI** | Nuyen + Essence cost only | +2 dice resisting sonic attacks, including flashbangs (p. 454) — no test resolution, no sonic/damage-resistance subsystem | WP77 |
| Armor (Cyberlimb Enhancement) | Cyberware (Cyberlimb Enhancement), installable only into a cyberlimb; **offered by today's UI** since WP42 (import-only before that) | Nuyen + Capacity cost; **since WP109, its +Rating Armor, into the character's Armor total** (p. 456) | Its "one enhancement of each type per limb" cap is part of the same unmodeled per-limb system Customized/Enhanced Agility/Strength are already registered for | WP77, narrowed by WP109 |
| Internal Air Tank | Cyberware (Bodyware); **offered by today's UI** since WP42 (import-only before that) | Nuyen + Essence cost | Holding your breath for up to Rating hours, and complete protection from inhalation-vector toxin attacks while you do (p. 455) — the same toxin/pathogen bucket Natural Immunity and Resistance to Pathogens/Toxins are already in, plus no breath/environmental subsystem | WP77 |
| Skillwires | Cyberware (Bodyware); **offered by today's UI** since WP42 (import-only before that) | Nuyen + Essence cost (both Rating-scaled) | Use of activesofts up to the skillwire's Rating, and only while they run on an implanted skilljack (p. 455) — no skillsoft subsystem. The softs themselves are equally absent: SR5's Activesoft/Knowsoft/Linguasoft are Rating-scaled-cost gear and so fall outside WP21's flat-cost gear catalog, leaving nothing to run | WP77 |
| Skilljack | Cyberware (Headware); **offered by today's UI** since WP42 (import-only before that) | Nuyen + Essence cost (both Rating-scaled) | Interpreting knowsofts/linguasofts and running activesofts, capped at Rating × 2 total and Rating per skill (p. 452) — the same missing skillsoft subsystem as Skillwires | WP77 |
| Control Rig | Cyberware (Headware); **offered by today's UI** since WP42 (import-only before that) | Nuyen + Essence cost (both Rating-scaled; a full Essence point at rating 1) | Its entire printed payload: while you are jumped into a vehicle/drone/device, that device's limits rise by the rig's rating — vehicle and drone Sensor, Speed and Handling, plus the Accuracy of mounted weapons the rigger fires (p. 266). No character-level term exists in it at all, and there is no jumping-in, vehicle-test or weapon-Accuracy representation. **Found late for a reason worth recording:** it carries no `<bonus>` node, so it classifies `NO_EFFECT` and WP77's audit — a sweep of the `NOT_YET_SUPPORTED` bucket — could never have seen it | WP95 |
| Vehicles (all 24 offerable) | Vehicle (catalog); **offered by today's UI** (WP93) | Purchase + nuyen cost + the derived Condition Monitor (`12 + ⌈Body/2⌉`, p. 199) | Every printed stat (Handling, Speed, Acceleration, Body, Armor, Pilot, Sensor) exists to be rolled in Vehicle Tests and vehicle combat — no test resolution or vehicle combat exists. **Plus the rigger-interface gap:** a bought vehicle cannot be jumped into, because p. 265's 1,000¥ Rigger Interface is a *modification* and modifications are excluded by the 2026-07-21 ruling | WP95 |
| Drones (all 11 offerable) | Vehicle (catalog, `is_drone`); **offered by today's UI** (WP93) | Purchase + nuyen cost + the derived Condition Monitor (`6 + ⌈Body/2⌉`, p. 199) | Same missing Vehicle Tests/vehicle combat as above. A drone *does* ship with its rigger interface built in (p. 265), so unlike a vehicle it needs no modification to be rigger-usable — but there is no jumping in, no autosoft slot accounting (`⌈Device Rating / 2⌉`, p. 269) and no autonomous Pilot behaviour for that to enable | WP95 |
| Commlinks (6 offerable) | Gear (`Commlinks`); **offered by today's UI** | Nuyen cost + the printed Device Rating / Data Processing / Firewall, **displayed** since WP94 | Those numbers feed nothing — this project has no Matrix rules at all, so there is no Matrix test, PAN, noise or hacking defence for them to be a limit or dice pool in (pp. 226, 438) | WP95 |
| Cyberdecks (7 offerable) | Gear (`Cyberdecks`); **offered by today's UI** | Nuyen cost + the printed Device Rating / Attribute Array / Programs, **displayed** since WP94 | Same absent Matrix rules. The Array's four values are also assigned among Attack/Sleaze/Data Processing/Firewall in play (p. 439), a choice nothing here records, and the deck's built-in hot-sim module has no simsense/VR representation | WP95 |
| Rigger Command Consoles (8 offerable) | Gear (`Rigger Command Consoles`); **offered by today's UI** | Nuyen cost + the printed Device Rating / Data Processing / Firewall, **displayed** since WP94 | Same absent Matrix rules, plus everything an RCC is actually *for*: slaving up to (Device Rating × 3) drones into a WAN, the boot-time Noise Reduction/Sharing split bounded by Device Rating, and running shared autosofts for slaved drones (p. 267). Its `<programs>` count is loaded but not displayed — SR5 core prints none for an RCC | WP95 |
| Autosofts (6, Rating-priced) | Gear (`Autosofts`); **offered by today's UI** | Nuyen cost (`Rating × 500¥`) | An autosoft is a drone's *skill* (p. 269) — Clearsight acts as its Perception, [Model] Maneuvering as its Pilot skill. No drone test resolution exists to roll one into, no autosoft slot accounting, and no way to bind a `[Model]`/`[Weapon]` copy to the drone or weapon it was bought for | WP95 |

## Architecture & major design decisions

### Stack
- **Python**, targeting a recent 3.x (specifics TBD when scaffolding — low switching cost, not a blocking
  decision).
- **FastAPI + server-rendered HTML (Jinja2) + HTMX** for the UI. Chosen over a pure-Python UI library
  (binds you to that library's widget model) and over a full SPA (React/Svelte + TypeScript — doubles
  the language/toolchain surface for a solo, agent-assisted maintainer). Chargen is fundamentally a
  forms-and-computed-values app; HTMX's partial re-renders cover the dynamic bits (live totals, dependent
  dropdowns) without a JS build pipeline.
- **pytest** for testing, with the legacy `.chum5` corpus as golden-output fixtures.

### Rules engine first, UI last
Build and validate the domain/rules layer headless — driven by pytest against golden `.chum5` outputs —
before writing UI code. The UI is a thin layer over a rules engine that must already be correct on its own.

### Data & save format
- Game rules data (`data/*.xml`) is parsed once at startup from the legacy files into indexed Python
  structures. Not re-entered, not queried live via XPath per UI action.
- The new app uses its **own save format** (not legacy `.chum5`). Legacy `.chum5` files are supported as
  **read-only import** — enough to bring a character in and to use the test corpus directly as fixtures —
  but the app never needs to reproduce legacy XML schema quirks for features it hasn't built yet. This was
  a deliberate trade against full bidirectional compatibility, which would require schema fidelity for
  Improvements/cyberware/etc. this project doesn't have.

### Improvement engine design
The legacy model — confirmed by reading the C# — is: every derived value (`attribute.Value`,
`skill.Pool`, etc.) equals a base term plus the sum of whatever `Improvement` records currently target it.
Each `Improvement` carries: its source (what granted it, and that specific instance's id, so removing the
source cleanly removes its improvements), a target key (what aspect it affects), a value/rating, an
optional dedup group (`UniqueName`, for SR5's "highest bonus wins" stacking rules), and an optional
condition. The new engine keeps this shape but changes *how it's evaluated*, based directly on where the
legacy app's performance problems live:

- **Conditions compile to typed predicates once, at construction** — not re-parsed from a string
  (regex + reflection) on every read. This is the single biggest identified perf/complexity cause in the
  legacy engine (`ImprovementManager.ValueOf` has 465 call sites, each capable of re-triggering condition
  evaluation).
- **Improvements are stored in an index** — `dict[(ImprovementType, target)] -> list[Improvement]` —
  rebuilt on mutation. Resolving a value is a lookup + sum + dedup-by-`UniqueName`, not a scan.
- **No manual per-field cache invalidation.** The legacy app clears cache entries individually on every
  field mutation of every `Improvement`. The new design recomputes the (cheap, character-sized) index on
  add/remove instead. Add caching only if profiling actually shows it's needed — the legacy caching
  complexity exists to offset reflection/regex overhead that doesn't exist in this design to begin with.

**Why `ImprovementIndex` is the one genuinely mutable object in an otherwise-frozen domain model.**
`Character` and every other engine dataclass are `frozen=True` — no field of an existing instance is
ever reassigned. `ImprovementIndex` is the deliberate exception (`add`/`remove_source` mutate
`self._improvements`/`self._index` directly). The line holds up on its own logic, not just as a
mirror of the legacy shape: fields with a *joint, shared-budget constraint* — attribute points
collectively bounded by one priority budget, each individually bounded by a metatype range — belong
in "reconstruct wholesale to validate," since checking one requires knowing the others
simultaneously. Independently-scoped, per-source deltas (a quality's flat bonus, eventually a
cyberware's) don't share that constraint — each is addable/removable on its own, with no reference to
any other Improvement — so a mutable, per-source collection is the right shape there, and making it
immutable too would buy nothing. This is the same "no manual per-field cache invalidation" principle
above, generalized: keep the mutable surface exactly as large as the actual mutation-shaped problem,
and reconstruct everything else. "Frozen," though, doesn't mean "always rebuilt from nothing" — see
the next section for how a `frozen` `Character` actually advances one stage at a time.

### Character as the single aggregate

`Character` (`chummer5.engine.character`) is the one object representing an in-progress character:
metatype and attributes, plus — once each stage is committed — `skill_allocation`,
`quality_selection`, `contact_selection`, and `resources_selection`, all as fields on the same
instance. This wasn't the original shape. Attributes arrived first (WP6), the only thing `Character`
needed to hold at the time; skills, qualities, contacts, and resources (WP7-WP9) each rode in
afterward as independent `ChargenSession` siblings, reunited only ad hoc — for save/load and legacy
import — by a since-retired `BuiltCharacter` wrapper. A design discussion held after the UI MVP
milestone found this split had no rules justification, only a build-order one (nothing about a
quality is conceptually outside "the character"), and WP18 folded everything back onto `Character`
directly. `ChargenSession` (`chummer5.web.session`) now holds only `character` plus the handful of
state that genuinely predates having one — the 4 priority letters, before a metatype is even chosen.

Advancing a committed `Character` one stage — spending more attribute points, picking a quality — is
`dataclasses.replace(character, field=new_value)` wherever the change doesn't require re-deriving
anything else about the character, not always a fresh `create_character()` call. This is more than a
convenience. `replace()` copies every untouched field *by reference*, so a `Character`'s
already-populated `ImprovementIndex` and already-committed selections simply survive a `replace()`
call with nothing to re-link — the "re-apply a quality's Improvement onto a freshly-rebuilt, empty
index" workaround this design needed before WP18/WP19 (and, for attribute-point edits specifically,
before WP63 — see Phase R's own file) is no longer needed anywhere: every chargen-mutating route
now uses `replace()`, none rebuilds via a fresh `create_character()` call. Second: `Character` has
no `__post_init__` validation — every invariant
(attribute points fit their budget, values fit the metatype's range) is enforced only by
`create_character`'s own checks at construction time — so `replace()`-ing old, now-out-of-budget
values onto a newly reconfirmed metatype/priority selection simply succeeds rather than raising.
Validity is instead re-derived at render time, by re-running the same `create_*` validators that
already exist and reading their error message rather than raising it — a stale selection surfaces a
specific "no longer fits" diagnostic next to the affected section and clears itself automatically the
moment the player edits it back into range, rather than being discarded the moment a priority letter
changes.

### Performance lessons from the legacy app
Concrete, code-grounded findings (not general "Windows is slow" hand-waving) that this project deliberately
designs away from:
1. **Improvement conditions re-evaluated at read time via regex + reflection**, not resolved once —
   see Improvement engine design above.
2. **Fine-grained but scan-heavy caching**: any cache miss re-scans the character's full improvement list;
   every mutation independently invalidates cache entries. Death by a thousand small cuts rather than one
   bottleneck.
3. **UI-tree-walking localization**: every form load recursively walks the entire control tree
   (100+ controls on non-trivial forms) and reflects into each one to set translated text, marshaled
   through the UI thread. A web UI with a normal i18n library (dictionary lookup at render time) avoids
   this class of problem by construction — one of the reasons "web UI" isn't just a portability choice
   here, it's also a performance one.

### Development environment
Development happens inside a Podman-backed VS Code devcontainer (`.devcontainer/`), not directly on the
host. The host machine for this project is Bazzite, an immutable/atomic OS not meant for ad hoc package
installs — `pip install --break-system-packages` or similar host mutations are avoided by construction,
not by discipline. The devcontainer defines the actual toolchain (Python, `uv`); reopening the workspace
in it relocates the whole VS Code extension host — including agent sessions — into the container, so this
isn't just a CI convenience, it's how day-to-day (and agent-driven) development happens here.

**Stale `.venv` console scripts.** `.devcontainer/devcontainer.json` pins `workspaceFolder` to
`/workspace`. If a session ever ends up with the repo checked out at a *different* absolute path
(seen in some agent-harness sessions, not a real "Reopen in Container" flow), `.venv/bin/{pytest,
ruff,mypy}` — small scripts with a `#!/workspace/.venv/bin/python`-style shebang baked in at
`uv sync` time — fail with a misleading `No such file or directory` even though the file is right
there. Two fixes, in order of preference:
1. Invoke tools as `uv run python -m pytest` / `-m ruff` / `-m mypy` instead of the bare command —
   this runs the venv's `python` (a symlink, not a shebang script, so it isn't affected) with `-m`,
   sidestepping the stale shebang entirely. Prefer this form generally, since it's a strict superset
   of the bare-command case.
2. If something still doesn't work, regenerate the venv (`.venv/` is gitignored, so this is always
   safe): `rm -rf .venv && uv sync --group dev`.

### Testing strategy
- `legacy/Chummer.Tests/TestFiles/*.chum5` (34 real characters) used as golden-output regression fixtures:
  build the same character (metatype/priorities/qualities/skills) through the new engine, diff computed
  values against what's recorded in the legacy save.
- Legacy unit tests (`legacy/Chummer.Tests/*.cs`) ported as intent, not mechanically translated — they
  encode expected numeric outcomes for specific rules edge cases worth keeping as pytest equivalents.
- `legacy/` is kept buildable as a reference/oracle; it does not need to run day-to-day.


## Decisions log

Dated scoping decisions, corrections, and cross-phase findings discovered during implementation live
in [decisions-log.md](decisions-log.md), not here — split out as of WP57 (Phase Q) so this file stays
a compact, current-state architecture reference rather than growing indefinitely as a changelog.
Consult it for the reasoning behind anything in this document marked as settled by a dated ruling
(e.g. Mystic Adept's exclusion, the Availability-cap simplification, the Karma-based build method's
exclusion). Anything discovered during implementation that materially changes scope, data
compatibility, or the Improvement engine's shape gets raised as a new entry there before being acted
on.
