"""Legacy `.chum5` import: turns WP4's raw-field `LegacyCharacter` into a real, buildable character
through this project's own machinery (WP11's `CharacterSave` + `build_character()`), for MVP-covered
content only. Read-only, one-way (legacy -> native), per the Project Overview's "Data & save format"
section — the new engine never needs to write legacy XML back out.

**Two different responses to "this file has content MVP doesn't model", not one.** WP3/WP8 already
established the precedent for one shape of this problem (a quality whose `<bonus>` isn't a flat
skill/attribute bonus is excluded from the *offered* catalog, not silently mis-applied); this module
extends the same "exclude cleanly, never half-apply" discipline to *importing an existing
character's selections*, but splits it into two tiers by how much it actually distorts the imported
result:

- **Excluded and reported, not fatal.** A quality the character already has that isn't one of WP8's
  3 MVP-offered (`FLAT_BONUS`) qualities (e.g. Yeti's own Technomancer/Infirm/Impassive/Paranoia/
  Faceless/Data Anomaly — none overlap the offered catalog, confirmed in WP9/WP10) is dropped from
  the imported `CharacterSave`, and its name is collected in `ImportResult.dropped_qualities` so the
  caller can show the player exactly what didn't come across, instead of the import silently
  producing a character with fewer qualities than it should have with no indication why. Same
  treatment for a skill whose `<suid>` doesn't resolve against the loaded skill catalog
  (`ImportResult.dropped_skills`) — in practice this doesn't fire for any curated fixture (every
  `skills.xml` entry is `source == "SR5"`, so every legitimate active-skill `<suid>` resolves), but
  the reporting exists for the same "don't let something vanish with no trace" reason. **WP28**
  extends this same treatment to a Magician's spells (`ImportResult.dropped_spells` — a spell has no
  chargen-time computed effect, so dropping one that isn't `source == "SR5"` loses nothing an
  MVP-covered value depends on, mirroring the quality/skill precedent exactly) and an Adept's powers
  (`ImportResult.dropped_powers` — a power not in `mvp_power_catalog` (non-SR5-sourced, or SR5 but
  `NOT_YET_SUPPORTED`) is dropped the same way an unsupported quality is, not half-applied).
  **WP50** adds one more: a `<skill><specs><spec>` entry whose host skill either doesn't reach
  `skill_points` at all (group-purchased, karma-only `base <= 0`, or an unresolvable `<suid>`) or is
  a second-or-later specialization on one skill (this project only models Step Five's "one
  specialization per skill" rule) is excluded and collected in
  `ImportResult.dropped_specializations`, formatted `"{skill name}: {specialization name}"`.
  Confirmed against real corpus data: `Yeti-#ffffff2.chum5` (this project's one full-round-trip
  Priority fixture) has 6 real specializations recorded, 5 of which import cleanly
  (Compiling/Cybercombat/Hacking/Registering/Software, all individually purchased) and 1 of which is
  dropped for exactly this reason (Computer's own "Matrix Perception" — Computer's `<base>` is 0,
  only `<karma>` is nonzero, so Computer itself never reaches `skill_points` per the pre-existing
  "karma-bought skill points are out of scope" cut — see `chummer5.engine.skills`'s module docstring
  — and a specialization can't be imported for a skill
  that wasn't imported).
- **Blocking, itemized, fatal.** Content that would make an *already-imported* value silently wrong,
  not just incomplete, is rejected outright via `UnsupportedLegacyCharacterError` before any
  selection is built at all: a build method outside `chummer5.engine.build_method
  .SUPPORTED_BUILD_METHODS` (Karma/LifeModule stay unsupported per the Project Overview's explicit
  2026-07-21 ruling — MVP's engine only understands priority-letter budgets, which neither of those
  two build methods use at all), a non-`Standard` `<gameplayoption>` (WP2's
  `load_priorities()` only loads the Standard resources table, so a Prime Runner/Street Level
  character's nuyen budget would silently resolve to the *Standard* table's number for the same
  letter — wrong, not just incomplete), a metavariant (out of MVP scope per WP6's metatype filter --
  the base metatype's attribute ranges the rest of the import would use don't apply to it), and
  (WP20) a primary Lifestyle that's either missing entirely or not one of the 6 core-rulebook
  starting tiers `chummer5.data.lifestyle` offers -- silently defaulting to a tier the character
  never actually chose (e.g. free "Street") would misrepresent a real nuyen spend, not just omit
  one, so this is blocking rather than excluded-and-reported like a dropped quality/skill. **WP28**
  replaces the old blanket "Magic is enabled" rejection with two narrower, itemized checks fired
  only when `legacy.magic_enabled`: a Talent codename outside this project's offered set
  (`chummer5.engine.magic.OFFERED_TALENT_CODENAMES` — Mystic Adept/Technomancer/A.I./Aspected
  Magician/etc. are all still unrepresentable, exactly as unbuildable as before, just with a precise
  reason now); and, Magician-specific, a tradition name that isn't one of the 2 SR5-core traditions
  this phase offers (Hermetic/Shamanic) — unlike a dropped quality, there is no sensible "import
  without a tradition" fallback for a Magician (`chummer5.engine.magic.create_magic_selection`
  itself requires one), so an unresolvable tradition blocks the whole import rather than being
  silently dropped. **Confirmed against this phase's own two real fixtures**: Miko (Elf Magician)
  hits exactly this second check — her tradition, Shinto, is `SG`-sourced, not one of the 2 offered
  — so she is *still* rejected after this WP, just with an honest, specific reason instead of a
  blanket one (see `spec/worklogs/WP28.md` for why this corrects the Implementation Plan's own more
  optimistic acceptance text). Wesson (Human Adept) needs no tradition at all and imports cleanly.
  **WP33** replaces the old blanket "character has cyberware/bioware" rejection with a real,
  itemized check per real `<cyberwares><cyberware>` entry
  (`chummer5.io.legacy_chum5.LegacyCyberware`): a Bioware entry
  (`improvement_source == "Bioware"`) is always rejected by name, since no Bioware catalog exists at
  all yet; a Cyberware entry is rejected by name+grade unless it resolves against WP31's
  flat-cost/flat-Essence, Standard-grade-only catalog (`chummer5.data.cyberware.load_cyberware`) --
  a non-Standard grade is rejected even when the item's *name* matches a catalog entry, because a
  real fixture check (`spec/worklogs/WP32.md`) found the legacy save format stores a Standard-grade
  item's raw `<ess>`/`<cost>` fields unchanged regardless of the grade actually purchased (the grade
  multiplier is applied at read time, not baked into the stored fields) -- silently treating a
  non-Standard purchase as Standard grade would misrepresent the real Essence/nuyen cost the
  character actually paid, not just approximate it. Per the Phase J intro, most real cyberware
  content across the corpus's cyberware-bearing fixtures hits this rejection (rating-scaled formulas
  and non-Standard grades are the common case, not the exception) -- see
  `spec/worklogs/WP33.md`/`tests/integration/test_cyberware_import_fixtures.py`. **WP45** now
  resolves a Bioware entry the identical way a Cyberware entry already was, against
  `chummer5.data.bioware.load_bioware`'s own flat-cost/flat-Essence/low-Availability/Standard-grade
  catalog, rather than the blanket by-name rejection above -- 6 of the 11 curated mundane fixtures
  turn out to carry real Bioware (`Barrett`, `Bastion`, `Blindfire`, `Fuzzy-chargen`,
  `Gentle Earthquake`, `SCSi` -- a correction to this WP's own Implementation Plan entry, which
  claimed "no fixture ... carries real bioware"; see `spec/worklogs/WP45.md`), giving this itemized
  check real positive-case coverage (`Barrett`'s Reflex Recorder/Sleep Regulator/Platelet Factories,
  all Standard grade) alongside negative cases (rating-scaled Bioware, and Bioware bought at a
  non-Standard grade, e.g. `Bastion`'s Platelet Factories at `Used` grade).
  **WP41 makes this check recursive and widens the catalog it runs against.** WP33 read only
  top-level `<cyberware>` entries, because nothing downstream could receive a nested purchase;
  Phase K's `chummer5.engine.cyberware_subsystems` now models a purchase *tree*, so each nested
  `<children><cyberware>` is resolved and itemized independently, exactly the way a top-level entry
  already was. The catalog moves with it, from WP31's 60-row flat-only `load_cyberware()` to WP37's
  full 87-row `chummer5.data.cyberware_subsystems.load_cyberware_entries()` -- a rating-scaled row
  (`Cybereyes Basic System`, `Vision Enhancement`, `Customized Agility`) is exactly what Phase K
  built a formula resolver for, so "rating-scaled" is no longer a rejection reason at either level.
  Non-`SR5` source and non-Standard grade still are, at both levels. Two consequences worth naming:
  a **nested Bioware entry is rejected outright** (bioware-in-a-cyberlimb is a real SR5 mechanic --
  p. 456's "Bodyware with a Capacity cost can be installed in cyberlimbs" -- but this project has no
  Bioware Capacity data, and no fixture in the corpus exercises it: zero nested entries carry
  `improvementsource == "Bioware"`); and the *structural* rules (a plugin's category being one its
  parent accepts, the parent's Capacity budget, a rating inside the item's own bounds) are
  deliberately **not** re-implemented here -- they surface from `create_cyberware_tree_selection`
  during `build_character`, the same place an over-budget nuyen spend has always surfaced from.
  `UnsupportedLegacyCharacterError.reasons` collects *every* blocking issue found in one pass, not
  just the first, so a caller gets one itemized report rather than a fix-one-rerun-find-the-next
  loop. **WP44** widens the build-method check above from "Priority only" to "Priority or
  Sum-to-Ten" (`chummer5.engine.build_method.SUPPORTED_BUILD_METHODS`) and adds one more itemized
  check alongside it: any of the 5 `<priority*>` categories whose raw field doesn't resolve to a
  real A-E letter (`chummer5.io.legacy_chum5.priority_letter` returning `""` or something outside
  A-E) blocks the import outright, rather than reaching `create_skill_allocation`/`create_character`
  and crashing with a `KeyError` on a blank dict lookup. This is a real, if latent, gap the
  build-method widening newly makes reachable: confirmed directly against the corpus, every one of
  the 11 curated mundane fixtures whose Talent codename is "Mundane" *and* build method is
  `SumtoTen` (`BLUE`, `Barrett`, `Blindfire`, `Fuzzy-chargen`, `Gentle Earthquake`, `Monomax
  (approved) 3`) has a blank `<priorityskills>` scalar -- a genuine legacy save-format quirk (see
  `spec/rulebooks/learnings.md`'s WP44 entry), not a parser bug -- that only a Priority-only import
  gate had been hiding. None of those 6 fixtures actually reaches this new check in isolation today
  (each already hits an unrelated, pre-existing blocker -- cyberware, bioware, or a karma-bought
  attribute), so this check's own acceptance is necessarily synthetic/hand-verified rather than
  fixture-backed, the same honesty caveat WP44's own Implementation Plan entry anticipated for the
  Sum-to-Ten rule itself, just for a different, more specific reason.

**Deliberately not imported at all: `<spirits>` (bound spirits, WP46).** `chummer5.io.legacy_chum5
.LegacyCharacter` has no parsing for a `.chum5`'s `<spirits>` container, so any real bound spirits a
legacy character has are silently absent from the import today — flagged here rather than fixed,
mirroring this project's Availability-cap precedent ("flagged, not scheduled") rather than the
excluded-and-reported treatment above, because there is currently no live fixture this gap actually
affects: only a Magician can have bound spirits (see `chummer5.engine.spirits`'s module docstring),
and of this project's two magic-capable Priority-built fixtures, Miko is rejected outright before
reaching this point (her tradition isn't one of the 2 offered) and Wesson is an Adept (never has
any). A future WP adding real `<spirits>` parsing should upgrade this to the excluded-and-reported
tier instead, the same way WP28 already did for spells/powers.

**Deliberately not imported either: bonded foci (WP47).** A legacy `<gear>` entry with `<bonded>
true</bonded>` is how the legacy save format records a bonded focus, but this module never parses
`<gears>` at all -- the same "no general gear-catalog import" gap `gear_names=()` below already
documents for ordinary Step Six gear, now extended to Foci for an identical reason (no fixture in
this project's curated corpus needs it reconstructed, and building a real `<gear>` parser is a
separate, much larger undertaking than this one-line gap). `foci_picks` is simply never passed to
`create_character_save` here, defaulting to `()` the same way `bound_spirit_picks` already does.

**Deliberately not imported either: the Mentor Spirit archetype pick (WP48).** `chummer5.io
.legacy_chum5.LegacyCharacter` has no parsing for a `.chum5`'s `<mentorspirit>` element, so a real
character's picked archetype can't be recovered even if the "Mentor Spirit" quality itself were
let through. Nothing changes here as a result: `offered_qualities` above is still built from
`mvp_quality_catalog(qualities)` (unchanged by WP48 -- only `offerable_quality_catalog`, a
per-character widening this function has no live `Character` to call with at this point in the
pipeline, gained Mentor Spirit), so a legacy `qualitysource != "Metatype"` Mentor Spirit pick
continues to land in `dropped_qualities`, the ordinary excluded-and-reported path every other
not-yet-importable quality already takes -- correct behavior, not a gap, since there would be
nothing to attach an archetype to even if the quality itself were accepted. Mirrors WP46/47's
"flagged, not scheduled" treatment: no fixture in this project's curated corpus has a real,
selected Mentor Spirit to exercise this either way (see Phase M's own intro in the Implementation
Plan). A future WP adding real `<mentorspirit>` parsing should upgrade this the same way WP28
upgraded the old blanket magic rejection into itemized spell/power drops.

**Knowledge/Language skills (WP49): imported faithfully, but no fixture in the corpus records a
native language at all.** Every `<newskills><knoskills>` entry becomes a `KnowledgeSkillPick`
(Academic/Interest/Professional/Street) or `LanguageSkillPick` (Language), keyed on the same
`<skillcategory>` the save itself uses -- no dropping/reporting tier is needed here (unlike
qualities/skills/spells/powers) since names are freeform, not catalog-matched. `native` reads
straight from `LegacyKnowledgeSkill.native` (`<isnativelanguage>`, WP49) -- which happens to be
`False`
for every entry in every fixture this project's own corpus has, since all three Priority-built
fixtures (`Yeti-#ffffff2.chum5`, `Miko.chum5`, `Wesson.chum5`) predate that field's introduction in
the legacy engine (see `chummer5.io.legacy_chum5.LegacyKnowledgeSkill`'s own docstring and
`spec/rulebooks/learnings.md`'s WP49 entry). A real, honest gap, not a bug: a legacy character's
native language(s) cannot be recovered from any fixture this project has, so an imported
character's `knowledge_selection` never marks one native even when the source character clearly
has one (e.g. Yeti's own "English" entry, recorded at `<base>0</base>` with no native flag at all)
-- that specific entry is simply excluded by the ordinary `base <= 0` skip (see the code below),
the same filter that already excludes a real placeholder-empty `<skill>` entry (confirmed present
in `Wesson.chum5`).

**Which `<lifestyle>` entry counts as "primary" (WP20).** The legacy save format has no explicit
"is this the primary Lifestyle" flag (confirmed: no such field exists anywhere in `Lifestyle.cs`,
only a general `LifestyleType.Standard` -- see `spec/rulebooks/learnings.md`'s WP20 entry). This
module treats the *first* `<lifestyle>` child in document order as primary, matching every one of
the 11 curated mundane fixtures (including `BLUE.chum5`, the only one with more than one entry --
its in-scope Medium tier appears first, its out-of-scope `RF`-sourced "Bolt Hole" second). A
character's other, non-primary lifestyles (if any) are simply not imported -- consistent with the
core rulebook's own framing of them as optional extras beyond the one mandatory primary choice.

**Deliberately not blocking: `<resenabled>True</resenabled>` (Resonance/Technomancer).** This is the
one place this module's scope cut doesn't match the Project Overview's "no magic/resonance" MVP
framing literally. `Yeti-#ffffff2.chum5` — this project's sole `buildmethod == Priority` fixture and
therefore the only real corpus member this import path can exercise past the build-method gate — is
itself a Technomancer (`resenabled == True`). WP6-WP10 already set this precedent repeatedly: they
build a `Character` from Yeti's data by simply never consuming anything Resonance-specific (RES
isn't in `ALLOCATABLE_ATTRIBUTES`, no Resonance-linked skill gets special handling, the
Technomancer quality isn't MVP-offered so it's excluded the same as any other unsupported quality).
Import follows the same rule rather than inventing a stricter one Yeti itself couldn't pass:
nothing about a Technomancer's *mundane-shaped* subset of data (metatype, primary attributes,
active skills, karma, nuyen, contacts) is silently wrong by ignoring Resonance — unlike cyberware,
there's no MVP-computed value Resonance content would corrupt if left unconsumed.

**WP52 retires the karma-bought-attribute blocking check for `ALLOCATABLE_ATTRIBUTES`, now that
`chummer5.engine.character.create_karma_attribute_points` actually models chargen-time Karma spend
on Mental/Physical/Edge attributes.** WP28's own blocking check (see the "blocking, itemized,
fatal" tier above) rejected *any* nonzero `<attribute><karma>` on an allocatable attribute --
correct at the time (the mechanic didn't exist). Now `legacy.attributes[code].karma` for each
`ALLOCATABLE_ATTRIBUTES` code feeds `CharacterSave.karma_attribute_points` instead of being
rejected outright, and `build_character` validates it the normal way (against the Karma ledger,
the metatype maximum, and the "only one Mental/Physical attribute at natural maximum" rule).
**MAG's own `<karma>` field stays blocked** -- WP52 deliberately does not extend Karma-funded
attribute increases to MAG/RES (see `chummer5.engine.character.KarmaAttributeSelection`'s own
docstring for why), so a magic-active character with Karma-bought Magic is still rejected, just
under a narrower, MAG-specific reason than before.

**`Wesson.chum5` still cannot reach a full end-to-end import after WP52 -- a second, previously-
invisible gap this WP's own research surfaced, distinct from the one it fixes.** His real EDG
Karma-buy (rating 3 -> 4) legitimately costs 20 Karma (`(3+1) x 5`, confirmed against the legacy
engine's own `CharacterAttrib.UpgradeKarmaCost` formula, `Attribute.Core.cs` -- the Standard
`AlternateMetatypeAttributeKarma` houserule that would otherwise discount this is `False` by
default, so the plain formula applies). His real character could afford it because his real
`<qualities>` block includes `SINner (Corporate Limited)` (a Negative quality worth Karma value
-15, i.e. a +15 Karma credit) -- but SINner is not, and per WP22's own scoping deliberately never
will be, one of this project's MVP-offered qualities (its background-check/social-consequence
weight is unmodeled narrative content, not a chargen-time computed value -- see WP22's own
"deliberately deferred" list). Every unsupported quality a legacy character has was already
silently excluded from the reconstructed `quality_selection` (WP8's "excluded, not silently
mis-applied" rule) -- including, before now, its Karma-cost side effect -- but nothing was Karma-
budget-sensitive enough for that omission to actually block an import until WP52 added a
Karma-spending consumer expensive enough to need it. Confirmed by direct calculation: without
SINner, Wesson's reconstructed `character.karma_remaining` before the EDG purchase is 15 (`25 -
10` for the one MVP-offered quality he keeps, Guts); the purchase itself costs 20; with SINner's
real -15 Karma value included it would be 30, comfortably enough. This is not a WP52 bug -- it's
the same "corrects the Implementation Plan's own more optimistic acceptance text" situation WP28
already hit for Miko, just discovered one WP later and via a different mechanism (a Karma-budget
`ValueError` bubbling out of `build_character`, per this module's own "any create_* rejection
surfaces unchanged" rule below, rather than an itemized `UnsupportedLegacyCharacterError`). See
`tests/integration/test_magic_fixtures.py`'s WP52 test for the exact assertion, and this WP's own
worklog for why fixing SINner's exclusion is out of this WP's scope.

**WP55 resolves the SINner gap above -- `Wesson.chum5` now reaches a full end-to-end import.**
SINner (Corporate Limited) and 8 other previously-`NOT_YET_SUPPORTED` qualities are now
`BonusSupport.SELECT_TEXT` and offered (see `chummer5.data.qualities`'s module docstring), so the
quality-resolution loop above picks them up like any other offered quality -- the only new step is
resolving each one's own `<extra>` (the same free-text field `LegacyPower.extra` already threads
through for select-attribute powers) into the pick's text (WP107: `QualityPickRequest.text`).
No itemized check was added for a SELECT_TEXT quality with a blank `<extra>` (none of the curated
corpus's real instances have one) -- if one ever did, `build_character`'s own `create_quality_
selection` call would reject it with a plain `ValueError`, the same "any create_* rejection surfaces
unchanged" fallback this module already relies on elsewhere (see the paragraph below).

**Import validates by actually building, not just by shape.** `import_chum5`/
`import_legacy_character` call straight into WP11's `build_character()` before returning, so
"successfully imports" means "this `CharacterSave` reconstructs into a real `Character` (carrying
its own `skill_allocation`/`quality_selection`/`contact_selection`/`resources_selection`, per WP18's
fold) that passes every one of `create_*`'s own validations" — not merely "the fields were
extracted into the right shape." Any `create_*` rejection (e.g. a corpus file with a real rules
violation this module's own checks don't anticipate) surfaces as `build_character`'s own
`ValueError`, unchanged; this module does not catch or reinterpret it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from chummer5.data.bioware import Bioware
from chummer5.data.cyberware_subsystems import CyberwareEntry
from chummer5.data.knowledge import KNOWLEDGE_CATEGORY_NAMES
from chummer5.data.lifestyle import STARTING_TIER_NAMES, LifestyleTier
from chummer5.data.metatypes import Metatype
from chummer5.data.powers import Power
from chummer5.data.priorities import PriorityTable
from chummer5.data.qualities import BonusSupport, Quality
from chummer5.data.skills import Skill
from chummer5.data.spells import Spell
from chummer5.data.traditions import Tradition
from chummer5.engine.bioware import BiowarePurchaseRequest, select_skill_choices
from chummer5.engine.build_method import SUPPORTED_BUILD_METHODS
from chummer5.engine.character import ALLOCATABLE_ATTRIBUTES, Character, sr5_metatypes
from chummer5.engine.cyberware_subsystems import CyberwarePurchaseRequest
from chummer5.engine.magic import (
    OFFERED_TALENT_CODENAMES,
    mvp_power_catalog,
    power_target_options,
)
from chummer5.engine.qualities import QualityPickRequest, choice_options, mvp_quality_catalog
from chummer5.engine.resources import Contact
from chummer5.io.legacy_chum5 import LegacyCharacter, LegacyCyberware, load_chum5, priority_letter
from chummer5.io.save_format import (
    DEFAULT_TALENT_CODENAME,
    DEFAULT_TALENT_LETTER,
    CharacterSave,
    build_character,
    create_character_save,
)

# load_priorities() only loads the Standard prioritytable's Resources category (see
# chummer5.data.priorities); a character built under a different gameplay option would silently
# resolve its nuyen budget against the wrong table for the same letter if this weren't checked.
STANDARD_GAME_OPTION = "Standard"

# WP44: every one of the 5 priority categories' raw <priority*> field must resolve to one of these
# -- a blank/unresolvable letter (a real, confirmed legacy save-format gap for Mundane-Talent
# Sum-to-Ten characters -- see this module's own docstring and spec/rulebooks/learnings.md's WP44
# entry) would otherwise crash create_skill_allocation/create_character with a KeyError instead of
# failing cleanly.
VALID_PRIORITY_LETTERS = frozenset("ABCDE")

# Both cyberware catalogs only carry Standard-grade values (see chummer5.data.cyberware's
# docstring and the Phase J intro) -- a real purchase at any other grade is rejected even when its
# name matches a catalog entry (see this module's own docstring for why the stored raw fields can't
# be trusted to reflect the real grade-adjusted cost/Essence).
STANDARD_CYBERWARE_GRADE = "Standard"

# <improvementsource> value that marks a <cyberwares><cyberware> entry as Bioware rather than
# Cyberware (see chummer5.io.legacy_chum5.LegacyCyberware's own docstring).
BIOWARE_IMPROVEMENT_SOURCE = "Bioware"

# chummer5.data.bioware.load_bioware() only offers Standard-grade values, mirroring cyberware's own
# scope restriction (see this module's own docstring for why a non-Standard purchase can't be
# trusted to reflect the real grade-adjusted cost/Essence).
STANDARD_BIOWARE_GRADE = "Standard"


class UnsupportedLegacyCharacterError(ValueError):
    """A `.chum5` file uses content MVP's engine cannot represent at all.

    `reasons` enumerates every blocking issue found in one pass (see module docstring) -- itemized,
    not just the first one hit, so a caller doesn't have to fix-and-retry one at a time.
    """

    def __init__(self, reasons: tuple[str, ...]) -> None:
        self.reasons = reasons
        super().__init__("cannot import: " + "; ".join(reasons))


def _bioware_pick_reason(
    item: LegacyCyberware, entry: Bioware, skills: Iterable[Skill]
) -> str | None:
    """WP80: itemize a `SELECT_SKILL` bioware entry whose `<extra>` doesn't resolve to a legal pick.

    `Reflex Recorder` is the only such row (`Barrett.chum5` stores `<extra>Longarms</extra>`). An
    unresolvable or missing pick is a blocking reason like every other unimportable augmentation
    detail, rather than being silently dropped -- dropping it would import an item whose whole
    modeled effect is that pick. Duplicate picks across two purchases of the same item are *not*
    checked here: like every other structural rule (see this module's WP41 docstring paragraph),
    that one surfaces from `create_bioware_selection` at build time.
    """
    if entry.select_skill_bonus is None:
        return None
    eligible = {skill.name for skill in select_skill_choices(entry, skills)}
    if item.extra in eligible:
        return None
    filter_codes = "/".join(entry.select_skill_bonus.limit_to_attributes)
    chosen = item.extra or "(none recorded)"
    return (
        f"cannot import {item.name!r}: its chosen skill {chosen!r} is not an active skill linked "
        f"to {filter_codes}"
    )


def _augmentation_reasons(
    items: Iterable[LegacyCyberware],
    cyberware_by_name: Mapping[str, CyberwareEntry],
    bioware_by_name: Mapping[str, Bioware],
    skills: tuple[Skill, ...],
    *,
    parent_name: str | None,
) -> list[str]:
    """Itemize every `<cyberwares><cyberware>` entry this engine can't represent, at every depth.

    One reason per unresolvable item, named individually (never "this character has cyberware") --
    see the module docstring for why cyberware/bioware issues are *blocking* rather than
    dropped-and-reported, and for the WP41 split between the name/grade/source checks done here and
    the structural ones (`<allowsubsystems>` category eligibility, Capacity budget, rating bounds)
    left to `create_cyberware_tree_selection` at build time.
    """
    reasons: list[str] = []
    where = f" installed in {parent_name!r}" if parent_name is not None else ""
    for item in items:
        if item.improvement_source == BIOWARE_IMPROVEMENT_SOURCE:
            if parent_name is not None:
                # Real SR5 allows Capacity-priced bodyware inside a cyberlimb (p. 456), but
                # `chummer5.data.bioware` carries no Capacity data at all, and no fixture in the
                # corpus does it -- so this is refused rather than half-costed.
                reasons.append(
                    f"cannot import {item.name!r} installed in {parent_name!r}: bioware installed "
                    "as a cyberware subsystem is out of scope (no bioware Capacity data)"
                )
            elif bioware_by_name.get(item.name) is None or item.grade != STANDARD_BIOWARE_GRADE:
                reasons.append(
                    f"cannot import {item.name!r} ({item.grade or 'unknown'} grade): "
                    "rating-scaled, non-Standard-grade, high-Availability, or non-SR5 bioware is "
                    "out of scope"
                )
            else:
                # WP80: the item resolves -- but if it carries a purchase-time skill pick, that pick
                # has to resolve too.
                pick_reason = _bioware_pick_reason(item, bioware_by_name[item.name], skills)
                if pick_reason is not None:
                    reasons.append(pick_reason)
            reasons.extend(
                _augmentation_reasons(
                    item.children,
                    cyberware_by_name,
                    bioware_by_name,
                    skills,
                    parent_name=item.name,
                )
            )
            continue
        if cyberware_by_name.get(item.name) is None or item.grade != STANDARD_CYBERWARE_GRADE:
            reasons.append(
                f"cannot import {item.name!r} ({item.grade or 'unknown'} grade){where}: "
                "non-Standard-grade or non-SR5 cyberware is out of scope"
            )
        reasons.extend(
            _augmentation_reasons(
                item.children, cyberware_by_name, bioware_by_name, skills, parent_name=item.name
            )
        )
    return reasons


def _import_rating(item: LegacyCyberware, entry: CyberwareEntry) -> int:
    """The rating to buy an imported item at.

    The legacy format stores `<rating>0</rating>` for an unrated item, while this engine's floor for
    one is 1 (`CyberwarePurchaseRequest.rating`'s own default) -- so an unrated row is always bought
    at 1 regardless of what the save says, and only a genuinely rated row uses the stored value.
    """
    if entry.is_rated and item.rating > 0:
        return item.rating
    return 1


def _cyberware_purchase_requests(
    items: Iterable[LegacyCyberware], cyberware_by_name: Mapping[str, CyberwareEntry]
) -> tuple[CyberwarePurchaseRequest, ...]:
    """Turn resolved legacy entries into WP38's nested purchase requests (WP41).

    Only reachable once `_augmentation_reasons` has confirmed every entry at every depth resolves,
    so the `cyberware_by_name` lookups here cannot fail. Bioware entries are skipped: a top-level
    one is collected separately (it has its own catalog and its own flat selection), and a nested
    one is already a blocking reason.

    Bundled subsystems (`Cybereyes Basic System` -> `Image Link`, `Control Rig` -> `Datajack`)
    need no special case: legacy `<children>` lists them explicitly, and
    `create_cyberware_tree_selection` resolves an explicit request for a bundled name to the same
    free node it would have attached on its own (see `chummer5.engine.cyberware_subsystems`'
    bundled-subsystem section -- a decision WP38 made with this import path specifically in mind).
    """
    return tuple(
        CyberwarePurchaseRequest(
            item_id=cyberware_by_name[item.name].id,
            rating=_import_rating(item, cyberware_by_name[item.name]),
            plugins=_cyberware_purchase_requests(item.children, cyberware_by_name),
        )
        for item in items
        if item.improvement_source != BIOWARE_IMPROVEMENT_SOURCE
    )


def _blocking_reasons(
    legacy: LegacyCharacter,
    traditions: tuple[Tradition, ...],
    cyberware: tuple[CyberwareEntry, ...],
    bioware: tuple[Bioware, ...],
    skills: tuple[Skill, ...] = (),
) -> tuple[str, ...]:
    reasons = []
    if legacy.build_method not in SUPPORTED_BUILD_METHODS:
        reasons.append(
            f"build method {legacy.build_method!r} is not supported; MVP import only supports "
            f"{' or '.join(SUPPORTED_BUILD_METHODS)}-built characters"
        )
    else:
        # WP44: only reachable for a build method that's otherwise real -- a blank/unresolvable
        # letter on any of the 5 categories is a genuine legacy save-format gap (Mundane-Talent
        # Sum-to-Ten characters; see module docstring), not something a Karma/LifeModule save would
        # even reach this far to exhibit.
        missing_priority_categories = [
            label
            for label, raw in (
                ("Heritage", legacy.priorities.heritage),
                ("Talent", legacy.priorities.talent),
                ("Attributes", legacy.priorities.attributes),
                ("Skills", legacy.priorities.skills),
                ("Resources", legacy.priorities.resources),
            )
            if priority_letter(raw) not in VALID_PRIORITY_LETTERS
        ]
        if missing_priority_categories:
            reasons.append(
                "no priority letter recorded for "
                f"{', '.join(missing_priority_categories)} (a known Sum-to-Ten/Mundane-Talent "
                "legacy save-format gap; see spec/rulebooks/learnings.md's WP44 entry)"
            )
    if legacy.game_option != STANDARD_GAME_OPTION:
        reasons.append(
            f"gameplay option {legacy.game_option!r} is not Standard; MVP's priority tables are "
            "Standard-only"
        )
    if legacy.magic_enabled:
        codename = legacy.priorities.talent_codename
        if codename not in OFFERED_TALENT_CODENAMES:
            reasons.append(
                f"Talent option {codename!r} is not supported; MVP magic chargen only supports "
                "Magician and Adept"
            )
        elif codename == "Aspected Magician":
            # WP121: no corpus file holds one, so where legacy records the aspect is unverified.
            reasons.append(
                "Talent option 'Aspected Magician' can't be imported yet: its aspect isn't read "
                "from the .chum5"
            )
        elif codename == "Magician":
            tradition_names = {t.name for t in traditions}
            if legacy.tradition_name not in tradition_names:
                reasons.append(
                    f"tradition {legacy.tradition_name!r} is not one of the SR5-core traditions "
                    "MVP offers (Hermetic, Shamanic)"
                )
    # WP33/WP45: real, itemized cyberware and bioware checks, replacing the old blanket "character
    # has cyberware/bioware" rejection. WP41: recursive over <children> -- see module docstring.
    reasons.extend(
        _augmentation_reasons(
            legacy.cyberware,
            {item.name: item for item in cyberware},
            {item.name: item for item in bioware},
            skills,
            parent_name=None,
        )
    )
    if legacy.metavariant is not None:
        reasons.append(f"metavariant {legacy.metavariant!r} is out of MVP scope")
    # WP52: `ALLOCATABLE_ATTRIBUTES` (Mental/Physical/EDG) Karma-bought points are now modeled --
    # see chummer5.engine.character.create_karma_attribute_points -- so only MAG's `<karma>` field
    # still blocks (Post-WP29 correction gave MAG its own points budget, Special Attribute Points,
    # but WP52 deliberately did not extend Karma-funded attribute increases to it -- see
    # KarmaAttributeSelection's own docstring for why).
    if legacy.magic_enabled and "MAG" in legacy.attributes and legacy.attributes["MAG"].karma > 0:
        reasons.append(
            "character has Karma-bought Magic beyond the priority/Special-Attribute-Points "
            "budget; MVP's engine models Karma-funded attribute increases for Mental/Physical/"
            "Edge only (WP52) -- raising Magic with Karma remains out of scope"
        )
    if not legacy.lifestyles:
        reasons.append(
            "no primary Lifestyle found; SR5 requires selecting one at character creation"
        )
    elif legacy.lifestyles[0].base_lifestyle not in STARTING_TIER_NAMES:
        reasons.append(
            f"primary Lifestyle {legacy.lifestyles[0].base_lifestyle!r} is not one of the 6 "
            "core-rulebook starting tiers MVP offers"
        )
    return tuple(reasons)


@dataclass(frozen=True)
class ImportResult:
    """A successfully imported legacy character: the native `CharacterSave`, the `Character` that
    save reconstructs into (proving the import is actually buildable, not just shaped right; see
    `chummer5.io.save_format.build_character` -- `Character` itself carries the resulting
    `skill_allocation`/`quality_selection`/`contact_selection`/`resources_selection` since WP18's
    fold, so no separate wrapper type is needed here either), and what got excluded along the way
    -- see module docstring for the excluded-vs-blocking split.
    """

    save: CharacterSave
    built: Character
    dropped_qualities: tuple[str, ...]
    dropped_skills: tuple[str, ...]
    dropped_spells: tuple[str, ...]  # WP28: non-SR5-sourced spells, dropped and reported
    dropped_powers: tuple[str, ...]  # WP28: non-SR5-sourced or NOT_YET_SUPPORTED powers, likewise
    # WP50: a recorded specialization whose host skill isn't individually imported (group-purchased,
    # karma-only base<=0, or an unresolvable suid) or that's a second+ specialization on one skill
    # (MVP only supports one) -- see module docstring.
    dropped_specializations: tuple[str, ...]


def _legacy_quality_choice(quality: Quality, extra: str | None, magic_enabled: bool) -> str | None:
    """WP115: a legacy `<extra>` read as a `QualityPick.choice`, or `None` if it names no option.

    Legacy writes the choice as display text: an attribute code (`INT`), a bare spirit type
    (`Man` for "Spirit of Man"), a skill or action name, or a table row's own wording
    ("Memory Loss (short term)"). Each is tried verbatim, as a spirit type, and squashed to this
    project's PascalCase ids (`MemoryLossShortTerm`, `YouKnowAGuy`).
    """
    if not extra:
        return None
    options = choice_options(quality, "Magician" if magic_enabled else None)
    squashed = "".join(w[:1].upper() + w[1:] for w in re.split(r"[^A-Za-z0-9]+", extra) if w)
    for candidate in (extra, f"Spirit of {extra}", squashed):
        if candidate in options:
            return candidate
    return None


def import_legacy_character(
    legacy: LegacyCharacter,
    *,
    metatypes: tuple[Metatype, ...],
    priorities: PriorityTable,
    skills: tuple[Skill, ...],
    qualities: tuple[Quality, ...],
    lifestyles: tuple[LifestyleTier, ...],
    traditions: tuple[Tradition, ...] = (),
    spells: tuple[Spell, ...] = (),
    powers: tuple[Power, ...] = (),
    cyberware: tuple[CyberwareEntry, ...] = (),
    bioware: tuple[Bioware, ...] = (),
) -> ImportResult:
    """Convert an already-parsed `LegacyCharacter` into a validated, built native character.

    Raises `UnsupportedLegacyCharacterError` for blocking content (see module docstring). Excludes
    (and reports via `ImportResult.dropped_*`) qualities, skills, spells, and powers MVP's engine
    doesn't otherwise model, then builds the result through WP11's `build_character()` so a caller
    gets back a ready-to-use character, not just a save file.

    `traditions`/`spells`/`powers`/`cyberware`/`bioware` default to `()`, mirroring
    `build_character`'s own WP28/WP33/WP45 defaults -- a Mundane, augmentation-free legacy character
    (every fixture this project imported before WP28/WP33/WP45) never touches any of the five.
    """
    reasons = _blocking_reasons(legacy, traditions, cyberware, bioware, skills)
    if reasons:
        raise UnsupportedLegacyCharacterError(reasons)

    # WP33/WP45: every remaining `legacy.cyberware` entry is now guaranteed (by `_blocking_reasons`
    # above) to be a Cyberware entry that resolves by name against `cyberware` at Standard grade, or
    # a Bioware entry that resolves by name against `bioware` at Standard grade -- nothing here can
    # fail. WP41: the cyberware half is a nested request tree now, the bioware half deliberately
    # stays a flat top-level list (a nested bioware entry is a blocking reason, see
    # `_augmentation_reasons`). WP80: each bioware entry is a request rather than a bare id, so a
    # `Reflex Recorder`'s own `<extra>` (its chosen skill, already confirmed resolvable above)
    # rides along.
    bioware_by_name = {item.name: item for item in bioware}
    cyberware_purchases = _cyberware_purchase_requests(
        legacy.cyberware, {item.name: item for item in cyberware}
    )
    bioware_purchases = [
        BiowarePurchaseRequest(
            item_id=bioware_by_name[item.name].id,
            chosen_skill=(
                item.extra if bioware_by_name[item.name].select_skill_bonus is not None else None
            ),
        )
        for item in legacy.cyberware
        if item.improvement_source == BIOWARE_IMPROVEMENT_SOURCE
    ]

    # `.base` -- priority-derived points only, validated by `create_character` against the
    # Attributes/special-attribute-points budgets.
    attribute_points = {
        code: legacy.attributes[code].base
        for code in ALLOCATABLE_ATTRIBUTES
        if code in legacy.attributes
    }
    # WP52: `.karma` -- Karma-bought points beyond that priority budget, validated separately by
    # `create_karma_attribute_points` against the Karma ledger (see this module's own WP52
    # docstring paragraph for why this replaces the old blanket rejection). `_blocking_reasons`
    # above still guarantees MAG's own `.karma` is 0 for any character reaching this point.
    karma_attribute_points = {
        code: legacy.attributes[code].karma
        for code in ALLOCATABLE_ATTRIBUTES
        if code in legacy.attributes and legacy.attributes[code].karma > 0
    }

    # Same allocation logic WP6/WP7/WP10's fixture tests already validated against Yeti: a skill
    # only contributes its own base points if its group wasn't also bought (the "strict skill
    # groups" rule `create_skill_allocation` enforces) and its <suid> resolves to a known skill.
    skills_by_id = {s.id: s for s in skills}
    bought_groups = {g.name: g.base for g in legacy.skill_groups if g.base > 0}
    skill_points: dict[str, int] = {}
    dropped_skills: list[str] = []
    for legacy_skill in legacy.skills:
        if legacy_skill.base <= 0:
            continue
        skill = skills_by_id.get(legacy_skill.suid)
        if skill is None:
            dropped_skills.append(legacy_skill.suid)
            continue
        if skill.skill_group is not None and skill.skill_group in bought_groups:
            continue
        skill_points[skill.id] = legacy_skill.base

    # WP50: specializations, resolved as a second pass now that `skill_points` is finalized -- a
    # specialization is only importable when its host skill actually reached `skill_points` (see
    # module docstring for the three ways it might not: an unresolvable <suid>, a group-purchased
    # skill, or a karma-only base<=0 skill). Only the first recorded specialization per skill is
    # kept (this project's model, like the rulebook's own Step Five rule, allows exactly one); any
    # further ones are dropped and reported like the unimportable case, not silently discarded.
    specializations: dict[str, str] = {}
    dropped_specializations: list[str] = []
    for legacy_skill in legacy.skills:
        if not legacy_skill.specializations:
            continue
        skill = skills_by_id.get(legacy_skill.suid)
        skill_name = skill.name if skill is not None else legacy_skill.suid
        if skill is None or skill.id not in skill_points:
            dropped_specializations.extend(
                f"{skill_name}: {name}" for name in legacy_skill.specializations
            )
            continue
        specializations[skill.id] = legacy_skill.specializations[0]
        dropped_specializations.extend(
            f"{skill_name}: {name} (only one specialization per skill is supported)"
            for name in legacy_skill.specializations[1:]
        )

    # WP49: Knowledge/Language skills, freeform (no dropping/reporting tier needed -- see module
    # docstring). A `native` Language entry is kept regardless of `base` (a real native pick is
    # legitimately recorded at 0 cost by design -- see chummer5.engine.knowledge.LanguageSkillPick's
    # own docstring); every other entry skips `base <= 0`, which excludes both an unmarked-native
    # language recorded at 0 cost with no `<isnativelanguage>` marker at all (e.g. Yeti's own
    # "English") and a real placeholder-empty `<skill>` entry (confirmed present in Wesson.chum5) --
    # neither is a real player spend to reconstruct.
    knowledge_skill_picks: list[tuple[str, str, int]] = []
    language_skill_picks: list[tuple[str, int, bool]] = []
    for legacy_knowledge in legacy.knowledge_skills:
        if legacy_knowledge.category in KNOWLEDGE_CATEGORY_NAMES:
            if legacy_knowledge.base <= 0:
                continue
            knowledge_skill_picks.append(
                (legacy_knowledge.name, legacy_knowledge.category, legacy_knowledge.base)
            )
        elif legacy_knowledge.native or legacy_knowledge.base > 0:
            language_skill_picks.append(
                (legacy_knowledge.name, legacy_knowledge.base, legacy_knowledge.native)
            )

    # WP23: `<qualitysource>Metatype</qualitysource>` isn't exclusively "this metatype's real
    # racial quality" in the legacy data -- it's the broader "auto-granted at character creation,
    # not manually picked from the quality list" tag, which also covers e.g. a Talent selection's
    # Technomancer/Adept/Magician quality (confirmed directly: `Yeti-#ffffff2.chum5`'s own
    # Technomancer quality is `qualitysource=Metatype` despite Yeti being Human, whose
    # `qualities_positive`/`qualities_negative` are both empty). Only skip (silently, since
    # `build_character` re-derives and re-grants it) a `Metatype`-sourced quality whose *name*
    # actually matches this character's real metatype's racial-quality list -- anything else
    # `qualitysource=Metatype` still flows through the normal offered/dropped check below, so it
    # doesn't just vanish with no trace (the module docstring's own rule).
    metatype_obj = next(
        (m for m in sr5_metatypes(metatypes) if m.name == legacy.metatype),
        None,
    )
    metatype_quality_names = (
        frozenset((*metatype_obj.qualities_positive, *metatype_obj.qualities_negative))
        if metatype_obj is not None
        else frozenset[str]()
    )

    offered_qualities = {q.id: q for q in mvp_quality_catalog(qualities)}
    quality_picks: list[QualityPickRequest] = []
    dropped_qualities: list[str] = []
    for legacy_quality in legacy.qualities:
        if (
            legacy_quality.quality_source == "Metatype"
            and legacy_quality.name in metatype_quality_names
        ):
            continue
        offered = offered_qualities.get(legacy_quality.id)
        if offered is None:
            dropped_qualities.append(legacy_quality.name)
            continue
        # WP107: the legacy format has no per-quality rating -- a rated quality is saved as one
        # `<quality>` node *per level* (Glessner.chum5 carries three Focused Concentration nodes),
        # so repeated nodes of a rated quality fold into one pick's rating.
        if offered.max_rating > 1:
            existing = next(
                (i for i, p in enumerate(quality_picks) if p.quality_id == offered.id), None
            )
            if existing is not None:
                previous = quality_picks[existing]
                quality_picks[existing] = replace(previous, rating=previous.rating + 1)
                continue
        # WP55: a SELECT_TEXT quality's own <extra> is exactly the free-text detail
        # create_quality_selection requires -- the same field LegacyPower.extra already threads
        # through for select-attribute powers (see chummer5.io.legacy_chum5's docstring).
        text = legacy_quality.extra if offered.bonus_support == BonusSupport.SELECT_TEXT else None
        # WP115: a choice-bearing quality's pick is its <extra> too. One that doesn't resolve to
        # an offered option is dropped and reported, like any other quality this can't carry.
        choice = None
        if offered.choice_kind is not None:
            choice = _legacy_quality_choice(offered, legacy_quality.extra, legacy.magic_enabled)
            if choice is None:
                dropped_qualities.append(legacy_quality.name)
                continue
        quality_picks.append(QualityPickRequest(quality_id=offered.id, text=text, choice=choice))

    contacts = tuple(
        Contact(name=c.name, connection=c.connection, loyalty=c.loyalty, free=c.free)
        for c in legacy.contacts
    )

    # WP28: Talent/tradition/free-skill grant. Only trust the legacy save's own `talent_letter`/
    # `talent_codename` (and its free-skill grant) when `legacy.magic_enabled` -- a Resonance
    # character (Technomancer/A.I.) carries a real, non-"Mundane" `talent_codename` at a letter that
    # doesn't even offer "Mundane" as an option (e.g. Yeti-#ffffff2.chum5's own "Technomancer" at
    # letter B) plus a Resonance-flavored free-skill grant, despite `magic_enabled` being `False`,
    # and none of it is something `chummer5.engine.magic` models at all (Resonance is out of scope
    # per the Project Overview; see `chummer5.io.legacy_import`'s own module docstring on
    # `resonance_enabled` not being blocking). Forcing both fields to their Mundane defaults for any
    # non-magic-enabled character is the same "ignore Resonance content, don't half-model it" rule
    # WP6-WP10 already established for Yeti, just applied to this WP's new Talent fields instead of
    # silently working by never reading them. `_blocking_reasons` above already guarantees a
    # Magician's tradition resolves against `traditions` (there's no sensible "import without a
    # tradition" fallback), so that lookup cannot fail here.
    if legacy.magic_enabled:
        talent_letter = priority_letter(legacy.priorities.talent)
        talent_codename = legacy.priorities.talent_codename
    else:
        talent_letter = DEFAULT_TALENT_LETTER
        talent_codename = DEFAULT_TALENT_CODENAME
    tradition_id = None
    if talent_codename == "Magician":
        tradition_id = next(t.id for t in traditions if t.name == legacy.tradition_name)

    # Post-WP29 correction: Special Attribute Points spent raising MAG beyond the Talent-granted
    # starting rating -- `legacy.attributes["MAG"].base` is exactly that number, the same field
    # `attribute_points` above already reads for EDG. `_blocking_reasons` guarantees `.karma` is 0
    # here (see its own updated check), so `.base` alone is the full priority-derived spend.
    magic_attribute_points = (
        legacy.attributes["MAG"].base if legacy.magic_enabled and "MAG" in legacy.attributes else 0
    )

    # Every name here comes from `priorities.xml`'s own Talent free-skill grant, cross-referencing
    # `chummer5.data.skills.load_skills()` -- a catalog that's already 100% SR5-sourced (WP3), so an
    # unresolvable name would mean a real data-integrity bug, not an expected edge case (mirrors
    # `chummer5.engine.qualities.resolve_metatype_qualities`'s identical "raise, don't drop"
    # reasoning for the same kind of fixed, catalog-guaranteed cross-reference). Skipped entirely
    # for a non-magic-enabled character -- see the paragraph above.
    skills_by_name = {s.name: s for s in skills}
    granted_skill_ids: list[str] = []
    if legacy.magic_enabled:
        for bonus_skill_name in legacy.priorities.talent_bonus_skills:
            bonus_skill = skills_by_name.get(bonus_skill_name)
            if bonus_skill is None:
                raise ValueError(
                    f"Talent free-skill grant name {bonus_skill_name!r} does not resolve against "
                    "the SR5 skill catalog"
                )
            granted_skill_ids.append(bonus_skill.id)

    # WP28: spells -- excluded-and-reported like a dropped quality/skill, never fatal (a spell has
    # no chargen-time computed effect; see chummer5.engine.magic's module docstring).
    spells_by_name = {s.name: s for s in spells}
    spell_ids: list[str] = []
    dropped_spells: list[str] = []
    for legacy_spell in legacy.spells:
        spell = spells_by_name.get(legacy_spell.name)
        if spell is None:
            dropped_spells.append(legacy_spell.name)
        else:
            spell_ids.append(spell.id)

    # WP28: powers -- same excluded-and-reported treatment, restricted to `mvp_power_catalog`
    # (FLAT_BONUS only; a non-SR5-sourced or NOT_YET_SUPPORTED power is dropped, not half-applied).
    # A `select_attribute`-shaped power (only Improved Physical Attribute among the offered set)
    # needs its purchased target too -- carried in the legacy save's own `<extra>` field; if that
    # doesn't resolve to one of the power's real eligible attributes, the whole pick is dropped
    # rather than guessed at.
    offered_powers_by_name = {p.name: p for p in mvp_power_catalog(powers)}
    power_picks: list[tuple[str, int, str | None]] = []
    dropped_powers: list[str] = []
    for legacy_power in legacy.powers:
        power = offered_powers_by_name.get(legacy_power.name)
        if power is None:
            dropped_powers.append(legacy_power.name)
            continue
        # WP119: any target-taking power (an attribute, a skill, free text), not just WP28's
        # select-attribute one.
        target: str | None = None
        if power.target_kind == "text":
            target = legacy_power.extra or None
        elif power.target_kind is not None:
            target = (
                legacy_power.extra if legacy_power.extra in power_target_options(power) else None
            )
        if power.target_kind is not None and target is None:
            dropped_powers.append(legacy_power.name)
            continue
        power_picks.append((power.id, legacy_power.rating, target))

    save = create_character_save(
        metatype_name=legacy.metatype,
        heritage_letter=priority_letter(legacy.priorities.heritage),
        attributes_letter=priority_letter(legacy.priorities.attributes),
        attribute_points=attribute_points,
        karma_attribute_points=karma_attribute_points,
        skills_letter=priority_letter(legacy.priorities.skills),
        skill_points=skill_points,
        group_points=bought_groups,
        specializations=specializations,
        quality_picks=quality_picks,
        contacts=contacts,
        resources_letter=priority_letter(legacy.priorities.resources),
        # No general gear-catalog import -- WP9's STARTER_GEAR_CATALOG is a deliberately minimal
        # stub, and WP10 already found Yeti's real gear purchases aren't reconstructable from it.
        # Not "silently dropped": MVP's own scope explicitly excludes "the full gear catalog beyond
        # a basic purchase flow" (Project Overview), so there is nothing this import path was ever
        # going to represent here.
        gear_names=(),
        # WP20: unlike gear, the lifestyle catalog *is* a complete, real SR5 catalog (all 6
        # starting tiers), so the character's actual primary Lifestyle is faithfully
        # reconstructable -- `_blocking_reasons` above already rejected anything this can't
        # represent (missing, or not one of the 6 tiers).
        lifestyle_tier_name=legacy.lifestyles[0].base_lifestyle,
        lifestyle_months=legacy.lifestyles[0].months,
        talent_letter=talent_letter,
        talent_codename=talent_codename,
        tradition_id=tradition_id,
        granted_skill_ids=granted_skill_ids,
        spell_ids=spell_ids,
        power_picks=power_picks,
        magic_attribute_points=magic_attribute_points,
        cyberware_purchases=cyberware_purchases,
        bioware_purchases=bioware_purchases,
        # WP43: <nuyenbp> -- Karma actually converted to nuyen at Step Six. `_blocking_reasons`
        # doesn't need its own check for this: STANDARD_GAME_OPTION already restricts import to
        # Standard-gameplay-option characters, and every Standard settings.xml block caps this at
        # exactly the same 10 chummer5.engine.resources.MAX_KARMA_TO_NUYEN hardcodes (see
        # spec/rulebooks/learnings.md's WP43 entry) -- an honest legacy save can't carry a value
        # build_character's own karma_to_nuyen() call would reject.
        karma_converted=legacy.karma_converted_to_nuyen,
        # WP44: carried through as-is (already confirmed one of SUPPORTED_BUILD_METHODS by
        # _blocking_reasons above) -- see chummer5.io.save_format's own docstring for why nothing
        # downstream re-validates it.
        build_method=legacy.build_method,
        knowledge_skill_picks=knowledge_skill_picks,
        language_skill_picks=language_skill_picks,
    )

    built = build_character(
        save,
        metatypes=metatypes,
        priorities=priorities,
        skills=skills,
        qualities=qualities,
        lifestyles=lifestyles,
        traditions=traditions,
        spells=spells,
        powers=powers,
        cyberware=cyberware,
        bioware=bioware,
    )

    return ImportResult(
        save=save,
        built=built,
        dropped_qualities=tuple(dropped_qualities),
        dropped_skills=tuple(dropped_skills),
        dropped_spells=tuple(dropped_spells),
        dropped_powers=tuple(dropped_powers),
        dropped_specializations=tuple(dropped_specializations),
    )


def import_chum5(
    path: Path,
    *,
    metatypes: tuple[Metatype, ...],
    priorities: PriorityTable,
    skills: tuple[Skill, ...],
    qualities: tuple[Quality, ...],
    lifestyles: tuple[LifestyleTier, ...],
    traditions: tuple[Tradition, ...] = (),
    spells: tuple[Spell, ...] = (),
    powers: tuple[Power, ...] = (),
    cyberware: tuple[CyberwareEntry, ...] = (),
    bioware: tuple[Bioware, ...] = (),
) -> ImportResult:
    """Parse a `.chum5` file (WP4's `load_chum5`) and import it (see `import_legacy_character`)."""
    return import_legacy_character(
        load_chum5(path),
        metatypes=metatypes,
        priorities=priorities,
        skills=skills,
        qualities=qualities,
        lifestyles=lifestyles,
        traditions=traditions,
        spells=spells,
        powers=powers,
        cyberware=cyberware,
        bioware=bioware,
    )
