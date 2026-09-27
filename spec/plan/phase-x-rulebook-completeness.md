[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase X — Post-MVP: closing the "Creating a Shadowrunner" gaps (planned, WP107-135)

**Why now.** Raised 2026-09-26. A gap survey walked every step of
`spec/rulebooks/character_creation_chapter.md` (core rulebook pp. 62-104) against the code as it
stands after Phase W. It checked the live catalogs and validators, not the spec documents. The user
then ruled on each gap, step by step. This phase implements those rulings. The survey itself is
summarized in `spec/decisions-log.md`'s 2026-09-26 entry; the rulings are restated here so this file
can be executed cold.

**The rulings this phase implements (and the ones it deliberately doesn't):**

| Rulebook step | Ruling | Where |
|---|---|---|
| 1 — Street-level / Prime Runner play | **Left alone for now.** Not in this phase. | — |
| 2 — Metatype & attributes | Fix all: one-attribute-at-natural-maximum on priority spend, spend-all, Exceptional Attribute / Lucky, Dwarf/Troll racial traits. | WP112, WP113, WP135 |
| 3 — Magic | Mystic Adept / Technomancer / Resonance **stay ruled out**. Fix the rest: Aspected Magician, adept skill restrictions, the 22 missing adept powers, mentor-spirit bonuses, Karma-funded Magic. | WP118-123 |
| 4 — Qualities | Fix **all** 72 unoffered core qualities, including ones whose effect is in-play only — "not just the ones with a direct effect on values in the final character sheet." | WP107-108, WP114-117 |
| 5 — Skills | Fix all except "deckers can't use Resonance skills" (Resonance is ruled out). | WP116, WP124-125, WP135 |
| 6 — Resources | Lifestyle dice roll: **a character-sheet notice only** (it happens when play starts, not during creation). 5,000¥ carryover: **display cap only**. Availability: **leave already-offered over-cap items alone, cap scalable items only**. Vehicle modifications **stay ruled out**. Fix the rest. | WP126-133 |
| 7 — Leftover Karma | Only "carry at most 7 Karma into play", **done as a display cap** like the 5,000¥ one. The per-contact 7-Karma cap stays unenforced (WP9's Yeti-fixture reason stands). | WP133 |
| 8 — Final calculations | Fix all except Living Persona (Technomancer). | WP109-111 |
| 9 — Final touches | Add the Bio page and whole-character validation. | WP134-135 |

**Finding 1 — the rulebook's "dwarf/troll gear-cost modifiers" are the Lifestyle surcharge, not a
second mechanic.** The closing Character Creation Checklist says to "make certain you have taken their gear cost
modifiers into consideration". A full-text search of the PDF finds exactly one such rule, in the Street
Gear intro (printed p. 420, raw 422): the stores that sell dwarf- and troll-sized gear are "reflected in
the Lifestyle costs for dwarfs and trolls... the troll tax — their Lifestyle costs are doubled". So
WP113's Lifestyle multiplier *is* the gear-cost modifier. There is no per-item price adjustment to
build.

**Finding 2 — "Used" grade is legal at character creation. The survey missed it.** p. 451, "Cyberware
and Bioware Grades": "Only standard, alphaware, and used implants are available for purchase at
character creation." Used is ×1.25 Essence, −4 Availability, ×0.75 cost. `cyberware.xml` and
`bioware.xml` carry the same values in their `<grades>` blocks. WP127 offers all three grades.

**Finding 3 — Notoriety at creation comes from a fixed list of qualities, and the data is one short.**
Printed pp. 368-369, "Reputation": "Each character starts off with a Notoriety of 0. Modify this
according to the following qualities... (plus one point per negative quality, minus one point per
positive quality)". Listed positives: Blandness, First Impression, Lucky. Listed negatives: Addiction,
Bad Luck, Combat Paralysis, Elf Poser, **Gremlins**, Incompetent, Ork Poser, Scorched, SINner
(Criminal), Spirit Bane, Uncouth, Uneducated, Weak Immune System. Bad Rep sets its own 3 (p. 79).
`qualities.xml` expresses all of these as `<notoriety>` bonus nodes, **except Gremlins, which has no
`<bonus>` at all**. Street Cred is "total Karma earned ÷ 10", and no Karma has been *earned* at
creation, so it is 0. Public Awareness is GM-awarded, so it is 0. The legacy engine agrees
(`Character.cs` `CalculatedStreetCred` / `CalculatedNotoriety` / `CalculatedPublicAwareness`).

**Finding 4 — several adept rules have been silently violated since Phase I.** Printed p. 69: "Adepts
cannot use skills from any magic-related skill groups (Sorcery, Conjuring, or Enchanting)" and
"Adepts can learn the Assensing skill only if they have the Astral Perception power."
`chummer5.web.catalogs.offered_skills` offers all Magical Active skills to Adepts. Its WP61 comment
reads the rule backwards ("SR5 doesn't restrict regular skill-point spend by magic type").

**Finding 5 — two catalogs need plumbing before they can grow.** Many qualities can be taken more
than once or bought at a level: 8 qualities have `<limit>False</limit>` (unlimited instances with
distinct details), and 5 are rated (Focused Concentration 6, Gremlins 4, High Pain Tolerance 3,
Magic Resistance 4, Will to Live 3). Several adept powers can be bought once per skill (Critical
Strike, Enhanced Accuracy, Improved Ability — `<limit>100</limit>`). Both
`create_quality_selection` and `create_power_selection` reject any duplicate id outright. WP107 and
WP119 widen them to *instances*.

**Finding 6 — several things this phase adds need a character-level number that doesn't exist yet.**
These are an Armor total, Overflow boxes, a wound-modifier interval, and a Damage Resistance pool.
They are consumed by Troll dermal armor, Mystic Armor, Orthoskin, Dermal Plating and Bone Lacing (the
latter two already sold and registered as unmodeled), Will to Live, High/Low Pain Tolerance, Pain
Resistance, Damage Compensators, Toughness and Bone Density. WP109 builds them once, up front.

**Out of this phase, by the rulings above:** Street-level/Prime Runner play; Mystic Adept,
Technomancer, Resonance, Living Persona, complex forms, sprites; vehicle/drone modifications; the
per-contact 7-Karma cap. Also excluded, as catalog hygiene rather than rulings (WP108 records them):
the five Karma-build "talent" qualities (`Magician`, `Adept`, `Mystic Adept`, `Technomancer`,
`Aspected Magician` — these are `CharacterBuildMethod.Karma` scaffolding, already ruled out, and not
in the chapter's quality lists); `Astral Perception` as a *quality* (Pixie-only, not core);
`Infected Advanced Optional Power: *` (critter content); the `Improved Potential (Chaos Mentor)`
power (Chaos is not a core mentor); and the four DocWagon *lifestyle* qualities (already sold as gear
since WP21).

**Two conventions every WP in this phase follows:**
- **Per-action limits are enforced when the action is taken; whole-character "finish" rules are
  reported, never enforced.** A per-action limit is one a single submission can break: the
  one-at-maximum rule, adept skill bans, prerequisites, Karma caps, Availability. The engine rejects
  it at the `create_*` validator, as every existing cap already does. A finish rule is one an
  in-progress character is *expected* to break until it's done: spend all points, pick a Lifestyle,
  carry at most 7 Karma or 5,000¥. These are reported by WP135's validation panel, and saving is
  never blocked. The existing WP19 "no longer fits" re-derivation keeps working for both.
- **Every offered aspect whose effect this engine can't compute gets an "Unmodeled real effects" row**
  (`Project Overview.md`) and its matching catalog `_UNMODELED_EFFECT_NOTES` entry, in the same
  commit. This follows the 2026-07-24 policy. Most of Step 4 is exactly this.

**Sequencing.** WP107 → WP108 unblock every quality WP. WP109 (derived-stat foundations) and WP110
(Reputation) should land before the quality, power, bioware and racial WPs that feed them. WP119
precedes WP120 and WP122. WP127 precedes WP128, and WP128 precedes WP129. WP135 lands last, so its
checklist covers everything the phase built; it deliberately doesn't try to be extensible ahead of
the rules it checks.

---

#### Foundations

- [x] **WP107 — Quality instances: levels, repeats, and per-instance choices.**
  Goal: make a quality selection a list of *instances* rather than a set of unique ids. Offer nothing
  new yet.
  Deliverables:
  - `QualityPick(quality, rating=1, text=None, choice=None)`. `QualitySelection.qualities` becomes
    a tuple of picks. `quality_text` folds into `QualityPick.text`.
  - Parse `<limit>` properly. An integer means "rated, 1..N". `False` means "repeatable". Absent or
    `True` means "once". Keep `{arm} - 1` (Ambidextrous) as "once" — no core metatype has more than
    two arms.
  - Karma for a rated pick is `cost × rating`. Both 25-Karma caps sum per pick. A repeatable quality
    rejects two instances with the same `text`/`choice` (Home Ground's "different category each
    time", p. 74, generalized).
  - `choice` is a typed slot for the select-a-thing bonus shapes that later WPs will offer
    (`selectskill`, `selectattributes`, `skillgroupdisablechoice`, `actiondicepool`, `selecttext`
    against a fixed list). This WP adds the slot and round-trips it; it doesn't interpret it.
  - Save format: bump `format_version`, migrate old `quality_ids` / `quality_text`. Legacy import:
    map `<rating>` and `<extra>` onto the pick.
  - Quality UI: a rating stepper for rated qualities, and an "add another" row for repeatables.
  Depends on: nothing new.
  Acceptance: every existing quality test passes against the new shape; a v-previous save loads; a
  synthetic Indomitable ×3 build is unchanged.

- [x] **WP108 — Quality prerequisites and catalog hygiene.**
  Goal: parse `<required>` and enforce it, so metatype- and magic-gated qualities can be offered
  correctly.
  Deliverables:
  - Parse `<required><oneof|allof>` over `<metatype>` and `<quality>`. Resolve talent names
    (`Magician`, `Adept`, `Aspected Magician`) against `Character.magic_type`. Non-core branches
    (Centaur, Naga, Pixie, Sasquatch, Infected, ...) are ignored rather than rejected.
  - Map `forbidden_names` entries that are talent names onto `magic_type` the same way. This makes
    Magic Resistance correctly unavailable to any Awakened character (p. 76).
  - **Where the rulebook and the data disagree on a gate, the rulebook wins; record each case in
    `learnings/phase-x.md`.** Known candidates to check: Spirit Affinity ("magic users only", p. 77)
    and Spirit Bane (p. 85) — the data requires spellcaster talents and may exclude Adept.
  - `mvp_quality_catalog` excludes the out-of-scope entries listed in this file's intro by name.
    The eventual offered count is asserted in a test, so a data drift is loud.
  - Priority and Talent changes re-validate committed qualities, reusing the WP19 "no longer fits"
    path (an Elf who becomes a Human keeps Human-Looking as a stale pick).
  Depends on: WP107.
  Acceptance: an Elf is offered Human-Looking and a Human is not; a Magician is not offered Magic
  Resistance; a stale gated pick surfaces a diagnostic and doesn't raise.

- [x] **WP109 — Derived-stat foundations: Overflow, wound-modifier interval, Armor, Damage
  Resistance.**
  Goal: the four character-level numbers Finding 6 lists, on the character sheet, each with an
  Improvement type later WPs can target.
  Deliverables:
  - **Overflow** = BOD + Σ `CM_OVERFLOW` (p. 101, "Body + Augmentation bonuses"). Check the legacy
    `CMOverflow` getter for whether *augmented* BOD is meant.
  - **Wound modifier**: "−1 per N boxes, first M boxes ignored". N defaults to 3; M defaults to 0.
    Add `CM_THRESHOLD` / `CM_THRESHOLD_OFFSET` / `CM_SHARED_THRESHOLD_OFFSET` types, mirroring the
    data's `<conditionmonitor>` children.
  - **Armor**: the worn armor's rating, plus stacking (`+N`) accessories, plus Σ `ARMOR`
    improvements. Offer the three stacking items WP21 excluded (Helmet, Ballistic Shield, Riot
    Shield). Add a per-item "worn" flag, defaulting to the highest-rated body armor. Research the
    accessory-over-Strength encumbrance rule (Armor section, ~p. 169) and apply it if it's a
    chargen-visible number.
  - **Damage Resistance** pool = BOD + Armor + Σ `DAMAGE_RESISTANCE`.
  - Registry rows for Bone Lacing and Dermal Plating shrink to what's still unmodeled; their Armor
    and Body-dice parts become computed.
  Depends on: nothing new.
  Acceptance: hand-computed values for a synthetic street sam with an Armor Jacket, a Helmet and
  Dermal Plating 2; the Bone Lacing and Dermal Plating registry rows are updated in the same commit.

- [x] **WP110 — Reputation: Street Cred, Notoriety, Public Awareness.**
  Goal: the Step 8 "Reputation" row, per Finding 3.
  Deliverables: a `NOTORIETY` Improvement type fed from quality `<notoriety>` nodes, plus a
  name-gated override that gives Gremlins +1. Street Cred and Public Awareness are 0 at creation,
  with a docstring citing why. A sheet block for all three. SINner (Criminal)'s registry row loses its
  "unmodeled Notoriety point" clause.
  Depends on: WP107 (repeatable Addictions each count once — check the rulebook wording for whether
  two Addictions give +2).
  Acceptance: a synthetic character with SINner (Criminal) and Bad Rep shows Notoriety 4.

- [x] **WP111 — Initiative variants: Astral and Matrix.**
  Goal: the remaining Step 8 initiative rows (Living Persona is out of scope).
  Deliverables:
  - **Astral Initiative** `INT×2 + 2D6`, shown only for characters who can astrally project
    (Magician; not Adept, not Aspected — p. 69). Decide whether an astrally *perceiving* character
    needs it too, and record that in the WP's learnings.
  - **Matrix AR** `INT+REA + 1D6` for everyone.
  - **Matrix VR** cold/hot `DataProcessing + INT + 3D6 / 4D6`, shown only when the character owns a
    device that provides it. Research (pp. 229-230, 438-439) which devices provide cold-sim and
    hot-sim VR, and which device's Data Processing is used when several are owned. Record the answer.
  Depends on: nothing new.
  Acceptance: a Magician with a cyberdeck shows all four rows; a mundane character with only a
  commlink shows whatever the research concludes.

#### Step Two — attributes and metatype

- [x] **WP112 — Attribute rules: one at natural maximum; Exceptional Attribute and Lucky.**
  Goal: close Step Two's two remaining attribute rules.
  Deliverables:
  - `create_character` rejects a priority spend **that itself** raises a second Mental/Physical
    attribute to its natural maximum. This uses the same "only when this submission touches it"
    scoping WP52 uses, to avoid the edit-something-else trap its decisions-log entry describes. A
    legacy import that already violates the rule is reported by WP135, not rejected.
  - Offer **Exceptional Attribute** (choice: any attribute but EDG, including MAG) and **Lucky** (EDG).
    Each raises that attribute's natural *and* augmented maximum by 1; they're mutually exclusive
    (already parsed). The one-at-max rule reads the *raised* maximum (the closing checklist: "or one higher with
    Exceptional Attribute").
  Depends on: WP107, WP108.
  Acceptance: the rulebook's Rob example (troll STR 11 with Exceptional Attribute) builds; two
  attributes at maximum via one priority submission is rejected.

- [x] **WP113 — Racial traits: Lifestyle multiplier, Troll Reach and dermal armor.**
  Goal: the Metatype Attribute Table's racial column, complete.
  Deliverables:
  - A `LIFESTYLE_COST` percent Improvement. Dwarf +20% and Troll +100% come from `metatypes.xml`
    `<lifestylecost>`. `LifestyleSelection.total_cost` applies Σ percent. This is also the hook for
    Dependents (WP115) and any later `lifestylecost` source.
  - Troll **+1 Reach**: a sheet line, plus a registry row (no melee resolution). Troll **+1 dermal
    armor**: an `ARMOR` improvement into WP109's total.
  - Dwarf's +2 pathogen/toxin dice are already registered — reword the row to cite the metatype.
  Depends on: WP109.
  Acceptance: a Troll's Low Lifestyle for 3 months costs 12,000¥ (the rulebook's Rob example);
  Troll Armor includes +1.

#### Step Four — qualities

- [x] **WP114 — Positive qualities: the remaining core catalog.**
  Goal: offer every remaining core positive quality, each with its computed part modeled and the
  rest registered.
  Deliverables, grouped by what each needs:
  - **Computed:**
    - Toughness (Damage Resistance +1).
    - High Pain Tolerance 1-3 (wound threshold offset).
    - Will to Live 1-3 (Overflow).
    - Photographic Memory: Memory +2. Add the Memory derived stat (`LOG + WIL`) if it isn't there —
      it's a core derived attribute, and Mnemonic Enhancer (WP128) needs it too.
  - **Choice + registry:**
    - Codeslinger (a Matrix action from a fixed list).
    - Home Ground (one of its 5 named bonuses, repeatable).
    - Spirit Affinity (a spirit type, from the tradition's spirits).
  - **Registry only:**
    - Ambidextrous, Analytical Mind, Blandness (−1 Notoriety via WP110), First Impression.
    - Human-Looking, Quick Healer, Astral Chameleon.
    - Focused Concentration 1-6 (spellcasters only).
    - Magic Resistance 1-4 (mundane only).
    - The four Resistance to Pathogens/Toxins variants. Keep Dwarf's free grant, and block buying a
      variant a Dwarf already has for free, the same way WP23 blocks Low-Light Vision.
  Depends on: WP107-110.
  Acceptance: the offered-count test from WP108 moves by exactly this list; every row has a
  registry entry or a computed test.

- [x] **WP115 — Negative qualities: the remaining core catalog.**
  Goal: the same, for negatives.
  Deliverables:
  - **Computed:**
    - Dependents ×3 (Lifestyle +10/20/30% via WP113).
    - Low Pain Tolerance (wound interval 2).
    - Addiction (Burnout)'s −3 to Social Active dice pools, which is in the data. Check the
      rulebook's Severe "−2 to all Social Tests always" against the data, which lacks it; the
      rulebook wins.
    - Loss of Confidence: −2 on a chosen skill of rating 4+, and that skill's specialization
      disabled. Validate the rating ≥ 4 at pick time, and re-validate as stale if the rating drops.
  - **Choice + registry:**
    - Addiction ×4 and Allergy ×8 (substance text, repeatable).
    - Prejudiced ×6 (target group text).
    - Scorched (effect from the p. 83 table). Check the prerequisite: a BTL Addiction, or being a
      decker. Decide how "decker" is detected (owns a cyberdeck?) and record it.
    - Spirit Bane (spirit type).
  - **Registry only:** Astral Beacon, Bad Luck, Bad Rep, Combat Paralysis, Distinctive Style,
    Elf Poser, Ork Poser, Gremlins 1-4, Insomnia (Basic/Full), Weak Immune System.
  Depends on: WP107-110, WP113.
  Acceptance: the rulebook's James/Rob/Kyra Step Four examples each reproduce their stated net
  Karma.

- [x] **WP116 — Aptitude.**
  Goal: one chosen skill may be bought to 7 at creation, with an augmented ceiling of 13 (p. 72).
  Deliverables: a per-skill purchase-cap override read by `create_skill_allocation` and
  `create_karma_skill_selection`. Keep the `MAX_SKILL_RATING_CREATE` constant as the default, and
  give `MAX_SKILL_RATING` the matching override. Remove the "Aptitude deliberately not modeled"
  comment in `engine/skills.py`.
  Depends on: WP107.
  Acceptance: Aptitude (Pistols) allows Pistols 7 and still rejects Blades 7.

- [x] **WP117 — Qualities that change purchase rules: Uncouth, Uneducated, Incompetent, Sensitive
  System.**
  Goal: the four qualities that alter what other steps cost or allow.
  Deliverables:
  - **Uncouth:** double skill-point and Karma cost for Social Active skills (the data's
    `skillcategorypointcostmultiplier` / `karmacostmultiplier`, 200%). No Social skill *groups*.
    Unaware in Social skills at rating 0 (no defaulting).
  - **Uneducated:** the same double cost and no-defaulting for Technical Active, Academic and
    Professional knowledge (p. 87).
  - **Incompetent:** a chosen Active skill group whose skills are all unaware. Reject the choice for
    Language/Knowledge, and reject buying into that group.
  - **Sensitive System:** a cyberware Essence ×2 multiplier, and bioware purchase rejected. For the
    Awakened, the Drain clause goes to the registry.
  - "Unaware" means `dice_pool` returns nothing for that skill, rather than −1 defaulting.
  Depends on: WP107.
  Acceptance: Uncouth doubles an Etiquette 3 purchase to 6 points; Sensitive System plus a 0.2-Essence
  implant costs 0.4 Essence; a bioware pick with Sensitive System is rejected.

#### Step Three — magic

- [x] **WP118 — Adept skill restrictions, and the Astral Perception power.**
  Goal: fix Finding 4.
  Deliverables:
  - Adepts cannot buy or be granted Sorcery/Conjuring/Enchanting-group skills or groups. Enforce this
    in `create_skill_allocation` / `create_karma_skill_selection` (engine), not just
    `offered_skills` (UI).
  - Assensing requires the Astral Perception power.
  - Offer the **Astral Perception** power (its `unlockskills` bonus is exactly this gate).
  - Correct the WP61 comment in `web/catalogs.py`.
  - A committed Adept selection that now violates the rule surfaces as stale (WP19 path).
  Depends on: nothing new.
  Acceptance: an Adept cannot buy Counterspelling; an Adept with Astral Perception can buy
  Assensing; the Wesson fixture still imports (check whether his skills violate the rule — if they
  do, record it rather than weaken the rule).

- [x] **WP119 — Adept powers with computed effects, and power instances.**
  Goal: power picks become instances with a typed target. Offer the powers whose effect this engine
  can compute.
  Deliverables:
  - `PowerPick.target` (attribute / skill / skill category / free text) replaces
    `selected_attribute`. Duplicates are allowed for `<limit>` > 1, each instance with a distinct
    target.
  - Offer Improved Reflexes 1-3 (REA + Initiative dice), Improved Ability (skill rating; cap per the
    power's text), Mystic Armor (WP109 Armor), and Pain Resistance (wound offset).
  - Also offer Critical Strike, Enhanced Accuracy and Killing Hands: they're a choice plus a
    registry row, but they need the target plumbing, so they land here.
  - Save format and legacy import updated for targets.
  Depends on: WP109, WP118.
  Acceptance: the rulebook's Kyra power list (Step Three worked example) builds, with the Mystic
  Adept Power Points replaced by an Adept's free ones.

- [x] **WP120 — The remaining adept powers.**
  Goal: offer the rest of the core list, as registry rows.
  Deliverables:
  - Adrenaline Boost and Attribute Boost: in-play test, Adept Drain.
  - Combat Sense, Danger Sense, Kinesics, Light Body, Missile Parry, Traceless Walk, Wall Running.
  - Improved Sense (text choice), Natural Immunity, Rapid Healing, Spell Resistance.
  - Record the 2026-07-19 decisions-log caution: Attribute Boost is *not* a permanent attribute bonus.
  Depends on: WP119.
  Acceptance: all 27 core powers (28 minus Chaos Mentor) are offerable; every non-computed one has a
  registry row.

- [x] **WP121 — Aspected Magician.**
  Goal: offer the Talent option at B/C/D (`priorities.xml` value `Aspected Magician`).
  Deliverables:
  - `OFFERED_TALENT_CODENAMES` gains it. The talent needs a group choice (Sorcery, Conjuring or
    Enchanting) from `<skillgroupchoices>`, and the free grant is a *skill group* (`skillgroupqty` /
    `skillgroupval`, "grouped") — a new grant shape.
  - Skills from the other two groups are forbidden, forever (Step Three). Counterspelling is only
    available to a Sorcery aspect (Step Three).
  - Spells only for Sorcery; bound spirits only for Conjuring. Decide foci/alchemy for Enchanting,
    and record the decision.
  - No astral projection, so WP111's Astral Initiative doesn't apply.
  - Traditions, mentor spirits and drain work as for a Magician. Check the stale-selection matrix for
    a Magician → Aspected switch.
  Depends on: WP118.
  Acceptance: a Priority B Aspected (Conjuring) Magician gets Conjuring 4 free, can bind spirits,
  and can't pick spells.

- [x] **WP122 — Mentor spirit bonuses, complete.**
  Goal: apply every core mentor slot. Today 17 of 48 are applied.
  Deliverables:
  - **Adept slot:** free power levels granted outside the Power Point budget (`specificpower`), using
    WP119's pick shape with a `granted_by` source.
  - **Magician slot:** `spellcategory` dice bonuses, shown as conditional pools on the sheet, the
    same way WP40 shows conditional limits.
  - **General slots:** Bear's damage resistance (WP109); Dragonslayer's `selectskill` (a choice);
    Eagle's `addqualities` (auto-grant Allergy (pollutants, Mild) as a mentor-sourced quality at
    0 Karma).
  - Mentor *disadvantages* get registry rows.
  Depends on: WP109, WP115 (Allergy), WP119, WP120.
  Acceptance: an Adept following Bear or Eagle gets a non-empty applied bonus; the "applies nothing
  at all" note in `data/mentors.py` is gone.

- [x] **WP123 — Karma-funded Magic increases.**
  Goal: Step Seven Karma can raise MAG (`new Rating × 5`, p. 106), like any other attribute.
  Deliverables: extend `KarmaAttributeSelection` to MAG for Magician/Adept/Aspected. **Research
  first** how Karma-raised MAG interacts with WP35's Essence-driven Magic loss. The questions are
  whether the loss reduces the *maximum* or the rating, and whether raising MAG after an implant
  costs against the reduced value. Check the rulebook (p. 278) and the legacy engine, and record
  the answer. Power Points follow MAG for Adepts. Exceptional Attribute (MAG) from WP112 is
  respected.
  Depends on: WP112.
  Acceptance: a Magic 4 Adept raising MAG to 5 pays 25 Karma and gets 5 Power Points.

#### Step Five — skills

- [x] **WP124 — Exotic skills per specific weapon or vehicle.**
  Goal: Exotic Melee Weapon, Exotic Ranged Weapon and Pilot Exotic Vehicle are bought per named item
  (p. 90: "(Specific)"), as separate skills.
  Deliverables: skill allocation keys become `(skill_id, specific)` for exotic skills, with
  `specific` required and free text. Several instances of one exotic skill are allowed. Skill groups
  are unaffected (no exotic skill is grouped). Save format, legacy import (`<specific>` / `<name>`
  in the `.chum5` skill node) and UI all updated.
  Depends on: nothing new.
  Acceptance: a character with Exotic Ranged Weapon (Flamethrower) 3 and Exotic Ranged Weapon
  (Harpoon Gun) 2 round-trips.

- [x] **WP125 — Knowledge and Language completion.**
  Goal: the three Knowledge/Language gaps.
  Deliverables:
  - Active-skill priority points may fund Knowledge/Language ranks (p. 88), from the one shared
    Active pool, after the free (INT+LOG)×2 pool is used.
  - Karma can buy a **new** Knowledge/Language skill from rating 0 (`new Rating × 1`).
  - Knowledge/Language **specializations**: 1 skill point at creation, 7 Karma in Step Seven, one
    per skill. Language specializations follow the same rule.
  Depends on: nothing new.
  Acceptance: the rulebook's Rob example ("Dakota language to 2 (2 Karma)", Step Seven worked
  example) and a point-funded knowledge rank both build.

#### Step Six — resources

- [x] **WP126 — Availability and Device Rating caps for scalable items.**
  Goal: per the Step 6 ruling, **leave already-offered flat items that exceed Availability 12 as
  they are**; cap only the items whose rating scales their Availability.
  Deliverables:
  - Rating-scaled cyberware (`Rating * N` Availability, e.g. Muscle Replacement, Reaction Enhancers,
    Cybereyes) gets its maximum purchasable rating clamped so Availability ≤ 12. Reuse
    `parse_rating_availability`.
  - **Device Rating ≤ 6** (Step Six) for rating-priced gear whose rating *is* its Device Rating (the
    electronics categories: Sensors, Sensor Housings, Vision/Audio devices, ...). Arrows, explosives
    and other non-device ratings are untouched. Sensor Array and Single Sensor lose ratings 7-8.
  - Record in `decisions-log.md` that the flat over-cap items stay offered by ruling. This retires the
    Project Overview's standing "flagged, not scheduled" backfill note.
  Depends on: nothing new.
  Acceptance: Muscle Replacement offers ratings 1-2 only (5×R R); Single Sensor tops out at 6.

- [x] **WP127 — Implant grades: Standard, Alphaware, Used.**
  Goal: per Finding 2.
  Deliverables:
  - A grade on each cyberware and bioware purchase, applying the Essence / cost / Availability
    adjustments (p. 451; data `<grades>`). Plugins inherit their parent's grade ("all accessories and
    add-ons must be of the same grade", p. 451).
  - **Availability interaction:** the grade-adjusted Availability counts toward the cap for scalable
    items. A fixed-Availability item already over 12 stays offered at Standard only, and doesn't gain
    an over-cap Alphaware option.
  - Legacy import stops rejecting non-Standard grades. It recomputes Essence and cost from the grade
    rather than trusting the stored fields (the WP32 finding).
  Depends on: WP126.
  Acceptance: an Alphaware Datajack costs 0.08 Essence and 1,200¥; a Used one costs 0.125 Essence and
  750¥; a Bone Lacing (Titanium) offers Standard only.

- [ ] **WP128 — Rating-scaled bioware.**
  Goal: offer the 15 rating-scaled core bioware items, reusing `chummer5.data.cyberware_formula` for
  cost, Essence and Availability.
  Deliverables:
  - **Computed:**
    - Muscle Toner / Augmentation (AGI/STR, mutually exclusive via `unique="muscle"`).
    - Cerebral Booster (LOG).
    - Synaptic Booster (REA + Initiative dice; doesn't stack with Wired Reflexes — check the data's
      `precedence`).
    - Tailored Pheromones (Social limit, plus a conditional Acting bonus).
    - Mnemonic Enhancer (Memory, Mental limit, Academic/Language/Professional knowledge bonus).
    - Synthacardium (Athletics group bonus — a new `skillgroup` bonus shape).
    - Orthoskin (Armor), Bone Density (Damage Resistance + unarmed registry).
    - Damage Compensators (shared wound offset).
  - **Registry:** Adrenaline Pump, Pathogenic Defense, Symbiotes, Toxin Extractor, Tracheal Filter.
  - Pain Editor and Suprathyroid Gland stay excluded: fixed Availability over 12, and never offered.
    Record that under WP126's ruling.
  Depends on: WP109, WP126, WP127.
  Acceptance: Muscle Toner 2 raises AGI by 2 under the +4 augmentation cap; Toner plus Augmentation is
  rejected; Orthoskin 2 shows in Armor.

- [ ] **WP129 — Implants that replace racial traits.**
  Goal: Step Six, "Cyberware/bioware may remove a racial bonus."
  Deliverables:
  - Cybereyes suppress a metatype-granted Low-Light / Thermographic Vision unless the matching
    Vision Enhancement / Low-Light / Thermographic plugin is installed.
  - Orthoskin *replaces*, rather than stacks with, a Troll's +1 dermal armor. Confirm against the
    Armor rules, and against how the legacy engine handles `<armor group="0">`, whether the higher
    value wins or they're exclusive.
  - Look for any other core replacement pair (cyberears vs. nothing core?). Record what's found.
  - A suppressed racial quality renders struck through on the sheet, with the reason.
  Depends on: WP113, WP128.
  Acceptance: an Elf with Cybereyes Basic System and no Low-Light plugin loses Low-Light Vision on
  the sheet; adding the plugin restores it.

- [ ] **WP130 — Weapon accessories.**
  Goal: the 30 core weapon accessories (smartgun system, silencer, scopes, ...), installed on a
  purchased weapon.
  Deliverables:
  - A weapon-purchase tree like WP38's cyberware tree, with mount slots (top / under / barrel …)
    from the weapon's `<accessorymounts>`, and each accessory's `<mount>`.
  - Accessories a weapon ships with (`<accessories>` on the weapon) are included at no cost.
  - Registry rows: there are no attack tests.
  - Availability ≤ 12 for new picks.
  Depends on: nothing new.
  Acceptance: an Ares Predator V with a silencer and a smartgun system round-trips, and a second
  barrel-mount accessory is rejected.

- [ ] **WP131 — Armor modifications, Clothing, and the remaining excluded gear.**
  Goal: the 32 core armor mods, plus the handful of core gear rows WP21 excluded by cost shape.
  Deliverables:
  - Armor mods consume an armor's Capacity (`<armorcapacity>`), priced flat or by rating. Computed
    ones feed WP109 (e.g. a mod that adds Armor); the rest get registry rows.
  - **Clothing** (`Variable(20-100000)`): the player enters a price within the range.
  - The 2 `FixedValues` and the other `Variable` gear rows get the same treatment.
  - The 2 `+N` accessory rows attach to a parent commlink/device.
  Depends on: WP109.
  Acceptance: an Armor Jacket with Fire Resistance 2 within Capacity; Clothing at 500¥.

- [ ] **WP132 — Lifestyle options: qualities, roommates, permanent purchase.**
  Goal: the three Lifestyle features WP20 deferred.
  Deliverables:
  - The 5 core lifestyle qualities: Cramped, Dangerous Area, Obscure/Difficult to Find, Extra
    Secure, Special Work Area. Their cost/multiplier effects are applied, and their LP effects are
    shown. The DocWagon lifestyle rows are excluded (they're sold as gear).
  - Roommates split the monthly cost per the Lifestyle chapter's rule (pp. 369-373) — research the exact formula.
  - "Buy permanently" = 100 months' upkeep (p. 370), replacing the month count.
  - The WP113 percent multipliers apply to the final monthly cost.
  Depends on: WP113.
  Acceptance: a permanent Troll Low Lifestyle costs 400,000¥; Cramped reduces a Middle Lifestyle by
  10%.

- [ ] **WP133 — Carryover and starting-nuyen notices.**
  Goal: the two display caps and the dice-roll notice, per the Step 6/7 rulings. None of this
  changes a spendable number during creation.
  Deliverables:
  - **Nuyen:** the character sheet shows carried-over nuyen as `min(remaining, 5,000¥)`, with a note
    when it's capped ("N¥ over the carryover limit will be lost"). The sidebar resource panel keeps
    showing the true remaining amount, so the player can still see what's left to spend.
  - **Karma:** the same, for `min(karma_remaining, 7)`.
  - **Starting nuyen:** a sheet notice, "Roll {n}D6 × {m}¥ for starting nuyen when play begins,
    plus the carried-over nuyen", with the formula taken from the purchased primary Lifestyle's tier
    (Step Six's Starting Nuyen table). No rolling in-app.
  - Research whether the dice formula follows the Lifestyle *tier* or the tier after permanent
    purchase/roommates, and record the answer.
  Depends on: WP132 (tier source), otherwise nothing.
  Acceptance: the rulebook's James example shows 4,995¥ carried over and "4D6 × 100¥"; a character
  with 12 Karma left shows 7 on the sheet with a loss note.

#### Step Nine — final touches

- [ ] **WP134 — The Bio page.**
  Goal: enable Phase W's disabled "Bio" nav entry with a real data model.
  Deliverables:
  - A `Biography` field on `Character`: name, street name/alias, player name, concept, sex, age,
    height, weight, eyes, hair, skin, description, background, notes. These mirror the legacy
    `.chum5` fields so legacy import can fill them.
  - An htmx form page, a save-format bump, and legacy import mapping.
  - The character sheet header shows the street name (falling back to the name) and the concept.
  - Every string goes through the WP102 i18n layer.
  - No mugshot in this WP (it would need binary storage in the save format); record that as
    deferred.
  Depends on: nothing new.
  Acceptance: the Bio nav entry is enabled; a Bio round-trips through save/load; a legacy `.chum5`
  alias appears on the sheet.

- [ ] **WP135 — Character validation: the rulebook's closing checklist.**
  Goal: one validator that reports every whole-character rule (the chapter's closing Character Creation Checklist), so the player
  knows when the character is finished.
  Deliverables:
  - `chummer5.engine.validation.validate(character, session_letters) -> tuple[Issue, ...]`. Each
    issue has a severity (`error` = a rule is broken; `warning` = something expected isn't done yet),
    a step slug for nav routing, and an i18n message key.
  - **Checks:**
    - Every priority row used once (or Sum-to-Ten totals 10).
    - All attribute points spent.
    - Special Attribute points unspent: a warning, since they "disappear".
    - All skill and skill-group points spent.
    - At most one attribute at natural maximum (catches imports and stale states WP112 can't reject).
    - Quality caps.
    - A primary Lifestyle chosen.
    - Nuyen over budget; Karma negative.
    - No contacts: a warning.
    - Every existing WP19 "no longer fits" diagnostic.
    - The checks a save or import skips because they need a later step: Loss of Confidence's
      rating 4+ and Scorched's prerequisite (WP115, `LaterStepFacts`), and an Adept's free-skill
      grant naming Assensing without the Astral Perception power (WP118).
    - An Aspected Magician Incompetent in one of the two groups it can never learn (WP121).
  - The WP133 carryover notes are *informational*, not issues.
  - An Export-page panel lists the issues grouped by step, with links. The nav's existing `--stale`
    marker widens to "has validation issues". The title bar shows "✓ Complete" or "N issues".
  - Saving and export are never blocked.
  Depends on: every other WP in this phase, for full coverage. The framework itself has no
  dependency, so it can be started earlier if convenient.
  Acceptance: a fresh character lists the expected unspent-points warnings; the rulebook James
  example, fully entered, validates clean; Yeti's over-cap contact does **not** appear (that rule
  stays unenforced).
