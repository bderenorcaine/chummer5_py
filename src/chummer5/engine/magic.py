"""Magic-type, Magic-rating, tradition, and the Talent free-skill grant (Phase I, WP25).

Composes WP24's real Talent-letter plumbing with WP2's Talent priority data
(`chummer5.data.priorities`), the new SR5-tradition catalog (`chummer5.data.traditions`), and WP7's
skill catalog (`chummer5.data.skills`) into a buildable Magic-type + Magic-rating + tradition +
free-skill selection. Mundane/Magician/Adept only — Mystic Adept/Technomancer/A.I./Aspected
Magician/Apprentice/Explorer/Enchanter/Aware are all excluded, per the explicit scope cuts recorded
in the Implementation Plan's Phase I intro.

**The one finding this module must not miscopy from `chummer5.engine.character`'s EDG precedent:
Magic rating is not a point-buy.** Every other attribute is `metatype minimum + points spent + Σ
improvements`, funded from a priority-derived budget. Magic works differently: the chosen Talent
option's `magic` field (`chummer5.data.priorities.TalentOption.magic`) *is* the finished MAG rating
outright, confirmed against both of this phase's real fixtures (Miko: Talent A/Magician grants "6
Magic", her own MAG totalvalue is exactly 6; Wesson: Talent C/Adept grants "4 Magic", his MAG
totalvalue is exactly 4). See `spec/worklogs/WP25.md` for the full research, including a correction
to the Implementation Plan's own "Adept letter B grants a free skill, C/D don't" claim -- letter C
does too, confirmed both in `priorities.xml` and in Wesson's own `.chum5` (`<priorityskills>`
records his grant as `Pistols`).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from chummer5.data.priorities import PriorityTable, TalentOption
from chummer5.data.skills import Skill
from chummer5.data.spells import Spell
from chummer5.data.traditions import Tradition
from chummer5.engine.character import Character
from chummer5.engine.improvements import Improvement, ImprovementSource, ImprovementType

# This phase's offered subset of each Talent letter's real option list (Implementation Plan's Phase
# I intro): Mystic Adept (explicit product decision, not deferred) and Technomancer/A.I./Aspected
# Magician/Apprentice/Explorer/Enchanter/Aware (each a real archetype with its own restricted-access
# rules neither of this phase's two fixtures exercises) are all excluded. "Mundane" is included so a
# player assigning Talent a letter that happens to offer it can still choose it -- none of A-D
# currently do (every option at those letters is a real archetype; only E offers "Mundane" -- see
# `chummer5.data.priorities.PriorityTable.mundane_talent`), but this module doesn't hardcode that,
# it just restricts to the *name*.
OFFERED_TALENT_CODENAMES = ("Mundane", "Magician", "Adept")

# Talent's `skilltype = "magic"` grant (Magician, every letter that grants one): traced directly
# from `SelectMetatypePriority.cs`'s `GetMagicalSkillList()`, confirmed verbatim as
# `skills/skill[category = "Magical Active" or category = "Pseudo-Magical Active"]` -- a plain
# filter over `Skill.category`. See Implementation Plan's Phase I intro.
_MAGICAL_SKILL_CATEGORIES = frozenset({"Magical Active", "Pseudo-Magical Active"})


def _xpath_grant_eligible(skill: Skill) -> bool:
    """Talent's `skilltype = "xpath"` grant (Adept, letters B and C both carry it): the one literal
    XPath expression this phase's offered options ever produce, confirmed verbatim against
    `priorities.xml`: `not(attribute = 'RES' or attribute = 'DEP') and (not(category = 'Magical
    Active') or skillgroup = '' or not(skillgroup))` -- any active skill not linked to RES/DEP,
    excluding Magical Active skills that belong to a skill group. See Implementation Plan's Phase I
    intro for why this is recognized as one named, hardcoded predicate rather than a general XPath
    evaluator.
    """
    return skill.attribute not in {"RES", "DEP"} and (
        skill.category != "Magical Active" or not skill.skill_group
    )


@dataclass(frozen=True)
class MagicSelection:
    """A validated Magic-type + Magic-rating + tradition + free-skill-grant choice.

    Exists as `create_magic_selection`'s return value, not a field `Character` stores wholesale --
    a caller unpacks it onto `Character`'s own flat `magic_type`/`magic_rating`/`tradition`/
    `magic_granted_skill_ids` fields via `dataclasses.replace` (mirrors `MetatypeChoice`'s own
    relationship to `Character.metatype`/`heritage_letter`; see that class's docstring).
    """

    magic_type: str | None  # "Magician"/"Adept"; None for Mundane
    magic_rating: int  # 0 for Mundane
    tradition: Tradition | None  # Magician only
    granted_skill_ids: tuple[str, ...]  # () for Mundane or a no-grant letter/codename
    granted_skill_rating: int  # 0 when granted_skill_ids is empty


def offered_talent_options(letter: str, priorities: PriorityTable) -> tuple[TalentOption, ...]:
    """One Talent letter's real option list, restricted to this phase's offered codenames."""
    return tuple(
        option
        for option in priorities.talent[letter].options
        if option.codename in OFFERED_TALENT_CODENAMES
    )


def magic_skill_grant_eligible_skills(
    talent_option: TalentOption, skills: Iterable[Skill]
) -> tuple[Skill, ...]:
    """Which skills `talent_option`'s free-skill grant may be spent on, dispatching on
    `skill_type`. `talent_option.skill_type is None` (an option with no grant at all, e.g. Adept
    letter D or Magician letter C) has nothing eligible.

    Raises `ValueError` for a `skill_type` this phase doesn't recognize -- a genuinely different
    value would mean a Talent option this phase's traced predicates don't cover is somehow being
    offered; see the Implementation Plan's Phase I intro for why a general XPath evaluator isn't
    built for this instead.
    """
    if talent_option.skill_type is None:
        return ()
    if talent_option.skill_type == "magic":
        return tuple(s for s in skills if s.category in _MAGICAL_SKILL_CATEGORIES)
    if talent_option.skill_type == "xpath":
        return tuple(s for s in skills if _xpath_grant_eligible(s))
    raise ValueError(f"unrecognized Talent skill_type: {talent_option.skill_type!r}")


def create_magic_selection(
    talent_letter: str,
    talent_codename: str,
    tradition_id: str | None,
    granted_skill_ids: Iterable[str],
    priorities: PriorityTable,
    traditions: Iterable[Tradition],
    skills: Iterable[Skill],
) -> MagicSelection:
    """Build a `MagicSelection`, validating the codename/tradition/free-skill-grant together.

    Validates: `talent_codename` is one of `talent_letter`'s real, phase-offered options (`offered_
    talent_options`); Magician requires a `tradition_id` resolving to one of `traditions`'s 2
    entries, Adept/Mundane forbid one; the free-skill grant picks exactly the matched option's
    `skill_qty` distinct ids, each eligible per `magic_skill_grant_eligible_skills` -- Mundane or a
    no-grant option forbids any picks at all. Does not touch `chummer5.engine.skills
    .SkillAllocation` or its budget -- see `apply_magic_skill_grant_improvements` for how the grant
    still reaches a skill's real total rating without double-counting against that budget.
    """
    offered = {opt.codename: opt for opt in offered_talent_options(talent_letter, priorities)}
    option = offered.get(talent_codename)
    if option is None:
        raise ValueError(
            f"{talent_codename!r} is not an offered Talent option at letter {talent_letter!r}"
        )

    skill_ids = list(granted_skill_ids)

    if option.codename == "Mundane":
        if tradition_id is not None:
            raise ValueError("Mundane cannot choose a tradition")
        if skill_ids:
            raise ValueError("Mundane receives no Talent free-skill grant")
        return MagicSelection(
            magic_type=None,
            magic_rating=0,
            tradition=None,
            granted_skill_ids=(),
            granted_skill_rating=0,
        )

    if option.magic is None:
        raise ValueError(f"{talent_codename!r} at letter {talent_letter!r} has no Magic rating")
    magic_rating = option.magic

    tradition: Tradition | None = None
    if option.codename == "Magician":
        if tradition_id is None:
            raise ValueError("Magician requires a tradition")
        tradition = next((t for t in traditions if t.id == tradition_id), None)
        if tradition is None:
            raise ValueError(f"not an offered tradition id: {tradition_id!r}")
    elif tradition_id is not None:
        raise ValueError(f"{talent_codename!r} cannot choose a tradition")

    if option.skill_qty is None:
        if skill_ids:
            raise ValueError(
                f"{talent_codename!r} at letter {talent_letter!r} grants no free skill"
            )
        return MagicSelection(
            magic_type=option.codename,
            magic_rating=magic_rating,
            tradition=tradition,
            granted_skill_ids=(),
            granted_skill_rating=0,
        )

    eligible_ids = {s.id for s in magic_skill_grant_eligible_skills(option, skills)}
    unknown = sorted(set(skill_ids) - eligible_ids)
    if unknown:
        raise ValueError(f"not eligible for the Talent free-skill grant: {unknown}")
    duplicates = sorted({sid for sid in skill_ids if skill_ids.count(sid) > 1})
    if duplicates:
        raise ValueError(
            f"skill selected more than once for the Talent free-skill grant: {duplicates}"
        )
    if len(skill_ids) != option.skill_qty:
        raise ValueError(
            f"{talent_codename!r} at letter {talent_letter!r} grants exactly {option.skill_qty} "
            f"free skill(s), got {len(skill_ids)}"
        )

    return MagicSelection(
        magic_type=option.codename,
        magic_rating=magic_rating,
        tradition=tradition,
        granted_skill_ids=tuple(skill_ids),
        granted_skill_rating=option.skill_val or 0,
    )


# One shared source_id for every skill a single character's Talent grant touches, so a later Talent
# change can retract the whole grant in one `ImprovementIndex.remove_source` call (mirrors
# `chummer5.engine.qualities`'s per-quality `source_id`, just at the grant's own granularity since
# there's only ever one grant per character, not one per skill).
MAGIC_SKILL_GRANT_SOURCE_ID = "magic_skill_grant"


def apply_magic_skill_grant_improvements(
    character: Character, selection: MagicSelection, skills: Iterable[Skill]
) -> None:
    """Add the Talent free-skill grant's rating as `Improvement`s targeting each granted skill.

    Reuses `ImprovementType.SKILL`, the exact mechanism `chummer5.engine.qualities` already
    established for flat skill bonuses (targets a skill by name; `chummer5.engine.skills
    .skill_rating`'s existing `points + Σ improvements` formula already sums it in). This
    deliberately does **not** touch `SkillAllocation` or its budget: the grant isn't bought with
    Skills-priority points, so it must never be validated against that budget -- but it still needs
    to show up in the skill's real total rating, which routing it through `ImprovementIndex`
    (rather than, say, a second field on `SkillAllocation`) gets for free, no new formula needed.
    """
    by_id = {s.id: s for s in skills}
    for skill_id in selection.granted_skill_ids:
        character.improvements.add(
            Improvement(
                improvement_type=ImprovementType.SKILL,
                target=by_id[skill_id].name,
                value=selection.granted_skill_rating,
                source_type=ImprovementSource.TALENT,
                source_id=MAGIC_SKILL_GRANT_SOURCE_ID,
            )
        )


@dataclass(frozen=True)
class SpellSelection:
    """A validated set of spells picked against a Magician's Talent-option spell budget (WP26).

    `budget` is carried alongside `spells` (rather than left for a caller to re-derive) so a render
    can show "N of budget spells chosen" without re-looking-up the Talent option. There is no
    equivalent `apply_*_improvements` function for spells, unlike qualities/the Talent skill grant
    -- per the module docstring, a spell has no chargen-time computed effect to apply; it is purely
    a roster entry.
    """

    spells: tuple[Spell, ...]
    budget: int


def create_spell_selection(
    spell_ids: Iterable[str], catalog: Iterable[Spell], budget: int
) -> SpellSelection:
    """Build a `SpellSelection`, validating against `catalog` and `budget`.

    Validates: every id resolves against `catalog` (the SR5-scoped spell list --
    `chummer5.data.spells.load_spells()`); no spell is picked more than once; the total picked
    doesn't exceed `budget`. `budget` is the caller's responsibility to resolve correctly (a
    Magician's chosen Talent option's `spells` field -- see `chummer5.data.priorities.TalentOption
    .spells` -- or 0 for Adept/Mundane, which never have one); this function has no `magic_type`
    parameter of its own; passing `budget=0` already rejects any pick for a character with no spell
    grant at all, so there's nothing else for it to check.
    """
    ids = list(spell_ids)
    by_id = {s.id: s for s in catalog}

    unknown = sorted({sid for sid in ids if sid not in by_id})
    if unknown:
        raise ValueError(f"not an SR5-scoped spell id: {unknown}")

    duplicates = sorted({sid for sid in ids if ids.count(sid) > 1})
    if duplicates:
        raise ValueError(f"spell selected more than once: {duplicates}")

    if len(ids) > budget:
        raise ValueError(f"{len(ids)} spells selected, exceeding the budget of {budget}")

    return SpellSelection(spells=tuple(by_id[sid] for sid in ids), budget=budget)
