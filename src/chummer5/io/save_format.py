"""The project's own save format: JSON, mirroring the domain model's *selections*, not its
computed values.

Composes every chargen module built so far (WP6's `chummer5.engine.character`, WP7's
`chummer5.engine.skills`, WP8's `chummer5.engine.qualities`, WP9's `chummer5.engine.resources`)
into one persistable unit. Per the Project Overview's "Data & save format" section: this is a new,
native format, not a reproduction of legacy `.chum5` XML (that's WP12's read-only import job, a
one-way street in the other direction).

**Selections, not derived values.** Same principle the legacy `.chum5` format itself follows
(confirmed repeatedly across WP4/WP7/WP10's fixture research: no `.chum5` file stores a computed
dice pool, limit, or condition-monitor total -- only the inputs those formulas consume). This
format stores exactly the player-authored choices each `create_*` function in the engine layer
already takes as parameters -- metatype name, priority letters, attribute/skill points, quality ids,
contacts, gear names -- and `build_character()` re-derives everything else (attribute values,
Improvement-sourced bonuses, karma/nuyen totals) by calling straight back into the same `create_*`
functions WP6-WP9 already validated. Nothing about a finished character's *computed* state is ever
written to disk; reloading a save re-runs the same validated construction path a fresh selection
would, which also means a save file can never smuggle in a value the engine itself wouldn't accept.

**`CharacterSave` is this WP's one new bundling type.** WP10 explicitly declined to add a
dataclass bundling `Character` + `SkillAllocation` + `QualitySelection` + `ContactSelection` +
`ResourcesSelection`, reasoning that nothing yet needed one and a future consumer should be the one
to shape it (see `spec/worklogs/WP10.md`'s design decisions). Persistence is that consumer: a save
file has to be *some* single unit, and its natural shape is "the raw selections", not "the built
objects" -- the built objects hold references to catalog data (`Metatype`, `Quality`, ...) and a
mutable `ImprovementIndex` with no meaningful JSON encoding, whereas the selections are already
exactly the plain (str/int/bool/tuple) values every `create_*` function takes.

**`build_character()` returns a `Character` directly, not a `BuiltCharacter` wrapper (as of WP18).**
WP11 originally paired one alongside `Character` specifically because `Character` itself only held
metatype/attributes at the time -- a save's other four selections had nowhere to attach except a
bundling type built for the purpose. WP18 widened `Character` with
`skill_allocation`/`quality_selection`/`contact_selection`/`resources_selection` fields (see its own
docstring), which makes that wrapper redundant: `build_character` now attaches all four to the
`Character` it builds via one `dataclasses.replace` call and returns that directly.

**WP20** adds `lifestyle_tier_name`/`lifestyle_months` (required, not optional-with-a-tuple-default
like `gear_names`/`quality_ids`/`contacts`) -- a saved character always has a concrete primary
Lifestyle, even the free "Street" tier, since SR5 makes the choice mandatory (see
`chummer5.engine.lifestyle`'s module docstring); there is no meaningful "no lifestyle yet" save
state the way there is for e.g. an empty gear list.

**WP28** adds `talent_letter`/`talent_codename`/`tradition_id`/`granted_skill_ids`/`spell_ids`/
`power_picks` -- Phase I's Magic-type/tradition/spell/power selections, threaded through the same
"selections, not derived values" way every prior selection type already is. Unlike Lifestyle, these
default to Mundane (`talent_letter = DEFAULT_TALENT_LETTER`, `talent_codename = "Mundane"`, every
other new field empty/`None`) rather than being unconditionally required -- WP24 already established
"unset means Mundane" as the correct default shape for Talent (`Character.magic_type: str | None =
None`'s own default), and WP29 (the web UI for magic chargen) hasn't landed yet, so every save this
project's own web layer currently produces *is* Mundane -- defaulting these fields keeps every
pre-WP28 call site (`chummer5.web.app`'s save/load routes included) working unchanged rather than
forcing a mechanical "pass Mundane explicitly everywhere" edit for a UI capability that doesn't
exist yet. `DEFAULT_TALENT_LETTER` is its own module-local constant here, not imported from
`chummer5.web.session` (which defines an identically-valued one for the same reason) -- `io` must
not depend on `web`. A future WP29 would simply stop relying on the default once the web layer has
real Talent selections to pass.

**Post-WP29 correction** adds `magic_attribute_points` -- Special Attribute Points spent raising
MAG beyond `talent_codename`'s starting rating, a real, rulebook-confirmed mechanic WP25 originally
(and wrongly) modeled as impossible; see `chummer5.engine.character.Character`'s own docstring
correction and `spec/rulebooks/learnings.md`. Defaults to `0`, the same "predates this field"
shape every other magic field above defaults to Mundane.

**WP33** adds a purchased-cyberware field, the same "selection, not derived value" shape every
prior field already has. Defaults to empty ("predates this field", the same shape every WP28 magic
field defaults to), so every save written before that WP (which never had cyberware to lose)
round-trips unchanged. `build_character` validates it using `resources_selection.nuyen_remaining`
(gear + Lifestyle already subtracted) as the shared nuyen budget cyberware draws from -- one shared
Step Six pool, not a separate one. **WP34** (the cyberware UI) additionally folds
`cyberware_selection.nuyen_spent` back into the `resources_selection` this function returns, via a
second `create_resources_selection` call once cyberware is resolved -- see this function's own
inline comment for why that re-call always succeeds.

**WP41** replaces WP33's flat `cyberware_item_ids: tuple[str, ...]` with `cyberware_purchases:
tuple[CyberwarePurchaseRequest, ...]` -- Phase K's purchase *tree*, so a saved cybereye can carry
the Vision Enhancement installed into it instead of losing it. `CyberwarePurchaseRequest`
(`chummer5.engine.cyberware_subsystems`) is reused directly rather than copied into a
save-format-local mirror, for exactly the reason `Contact` already is: it is a plain, frozen,
JSON-shaped (`str`/`int`/nested-tuple) dataclass with no engine state in it, and it is *already*
the shape `create_cyberware_tree_selection` takes, so persisting anything else would mean
translating twice.

**A pre-WP41 save still loads**, and this is the one field whose backward compatibility isn't just
a default: `_dict_to_save` reads `"cyberware_purchases"` when present and otherwise falls back to
`"cyberware_item_ids"`, mapping each id to a zero-plugin, rating-1 request. That mapping is exact,
not approximate -- the two catalogs are the same `cyberware.xml` rows read twice, so WP31's ids are
a subset of WP37's (verified), and every WP31 row is unrated, whose only legal rating is 1. Writing
only ever emits the new key; `FORMAT_VERSION` is unchanged, since a reader that understands both
keys is not a schema break.

**WP43** adds `karma_converted` -- however much Karma the player converted to nuyen at Step Six
(core rulebook p. 94), the same "selection, not derived value" shape every prior field has.
Defaults to `0` ("predates this field"/"player didn't convert any"), so every pre-WP43 save
round-trips unchanged. `build_character` folds it into both `create_resources_selection` calls
(gear+Lifestyle, then gear+Lifestyle+cyberware) -- see `chummer5.engine.resources`'s own module
docstring for why it tops up the shared budget rather than spending from it.

**WP45** adds `bioware_item_ids` -- purchased `chummer5.data.bioware.Bioware` ids, the identical
"selection, not derived value" shape `cyberware_item_ids` already has. Defaults to `()` ("predates
this field"), so every save written before this WP round-trips unchanged. `build_character`
validates it against `chummer5.engine.bioware.create_bioware_selection`, resolved *after*
`cyberware_item_ids` (a fixed evaluation order -- see that module's own docstring for why): the
nuyen budget left over once gear/Lifestyle/cyberware are resolved, and cyberware's own
`essence_spent` as bioware's `other_essence_spent`, so the shared Essence floor accounts for both.

**WP80** replaces that flat id list with `bioware_purchases: tuple[BiowarePurchaseRequest, ...]`,
for the same reason and in the same shape WP41 replaced `cyberware_item_ids`: one bioware row
(`Reflex Recorder`) carries a purchase-time *skill pick* that a bare id cannot express, and
`BiowarePurchaseRequest` (`chummer5.engine.bioware`) is already exactly what
`create_bioware_selection` takes. **A pre-WP80 save still loads**: `_dict_to_save` reads
`"bioware_purchases"` when present and otherwise falls back to `"bioware_item_ids"`, mapping each
id to a request with no pick. That fallback is exact for every row *except* `Reflex Recorder`,
whose pick genuinely wasn't recorded before this WP -- such a save now fails to build, with
"Reflex Recorder requires a chosen skill", rather than loading a character whose skill bonus was
silently dropped. That is the intended behaviour and not a regression to work around: the pick was
never stored, so there is nothing to recover, and WP45-WP79 never applied the bonus either.
`FORMAT_VERSION` is unchanged, since a reader that understands both keys is not a schema break.

**WP46** adds `bound_spirit_picks` -- a Magician's bound spirits, the same "selection, not derived
value" shape every prior field has. Defaults to `()` ("predates this field"), so every save written
before this WP round-trips unchanged.

**WP70** widens each `bound_spirit_picks` entry from a `(spirit_type, services)` pair to a
`(spirit_type, force, services)` triple, now that Force is player-chosen (WP46-WP69 pinned it to the
live Magic rating and never stored it). `force` is persisted as `int | None`: a stored integer is
the player's chosen Force, while `None` -- and, on read, the total absence of a `"force"` key in a
pre-WP70 save -- means "default to the character's Magic rating", which is exactly the pre-WP70
behavior. So a pre-WP70 save (whose spirit entries have no `"force"` field) still round-trips
unchanged: `_from_dict` fills `force=None`, and `build_character` resolves it back to the live Magic
rating via `create_bound_spirit_selection`.

**WP47** adds `foci_picks` -- a magic-active character's bonded foci, as `(focus_id, force)` pairs
(the same "selection, not derived value" shape `power_picks` already has -- `chummer5.data.foci
.Focus.id` plus the player-chosen Force, exactly what `create_foci_selection` itself takes).
Defaults to `()` ("predates this field"), so every save written before this WP round-trips
unchanged. `build_character` resolves it *after* `bound_spirit_picks` (a fixed evaluation order, the
same reasoning `bioware_item_ids` already follows relative to `cyberware_item_ids` -- see
`chummer5.engine.foci`'s own module docstring for why a one-shot reconstruction needs one even
though neither `create_*_selection` chains into the other's own call): Foci's own Karma budget
accounts for Bound Spirits' already-resolved `karma_cost`, and its nuyen budget accounts for
gear/Lifestyle/cyberware/bioware's already-resolved spend, so the *combined* Step Six nuyen and
leftover-Karma pools are both correctly shared, not each independently assumed unclaimed.

**WP48** adds `mentor_spirit_archetype_id`/`mentor_spirit_general_choice_id` -- a magic-active
character's picked Mentor Spirit archetype (the "Mentor Spirit" quality itself is already carried
by `quality_ids`, unchanged) and, only when that archetype's General bonus slot is itself a
player choice (3 of 16 SR5 archetypes -- see `chummer5.data.mentors`'s own docstring), which
option was chosen. Both default to `None` ("predates this field"/"Mentor Spirit not taken"), so
every pre-WP48 save round-trips unchanged. `build_character` resolves `quality_selection` with
these threaded through *and* `magic_type` computed up front from `save.talent_codename` (`None`
for `"Mundane"`, `save.talent_codename` itself otherwise -- exactly what `create_magic_selection`
would later derive as `MagicSelection.magic_type`, computed early here since `create_quality_
selection` needs it and quality resolution happens before the Magic-selection block further
down this function) -- unlike Bound Spirits/Foci, Mentor Spirit's Karma cost is a normal Positive
Quality cost already covered by `QualitySelection.positive_karma`/`QUALITY_KARMA_LIMIT`, not a
separate draw against `Character.karma_remaining` (WP51's unified ledger; Bound Spirits/Foci's own
leftover-Karma pool), so no evaluation-order concern with Bound Spirits/Foci exists here.

**WP49** adds `knowledge_skill_picks`/`language_skill_picks` -- a player's Knowledge/Language skill
spend, as `(name, category, rating)`/`(name, rating, native)` tuples (the same "selection, not
derived value" shape every prior field has -- `chummer5.engine.knowledge.KnowledgeSkillPick`/
`LanguageSkillPick` themselves, just flattened for JSON). Defaults to `()` for both ("predates this
field"), so every pre-WP49 save round-trips unchanged. `build_character` resolves this immediately
after `quality_selection` (not before) -- Bilingual's `NATIVE_LANGUAGE_LIMIT` Improvement, applied
by `apply_quality_improvements` a few lines above, has to already be on `character.improvements`
before `create_knowledge_selection` reads it (see
`chummer5.engine.knowledge.native_language_limit`).

**WP44** adds `build_method` -- which of the two supported priority-letter validity rules
(`chummer5.engine.build_method.PRIORITY_BUILD_METHOD`/`SUM_TO_TEN_BUILD_METHOD`) produced
`heritage_letter`/`talent_letter`/`attributes_letter`/`skills_letter`/`resources_letter`. Unlike
every other field in this dataclass, it is deliberately **not** re-validated by `build_character`:
neither `create_character` nor any other `create_*` function here has ever validated the letter
*assignment*'s shape (bijection vs. Sum-to-Ten's repeats-allowed/sum-to-10 rule) -- only
`chummer5.web.app.submit_priorities` does, at the point of interactive submission (see its own
docstring) -- so there is no validation step downstream for this field to feed. It is carried
through purely so a reloaded character's *next* priorities reconfirmation applies the right rule
(`chummer5.web.app._apply_built_character_to_session` restores `ChargenSession.build_method` from
it) rather than silently defaulting back to Priority's bijection, which a Sum-to-Ten character's
own letters might not even satisfy if they repeat. Defaults to `PRIORITY_BUILD_METHOD` ("predates
this field"), so every pre-WP44 save round-trips unchanged.

**WP50** adds `specializations` -- `skill_id -> name` (mirroring `skill_points`/`group_points`'s
own `{key: value}` shape, not a flattened tuple like WP49's Knowledge/Language fields, since it's
already a plain `str -> str` mapping with no third field to carry). Defaults to `{}` ("predates this
field"), so every pre-WP50 save round-trips unchanged. `build_character` passes it straight into
`create_skill_allocation` alongside `skill_points`/`group_points` -- no separate resolution step is
needed, unlike Knowledge/Language's Bilingual dependency, since a specialization's only precondition
(its skill having at least 1 of its own `skill_points`) is already checked from data this dataclass
carries directly.

**WP52** adds `karma_attribute_points` -- attribute code -> extra points bought with leftover
Karma, mirroring `attribute_points`'s own `{code: points}` shape (see
`chummer5.engine.character.KarmaAttributeSelection`). Defaults to `{}` ("predates this field"), so
every pre-WP52 save round-trips unchanged. Resolved in `build_character` after `quality_selection`/
`contact_selection` are attached (so `character.karma_remaining` at that point already reflects
both) but before `bound_spirit_selection` (which reads `character.attribute_value("CHA")` --
one of `PRIMARY_ATTRIBUTES`, so it must see any Karma-funded CHA increase already applied).

**WP53** adds `karma_skill_points`/`karma_group_points`/`karma_specializations` (mirroring
`skill_points`/`group_points`/`specializations`' own shapes -- see
`chummer5.engine.skills.KarmaSkillSelection`) and `karma_knowledge_points` (mirroring
`knowledge_skill_picks`/`language_skill_picks`'s "name is the key, not an id" shape -- see
`chummer5.engine.knowledge.KarmaKnowledgeSelection`). All four default to `{}` ("predates this
field"), so every pre-WP53 save round-trips unchanged. Resolved in `build_character` right after
`karma_attribute_selection` (both Step Seven spends against the same ledger, in the order
`chummer5.web.app`'s own `submit_attributes`/`submit_skills` already establish -- attributes
first) and before Bound Spirits, which reads `character.karma_remaining` and must therefore see
both already-resolved.

**WP55** adds `quality_text` -- `{quality_id: free_text}` for exactly the selected `BonusSupport
.SELECT_TEXT` qualities (e.g. SINner's chosen SIN, Code of Honor's protected group). Defaults to
`{}` ("predates this field"), so every pre-WP55 save round-trips unchanged. Threaded straight into
`create_quality_selection`'s new `quality_text` parameter alongside `save.quality_ids` -- no
separate resolution step is needed, since `create_quality_selection` itself validates that every
selected `SELECT_TEXT` quality has a non-blank entry and that no entry is orphaned.

**WP107** replaces `quality_ids` and WP55's `quality_text` with `quality_picks`, one
`{quality_id, rating, text, choice}` object per quality *instance* -- an id-keyed text map cannot
represent two Addictions, and a flat id list cannot represent Focused Concentration 3. This is the
first real schema break, so `FORMAT_VERSION` goes to 2; version-1 files are still read and migrated
exactly by `_quality_picks_from_dict` (each id becomes one rating-1 pick carrying its text).

**WP92** adds `vehicle_ids` -- purchased stock vehicles/drones as catalog ids, repeats meaning
quantity. The simplest persistable selection in this file: no tree (unlike cyberware), no player
choice (unlike bioware's `Reflex Recorder`), no Force (unlike foci), because a stock vehicle
purchase carries none of those. Defaults to `()` ("predates this field"), so every pre-WP92 save
round-trips unchanged. `build_character` resolves it third among the shared-nuyen-pool spenders
(cyberware, then bioware, then vehicles) and folds `vehicle_selection.nuyen_spent` back into
`resources_selection` in the same re-call that already folds cyberware's and bioware's.

**WP109** adds `unworn_armor` -- the names of purchased armor the player marked as not worn.
Additive with a `()` default ("everything bought is worn"), so no version bump.

**WP124** keys each exotic-skill instance `"{skill_id}|{specific}"` inside the existing
`skill_points`/`karma_skill_points` maps (`chummer5.engine.skills.exotic_skill_key`). No new field
and no version bump: the maps' shape is unchanged. A pre-WP124 save's bare exotic id is moved onto
an "Unspecified" instance by `build_character`, and its exotic specialization, which the book never
allowed, is dropped.

**WP127** adds `grade` to each cyberware purchase node and each bioware purchase (`"Standard"`,
`"Alphaware"` or `"Used"`). Additive: an older save's missing key reads as Standard, which is all
it could have bought. A plugin's stored grade is its parent's; the engine ignores it and inherits.

**WP128** adds `rating` to each bioware purchase, for the rated rows it offers. Additive, default 1
(every flat row's only rating).

**WP125** adds `knowledge_specializations` and `karma_knowledge_specializations`, pick name ->
specialization, the same name-keyed shape as `karma_knowledge_points`. Additive, `{}` default, no
bump. A Knowledge/Language pick may now be rated 0 (Karma buys it), and the Knowledge spend past
its free pool is re-derived, not stored: `build_character` passes it to `create_skill_allocation`.

**WP132** adds `lifestyle_options` (`{name, text}` per Lifestyle Option) and `lifestyle_permanent`.
Additive, defaulting to none and `false`. A permanent Lifestyle also stores `lifestyle_months` =
100, so an older reader prices it the same.

**`format_version` is a real field from day one, not speculative scaffolding.** Unlike the
"validate now, don't add hooks for hypothetical future rules" discipline used elsewhere in this
project, a save *file* is data that outlives the code that wrote it by construction -- the legacy
`.chum5` format itself carries an analogous `<appversion>` tag (confirmed by inspection of the
corpus). `from_json`/`from_dict` reject any version not in `READABLE_FORMAT_VERSIONS` outright
rather than guessing. Through WP106 there was exactly one version; WP107's is the first migration
(see its paragraph above), and it is written per field, not as a generic upgrade pass.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any

from chummer5.data.bioware import Bioware
from chummer5.data.cyberware_subsystems import CyberwareEntry
from chummer5.data.foci import Focus
from chummer5.data.grades import STANDARD_GRADE
from chummer5.data.lifestyle import LifestyleTier, load_lifestyle_options
from chummer5.data.mentors import MentorSpiritArchetype
from chummer5.data.metatypes import Metatype
from chummer5.data.powers import Power
from chummer5.data.priorities import PriorityTable
from chummer5.data.qualities import Quality
from chummer5.data.skills import Skill
from chummer5.data.spells import Spell
from chummer5.data.traditions import Tradition
from chummer5.data.vehicles import Vehicle
from chummer5.engine.bioware import (
    BiowarePurchaseRequest,
    apply_bioware_improvements,
    augmentation_names,
    bioware_disabled,
    create_bioware_selection,
)
from chummer5.engine.build_method import PRIORITY_BUILD_METHOD
from chummer5.engine.character import (
    Character,
    create_character,
    create_karma_attribute_points,
    metatype_choices,
)
from chummer5.engine.cyberware_subsystems import (
    CyberwarePurchaseRequest,
    apply_cyberware_tree_improvements,
    create_cyberware_tree_selection,
    cyberlimb_attribute_maximums,
    cyberware_essence_multiplier,
)
from chummer5.engine.foci import apply_foci_improvements, create_foci_selection
from chummer5.engine.improvements import ImprovementSource
from chummer5.engine.knowledge import (
    KnowledgeSkillPick,
    LanguageSkillPick,
    create_karma_knowledge_selection,
    create_knowledge_selection,
)
from chummer5.engine.lifestyle import create_lifestyle_selection, lifestyle_cost_percent
from chummer5.engine.magic import (
    apply_magic_skill_grant_improvements,
    apply_power_improvements,
    create_magic_attribute_points,
    create_magic_selection,
    create_power_selection,
    create_spell_selection,
    offered_talent_options,
)
from chummer5.engine.qualities import (
    QualityPickRequest,
    apply_mentor_spirit_improvements,
    apply_metatype_bonus_improvements,
    apply_quality_improvements,
    create_quality_selection,
    requested_attribute_maximum_bonuses,
    resolve_metatype_qualities,
)
from chummer5.engine.resources import (
    Contact,
    create_contact_selection,
    create_resources_selection,
)
from chummer5.engine.skills import (
    create_karma_skill_selection,
    create_skill_allocation,
    drop_exotic_specializations,
    migrate_bare_exotic_keys,
    skill_point_budget,
    skill_purchase_rules,
)
from chummer5.engine.spirits import create_bound_spirit_selection
from chummer5.engine.vehicles import VEHICLE_CATALOG, create_vehicle_selection

# Bumped only if a future WP changes this format's shape in a way older saves can't be read as.
# MVP has exactly one version; there is no migration path yet because there is nothing to migrate
# from.
FORMAT_VERSION = 2
# WP107: version 1 (`quality_ids` + `quality_text`) is still read, and migrated on the way in -- see
# `_quality_picks_from_dict`. Only FORMAT_VERSION is ever written.
READABLE_FORMAT_VERSIONS = (1, 2)

# See the module docstring's WP28 paragraph for why this duplicates (rather than imports)
# `chummer5.web.session.DEFAULT_TALENT_LETTER`'s value.
DEFAULT_TALENT_LETTER = "E"
DEFAULT_TALENT_CODENAME = "Mundane"

# One `(power_id, rating, target)` triple, as `create_power_selection` already takes --
# see that function's own docstring. Named here so `CharacterSave.power_picks`'s element type has a
# readable name instead of an inline tuple annotation repeated at every use site.
PowerPickTriple = tuple[str, int, str | None]

# One `(spirit_type_name, force, services)` triple, as `create_bound_spirit_selection` already
# takes -- see that function's own docstring. `force` is `int | None` (None = "default to the
# character's Magic rating", which is how a pre-WP70 save without a stored Force resolves). Named
# for the same readability reason as PowerPickTriple.
BoundSpiritPickTriple = tuple[str, int | None, int]

# One `(focus_id, force)` pair, as `create_foci_selection` already takes -- see that function's own
# docstring. Named for the same readability reason as PowerPickTriple/BoundSpiritPickTriple.
FociPickPair = tuple[str, int]

# One `(gear_name, rating)` pair for a Rating-priced starter-gear purchase (WP66), as
# `create_resources_selection`'s `rating_gear` argument takes -- repeats allowed for quantity.
# Named for the same readability reason as PowerPickTriple/FociPickPair.
RatingGearPick = tuple[str, int]

# One `(name, category, rating)` triple, as `chummer5.engine.knowledge.KnowledgeSkillPick` carries
# -- see that class's own docstring. Named for the same readability reason as PowerPickTriple.
KnowledgeSkillPickTriple = tuple[str, str, int]

# One `(name, rating, native)` triple, as `chummer5.engine.knowledge.LanguageSkillPick` carries.
LanguageSkillPickTriple = tuple[str, int, bool]


@dataclass(frozen=True)
class CharacterSave:
    """Every player-authored selection needed to reconstruct a full mundane MVP character.

    One-to-one with the parameters `create_character`/`create_skill_allocation`/
    `create_quality_selection`/`create_contact_selection`/`create_resources_selection` already
    take -- see the module docstring for why this holds selections, not computed state. `Contact`
    is reused directly from `chummer5.engine.resources` rather than a redundant save-format-local
    copy: it's already a plain, frozen, JSON-shaped (str/int/bool) dataclass with no engine state
    to strip out.
    """

    metatype_name: str
    heritage_letter: str
    attributes_letter: str
    attribute_points: MappingProxyType[str, int]
    skills_letter: str
    skill_points: MappingProxyType[str, int]
    group_points: MappingProxyType[str, int]
    # WP107: one entry per quality *instance* (rating, free-text detail, choice), replacing WP8's
    # `quality_ids` and WP55's `quality_text` -- see the module docstring's WP107 paragraph.
    quality_picks: tuple[QualityPickRequest, ...]
    contacts: tuple[Contact, ...]
    resources_letter: str
    gear_names: tuple[str, ...]
    lifestyle_tier_name: str
    lifestyle_months: int
    talent_letter: str = DEFAULT_TALENT_LETTER
    talent_codename: str = DEFAULT_TALENT_CODENAME
    tradition_id: str | None = None
    # WP121: an Aspected Magician's group. Absent from older saves, which hold no Aspected Magician.
    magic_aspect: str | None = None
    granted_skill_ids: tuple[str, ...] = ()
    spell_ids: tuple[str, ...] = ()
    power_picks: tuple[PowerPickTriple, ...] = ()
    # Post-WP29 correction: Special Attribute Points spent raising Magic beyond magic_rating (see
    # chummer5.engine.character.Character's own docstring correction and chummer5.engine.magic
    # .create_magic_attribute_points). Defaults to 0 for the same "predates this field" reason
    # every other WP28 magic field defaults to Mundane.
    magic_attribute_points: int = 0
    # WP33, retyped from a flat id list to WP38's purchase tree in WP41 (see module docstring).
    # Defaults to () -- "predates this field", the same shape every WP28 magic field defaults to.
    cyberware_purchases: tuple[CyberwarePurchaseRequest, ...] = ()
    # WP45, retyped from a flat id list to WP80's purchase requests (see module docstring) so a
    # Reflex Recorder's chosen skill survives a save/load. Defaults to () -- "predates this field",
    # the identical shape cyberware_purchases already has.
    bioware_purchases: tuple[BiowarePurchaseRequest, ...] = ()
    # WP43: Karma converted to nuyen at Step Six (core rulebook p. 94, up to 10). Defaults to 0 --
    # "predates this field"/"player didn't convert any", the same shape every prior optional field
    # defaults to.
    karma_converted: int = 0
    # WP46: a Magician's bound spirits, as (spirit_type, services) pairs -- see module docstring for
    # why `force` is never persisted. Defaults to () -- "predates this field", the identical shape
    # every other optional selection field defaults to.
    bound_spirit_picks: tuple[BoundSpiritPickTriple, ...] = ()
    # WP47: a magic-active character's bonded foci, as (focus_id, force) pairs. Defaults to () --
    # "predates this field", the identical shape every other optional selection field defaults to.
    foci_picks: tuple[FociPickPair, ...] = ()
    # WP48: a magic-active character's picked Mentor Spirit archetype id, and (only when that
    # archetype's General bonus slot is itself a choice) the chosen option's id. Both default to
    # None -- "predates this field"/"Mentor Spirit not taken", the same shape every other optional
    # selection field defaults to.
    mentor_spirit_archetype_id: str | None = None
    mentor_spirit_general_choice_id: str | None = None
    # WP122: Dragonslayer's skill of choice, and the Adept slot's free-power targets in order.
    mentor_spirit_skill_choice: str | None = None
    mentor_spirit_power_targets: tuple[str | None, ...] = ()
    # WP44: which priority-letter validity rule produced the 5 letters above -- see module
    # docstring for why this is carried through unvalidated rather than re-checked here.
    build_method: str = PRIORITY_BUILD_METHOD
    # WP49: Knowledge/Language skill picks. Both default to () -- "predates this field", the
    # identical shape every other optional selection field defaults to.
    knowledge_skill_picks: tuple[KnowledgeSkillPickTriple, ...] = ()
    language_skill_picks: tuple[LanguageSkillPickTriple, ...] = ()
    # WP50: skill_id -> specialization name. Defaults to {} -- "predates this field", the identical
    # shape every other optional selection field defaults to.
    specializations: MappingProxyType[str, str] = MappingProxyType({})
    # WP52: attribute code -> extra points bought with leftover Karma beyond the priority budget
    # (ALLOCATABLE_ATTRIBUTES only -- see chummer5.engine.character.KarmaAttributeSelection's own
    # docstring for why MAG/RES are excluded). Defaults to {} -- "predates this field", the
    # identical shape every other optional selection field defaults to.
    karma_attribute_points: MappingProxyType[str, int] = MappingProxyType({})
    # WP53: Karma-funded Active skill/skill-group increases and specializations, mirroring
    # skill_points/group_points/specializations' own shapes. Defaults to {} -- "predates this
    # field", the identical shape every other optional selection field defaults to.
    karma_skill_points: MappingProxyType[str, int] = MappingProxyType({})
    karma_group_points: MappingProxyType[str, int] = MappingProxyType({})
    karma_specializations: MappingProxyType[str, str] = MappingProxyType({})
    # WP53: Karma-funded Knowledge/Language rating increases, keyed by pick name (see
    # chummer5.engine.knowledge.KarmaKnowledgeSelection). Defaults to {} -- "predates this field".
    karma_knowledge_points: MappingProxyType[str, int] = MappingProxyType({})
    # WP125: Knowledge/Language specializations by pick name, point-funded and Karma-funded.
    knowledge_specializations: MappingProxyType[str, str] = MappingProxyType({})
    karma_knowledge_specializations: MappingProxyType[str, str] = MappingProxyType({})
    # WP132: the primary Lifestyle's Options, as (name, text) pairs, and a permanent purchase.
    lifestyle_options: tuple[tuple[str, str | None], ...] = ()
    lifestyle_permanent: bool = False
    # WP66: Rating-priced starter-gear purchases, as (gear_name, rating) pairs (repeats = quantity)
    # -- kept separate from flat `gear_names` since a rating item's price depends on the chosen
    # rating. Defaults to () -- "predates this field", the identical shape every other optional
    # selection field defaults to.
    rating_gear_picks: tuple[RatingGearPick, ...] = ()
    # WP92: purchased stock vehicles/drones, as catalog ids (repeats = quantity, e.g. four
    # Fly-Spies). A bare id list is the whole persistable shape a vehicle purchase has -- unlike
    # cyberware there is no tree, unlike bioware no player choice, unlike foci no Force. Defaults
    # to () -- "predates this field", the identical shape every other optional selection field
    # defaults to.
    vehicle_ids: tuple[str, ...] = ()
    # WP109: names of purchased armor marked *not* worn (`Character.unworn_armor`). Defaults to ()
    # -- "predates this field", which is also "everything bought is worn".
    unworn_armor: tuple[str, ...] = ()


def create_character_save(
    *,
    metatype_name: str,
    heritage_letter: str,
    attributes_letter: str,
    attribute_points: Mapping[str, int],
    skills_letter: str,
    skill_points: Mapping[str, int],
    group_points: Mapping[str, int],
    quality_picks: Iterable[str | QualityPickRequest],
    contacts: Iterable[Contact],
    resources_letter: str,
    gear_names: Iterable[str],
    lifestyle_tier_name: str,
    lifestyle_months: int,
    talent_letter: str = DEFAULT_TALENT_LETTER,
    talent_codename: str = DEFAULT_TALENT_CODENAME,
    tradition_id: str | None = None,
    magic_aspect: str | None = None,
    granted_skill_ids: Iterable[str] = (),
    spell_ids: Iterable[str] = (),
    power_picks: Iterable[PowerPickTriple] = (),
    magic_attribute_points: int = 0,
    cyberware_purchases: Iterable[CyberwarePurchaseRequest] = (),
    bioware_purchases: Iterable[str | BiowarePurchaseRequest] = (),
    karma_converted: int = 0,
    bound_spirit_picks: Iterable[BoundSpiritPickTriple] = (),
    foci_picks: Iterable[FociPickPair] = (),
    mentor_spirit_archetype_id: str | None = None,
    mentor_spirit_general_choice_id: str | None = None,
    mentor_spirit_skill_choice: str | None = None,
    mentor_spirit_power_targets: Iterable[str | None] = (),
    build_method: str = PRIORITY_BUILD_METHOD,
    knowledge_skill_picks: Iterable[KnowledgeSkillPickTriple] = (),
    language_skill_picks: Iterable[LanguageSkillPickTriple] = (),
    specializations: Mapping[str, str] = MappingProxyType({}),
    karma_attribute_points: Mapping[str, int] = MappingProxyType({}),
    karma_skill_points: Mapping[str, int] = MappingProxyType({}),
    karma_group_points: Mapping[str, int] = MappingProxyType({}),
    karma_specializations: Mapping[str, str] = MappingProxyType({}),
    karma_knowledge_points: Mapping[str, int] = MappingProxyType({}),
    knowledge_specializations: Mapping[str, str] = MappingProxyType({}),
    karma_knowledge_specializations: Mapping[str, str] = MappingProxyType({}),
    lifestyle_options: Iterable[tuple[str, str | None]] = (),
    lifestyle_permanent: bool = False,
    rating_gear_picks: Iterable[RatingGearPick] = (),
    vehicle_ids: Iterable[str] = (),
    unworn_armor: Iterable[str] = (),
) -> CharacterSave:
    """Build a `CharacterSave` from plain selections, wrapping mappings/iterables the same
    immutable-field way `create_character`/`create_skill_allocation` already do.

    No validation here -- `build_character` re-runs the exact `create_*` functions that already
    validate every one of these values, so duplicating that logic on the way *in* would just be a
    second copy of the same checks with no new value (and a save file's contents are only ever
    trusted as far as `build_character` accepts them, never before).
    """
    return CharacterSave(
        metatype_name=metatype_name,
        heritage_letter=heritage_letter,
        attributes_letter=attributes_letter,
        attribute_points=MappingProxyType(dict(attribute_points)),
        skills_letter=skills_letter,
        skill_points=MappingProxyType(dict(skill_points)),
        group_points=MappingProxyType(dict(group_points)),
        quality_picks=tuple(
            QualityPickRequest(quality_id=p) if isinstance(p, str) else p for p in quality_picks
        ),
        contacts=tuple(contacts),
        resources_letter=resources_letter,
        gear_names=tuple(gear_names),
        lifestyle_tier_name=lifestyle_tier_name,
        lifestyle_months=lifestyle_months,
        talent_letter=talent_letter,
        talent_codename=talent_codename,
        magic_aspect=magic_aspect,
        tradition_id=tradition_id,
        granted_skill_ids=tuple(granted_skill_ids),
        spell_ids=tuple(spell_ids),
        power_picks=tuple(power_picks),
        magic_attribute_points=magic_attribute_points,
        cyberware_purchases=tuple(cyberware_purchases),
        bioware_purchases=tuple(_as_bioware_request(p) for p in bioware_purchases),
        karma_converted=karma_converted,
        bound_spirit_picks=tuple(bound_spirit_picks),
        foci_picks=tuple(foci_picks),
        mentor_spirit_archetype_id=mentor_spirit_archetype_id,
        mentor_spirit_general_choice_id=mentor_spirit_general_choice_id,
        mentor_spirit_skill_choice=mentor_spirit_skill_choice,
        mentor_spirit_power_targets=tuple(mentor_spirit_power_targets),
        build_method=build_method,
        knowledge_skill_picks=tuple(knowledge_skill_picks),
        language_skill_picks=tuple(language_skill_picks),
        specializations=MappingProxyType(dict(specializations)),
        karma_attribute_points=MappingProxyType(dict(karma_attribute_points)),
        karma_skill_points=MappingProxyType(dict(karma_skill_points)),
        karma_group_points=MappingProxyType(dict(karma_group_points)),
        karma_specializations=MappingProxyType(dict(karma_specializations)),
        karma_knowledge_points=MappingProxyType(dict(karma_knowledge_points)),
        knowledge_specializations=MappingProxyType(dict(knowledge_specializations)),
        karma_knowledge_specializations=MappingProxyType(dict(karma_knowledge_specializations)),
        lifestyle_options=tuple(lifestyle_options),
        lifestyle_permanent=lifestyle_permanent,
        rating_gear_picks=tuple(rating_gear_picks),
        vehicle_ids=tuple(vehicle_ids),
        unworn_armor=tuple(sorted(set(unworn_armor))),
    )


def _purchase_to_dict(purchase: CyberwarePurchaseRequest) -> dict[str, Any]:
    """One cyberware purchase-tree node as JSON (WP41), recursing into its plugins.

    Written unconditionally with all three keys, even for the overwhelmingly common zero-plugin,
    rating-1 leaf, so a save file reads the same way at every node -- this format has never
    optimized for byte count (`indent=2`), and an omitted key would make "rating not stated" and
    "rating 1" indistinguishable to a human reading the file.
    """
    return {
        "item_id": purchase.item_id,
        "rating": purchase.rating,
        "plugins": [_purchase_to_dict(plugin) for plugin in purchase.plugins],
        "grade": purchase.grade,  # WP127
    }


def _purchase_from_dict(data: Mapping[str, Any]) -> CyberwarePurchaseRequest:
    return CyberwarePurchaseRequest(
        item_id=data["item_id"],
        rating=data.get("rating", 1),
        plugins=tuple(_purchase_from_dict(p) for p in data.get("plugins", ())),
        grade=data.get("grade", STANDARD_GRADE),
    )


def _as_bioware_request(purchase: str | BiowarePurchaseRequest) -> BiowarePurchaseRequest:
    """A bare id means "this item, no player choice" (WP80) -- the same shorthand
    `create_bioware_selection` itself accepts, so a caller with nothing to pick keeps passing ids.
    """
    return BiowarePurchaseRequest(item_id=purchase) if isinstance(purchase, str) else purchase


def _bioware_purchase_to_dict(purchase: BiowarePurchaseRequest) -> dict[str, Any]:
    """One bioware purchase as JSON (WP80), with both keys written unconditionally for the same
    reason `_purchase_to_dict` writes all three: a save file should read the same way at every
    entry, and `null` is a clearer "no pick to make" than an absent key."""
    return {
        "item_id": purchase.item_id,
        "chosen_skill": purchase.chosen_skill,
        "grade": purchase.grade,  # WP127
        "rating": purchase.rating,  # WP128
    }


def _bioware_purchases_from_dict(data: Mapping[str, Any]) -> tuple[BiowarePurchaseRequest, ...]:
    """Read WP80's `bioware_purchases`, falling back to WP45's flat `bioware_item_ids`.

    See the module docstring for the one row (`Reflex Recorder`) whose fallback is deliberately not
    exact: its pick was never persisted before WP80, so such a save now fails to build rather than
    loading with a silently-dropped bonus.
    """
    if "bioware_purchases" in data:
        return tuple(
            BiowarePurchaseRequest(
                item_id=purchase["item_id"],
                chosen_skill=purchase.get("chosen_skill"),
                grade=purchase.get("grade", STANDARD_GRADE),
                rating=purchase.get("rating", 1),
            )
            for purchase in data["bioware_purchases"]
        )
    return tuple(
        BiowarePurchaseRequest(item_id=item_id) for item_id in data.get("bioware_item_ids", ())
    )


def _quality_picks_from_dict(data: Mapping[str, Any]) -> tuple[QualityPickRequest, ...]:
    """Read WP107's `quality_picks`, migrating a version-1 save's `quality_ids` + `quality_text`.

    The migration is exact: version 1 could only express "each id once, at rating 1", and its
    `quality_text` was keyed by id, so each id's text lands on its one pick.
    """
    if "quality_picks" in data:
        return tuple(
            QualityPickRequest(
                quality_id=p["quality_id"],
                rating=p.get("rating", 1),
                text=p.get("text"),
                choice=p.get("choice"),
            )
            for p in data["quality_picks"]
        )
    quality_text: Mapping[str, str] = data.get("quality_text", {})
    return tuple(
        QualityPickRequest(quality_id=qid, text=quality_text.get(qid))
        for qid in data.get("quality_ids", ())
    )


def _purchases_from_dict(data: Mapping[str, Any]) -> tuple[CyberwarePurchaseRequest, ...]:
    """Read WP41's `cyberware_purchases`, falling back to WP33's flat `cyberware_item_ids`.

    See the module docstring for why that fallback is exact rather than lossy: every WP33-era id is
    also a WP37 catalog id, and every WP31 row is unrated (so rating 1 is its only legal value).
    """
    if "cyberware_purchases" in data:
        return tuple(_purchase_from_dict(p) for p in data["cyberware_purchases"])
    return tuple(
        CyberwarePurchaseRequest(item_id=item_id) for item_id in data.get("cyberware_item_ids", ())
    )


def _save_to_dict(save: CharacterSave) -> dict[str, Any]:
    return {
        "format_version": FORMAT_VERSION,
        "metatype_name": save.metatype_name,
        "heritage_letter": save.heritage_letter,
        "attributes_letter": save.attributes_letter,
        "attribute_points": dict(save.attribute_points),
        "skills_letter": save.skills_letter,
        "skill_points": dict(save.skill_points),
        "group_points": dict(save.group_points),
        "quality_picks": [
            {"quality_id": p.quality_id, "rating": p.rating, "text": p.text, "choice": p.choice}
            for p in save.quality_picks
        ],
        "contacts": [
            {
                "name": contact.name,
                "connection": contact.connection,
                "loyalty": contact.loyalty,
                "free": contact.free,
            }
            for contact in save.contacts
        ],
        "resources_letter": save.resources_letter,
        "gear_names": list(save.gear_names),
        "lifestyle_tier_name": save.lifestyle_tier_name,
        "lifestyle_months": save.lifestyle_months,
        "talent_letter": save.talent_letter,
        "talent_codename": save.talent_codename,
        "tradition_id": save.tradition_id,
        "magic_aspect": save.magic_aspect,
        "granted_skill_ids": list(save.granted_skill_ids),
        "spell_ids": list(save.spell_ids),
        "power_picks": [
            {"power_id": power_id, "rating": rating, "target": target}
            for power_id, rating, target in save.power_picks
        ],
        "magic_attribute_points": save.magic_attribute_points,
        "cyberware_purchases": [
            _purchase_to_dict(purchase) for purchase in save.cyberware_purchases
        ],
        "bioware_purchases": [
            _bioware_purchase_to_dict(purchase) for purchase in save.bioware_purchases
        ],
        "karma_converted": save.karma_converted,
        "bound_spirit_picks": [
            {"spirit_type": spirit_type, "force": force, "services": services}
            for spirit_type, force, services in save.bound_spirit_picks
        ],
        "foci_picks": [
            {"focus_id": focus_id, "force": force} for focus_id, force in save.foci_picks
        ],
        "mentor_spirit_archetype_id": save.mentor_spirit_archetype_id,
        "mentor_spirit_general_choice_id": save.mentor_spirit_general_choice_id,
        "mentor_spirit_skill_choice": save.mentor_spirit_skill_choice,
        "mentor_spirit_power_targets": list(save.mentor_spirit_power_targets),
        "build_method": save.build_method,
        "knowledge_skill_picks": [
            {"name": name, "category": category, "rating": rating}
            for name, category, rating in save.knowledge_skill_picks
        ],
        "language_skill_picks": [
            {"name": name, "rating": rating, "native": native}
            for name, rating, native in save.language_skill_picks
        ],
        "specializations": dict(save.specializations),
        "karma_attribute_points": dict(save.karma_attribute_points),
        "karma_skill_points": dict(save.karma_skill_points),
        "karma_group_points": dict(save.karma_group_points),
        "karma_specializations": dict(save.karma_specializations),
        "karma_knowledge_points": dict(save.karma_knowledge_points),
        "knowledge_specializations": dict(save.knowledge_specializations),
        "karma_knowledge_specializations": dict(save.karma_knowledge_specializations),
        "lifestyle_options": [{"name": n, "text": t} for n, t in save.lifestyle_options],
        "lifestyle_permanent": save.lifestyle_permanent,
        "rating_gear_picks": [
            {"name": name, "rating": rating} for name, rating in save.rating_gear_picks
        ],
        "vehicle_ids": list(save.vehicle_ids),
        "unworn_armor": list(save.unworn_armor),
    }


def _dict_to_save(data: Mapping[str, Any]) -> CharacterSave:
    version = data.get("format_version")
    if version not in READABLE_FORMAT_VERSIONS:
        raise ValueError(
            f"unsupported save format version {version!r}; this build reads "
            f"{list(READABLE_FORMAT_VERSIONS)!r}"
        )
    return create_character_save(
        metatype_name=data["metatype_name"],
        heritage_letter=data["heritage_letter"],
        attributes_letter=data["attributes_letter"],
        attribute_points=data["attribute_points"],
        skills_letter=data["skills_letter"],
        skill_points=data["skill_points"],
        group_points=data["group_points"],
        quality_picks=_quality_picks_from_dict(data),
        contacts=(
            Contact(
                name=c["name"],
                connection=c["connection"],
                loyalty=c["loyalty"],
                free=c["free"],
            )
            for c in data["contacts"]
        ),
        resources_letter=data["resources_letter"],
        gear_names=data["gear_names"],
        lifestyle_tier_name=data["lifestyle_tier_name"],
        lifestyle_months=data["lifestyle_months"],
        # `.get(..., default)`, not `data[...]`: a save written before WP28 has none of these keys
        # at all -- still the same FORMAT_VERSION (1), since this is a purely additive, backward-
        # compatible shape change (every new field already defaults to Mundane), not the kind of
        # breaking schema change `FORMAT_VERSION` exists to gate.
        talent_letter=data.get("talent_letter", DEFAULT_TALENT_LETTER),
        talent_codename=data.get("talent_codename", DEFAULT_TALENT_CODENAME),
        tradition_id=data.get("tradition_id"),
        magic_aspect=data.get("magic_aspect"),
        granted_skill_ids=data.get("granted_skill_ids", ()),
        spell_ids=data.get("spell_ids", ()),
        power_picks=(
            # WP119: `target` replaced `selected_attribute`; an older save's key still reads.
            (p["power_id"], p["rating"], p.get("target", p.get("selected_attribute")))
            for p in data.get("power_picks", ())
        ),
        magic_attribute_points=data.get("magic_attribute_points", 0),
        cyberware_purchases=_purchases_from_dict(data),
        bioware_purchases=_bioware_purchases_from_dict(data),
        karma_converted=data.get("karma_converted", 0),
        bound_spirit_picks=(
            (p["spirit_type"], p.get("force"), p["services"])
            for p in data.get("bound_spirit_picks", ())
        ),
        foci_picks=((p["focus_id"], p["force"]) for p in data.get("foci_picks", ())),
        mentor_spirit_archetype_id=data.get("mentor_spirit_archetype_id"),
        mentor_spirit_general_choice_id=data.get("mentor_spirit_general_choice_id"),
        mentor_spirit_skill_choice=data.get("mentor_spirit_skill_choice"),
        mentor_spirit_power_targets=tuple(data.get("mentor_spirit_power_targets", ())),
        build_method=data.get("build_method", PRIORITY_BUILD_METHOD),
        knowledge_skill_picks=(
            (p["name"], p["category"], p["rating"]) for p in data.get("knowledge_skill_picks", ())
        ),
        language_skill_picks=(
            (p["name"], p["rating"], p["native"]) for p in data.get("language_skill_picks", ())
        ),
        specializations=data.get("specializations", {}),
        karma_attribute_points=data.get("karma_attribute_points", {}),
        karma_skill_points=data.get("karma_skill_points", {}),
        karma_group_points=data.get("karma_group_points", {}),
        karma_specializations=data.get("karma_specializations", {}),
        karma_knowledge_points=data.get("karma_knowledge_points", {}),
        knowledge_specializations=data.get("knowledge_specializations", {}),
        karma_knowledge_specializations=data.get("karma_knowledge_specializations", {}),
        lifestyle_options=((o["name"], o.get("text")) for o in data.get("lifestyle_options", ())),
        lifestyle_permanent=data.get("lifestyle_permanent", False),
        rating_gear_picks=((p["name"], p["rating"]) for p in data.get("rating_gear_picks", ())),
        vehicle_ids=data.get("vehicle_ids", ()),
        unworn_armor=data.get("unworn_armor", ()),
    )


def to_json(save: CharacterSave) -> str:
    return json.dumps(_save_to_dict(save), indent=2)


def from_json(text: str) -> CharacterSave:
    data: dict[str, Any] = json.loads(text)
    return _dict_to_save(data)


def build_character(
    save: CharacterSave,
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
    foci: tuple[Focus, ...] = (),
    mentors: tuple[MentorSpiritArchetype, ...] = (),
    vehicles: tuple[Vehicle, ...] = VEHICLE_CATALOG,
) -> Character:
    """Reconstruct a fully-populated `Character` from a `CharacterSave`, re-running the same
    `create_*` validation each selection already has (see module docstring).

    A save always carries every selection at once (unlike an in-progress `ChargenSession`, which
    fills `Character`'s four optional fields in one at a time), so this builds and attaches all
    four in a single `dataclasses.replace` rather than the incremental per-stage updates
    `chummer5.web.app` performs against a live session -- see `chummer5.engine.character
    .Character`'s own docstring for that shape (introduced in WP18, which also retired this
    function's prior `BuiltCharacter` return type: a save's `Character` already carries
    `skill_allocation`/`quality_selection`/`contact_selection`/`resources_selection` directly, so a
    separate bundling type added nothing).

    `metatypes`/`priorities`/`skills`/`qualities` are the static rules catalogs (WP2/WP3's loader
    output) -- passed in rather than loaded here, mirroring how every other engine module takes
    catalogs as parameters instead of loading its own copy.

    **WP28**: `traditions`/`spells`/`powers` default to `()`, unlike `metatypes`/`priorities`/etc.
    -- mirrors `CharacterSave`'s own Mundane-defaulted new fields (see this module's docstring):
    a Mundane save (`save.talent_codename == "Mundane"`, every pre-WP28 save's shape) never
    resolves a tradition or spell/power picks against these catalogs at all, so a caller building
    only Mundane characters (every existing call site, until WP29) has nothing new to pass.

    **WP33**: `cyberware` defaults to `()` for the same reason -- a save with no
    `cyberware_purchases` (every pre-WP33 save) never resolves against it. **WP41** retypes it to
    WP37's wider `CyberwareEntry` catalog (`chummer5.data.cyberware_subsystems
    .load_cyberware_entries()`, all 87 SR5 rows), since a purchase tree's nodes are
    `CyberwareEntry`s -- passing WP31's 60-row flat catalog here no longer type-checks.

    **WP45**: `bioware` defaults to `()` for the same reason -- a save with no `bioware_item_ids`
    (every pre-WP45 save) never resolves against it. Resolved *after* cyberware (a fixed evaluation
    order -- see `chummer5.engine.bioware`'s own module docstring), so its Essence-floor/nuyen
    checks correctly account for cyberware's already-resolved spend.

    **WP47**: `foci` defaults to `()` for the same reason -- a save with no `foci_picks` (every
    pre-WP47 save) never resolves against it. Resolved last of all (after Bound Spirits -- a fixed
    evaluation order, see `chummer5.engine.foci`'s own module docstring), so its Karma budget
    accounts for Bound Spirits' already-resolved `karma_cost` and its nuyen budget accounts for
    gear/Lifestyle/cyberware/bioware's already-resolved spend.

    **WP92**: `vehicles` is the one new catalog that does *not* default to `()`. Unlike
    `traditions`/`cyberware`/`foci`/etc., whose catalogs are only ever consulted by a save that
    opted into that subsystem, `chummer5.engine.vehicles.VEHICLE_CATALOG` is a single, fixed,
    35-row constant with no per-character variation and no filtering a caller could reasonably want
    to override -- so defaulting to it means no existing call site needs to learn about vehicles at
    all, while a test can still substitute a stub. Passing `()` would silently reject every
    `vehicle_ids` entry as an unknown id, which is a worse default than the real catalog.

    **WP53**: `save.karma_skill_points`/`karma_group_points`/`karma_specializations`/`karma_
    knowledge_points` are resolved right after `karma_attribute_selection` (both are Step Seven
    spends against the identical Karma ledger) and before Bound Spirits -- see the inline comment
    at that call site for the exact evaluation-order reasoning.

    **WP54**: `spell_selection` moves from the Magic-selection block (where WP26/WP28 originally
    placed it, before the main `replace()` above) to right after `karma_knowledge_selection` --
    Karma-funded extra spells need `character.karma_remaining` to already reflect every earlier
    Step Seven spend, which only holds once `character` carries `quality_selection`/`contact_
    selection`/`karma_attribute_selection`/`karma_skill_selection`/`karma_knowledge_selection`, all
    attached by that point. `spell_budget`/`spell_magic_rating` are still resolved in the earlier
    Magic-selection block (0 for a non-Magician save either way) since neither depends on the Karma
    ledger.
    """
    heritage = priorities.heritage[save.heritage_letter]
    choice = next(
        (c for c in metatype_choices(heritage, metatypes) if c.metatype.name == save.metatype_name),
        None,
    )
    if choice is None:
        raise ValueError(
            f"{save.metatype_name!r} is not offered under Heritage priority "
            f"{save.heritage_letter!r}"
        )

    character = create_character(
        metatype_choice=choice,
        heritage_letter=save.heritage_letter,
        attributes_letter=save.attributes_letter,
        priorities=priorities,
        attribute_points=save.attribute_points,
        # WP112: Exceptional Attribute / Lucky raise a maximum before any quality is committed.
        maximum_bonus=requested_attribute_maximum_bonuses(save.quality_picks, qualities),
    )

    # WP23: metatype_qualities is never persisted in CharacterSave (it's 100% determined by
    # metatype + the current quality catalog -- see this module's own "selections, not derived
    # values" docstring), so it's re-derived here exactly like a freshly-built Character would.
    metatype_qualities = resolve_metatype_qualities(character.metatype, qualities)
    apply_quality_improvements(
        character, metatype_qualities, source_type=ImprovementSource.METATYPE
    )
    apply_metatype_bonus_improvements(character)  # WP113: Lifestyle surcharge, Reach, dermal armor

    # WP48: computed early (before the Magic-selection block further down) since
    # create_quality_selection needs it to resolve a Mentor Spirit archetype pick -- exactly what
    # create_magic_selection would later derive as MagicSelection.magic_type, for a save whose
    # talent_codename is already known. See this module's own WP48 docstring paragraph.
    magic_type = None if save.talent_codename == "Mundane" else save.talent_codename

    quality_selection = create_quality_selection(
        save.quality_picks,
        qualities,
        magic_type=magic_type,
        mentor_catalog=mentors,
        mentor_spirit_archetype_id=save.mentor_spirit_archetype_id,
        mentor_spirit_general_choice_id=save.mentor_spirit_general_choice_id,
        mentor_spirit_skill_choice=save.mentor_spirit_skill_choice,
        mentor_spirit_power_targets=save.mentor_spirit_power_targets,
        metatype_name=character.metatype.name,
        granted_quality_names=(q.name for q in metatype_qualities),
    )
    apply_quality_improvements(character, quality_selection.qualities)
    if quality_selection.mentor_spirit is not None:
        apply_mentor_spirit_improvements(character, quality_selection.mentor_spirit)

    # WP49: resolved right here, not earlier -- Bilingual's NATIVE_LANGUAGE_LIMIT Improvement
    # (applied by apply_quality_improvements just above) must already be on character.improvements
    # before create_knowledge_selection reads it (see chummer5.engine.knowledge
    # .native_language_limit).
    knowledge_selection = create_knowledge_selection(
        character,
        (
            KnowledgeSkillPick(name=name, category=category, rating=rating)
            for name, category, rating in save.knowledge_skill_picks
        ),
        (
            LanguageSkillPick(name=name, rating=rating, native=native)
            for name, rating, native in save.language_skill_picks
        ),
        save.knowledge_specializations,
        # WP125: bounded by the whole Skills budget here; `create_skill_allocation` below counts
        # `active_points_used` against what the Active skills actually left.
        active_points_available=skill_point_budget(save.skills_letter, priorities).skills,
    )

    contact_selection = create_contact_selection(character, save.contacts)

    lifestyle_selection = create_lifestyle_selection(
        save.lifestyle_tier_name,
        save.lifestyle_months,
        lifestyles,
        cost_percent=lifestyle_cost_percent(character),  # WP113: Dwarf/Troll surcharge
        # WP132: Lifestyle Options and a permanent purchase.
        options=save.lifestyle_options,
        option_catalog=load_lifestyle_options(),
        permanent=save.lifestyle_permanent,
    )

    resources_selection = create_resources_selection(
        save.resources_letter,
        priorities,
        gear_names=save.gear_names,
        rating_gear=save.rating_gear_picks,
        lifestyle_cost=lifestyle_selection.total_cost,
        karma_converted=save.karma_converted,
    )

    # WP33: cyberware draws from the same shared Step Six nuyen pool gear/Lifestyle already spent
    # out of `resources_selection.nuyen_budget` -- `nuyen_remaining` is exactly what's left (see
    # chummer5.engine.cyberware_subsystems' own docstring for the confirmed-shared-budget citation).
    # WP41: built as a purchase tree. `attribute_maximums` is what `{AGIMaximum}`/`{STRMaximum}`
    # rating bounds resolve against (Customized Agility/Strength only) -- `character` already
    # carries its metatype's ranges at this point, and passing them unconditionally means a save
    # carrying one of those two items validates the same way a live chargen session does.
    cyberware_selection = create_cyberware_tree_selection(
        save.cyberware_purchases,
        cyberware,
        resources_selection.nuyen_remaining,
        attribute_maximums=cyberlimb_attribute_maximums(character),
        essence_multiplier=cyberware_essence_multiplier(character),  # WP117: Sensitive System
    )
    apply_cyberware_tree_improvements(character, cyberware_selection)

    # WP45: bioware is resolved second (a fixed evaluation order -- see chummer5.engine.bioware's
    # own docstring), against whatever nuyen cyberware left over and cyberware's own essence_spent
    # as other_essence_spent, so the shared Essence floor accounts for both.
    bioware_selection = create_bioware_selection(
        save.bioware_purchases,
        bioware,
        resources_selection.nuyen_remaining - cyberware_selection.nuyen_spent,
        other_essence_spent=cyberware_selection.essence_spent,
        # WP80: re-validates a persisted skill pick against the same filter the purchase did.
        skills=skills,
        bioware_disabled=bioware_disabled(character),  # WP117: Sensitive System
        # WP128: Orthoskin with Dermal Plating, a Synaptic Booster with Wired Reflexes, ...
        other_augmentations=augmentation_names(
            character, (node.item.name for node in cyberware_selection.walk())
        ),
    )
    apply_bioware_improvements(character, bioware_selection)

    # WP92: vehicles/drones resolve third, against whatever nuyen cyberware and bioware left. The
    # same fixed-evaluation-order convention cyberware->bioware already follows (chummer5.engine
    # .bioware's module docstring), extended by one: a purchase that only overruns the budget once
    # all three are counted is always caught, on this last call. There is no Essence term and no
    # apply_*_improvements step -- a vehicle grants no Improvement of any kind (see
    # chummer5.engine.vehicles' module docstring).
    vehicle_selection = create_vehicle_selection(
        save.vehicle_ids,
        vehicles,
        resources_selection.nuyen_remaining
        - cyberware_selection.nuyen_spent
        - bioware_selection.nuyen_spent,
    )

    # WP34/WP45/WP92: fold the now-resolved cyberware+bioware+vehicle cost back into
    # `resources_selection` itself, so the `Character` this function returns carries a
    # `nuyen_remaining` that reflects the true 5-way gear+Lifestyle+cyberware+bioware+vehicle spend
    # (what `chummer5.web.app._character_sheet_context` and every other reader of
    # `character.resources_selection` display) rather than the gear+Lifestyle-only figure computed
    # above, before the other three were known. Guaranteed to re-validate cleanly:
    # `create_cyberware_selection`/`create_bioware_selection`/`create_vehicle_selection` above each
    # already confirmed their own nuyen_spent fits what the previous one left, so the combined
    # total still fits the same budget.
    resources_selection = create_resources_selection(
        save.resources_letter,
        priorities,
        gear_names=save.gear_names,
        rating_gear=save.rating_gear_picks,
        lifestyle_cost=lifestyle_selection.total_cost,
        cyberware_cost=cyberware_selection.nuyen_spent,
        bioware_cost=bioware_selection.nuyen_spent,
        karma_converted=save.karma_converted,
        vehicle_cost=vehicle_selection.nuyen_spent,
    )

    # WP28: Magic-type/tradition/free-skill-grant. `apply_magic_skill_grant_improvements` mutates
    # `character.improvements` in place, the same "call it, don't just build the selection" shape
    # `apply_quality_improvements` above already has.
    magic_selection = create_magic_selection(
        save.talent_letter,
        save.talent_codename,
        save.tradition_id,
        save.granted_skill_ids,
        priorities,
        traditions,
        skills,
        aspect=save.magic_aspect,  # WP121
    )
    apply_magic_skill_grant_improvements(character, magic_selection, skills)

    # Post-WP29 correction: Special Attribute Points spent raising MAG beyond magic_selection
    # .magic_rating, drawn from the same pool `create_character` above already validated EDG
    # against -- see chummer5.engine.magic.create_magic_attribute_points's own docstring.
    magic_attribute_points = create_magic_attribute_points(
        magic_selection.magic_type,
        save.magic_attribute_points,
        magic_selection.magic_rating,
        character.attribute_maximum("MAG"),  # WP112: Exceptional Attribute (MAG)
        choice.special_attribute_points,
        save.attribute_points.get("EDG", 0),
    )
    total_magic_rating = magic_selection.magic_rating + magic_attribute_points

    # Spell/power budgets are each the matched Talent option's own field -- 0 for whichever of the
    # two doesn't apply to `magic_selection.magic_type`, which is exactly what lets
    # `create_power_selection` reject a mismatched save's picks via its own existing budget check
    # rather than a special case here. Power Points use `total_magic_rating` (the *finished* Magic
    # rating, including any Special Attribute Points spent), not the raw Talent-granted
    # `magic_rating` alone, per the rulebook's own "Power Points equal to their Magic attribute"
    # (p.278). WP54: `spell_magic_rating` mirrors the same "0 unless Magician" gating as
    # `spell_budget` itself -- an Adept's own nonzero `total_magic_rating` must NOT reach `create_
    # spell_selection`'s "Magic Rating x2" cap computation, since a non-mystic Adept never casts
    # spells at all regardless of Magic rating (see chummer5.engine.spirits' own WP46 citation for
    # the same rule applied to conjuring) -- passing 0 for both keeps that cap at 0 too.
    spell_budget = 0
    spell_magic_rating = 0
    power_point_budget = 0
    # WP121: a Sorcery-aspected Aspected Magician casts too, with its own option's (zero) free
    # spells.
    if magic_selection.magic_type == "Magician" or magic_selection.aspect == "Sorcery":
        magician_option = next(
            o
            for o in offered_talent_options(save.talent_letter, priorities)
            if o.codename == magic_selection.magic_type
        )
        spell_budget = magician_option.spells or 0
        spell_magic_rating = total_magic_rating
    elif magic_selection.magic_type == "Adept":
        power_point_budget = total_magic_rating

    power_selection = create_power_selection(
        save.power_picks, powers, power_point_budget=power_point_budget
    )
    apply_power_improvements(character, power_selection)

    # WP118: the skill spend is validated here, after the Talent and powers, because an Adept's
    # magic-group and Assensing bans (and Astral Perception's unlock) are part of its rules.
    # WP116/WP117: so are Aptitude and the purchase-rule qualities, applied further up.
    skill_allocation = create_skill_allocation(
        letter=save.skills_letter,
        priorities=priorities,
        skills=skills,
        # WP124: a pre-WP124 save may have bought an exotic skill without naming its item.
        skill_points=migrate_bare_exotic_keys(save.skill_points, skills),
        group_points=save.group_points,
        specializations=drop_exotic_specializations(save.specializations, skills),
        rules=skill_purchase_rules(replace(character, magic_type=magic_selection.magic_type)),
        knowledge_active_points=knowledge_selection.active_points_used,  # WP125
    )

    character = replace(
        character,
        skill_allocation=skill_allocation,
        quality_selection=quality_selection,
        contact_selection=contact_selection,
        resources_selection=resources_selection,
        lifestyle_selection=lifestyle_selection,
        metatype_qualities=metatype_qualities,
        magic_type=magic_selection.magic_type,
        magic_aspect=magic_selection.aspect,
        magic_rating=magic_selection.magic_rating,
        tradition=magic_selection.tradition,
        magic_granted_skill_ids=magic_selection.granted_skill_ids,
        power_selection=power_selection,
        magic_attribute_points=magic_attribute_points,
        cyberware_selection=cyberware_selection,
        bioware_selection=bioware_selection,
        knowledge_selection=knowledge_selection,
    )

    # WP52: resolved next, against the now-fully-populated `character` -- `character.karma_
    # remaining` at this point already reflects quality_selection/contact_selection (both set by
    # the replace() above) and nothing else (karma_attribute_selection/bound_spirit_selection/
    # foci_selection are all still None), so it's exactly the right budget to validate this
    # selection's own Karma spend against. Resolved *before* Bound Spirits specifically because
    # create_bound_spirit_selection below reads character.attribute_value("CHA") -- one of
    # PRIMARY_ATTRIBUTES, so it must see any Karma-funded CHA increase already applied, not the
    # pre-Karma value.
    karma_attribute_selection = create_karma_attribute_points(
        character, save.karma_attribute_points, character.karma_remaining
    )
    character = replace(character, karma_attribute_selection=karma_attribute_selection)

    # WP53: resolved next, right after karma_attribute_selection -- character.karma_remaining now
    # also reflects that selection's own cost, exactly the "add the next Step Seven spend's own
    # section, then re-derive the budget for the one after it" evaluation order this function
    # already established for WP52. skill_allocation/knowledge_selection are both already attached
    # (the replace() above), which is all create_karma_skill_selection/create_karma_knowledge_
    # selection need to resolve their own starting ratings from.
    karma_skill_selection = create_karma_skill_selection(
        character,
        skills,
        migrate_bare_exotic_keys(save.karma_skill_points, skills),
        save.karma_group_points,
        drop_exotic_specializations(save.karma_specializations, skills),
        character.karma_remaining,
    )
    character = replace(character, karma_skill_selection=karma_skill_selection)
    karma_knowledge_selection = create_karma_knowledge_selection(
        character,
        save.karma_knowledge_points,
        character.karma_remaining,
        save.karma_knowledge_specializations,
    )
    character = replace(character, karma_knowledge_selection=karma_knowledge_selection)

    # WP54: resolved next, right after karma_knowledge_selection -- character.karma_remaining now
    # also reflects quality/contact/karma_attribute/karma_skill/karma_knowledge costs, exactly the
    # budget a Karma-funded extra spell should be checked against (the same "next Step Seven spend
    # sees the prior ones' cost already reflected" evaluation order WP52/WP53 established).
    spell_selection = create_spell_selection(
        save.spell_ids, spells, spell_budget, spell_magic_rating, character.karma_remaining
    )
    character = replace(character, spell_selection=spell_selection)

    # WP46: resolved next, against the now-fully-populated `character` -- create_bound_spirit_
    # selection reads character.attribute_value("CHA")/("MAG"), both of which depend on the
    # magic_type/tradition/magic_rating/magic_attribute_points/karma_attribute_selection fields
    # already set above (force is always the *live* Magic rating, never a persisted value -- see
    # module docstring). WP51: `character.karma_remaining` at this point already reflects quality_
    # selection/contact_selection/karma_attribute_selection and nothing else (bound_spirit_
    # selection/foci_selection are still None), so it's exactly the pre-WP51 `provisional_karma_
    # budget(quality_selection.karma_cost, contact_selection.karma_cost)` call it replaces, widened
    # by WP52's own term.
    bound_spirit_selection = create_bound_spirit_selection(
        save.bound_spirit_picks, character, character.karma_remaining
    )
    character = replace(character, bound_spirit_selection=bound_spirit_selection)

    # WP47: resolved last of all, against the now-fully-populated `character` (create_foci_
    # selection reads character.attribute_value("MAG"), which depends on the magic fields the
    # replace() above already set) -- a fixed evaluation order, aware of Bound Spirits' own
    # already-resolved karma_cost and of the nuyen resources_selection already spent on gear/
    # Lifestyle/cyberware/bioware. See chummer5.engine.foci's own module docstring for why a
    # one-shot reconstruction like this one needs a fixed order even though neither create_*_
    # selection chains into the other's own call. WP51: `character.karma_remaining` now also
    # reflects the bound_spirit_selection the replace() above just attached, so it's exactly the
    # pre-WP51 `provisional_karma_budget(..., bound_spirit_karma_cost=...)` call it replaces.
    foci_selection = create_foci_selection(
        save.foci_picks,
        character,
        foci,
        resources_selection.nuyen_remaining,
        character.karma_remaining,
    )
    apply_foci_improvements(character, foci_selection)

    # Fold foci's now-resolved nuyen cost back into resources_selection, the same WP34/WP45
    # "re-call once the last shared-budget spender is known" pattern -- guaranteed to re-validate
    # cleanly, since create_foci_selection above already confirmed its own nuyen_cost fits the
    # nuyen_remaining this same resources_selection reported.
    resources_selection = create_resources_selection(
        save.resources_letter,
        priorities,
        gear_names=save.gear_names,
        rating_gear=save.rating_gear_picks,
        lifestyle_cost=lifestyle_selection.total_cost,
        cyberware_cost=cyberware_selection.nuyen_spent,
        bioware_cost=bioware_selection.nuyen_spent,
        karma_converted=save.karma_converted,
        foci_cost=foci_selection.nuyen_cost,
        vehicle_cost=vehicle_selection.nuyen_spent,
    )
    return replace(
        character,
        foci_selection=foci_selection,
        vehicle_selection=vehicle_selection,
        resources_selection=resources_selection,
        unworn_armor=frozenset(save.unworn_armor),
    )
