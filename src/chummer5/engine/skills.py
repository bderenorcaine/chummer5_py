"""Skill allocation & dice pools.

Composes WP3's skill catalog (`chummer5.data.skills`) and WP2's Skills-priority data
(`chummer5.data.priorities`) with WP6's `Character` into a buildable skill point spend and the
dice-pool formula it feeds. Mundane MVP scope only — see `spec/Project Overview.md`.

Checked directly against `legacy/Chummer/Backend/Skills/Skill.cs` (`Base`, `LearnedRating`,
`TotalBaseRating`, `Rating`, `RatingMaximum`, `PoolOtherAttribute`, `DefaultModifier`,
`GetSpecializationBonus`) and `SkillGroup.cs` (`Base`), and cross-checked against
`Yeti-#ffffff2.chum5` (the corpus's one `buildmethod == Priority` fixture, also usable here for the
same reason WP6 used it for attributes: skill allocation doesn't depend on the Talent/magic path).
See `spec/worklogs/WP7.md` for the rules research this was checked against, including two points
that don't show up in `Implementation Plan.md`'s one-line summary of this WP:

- **Skill groups override, not add to, member skills' individual points.** Confirmed against
  legacy's default `StrictSkillGroupsInCreateMode = True`: a skill's rating comes from its group's
  points if the group has any spent, never from its own `skill_points` at the same time. Verified
  against Yeti: every skill belonging to a group with nonzero group points (Firearms, Stealth) has
  zero of its own base points in the save, and every skill with nonzero base points belongs to a
  group that itself has zero group points (Cracking, Tasking, Electronics, all unbought). WP7
  enforces this as a construction-time rule (`create_skill_allocation` rejects the conflicting
  combination) rather than silently letting one side win.
- **Karma-bought skill points are out of scope**, mirroring WP6's undocumented-but-consistent
  precedent for attributes (WP6 never modeled karma-bought points beyond the priority budget
  either). Two of Yeti's skills (Compiling, Computer) have nonzero `<karma>` on top of `<base>`;
  `create_skill_allocation`/`skill_rating` only ever consume `<base>` (the priority-budget-funded
  points), so a fully karma-complete rating isn't reproduced. This is a real, deliberate scope cut,
  not an oversight — flagged explicitly here (unlike WP6) so a future reader doesn't have to
  rediscover it. There's nothing in the corpus that stores a skill's *computed dice pool* to check
  against anyway (see below), so this cut costs no test coverage for this WP.

**WP50 — Step Five's skill-point-funded specialization.** Confirmed via `pdftotext -layout` against
the core rulebook's own "Purchase Skills" step (p.88, chapter 2) — see
`spec/rulebooks/learnings.md`'s WP50 entry for the full citation — and cross-checked against the
Skills chapter's own "SPECIALIZATIONS" section (p.129): a specialization costs 1 skill point (spent
from the same pool `skill_points` already draws from, on top of whatever points bought the skill's
own rating), grants `SPECIALIZATION_BONUS` (+2) to that narrow area, and is capped at exactly one
per skill at character creation. Two restrictions, both enforced by `create_skill_allocation`:

- **A skill group cannot be specialized in Step Five at all.** The rulebook is explicit that buying
  a specialization for a skill within a purchased group permanently breaks that group, and "this
  cannot happen in Step Five of character creation — you can only break up a skill group by buying
  a specialization for it in Step Seven" (p.88; Step Seven's group-breaking case is Phase O's WP53,
  not this one). Enforced here as "a specialization's skill must already have its own
  `skill_points` entry of at least 1" — which the existing "strict skill groups" rule already
  guarantees can't coexist with that skill's group having any points spent, so no separate group
  check is needed.
- **You have to have the skill first (Rating >= 1).** Skills chapter, p.129: "If you want a
  specialization in a skill, you have to have it first (meaning a Rating of at least 1)." Same
  `skill_points.get(skill_id, 0) >= 1` check as above covers this too.

`SkillAllocation.specializations` is a `dict[skill_id, name]` — keying by skill id both encodes "at
most one specialization per skill" for free (a dict can't have two values for the same key) and
mirrors `skill_points`/`group_points`'s own keying. The specialization's *name* (e.g. "Axes",
"Revolvers") is freeform player-authored text, not a catalog entry — SR5 doesn't enumerate valid
specialization names, mirroring `chummer5.engine.knowledge.KnowledgeSkillPick`'s identical "no
catalog, the player invents it" shape.

**WP53 — Step Seven's Karma-funded skill/skill-group increases, including group-breaking.**
Confirmed via `pdftotext -layout` against the same "Purchase Skills" passage (p. 87-88) WP50 already
cited, read past WP50's own quoted sentence: a skill group's rating can be broken and one member
raised individually "during game play" (i.e. outside Step Five), and "skill groups cannot be broken
up in this step [Five]... skill groups can be broken up in Step Seven" — see
`spec/rulebooks/learnings.md`'s WP53 entry for the full citation, including the finding that this is
a **second, independent trigger** for breaking a group alongside WP50's own specialization-based
one: raising one member's rating directly with Karma breaks the group exactly the same way a
Karma-funded specialization does, with no specialization required. `KARMA_SKILL_PER_RATING`
(2)/`KARMA_SKILL_GROUP_PER_RATING` (5) come from the "KARMA ADVANCEMENT TABLE FOR SKILLS" (p.
106-107, confirmed by WP51's own research pass); `KARMA_SPECIALIZATION_COST` (7, flat, not a
per-rating formula) comes from the same page's "CHARACTER IMPROVEMENT TABLE" (also already banked
by WP51's research, since a specialization has no "rating" to plug into `karma_advancement_cost`'s
shape at all).

`KarmaSkillSelection` wraps the whole Step Seven skill-side spend: `skill_points`/`group_points`
mirror `SkillAllocation`'s own shape (extra Karma-funded points on top of whatever the priority
budget already bought), `specializations` mirrors `SkillAllocation.specializations` (Karma-funded
ones specifically -- 7 Karma flat each, validated against `character.skill_allocation`'s own
skill-point-funded specializations for the "at most one per skill" rule), and `broken_groups`
records which group names this selection itself broke (derived, not player-submitted -- see
`create_karma_skill_selection`'s own docstring). Knowledge/Language Karma increases are a *separate*
selection, `chummer5.engine.knowledge.KarmaKnowledgeSelection` -- Knowledge/Language picks are
player-authored names living on `character.knowledge_selection`, not `Skill` catalog entries this
module's own `skills: tuple[Skill, ...]` parameter could resolve, and (more importantly) they're
submitted through a different web-layer form/route (`POST /ui/knowledge`) than Active
skills/groups/specializations (`POST /ui/skills`) -- keeping them as two independent `Character`
fields avoids one route's submission silently clobbering the other's already-committed Karma spend
the way a single shared selection object would if each route naively replaced it whole.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from chummer5.data.priorities import PriorityTable
from chummer5.data.skills import Skill
from chummer5.engine.character import Character, karma_advancement_cost
from chummer5.engine.improvements import ImprovementType

# CharacterSettings.MaxSkillRatingCreate (legacy default, confirmed in CharacterSettings.cs:
# `_intMaxSkillRatingCreate = 6`) -- the chargen-time cap on both individual skill and skill group
# rating; SR5's post-creation cap (`MaxSkillRating = 12`) doesn't apply to MVP, which only builds
# freshly-created characters.
MAX_SKILL_RATING_CREATE = 6

# CharacterSettings.SpecializationBonus -- flat dice pool bonus for a specialized test with that
# skill. (Legacy also has `ExpertiseBonus` for a stacked "Expertise" specialization tier; not
# modeled -- MVP's specialization support is the plain +2 case only.)
SPECIALIZATION_BONUS = 2

# Skill.DefaultModifier's unconditional case (-1) -- the dice pool penalty for using a skill
# "untrained" (rating 0, `can_default = True`). Legacy has several Improvement-driven ways to zero
# this out (Reflex Recorder, RemoveSkillDefaultPenalty, ...); none are in MVP scope.
DEFAULT_MODIFIER = -1

# WP53: core rulebook p.106-107, "KARMA ADVANCEMENT TABLE FOR SKILLS" (confirmed by WP51's own
# research pass -- spec/rulebooks/learnings.md's WP51/WP53 entries) -- Active Skill/Active Skill
# Group rows, fed into karma_advancement_cost the same way ATTRIBUTE_KARMA_PER_RATING is.
KARMA_SKILL_PER_RATING = 2
KARMA_SKILL_GROUP_PER_RATING = 5

# WP53: same page's "CHARACTER IMPROVEMENT TABLE" -- a flat, non-per-rating cost ("New
# specialization (for Active, Knowledge, or Language)"), distinct from every formula above.
KARMA_SPECIALIZATION_COST = 7


@dataclass(frozen=True)
class SkillPointBudget:
    """One Skills-priority-letter's point pools, split the same way `priorities.xml` splits them."""

    skills: int
    skill_groups: int


def skill_point_budget(letter: str, priorities: PriorityTable) -> SkillPointBudget:
    skills_priority = priorities.skills[letter]
    return SkillPointBudget(
        skills=skills_priority.skills, skill_groups=skills_priority.skill_groups
    )


@dataclass(frozen=True)
class SkillAllocation:
    """Points spent on individual skills and skill groups from one Skills-priority-letter budget.

    `skill_points` is keyed by `Skill.id` (stable, unambiguous -- matches how `LegacySkill.suid`
    cross-references the catalog, per WP4). `group_points` is keyed by skill group name (skill
    groups have no id in `skills.xml`, only a name -- same choice WP4's `LegacySkillGroup` already
    made).
    """

    skill_points: MappingProxyType[str, int]
    group_points: MappingProxyType[str, int]
    # WP50: skill_id -> specialization name, freeform player-authored text (see module docstring).
    specializations: MappingProxyType[str, str] = MappingProxyType({})


def create_skill_allocation(
    letter: str,
    priorities: PriorityTable,
    skills: tuple[Skill, ...],
    skill_points: Mapping[str, int],
    group_points: Mapping[str, int],
    specializations: Mapping[str, str] = MappingProxyType({}),
) -> SkillAllocation:
    """Build a `SkillAllocation`, validating the spend against the Skills-priority-letter budget.

    Validates: every `skill_points` key is a known `Skill.id`; every `group_points` key is a group
    name actually used by at least one skill; no negative spend; no single skill or group rated
    above `MAX_SKILL_RATING_CREATE`; no skill has its own `skill_points` entry while its group also
    has `group_points` spent (the "strict skill groups" rule -- see module docstring); and total
    spend in each pool doesn't exceed that pool's budget for `letter`. Does not require the full
    budget to be spent, mirroring WP6's `create_character`.

    WP50: every `specializations` key must be a known `Skill.id` with a nonblank name and at least 1
    of its own `skill_points` (see module docstring for why this alone enforces both "no skill group
    specializations in Step Five" and "you have to have the skill first"). Each specialization costs
    1 additional skill point, counted against the same `skill_points` budget.
    """
    skills_by_id = {s.id: s for s in skills}
    unknown_skills = set(skill_points) - set(skills_by_id)
    if unknown_skills:
        raise ValueError(f"not a known skill id: {sorted(unknown_skills)}")

    group_names = {s.skill_group for s in skills if s.skill_group is not None}
    unknown_groups = set(group_points) - group_names
    if unknown_groups:
        raise ValueError(f"not a known skill group: {sorted(unknown_groups)}")

    for skill_id, points in skill_points.items():
        if points < 0:
            raise ValueError(f"{skill_id}: points spent must not be negative, got {points}")
        if points > MAX_SKILL_RATING_CREATE:
            raise ValueError(
                f"{skill_id}: {points} exceeds the chargen skill rating maximum of "
                f"{MAX_SKILL_RATING_CREATE}"
            )
        group = skills_by_id[skill_id].skill_group
        if group is not None and group_points.get(group, 0) > 0:
            raise ValueError(
                f"{skill_id}: cannot spend points directly while its group {group!r} also has "
                f"points spent (strict skill groups)"
            )

    for group, points in group_points.items():
        if points < 0:
            raise ValueError(f"{group}: points spent must not be negative, got {points}")
        if points > MAX_SKILL_RATING_CREATE:
            raise ValueError(
                f"{group}: {points} exceeds the chargen skill rating maximum of "
                f"{MAX_SKILL_RATING_CREATE}"
            )

    unknown_spec_skills = set(specializations) - set(skills_by_id)
    if unknown_spec_skills:
        raise ValueError(f"not a known skill id: {sorted(unknown_spec_skills)}")

    for skill_id, name in specializations.items():
        if not name.strip():
            raise ValueError(f"{skill_id}: a specialization's name must not be blank")
        if skill_points.get(skill_id, 0) < 1:
            raise ValueError(
                f"{skill_id}: cannot add a specialization without at least 1 point spent "
                "directly on the skill (a skill group cannot be specialized in Step Five, and "
                "you must have the skill before specializing it)"
            )

    budget = skill_point_budget(letter, priorities)
    skills_spent = sum(skill_points.values()) + len(specializations)
    if skills_spent > budget.skills:
        raise ValueError(
            f"skill point spend {skills_spent} (including {len(specializations)} "
            f"specialization(s)) exceeds Skills priority {letter}'s budget of {budget.skills}"
        )
    groups_spent = sum(group_points.values())
    if groups_spent > budget.skill_groups:
        raise ValueError(
            f"skill group point spend {groups_spent} exceeds Skills priority {letter}'s budget of "
            f"{budget.skill_groups}"
        )

    return SkillAllocation(
        skill_points=MappingProxyType(dict(skill_points)),
        group_points=MappingProxyType(dict(group_points)),
        specializations=MappingProxyType(dict(specializations)),
    )


@dataclass(frozen=True)
class KarmaSkillSelection:
    """Leftover-Karma-funded Active skill/skill-group rating increases and specializations (Step
    Seven, WP53) -- see `create_karma_skill_selection`'s own docstring for the validation this
    wraps, and the module docstring's WP53 paragraph for why Knowledge/Language Karma spend is a
    separate selection (`chummer5.engine.knowledge.KarmaKnowledgeSelection`), not part of this one.

    `skill_points`/`group_points` mirror `SkillAllocation`'s own shape: however many *additional*
    points, per skill id / group name, were bought with Karma on top of whatever the priority
    budget (`character.skill_allocation`) already funded. `specializations` mirrors `SkillAllocation
    .specializations` the same way -- skill id -> Karma-funded specialization name, 7 Karma flat
    each. `broken_groups` is *derived*, not player-submitted: the set of group names this selection
    itself broke by individually funding or specializing one of that group's member skills (see
    `create_karma_skill_selection`'s own docstring for exactly when that happens). Always the full
    resulting state, not an incremental delta on top of a prior `KarmaSkillSelection` -- the same
    "recompute wholesale, not incrementally" shape `KarmaAttributeSelection` already established.
    """

    skill_points: MappingProxyType[str, int]
    group_points: MappingProxyType[str, int]
    specializations: MappingProxyType[str, str]
    broken_groups: frozenset[str]
    karma_cost: int


def create_karma_skill_selection(
    character: Character,
    skills: tuple[Skill, ...],
    karma_skill_points: Mapping[str, int] = MappingProxyType({}),
    karma_group_points: Mapping[str, int] = MappingProxyType({}),
    karma_specializations: Mapping[str, str] = MappingProxyType({}),
    karma_budget: int = 0,
) -> KarmaSkillSelection:
    """Validate and build a `KarmaSkillSelection` against `character.skill_allocation`'s own
    already-committed priority-point spend.

    **Group-breaking (WP53's own core mechanic).** A group whose member skill(s) already have
    points spent via `character.skill_allocation.group_points` is normally "strict" (WP7): every
    member shares one uniform, group-funded rating. Step Seven relaxes this in exactly two ways,
    both confirmed via `pdftotext -layout` against the core rulebook's own Skills-chapter Step Five
    text (p. 87-88 -- see `spec/rulebooks/learnings.md`'s WP53 entry for the full citation,
    including why this is a *second* trigger distinct from WP50's own specialization-only one):
    raising one member's rating *individually* with `karma_skill_points`, or buying that member a
    Karma-funded specialization via `karma_specializations` -- either one "breaks" that member's
    group from this point forward, so it becomes individually tracked (frozen at whatever rating
    the group already had, plus whatever this selection itself adds to that one member) while every
    other member stays at the group's own rating. A group referenced by *both* `karma_group_points`
    (funding the group as a whole) and `karma_skill_points`/`karma_specializations` (breaking one of
    its own members) in the same submission is rejected outright -- contradictory in the same
    submission, not a sequencing question this function could resolve on its own.

    Validates: every `karma_skill_points`/`karma_group_points` key is a known skill id / skill
    group name; every `karma_specializations` key is a known skill id; no negative spend; no
    resulting rating exceeds `MAX_SKILL_RATING_CREATE`; a group can only be freshly Karma-funded
    from 0 (`karma_group_points` with no existing `character.skill_allocation.group_points` entry)
    if none of its members already have individually-spent points (priority or Karma) -- the
    "strict skill groups" rule extended to Karma, mirroring `create_skill_allocation`'s own check;
    a specialization's skill must not already have one (from `character.skill_allocation
    .specializations` or from `karma_specializations` itself) and must have a rating of at least 1
    (post-spend, for a skill this same submission raises via `karma_skill_points`) before it can be
    specialized; and the total Karma cost does not exceed `karma_budget` (the caller's
    responsibility to derive -- typically `character.karma_remaining + <this selection's own
    currently-committed karma_cost>`, mirroring `create_karma_attribute_points`'s identical
    parameter; see WP51's worklog for this "add back this section's own current commitment" idiom).

    Uses `character.skill_allocation`'s `skill_points`/`group_points`/`specializations` as the
    starting point for every Karma-funded rating step's cost (`karma_advancement_cost`) -- an
    unset `character.skill_allocation` (nothing committed yet) is treated as all-empty, the same
    "None means nothing spent yet" default every other selection in this engine uses.
    """
    allocation = character.skill_allocation
    existing_skill_points = (
        allocation.skill_points if allocation is not None else MappingProxyType({})
    )
    existing_group_points = (
        allocation.group_points if allocation is not None else MappingProxyType({})
    )
    existing_specializations = (
        allocation.specializations if allocation is not None else MappingProxyType({})
    )

    skills_by_id = {s.id: s for s in skills}
    group_names = {s.skill_group for s in skills if s.skill_group is not None}

    unknown_skills = set(karma_skill_points) - set(skills_by_id)
    if unknown_skills:
        raise ValueError(f"not a known skill id: {sorted(unknown_skills)}")
    unknown_groups = set(karma_group_points) - group_names
    if unknown_groups:
        raise ValueError(f"not a known skill group: {sorted(unknown_groups)}")
    unknown_spec_skills = set(karma_specializations) - set(skills_by_id)
    if unknown_spec_skills:
        raise ValueError(f"not a known skill id: {sorted(unknown_spec_skills)}")

    # A group is "broken" by this selection if it's currently group-purchased (has an existing
    # group_points entry) and one of its own members is targeted by karma_skill_points or
    # karma_specializations -- see this function's own "Group-breaking" docstring paragraph.
    broken_groups: set[str] = set()
    for skill_id in set(karma_skill_points) | set(karma_specializations):
        group = skills_by_id[skill_id].skill_group
        if group is not None and existing_group_points.get(group, 0) > 0:
            broken_groups.add(group)

    conflicting_groups = set(karma_group_points) & broken_groups
    if conflicting_groups:
        raise ValueError(
            f"cannot Karma-fund skill group(s) {sorted(conflicting_groups)} while also breaking "
            "them by individually raising or specializing one of their member skills in the same "
            "submission"
        )

    cost = 0

    for skill_id, points in karma_skill_points.items():
        if points < 0:
            raise ValueError(f"{skill_id}: Karma-funded points must not be negative, got {points}")
        if points == 0:
            continue
        skill = skills_by_id[skill_id]
        group = skill.skill_group
        if group is not None and group in broken_groups:
            start_rating = existing_group_points.get(group, 0)
        else:
            start_rating = existing_skill_points.get(skill_id, 0)
        total = start_rating + points
        if total > MAX_SKILL_RATING_CREATE:
            raise ValueError(
                f"{skill_id}: {total} exceeds the chargen skill rating maximum of "
                f"{MAX_SKILL_RATING_CREATE}"
            )
        cost += karma_advancement_cost(start_rating, points, KARMA_SKILL_PER_RATING)

    for group, points in karma_group_points.items():
        if points < 0:
            raise ValueError(f"{group}: Karma-funded points must not be negative, got {points}")
        if points == 0:
            continue
        start_rating = existing_group_points.get(group, 0)
        if start_rating == 0:
            members_with_points = sorted(
                s.id
                for s in skills
                if s.skill_group == group
                and (existing_skill_points.get(s.id, 0) > 0 or karma_skill_points.get(s.id, 0) > 0)
            )
            if members_with_points:
                raise ValueError(
                    f"{group}: cannot Karma-fund a fresh skill group while its member skill(s) "
                    f"{members_with_points} already have individually-spent points "
                    "(strict skill groups)"
                )
        total = start_rating + points
        if total > MAX_SKILL_RATING_CREATE:
            raise ValueError(
                f"{group}: {total} exceeds the chargen skill rating maximum of "
                f"{MAX_SKILL_RATING_CREATE}"
            )
        cost += karma_advancement_cost(start_rating, points, KARMA_SKILL_GROUP_PER_RATING)

    for skill_id, name in karma_specializations.items():
        if not name.strip():
            raise ValueError(f"{skill_id}: a specialization's name must not be blank")
        if skill_id in existing_specializations:
            raise ValueError(
                f"{skill_id}: already has a specialization ({existing_specializations[skill_id]!r})"
            )
        skill = skills_by_id[skill_id]
        group = skill.skill_group
        if group is not None and group in broken_groups:
            rating_after = existing_group_points.get(group, 0) + karma_skill_points.get(skill_id, 0)
        else:
            rating_after = existing_skill_points.get(skill_id, 0) + karma_skill_points.get(
                skill_id, 0
            )
        if rating_after < 1:
            raise ValueError(
                f"{skill_id}: cannot add a specialization without at least 1 point in the skill"
            )
        cost += KARMA_SPECIALIZATION_COST

    if cost > karma_budget:
        raise ValueError(
            f"Karma-funded skill spend {cost} exceeds the Karma budget of {karma_budget}"
        )

    return KarmaSkillSelection(
        skill_points=MappingProxyType({k: v for k, v in karma_skill_points.items() if v}),
        group_points=MappingProxyType({k: v for k, v in karma_group_points.items() if v}),
        specializations=MappingProxyType(dict(karma_specializations)),
        broken_groups=frozenset(broken_groups),
        karma_cost=cost,
    )


def skill_rating(character: Character, allocation: SkillAllocation, skill: Skill) -> int:
    """`Skill.Rating`: a skill's group rating if its group has points spent, else its own points,
    plus Σ improvements, capped at `MAX_SKILL_RATING_CREATE`.

    **WP53**: `character.karma_skill_selection` -- if set -- adds Karma-funded points on top,
    reading its own `broken_groups` to decide whether a group member's rating is still group-wide
    (unbroken: group_points + karma group_points) or individually tracked (broken: the group's own
    frozen rating + this skill's own karma_skill_points), and an ordinary individually-tracked
    skill's rating gains its own karma_skill_points the same way.
    """
    karma = character.karma_skill_selection
    group = skill.skill_group
    broken = karma is not None and group is not None and group in karma.broken_groups
    if group is not None and not broken:
        group_rating = allocation.group_points.get(group, 0)
        if karma is not None:
            group_rating += karma.group_points.get(group, 0)
    else:
        group_rating = 0
    if group_rating > 0:
        points = group_rating
    elif broken and group is not None:
        points = allocation.group_points.get(group, 0)
        if karma is not None:
            points += karma.skill_points.get(skill.id, 0)
    else:
        points = allocation.skill_points.get(skill.id, 0)
        if karma is not None:
            points += karma.skill_points.get(skill.id, 0)
    bonus = character.improvements.resolve(ImprovementType.SKILL, skill.name)
    return min(points + bonus, MAX_SKILL_RATING_CREATE)


def dice_pool(
    character: Character,
    allocation: SkillAllocation,
    skill: Skill,
    specialized: bool | None = None,
) -> int:
    """`Skill.PoolOtherAttribute`'s unconditional core: rating + linked attribute (+2 if
    specialized, at rating > 0 and not exotic), or the -1 "defaulting" penalty at rating 0 for
    skills that allow it, or 0 otherwise. Wound/sustaining penalties and Improvement-driven pool
    modifiers beyond `ImprovementType.SKILL` are out of MVP scope -- nothing in the MVP Improvement
    engine (WP5/WP8) produces one.

    WP50: `specialized` defaults to whether `skill.id` has an entry in
    `allocation.specializations` -- pass an explicit `True`/`False` to override (e.g. a synthetic
    what-if preview with no real `SkillAllocation` behind it).

    WP53: also true when `skill.id` has a Karma-funded specialization in
    `character.karma_skill_selection.specializations`.
    """
    if specialized is None:
        karma = character.karma_skill_selection
        specialized = skill.id in allocation.specializations or (
            karma is not None and skill.id in karma.specializations
        )
    rating = skill_rating(character, allocation, skill)
    attribute_value = character.attribute_value(skill.attribute)
    if rating > 0:
        spec_bonus = SPECIALIZATION_BONUS if specialized and not skill.exotic else 0
        return max(0, rating + attribute_value + spec_bonus)
    if skill.can_default:
        return max(0, attribute_value + DEFAULT_MODIFIER)
    return 0
