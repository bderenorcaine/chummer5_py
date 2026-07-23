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

**WP33** adds `cyberware_item_ids` -- purchased `chummer5.data.cyberware.Cyberware` ids, the same
"selection, not derived value" shape every prior field already has. Defaults to `()` ("predates
this field", the same shape every WP28 magic field defaults to), so every save written before this
WP (which never had cyberware to lose) round-trips unchanged. `build_character` validates it
against WP32's `create_cyberware_selection`, using `resources_selection.nuyen_remaining` (gear +
Lifestyle already subtracted) as the shared nuyen budget cyberware draws from -- see
`chummer5.engine.cyberware`'s own docstring for why this is one shared Step Six pool, not a separate
one. **WP34** (the cyberware UI) additionally folds `cyberware_selection.nuyen_spent` back into the
`resources_selection` this function returns, via a second `create_resources_selection` call once
cyberware is resolved -- see this function's own inline comment for why that re-call always
succeeds.

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

**WP46** adds `bound_spirit_picks` -- a Magician's bound spirits, as `(spirit_type, services)`
pairs (the same "selection, not derived value" shape every prior field has -- `force` is never
stored, since it's always exactly the *live* Magic rating at load time, recomputed by `build_
character` the same way it would be for a freshly-committed selection; see `chummer5.engine
.spirits`'s module docstring for why storing a snapshot `force` would just be redundant,
staleness-prone data). Defaults to `()` ("predates this field"), so every save written before this
WP round-trips unchanged.

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
draw against `chummer5.engine.spirits.provisional_karma_budget`'s separate leftover-Karma pool, so
no evaluation-order concern with Bound Spirits/Foci exists here.

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

**`format_version` is a real field from day one, not speculative scaffolding.** Unlike the
"validate now, don't add hooks for hypothetical future rules" discipline used elsewhere in this
project, a save *file* is data that outlives the code that wrote it by construction -- the legacy
`.chum5` format itself carries an analogous `<appversion>` tag (confirmed by inspection of the
corpus). `from_json`/`from_dict` reject anything other than the current `FORMAT_VERSION` outright
rather than guessing at a migration, since MVP has exactly one schema version to support.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any

from chummer5.data.bioware import Bioware
from chummer5.data.cyberware import Cyberware
from chummer5.data.foci import Focus
from chummer5.data.lifestyle import LifestyleTier
from chummer5.data.mentors import MentorSpiritArchetype
from chummer5.data.metatypes import Metatype
from chummer5.data.powers import Power
from chummer5.data.priorities import PriorityTable
from chummer5.data.qualities import Quality
from chummer5.data.skills import Skill
from chummer5.data.spells import Spell
from chummer5.data.traditions import Tradition
from chummer5.engine.bioware import apply_bioware_improvements, create_bioware_selection
from chummer5.engine.build_method import PRIORITY_BUILD_METHOD
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.cyberware import apply_cyberware_improvements, create_cyberware_selection
from chummer5.engine.foci import apply_foci_improvements, create_foci_selection
from chummer5.engine.improvements import ImprovementSource
from chummer5.engine.lifestyle import create_lifestyle_selection
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
    apply_mentor_spirit_improvements,
    apply_quality_improvements,
    create_quality_selection,
    resolve_metatype_qualities,
)
from chummer5.engine.resources import (
    Contact,
    create_contact_selection,
    create_resources_selection,
)
from chummer5.engine.skills import create_skill_allocation
from chummer5.engine.spirits import create_bound_spirit_selection, provisional_karma_budget

# Bumped only if a future WP changes this format's shape in a way older saves can't be read as.
# MVP has exactly one version; there is no migration path yet because there is nothing to migrate
# from.
FORMAT_VERSION = 1

# See the module docstring's WP28 paragraph for why this duplicates (rather than imports)
# `chummer5.web.session.DEFAULT_TALENT_LETTER`'s value.
DEFAULT_TALENT_LETTER = "E"
DEFAULT_TALENT_CODENAME = "Mundane"

# One `(power_id, rating, selected_attribute)` triple, as `create_power_selection` already takes --
# see that function's own docstring. Named here so `CharacterSave.power_picks`'s element type has a
# readable name instead of an inline tuple annotation repeated at every use site.
PowerPickTriple = tuple[str, int, str | None]

# One `(spirit_type_name, services)` pair, as `create_bound_spirit_selection` already takes -- see
# that function's own docstring. Named for the same readability reason as PowerPickTriple.
BoundSpiritPickPair = tuple[str, int]

# One `(focus_id, force)` pair, as `create_foci_selection` already takes -- see that function's own
# docstring. Named for the same readability reason as PowerPickTriple/BoundSpiritPickPair.
FociPickPair = tuple[str, int]


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
    quality_ids: tuple[str, ...]
    contacts: tuple[Contact, ...]
    resources_letter: str
    gear_names: tuple[str, ...]
    lifestyle_tier_name: str
    lifestyle_months: int
    talent_letter: str = DEFAULT_TALENT_LETTER
    talent_codename: str = DEFAULT_TALENT_CODENAME
    tradition_id: str | None = None
    granted_skill_ids: tuple[str, ...] = ()
    spell_ids: tuple[str, ...] = ()
    power_picks: tuple[PowerPickTriple, ...] = ()
    # Post-WP29 correction: Special Attribute Points spent raising Magic beyond magic_rating (see
    # chummer5.engine.character.Character's own docstring correction and chummer5.engine.magic
    # .create_magic_attribute_points). Defaults to 0 for the same "predates this field" reason
    # every other WP28 magic field defaults to Mundane.
    magic_attribute_points: int = 0
    # WP33: purchased cyberware ids (chummer5.data.cyberware.Cyberware.id). Defaults to () --
    # "predates this field", the same shape every WP28 magic field defaults to.
    cyberware_item_ids: tuple[str, ...] = ()
    # WP45: purchased bioware ids (chummer5.data.bioware.Bioware.id). Defaults to () -- "predates
    # this field", the identical shape cyberware_item_ids already has.
    bioware_item_ids: tuple[str, ...] = ()
    # WP43: Karma converted to nuyen at Step Six (core rulebook p. 94, up to 10). Defaults to 0 --
    # "predates this field"/"player didn't convert any", the same shape every prior optional field
    # defaults to.
    karma_converted: int = 0
    # WP46: a Magician's bound spirits, as (spirit_type, services) pairs -- see module docstring for
    # why `force` is never persisted. Defaults to () -- "predates this field", the identical shape
    # every other optional selection field defaults to.
    bound_spirit_picks: tuple[BoundSpiritPickPair, ...] = ()
    # WP47: a magic-active character's bonded foci, as (focus_id, force) pairs. Defaults to () --
    # "predates this field", the identical shape every other optional selection field defaults to.
    foci_picks: tuple[FociPickPair, ...] = ()
    # WP48: a magic-active character's picked Mentor Spirit archetype id, and (only when that
    # archetype's General bonus slot is itself a choice) the chosen option's id. Both default to
    # None -- "predates this field"/"Mentor Spirit not taken", the same shape every other optional
    # selection field defaults to.
    mentor_spirit_archetype_id: str | None = None
    mentor_spirit_general_choice_id: str | None = None
    # WP44: which priority-letter validity rule produced the 5 letters above -- see module
    # docstring for why this is carried through unvalidated rather than re-checked here.
    build_method: str = PRIORITY_BUILD_METHOD


def create_character_save(
    *,
    metatype_name: str,
    heritage_letter: str,
    attributes_letter: str,
    attribute_points: Mapping[str, int],
    skills_letter: str,
    skill_points: Mapping[str, int],
    group_points: Mapping[str, int],
    quality_ids: Iterable[str],
    contacts: Iterable[Contact],
    resources_letter: str,
    gear_names: Iterable[str],
    lifestyle_tier_name: str,
    lifestyle_months: int,
    talent_letter: str = DEFAULT_TALENT_LETTER,
    talent_codename: str = DEFAULT_TALENT_CODENAME,
    tradition_id: str | None = None,
    granted_skill_ids: Iterable[str] = (),
    spell_ids: Iterable[str] = (),
    power_picks: Iterable[PowerPickTriple] = (),
    magic_attribute_points: int = 0,
    cyberware_item_ids: Iterable[str] = (),
    bioware_item_ids: Iterable[str] = (),
    karma_converted: int = 0,
    bound_spirit_picks: Iterable[BoundSpiritPickPair] = (),
    foci_picks: Iterable[FociPickPair] = (),
    mentor_spirit_archetype_id: str | None = None,
    mentor_spirit_general_choice_id: str | None = None,
    build_method: str = PRIORITY_BUILD_METHOD,
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
        quality_ids=tuple(quality_ids),
        contacts=tuple(contacts),
        resources_letter=resources_letter,
        gear_names=tuple(gear_names),
        lifestyle_tier_name=lifestyle_tier_name,
        lifestyle_months=lifestyle_months,
        talent_letter=talent_letter,
        talent_codename=talent_codename,
        tradition_id=tradition_id,
        granted_skill_ids=tuple(granted_skill_ids),
        spell_ids=tuple(spell_ids),
        power_picks=tuple(power_picks),
        magic_attribute_points=magic_attribute_points,
        cyberware_item_ids=tuple(cyberware_item_ids),
        bioware_item_ids=tuple(bioware_item_ids),
        karma_converted=karma_converted,
        bound_spirit_picks=tuple(bound_spirit_picks),
        foci_picks=tuple(foci_picks),
        mentor_spirit_archetype_id=mentor_spirit_archetype_id,
        mentor_spirit_general_choice_id=mentor_spirit_general_choice_id,
        build_method=build_method,
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
        "quality_ids": list(save.quality_ids),
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
        "granted_skill_ids": list(save.granted_skill_ids),
        "spell_ids": list(save.spell_ids),
        "power_picks": [
            {"power_id": power_id, "rating": rating, "selected_attribute": selected_attribute}
            for power_id, rating, selected_attribute in save.power_picks
        ],
        "magic_attribute_points": save.magic_attribute_points,
        "cyberware_item_ids": list(save.cyberware_item_ids),
        "bioware_item_ids": list(save.bioware_item_ids),
        "karma_converted": save.karma_converted,
        "bound_spirit_picks": [
            {"spirit_type": spirit_type, "services": services}
            for spirit_type, services in save.bound_spirit_picks
        ],
        "foci_picks": [
            {"focus_id": focus_id, "force": force} for focus_id, force in save.foci_picks
        ],
        "mentor_spirit_archetype_id": save.mentor_spirit_archetype_id,
        "mentor_spirit_general_choice_id": save.mentor_spirit_general_choice_id,
        "build_method": save.build_method,
    }


def _dict_to_save(data: Mapping[str, Any]) -> CharacterSave:
    version = data.get("format_version")
    if version != FORMAT_VERSION:
        raise ValueError(
            f"unsupported save format version {version!r}; this build only reads {FORMAT_VERSION!r}"
        )
    return create_character_save(
        metatype_name=data["metatype_name"],
        heritage_letter=data["heritage_letter"],
        attributes_letter=data["attributes_letter"],
        attribute_points=data["attribute_points"],
        skills_letter=data["skills_letter"],
        skill_points=data["skill_points"],
        group_points=data["group_points"],
        quality_ids=data["quality_ids"],
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
        granted_skill_ids=data.get("granted_skill_ids", ()),
        spell_ids=data.get("spell_ids", ()),
        power_picks=(
            (p["power_id"], p["rating"], p["selected_attribute"])
            for p in data.get("power_picks", ())
        ),
        magic_attribute_points=data.get("magic_attribute_points", 0),
        cyberware_item_ids=data.get("cyberware_item_ids", ()),
        bioware_item_ids=data.get("bioware_item_ids", ()),
        karma_converted=data.get("karma_converted", 0),
        bound_spirit_picks=(
            (p["spirit_type"], p["services"]) for p in data.get("bound_spirit_picks", ())
        ),
        foci_picks=((p["focus_id"], p["force"]) for p in data.get("foci_picks", ())),
        mentor_spirit_archetype_id=data.get("mentor_spirit_archetype_id"),
        mentor_spirit_general_choice_id=data.get("mentor_spirit_general_choice_id"),
        build_method=data.get("build_method", PRIORITY_BUILD_METHOD),
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
    cyberware: tuple[Cyberware, ...] = (),
    bioware: tuple[Bioware, ...] = (),
    foci: tuple[Focus, ...] = (),
    mentors: tuple[MentorSpiritArchetype, ...] = (),
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
    `cyberware_item_ids` (every pre-WP33 save) never resolves against it.

    **WP45**: `bioware` defaults to `()` for the same reason -- a save with no `bioware_item_ids`
    (every pre-WP45 save) never resolves against it. Resolved *after* cyberware (a fixed evaluation
    order -- see `chummer5.engine.bioware`'s own module docstring), so its Essence-floor/nuyen
    checks correctly account for cyberware's already-resolved spend.

    **WP47**: `foci` defaults to `()` for the same reason -- a save with no `foci_picks` (every
    pre-WP47 save) never resolves against it. Resolved last of all (after Bound Spirits -- a fixed
    evaluation order, see `chummer5.engine.foci`'s own module docstring), so its Karma budget
    accounts for Bound Spirits' already-resolved `karma_cost` and its nuyen budget accounts for
    gear/Lifestyle/cyberware/bioware's already-resolved spend.
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
    )

    # WP23: metatype_qualities is never persisted in CharacterSave (it's 100% determined by
    # metatype + the current quality catalog -- see this module's own "selections, not derived
    # values" docstring), so it's re-derived here exactly like a freshly-built Character would.
    metatype_qualities = resolve_metatype_qualities(character.metatype, qualities)
    apply_quality_improvements(
        character, metatype_qualities, source_type=ImprovementSource.METATYPE
    )

    # WP48: computed early (before the Magic-selection block further down) since
    # create_quality_selection needs it to resolve a Mentor Spirit archetype pick -- exactly what
    # create_magic_selection would later derive as MagicSelection.magic_type, for a save whose
    # talent_codename is already known. See this module's own WP48 docstring paragraph.
    magic_type = None if save.talent_codename == "Mundane" else save.talent_codename

    quality_selection = create_quality_selection(
        save.quality_ids,
        qualities,
        magic_type=magic_type,
        mentor_catalog=mentors,
        mentor_spirit_archetype_id=save.mentor_spirit_archetype_id,
        mentor_spirit_general_choice_id=save.mentor_spirit_general_choice_id,
    )
    apply_quality_improvements(character, quality_selection.qualities)
    if quality_selection.mentor_spirit is not None:
        apply_mentor_spirit_improvements(character, quality_selection.mentor_spirit)

    skill_allocation = create_skill_allocation(
        letter=save.skills_letter,
        priorities=priorities,
        skills=skills,
        skill_points=save.skill_points,
        group_points=save.group_points,
    )

    contact_selection = create_contact_selection(character, save.contacts)

    lifestyle_selection = create_lifestyle_selection(
        save.lifestyle_tier_name, save.lifestyle_months, lifestyles
    )

    resources_selection = create_resources_selection(
        save.resources_letter,
        priorities,
        gear_names=save.gear_names,
        lifestyle_cost=lifestyle_selection.total_cost,
        karma_converted=save.karma_converted,
    )

    # WP33: cyberware draws from the same shared Step Six nuyen pool gear/Lifestyle already spent
    # out of `resources_selection.nuyen_budget` -- `nuyen_remaining` is exactly what's left (see
    # chummer5.engine.cyberware's own docstring for the confirmed-shared-budget citation).
    cyberware_selection = create_cyberware_selection(
        save.cyberware_item_ids, cyberware, resources_selection.nuyen_remaining
    )
    apply_cyberware_improvements(character, cyberware_selection)

    # WP45: bioware is resolved second (a fixed evaluation order -- see chummer5.engine.bioware's
    # own docstring), against whatever nuyen cyberware left over and cyberware's own essence_spent
    # as other_essence_spent, so the shared Essence floor accounts for both.
    bioware_selection = create_bioware_selection(
        save.bioware_item_ids,
        bioware,
        resources_selection.nuyen_remaining - cyberware_selection.nuyen_spent,
        other_essence_spent=cyberware_selection.essence_spent,
    )
    apply_bioware_improvements(character, bioware_selection)

    # WP34/WP45: fold the now-resolved cyberware+bioware cost back into `resources_selection`
    # itself, so the `Character` this function returns carries a `nuyen_remaining` that reflects the
    # true 4-way gear+Lifestyle+cyberware+bioware spend (what `chummer5.web.app
    # ._character_sheet_context` and every other reader of `character.resources_selection` display)
    # rather than the gear+Lifestyle-only figure computed above, before cyberware/bioware were
    # known. Guaranteed to re-validate cleanly: `create_cyberware_selection`/
    # `create_bioware_selection` above already confirmed their combined nuyen_spent doesn't exceed
    # the earlier resources_selection's own nuyen_remaining, so the combined total still fits the
    # same budget.
    resources_selection = create_resources_selection(
        save.resources_letter,
        priorities,
        gear_names=save.gear_names,
        lifestyle_cost=lifestyle_selection.total_cost,
        cyberware_cost=cyberware_selection.nuyen_spent,
        bioware_cost=bioware_selection.nuyen_spent,
        karma_converted=save.karma_converted,
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
    )
    apply_magic_skill_grant_improvements(character, magic_selection, skills)

    # Post-WP29 correction: Special Attribute Points spent raising MAG beyond magic_selection
    # .magic_rating, drawn from the same pool `create_character` above already validated EDG
    # against -- see chummer5.engine.magic.create_magic_attribute_points's own docstring.
    magic_attribute_points = create_magic_attribute_points(
        magic_selection.magic_type,
        save.magic_attribute_points,
        magic_selection.magic_rating,
        choice.metatype.attributes["MAG"].maximum,
        choice.special_attribute_points,
        save.attribute_points.get("EDG", 0),
    )
    total_magic_rating = magic_selection.magic_rating + magic_attribute_points

    # Spell/power budgets are each the matched Talent option's own field -- 0 for whichever of the
    # two doesn't apply to `magic_selection.magic_type`, which is exactly what lets
    # `create_spell_selection`/`create_power_selection` reject a mismatched save's picks (e.g. an
    # Adept save somehow carrying `spell_ids`) via their own existing budget check rather than a
    # special case here. Power Points use `total_magic_rating` (the *finished* Magic rating,
    # including any Special Attribute Points spent), not the raw Talent-granted `magic_rating`
    # alone, per the rulebook's own "Power Points equal to their Magic attribute" (p.278).
    spell_budget = 0
    power_point_budget = 0
    if magic_selection.magic_type == "Magician":
        magician_option = next(
            o
            for o in offered_talent_options(save.talent_letter, priorities)
            if o.codename == "Magician"
        )
        spell_budget = magician_option.spells or 0
    elif magic_selection.magic_type == "Adept":
        power_point_budget = total_magic_rating

    spell_selection = create_spell_selection(save.spell_ids, spells, budget=spell_budget)
    power_selection = create_power_selection(
        save.power_picks, powers, power_point_budget=power_point_budget
    )
    apply_power_improvements(character, power_selection)

    character = replace(
        character,
        skill_allocation=skill_allocation,
        quality_selection=quality_selection,
        contact_selection=contact_selection,
        resources_selection=resources_selection,
        lifestyle_selection=lifestyle_selection,
        metatype_qualities=metatype_qualities,
        magic_type=magic_selection.magic_type,
        magic_rating=magic_selection.magic_rating,
        tradition=magic_selection.tradition,
        magic_granted_skill_ids=magic_selection.granted_skill_ids,
        spell_selection=spell_selection,
        power_selection=power_selection,
        magic_attribute_points=magic_attribute_points,
        cyberware_selection=cyberware_selection,
        bioware_selection=bioware_selection,
    )

    # WP46: resolved last, against the now-fully-populated `character` -- create_bound_spirit_
    # selection reads character.attribute_value("CHA")/("MAG"), both of which depend on the
    # magic_type/tradition/magic_rating/magic_attribute_points fields the replace() above just set
    # (force is always the *live* Magic rating, never a persisted value -- see module docstring).
    spirit_karma_budget = provisional_karma_budget(
        quality_selection.karma_cost, contact_selection.karma_cost
    )
    bound_spirit_selection = create_bound_spirit_selection(
        save.bound_spirit_picks, character, spirit_karma_budget
    )
    character = replace(character, bound_spirit_selection=bound_spirit_selection)

    # WP47: resolved last of all, against the now-fully-populated `character` (create_foci_
    # selection reads character.attribute_value("MAG"), which depends on the magic fields the
    # replace() above already set) -- a fixed evaluation order, aware of Bound Spirits' own
    # already-resolved karma_cost and of the nuyen resources_selection already spent on gear/
    # Lifestyle/cyberware/bioware. See chummer5.engine.foci's own module docstring for why a
    # one-shot reconstruction like this one needs a fixed order even though neither create_*_
    # selection chains into the other's own call.
    foci_karma_budget = provisional_karma_budget(
        quality_selection.karma_cost,
        contact_selection.karma_cost,
        bound_spirit_karma_cost=bound_spirit_selection.karma_cost,
    )
    foci_selection = create_foci_selection(
        save.foci_picks,
        character,
        foci,
        resources_selection.nuyen_remaining,
        foci_karma_budget,
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
        lifestyle_cost=lifestyle_selection.total_cost,
        cyberware_cost=cyberware_selection.nuyen_spent,
        bioware_cost=bioware_selection.nuyen_spent,
        karma_converted=save.karma_converted,
        foci_cost=foci_selection.nuyen_cost,
    )
    return replace(
        character, foci_selection=foci_selection, resources_selection=resources_selection
    )
