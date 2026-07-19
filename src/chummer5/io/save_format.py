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

from chummer5.data.lifestyle import LifestyleTier
from chummer5.data.metatypes import Metatype
from chummer5.data.priorities import PriorityTable
from chummer5.data.qualities import Quality
from chummer5.data.skills import Skill
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.lifestyle import create_lifestyle_selection
from chummer5.engine.qualities import apply_quality_improvements, create_quality_selection
from chummer5.engine.resources import (
    Contact,
    create_contact_selection,
    create_resources_selection,
)
from chummer5.engine.skills import create_skill_allocation

# Bumped only if a future WP changes this format's shape in a way older saves can't be read as.
# MVP has exactly one version; there is no migration path yet because there is nothing to migrate
# from.
FORMAT_VERSION = 1


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

    quality_selection = create_quality_selection(save.quality_ids, qualities)
    apply_quality_improvements(character, quality_selection)

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
    )

    return replace(
        character,
        skill_allocation=skill_allocation,
        quality_selection=quality_selection,
        contact_selection=contact_selection,
        resources_selection=resources_selection,
        lifestyle_selection=lifestyle_selection,
    )
