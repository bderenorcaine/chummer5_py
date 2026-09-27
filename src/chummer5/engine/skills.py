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

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType

from chummer5.data.priorities import PriorityTable
from chummer5.data.skills import Skill
from chummer5.engine.character import Character, karma_advancement_cost
from chummer5.engine.improvements import ImprovementType

# CharacterSettings.MaxSkillRatingCreate (legacy default, confirmed in CharacterSettings.cs:
# `_intMaxSkillRatingCreate = 6`) -- the cap on what may be *bought* at character creation, for
# both an individual skill and a skill group. Core rulebook p. 131's Skill Rating Table calls
# Rating 6 "the maximum skill level for starting player characters" and then goes on to describe
# ratings 7-13, so this is explicitly a purchase cap, not a ceiling on the rating itself.
#
# **WP82**: it is no longer `skill_rating`'s clamp -- see `MAX_SKILL_RATING` below and
# `natural_skill_rating`. It remains the bound enforced by the two purchase-side validators
# (`create_skill_allocation`, `create_karma_skill_selection`), which read purchased points directly
# and so were natural-only by construction all along.
MAX_SKILL_RATING_CREATE = 6

# WP82: the ceiling on an *augmented* skill rating. Core rulebook p. 129, "SKILL RATINGS": "The
# skill Rating is a numerical value ranging from 1, representing the most rudimentary skill, to 12
# (or 13 with the Aptitude quality) representing the height of sentient achievement." Matches
# legacy's own `CharacterSettings.MaxSkillRating = 12` (the post-creation setting the pre-WP82
# comment here dismissed as inapplicable -- it is, as the *purchase* cap for a played character,
# but 12 is also where the printed rating scale itself stops).
#
# **WP116**: Aptitude raises both caps by one for its chosen skill -- 7 to buy at creation, 13 as
# the ceiling (p. 72) -- through `ImprovementType.SKILL_MAXIMUM`; see `purchase_maximum`. Legacy
# does the same by folding a per-skill maximum term into `Skill.RatingMaximum`.
#
# **Legacy does not apply this bound where this engine does.** `Skill.TotalBaseRating` is
# `LearnedRating + RatingModifiers(Attribute)`, unclamped -- legacy clamps only the *purchased*
# halves (`Base`, `Karma`) at `RatingMaximum`. Bounding the augmented total here is therefore this
# project's own call rather than a port: an unbounded rating would be a number the book's own scale
# doesn't define, and nothing in SR5 describes what a Rating 14 skill would mean. Unreachable in
# practice today (the largest stack this engine can build is well short of 12), so this is a
# guard-rail, not a live formula -- see `spec/worklogs/WP82.md`.
MAX_SKILL_RATING = 12

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

# WP124: an exotic skill is bought once per named weapon or vehicle, as separate skills (p. 131,
# Exotic Ranged Weapon: "This skill must be taken once for each unusual ranged weapon you want to
# use"; p. 147, Pilot Exotic Vehicle: "one time for each specific exotic vehicle"). Each instance is
# keyed `"{skill_id}|{specific}"` in the same `skill_points`/`specializations` maps every other
# skill uses, so the saves, the web forms and every id-keyed lookup keep their shape; the catalog
# entry's own id is never bought directly. See `spec/worklogs/WP124.md`.
EXOTIC_KEY_SEPARATOR = "|"
# What a pre-WP124 save's (or a legacy file's) bare exotic skill becomes: it was bought without a
# named item, so the instance says so rather than inventing one.
UNSPECIFIED_EXOTIC = "Unspecified"


def exotic_skill_key(skill_id: str, specific: str) -> str:
    """The allocation key of one exotic-skill instance (WP124)."""
    return f"{skill_id}{EXOTIC_KEY_SEPARATOR}{specific.strip()}"


def split_skill_key(key: str) -> tuple[str, str | None]:
    """`(skill_id, specific)` for an exotic instance key, `(key, None)` for any other skill."""
    skill_id, separator, specific = key.partition(EXOTIC_KEY_SEPARATOR)
    return (skill_id, specific) if separator else (key, None)


def exotic_instance(base: Skill, specific: str) -> Skill:
    """The `Skill` for one instance of the exotic catalog entry `base` (WP124). It keeps `base`'s
    name, so an Improvement naming the skill (Aptitude, Critical Strike) reaches every instance."""
    return replace(base, id=exotic_skill_key(base.id, specific), specific=specific.strip())


def exotic_instances(skills: Iterable[Skill], keys: Iterable[str]) -> tuple[Skill, ...]:
    """An instance for every well-formed exotic key in `keys` (WP124), once each, in key order. A
    key naming a non-exotic skill or a blank item is left out, for the validators' own error to
    report."""
    by_id = {s.id: s for s in skills}
    instances: dict[str, Skill] = {}
    for key in keys:
        skill_id, specific = split_skill_key(key)
        base = by_id.get(skill_id)
        if specific is None or base is None or not base.exotic or not specific.strip():
            continue
        if key == exotic_skill_key(skill_id, specific):
            instances.setdefault(key, exotic_instance(base, specific))
    return tuple(instances.values())


def with_exotic_instances(skills: Iterable[Skill], keys: Iterable[str]) -> tuple[Skill, ...]:
    """`skills`, plus `exotic_instances(skills, keys)` after them."""
    catalog = tuple(skills)
    return catalog + exotic_instances(catalog, keys)


def character_skills(character: Character, skills: Iterable[Skill]) -> tuple[Skill, ...]:
    """`skills` plus every exotic instance the character has bought, by priority points or Karma."""
    return with_exotic_instances(skills, bought_skill_keys(character))


def bought_skill_keys(character: Character) -> list[str]:
    """Every skill key the character spent priority points or Karma on."""
    keys: list[str] = []
    if character.skill_allocation is not None:
        keys += list(character.skill_allocation.skill_points)
    if character.karma_skill_selection is not None:
        keys += list(character.karma_skill_selection.skill_points)
    return keys


def migrate_bare_exotic_keys(points: Mapping[str, int], skills: Iterable[Skill]) -> dict[str, int]:
    """A pre-WP124 spend on an exotic catalog id, moved onto an `UNSPECIFIED_EXOTIC` instance."""
    exotic_ids = {s.id for s in skills if s.exotic}
    return {
        (exotic_skill_key(key, UNSPECIFIED_EXOTIC) if key in exotic_ids else key): value
        for key, value in points.items()
    }


def drop_exotic_specializations(
    specializations: Mapping[str, str], skills: Iterable[Skill]
) -> dict[str, str]:
    """A pre-WP124 specialization on an exotic skill, which the book never allowed (p. 131)."""
    exotic_ids = {s.id for s in skills if s.exotic}
    return {k: v for k, v in specializations.items() if split_skill_key(k)[0] not in exotic_ids}


def _check_skill_keys(keys: Iterable[str], skills_by_id: Mapping[str, Skill]) -> None:
    """Reject a bought exotic catalog entry with no named item, and a malformed instance key."""
    for key in keys:
        skill_id, specific = split_skill_key(key)
        base = skills_by_id.get(skill_id)
        if specific is None:
            if base is not None and base.exotic:
                raise ValueError(
                    f"{base.name}: an exotic skill is bought once per specific weapon or vehicle, "
                    "and needs one named"
                )
        elif base is not None and not base.exotic:
            raise ValueError(f"{base.name}: only an exotic skill is bought per specific item")
        elif base is not None and not specific.strip():
            raise ValueError(f"{base.name}: the specific weapon or vehicle must not be blank")


def _check_exotic_specializations(
    specializations: Iterable[str], skills_by_id: Mapping[str, Skill]
) -> None:
    """p. 131/147: the exotic skills list "Specializations: None" / "N/A"."""
    for skill_id in specializations:
        skill = skills_by_id.get(skill_id)
        if skill is not None and skill.exotic:
            raise ValueError(f"{skill.name}: an exotic skill has no specializations")


def _sum_by_target(character: Character, improvement_type: ImprovementType) -> dict[str, int]:
    totals: dict[str, int] = {}
    for imp in character.improvements.improvements:
        if imp.improvement_type is improvement_type:
            totals[imp.target] = totals.get(imp.target, 0) + imp.value
    return totals


def skill_maximum_bonuses(character: Character) -> dict[str, int]:
    """Σ `SKILL_MAXIMUM` per skill name (WP116)."""
    return _sum_by_target(character, ImprovementType.SKILL_MAXIMUM)


@dataclass(frozen=True)
class SkillPurchaseRules:
    """What the character's qualities change about buying skills (WP116, WP117).

    `create_skill_allocation` takes this rather than a `Character`, because it validates the
    priority spend on its own; `skill_purchase_rules(character)` builds it. The default is "no
    quality changes anything".

    - `maximum_bonus`: skill name -> extra levels of purchase cap (Aptitude).
    - `*_cost_percent`: skill category -> extra percent on a cost. Priority points for a skill and
      its specialization (Uncouth's Social skills, p. 85), Karma for a skill, a specialization, or a
      group with a member in the category (Uneducated, p. 87).
    - `disabled_group_categories`: no group with a member in these categories may be bought
      (Uncouth: "may never learn any Social skill groups").
    - `banned_groups`: group -> why. The group *and each of its skills* may not be bought.
      Incompetent (p. 81: "Characters may not possess that skill group"), and since WP118 an
      Adept's Sorcery, Conjuring and Enchanting (p. 69).
    - `banned_skills`: skill name -> why (WP118): an Adept's Assensing, until the Astral
      Perception power unlocks it (p. 69).
    """

    maximum_bonus: Mapping[str, int] = MappingProxyType({})
    point_cost_percent: Mapping[str, int] = MappingProxyType({})
    karma_cost_percent: Mapping[str, int] = MappingProxyType({})
    specialization_karma_cost_percent: Mapping[str, int] = MappingProxyType({})
    group_karma_cost_percent: Mapping[str, int] = MappingProxyType({})
    disabled_group_categories: frozenset[str] = frozenset()
    banned_groups: Mapping[str, str] = MappingProxyType({})
    banned_skills: Mapping[str, str] = MappingProxyType({})

    def skill_blocked(self, skill: Skill) -> str | None:
        """Why `skill` may not be bought, or `None` (WP117/WP118)."""
        if skill.name in self.banned_skills:
            return f"{skill.name}: {self.banned_skills[skill.name]}"
        if skill.skill_group is not None and skill.skill_group in self.banned_groups:
            return f"{skill.name}: {self.banned_groups[skill.skill_group]}"
        return None

    def group_blocked(self, group: str, skills: Iterable[Skill]) -> str | None:
        """Why `group` may not be bought, or `None`."""
        if group in self.banned_groups:
            return f"{group}: {self.banned_groups[group]}"
        categories = _group_categories(group, skills) & self.disabled_group_categories
        if categories:
            return (
                f"{group}: an Uncouth character may never learn {sorted(categories)} skill groups"
            )
        return None


# The rules for a character none of whose qualities change skill purchases.
NO_PURCHASE_RULES = SkillPurchaseRules()


# WP118, p. 69: "Adepts cannot use skills from any magic-related skill groups (Sorcery, Conjuring,
# or Enchanting)" and "can learn Assensing only if they have Astral Perception".
ADEPT_BANNED_GROUPS = ("Sorcery", "Conjuring", "Enchanting")
# WP121: the three aspect groups (the same three).
ASPECT_MAGIC_GROUPS = ADEPT_BANNED_GROUPS
ADEPT_LOCKED_SKILL = "Assensing"


def skill_purchase_rules(character: Character) -> SkillPurchaseRules:
    """The character's `SkillPurchaseRules`, from its Improvements (WP117) and, since WP118, its
    Talent: an Adept's magic-group and Assensing bans."""

    def flags(improvement_type: ImprovementType) -> frozenset[str]:
        return frozenset(k for k, v in _sum_by_target(character, improvement_type).items() if v)

    banned_groups = {
        group: "the character is Incompetent in this skill group"
        for group in flags(ImprovementType.SKILL_GROUP_DISABLED)
    }
    banned_skills: dict[str, str] = {}
    if character.magic_aspect is not None:
        # WP121, p. 69: an Aspected Magician "can never take skills from the other two" groups.
        for group in ASPECT_MAGIC_GROUPS:
            if group != character.magic_aspect:
                banned_groups.setdefault(
                    group, f"a {character.magic_aspect}-aspected magician can never learn it"
                )
    if character.magic_type == "Adept":
        for group in ADEPT_BANNED_GROUPS:
            banned_groups.setdefault(group, "an Adept cannot use magic skill groups' skills")
        if ADEPT_LOCKED_SKILL not in flags(ImprovementType.SKILL_UNLOCKED):
            banned_skills[ADEPT_LOCKED_SKILL] = (
                "an Adept can learn it only with the Astral Perception power"
            )

    return SkillPurchaseRules(
        maximum_bonus=skill_maximum_bonuses(character),
        point_cost_percent=_sum_by_target(
            character, ImprovementType.SKILL_CATEGORY_POINT_COST_PERCENT
        ),
        karma_cost_percent=_sum_by_target(
            character, ImprovementType.SKILL_CATEGORY_KARMA_COST_PERCENT
        ),
        specialization_karma_cost_percent=_sum_by_target(
            character, ImprovementType.SKILL_CATEGORY_SPECIALIZATION_KARMA_COST_PERCENT
        ),
        group_karma_cost_percent=_sum_by_target(
            character, ImprovementType.SKILL_GROUP_CATEGORY_KARMA_COST_PERCENT
        ),
        disabled_group_categories=flags(ImprovementType.SKILL_GROUP_CATEGORY_DISABLED),
        banned_groups=MappingProxyType(banned_groups),
        banned_skills=MappingProxyType(banned_skills),
    )


def _group_categories(group: str, skills: Iterable[Skill]) -> frozenset[str]:
    """Every category a member of `group` has -- Outdoors is both Physical and Technical, and
    legacy counts a group under each of its members' categories."""
    return frozenset(s.category for s in skills if s.skill_group == group)


def _with_percent(cost: int, percent: int) -> int:
    """`cost` raised by `percent` extra percent, rounded half up (legacy `StandardRound`)."""
    return (cost * (100 + percent) + 50) // 100


def purchase_maximum(skill: Skill, maximum_bonus: Mapping[str, int]) -> int:
    """The highest rating `skill` may be bought to at creation (WP116): 6, or 7 with Aptitude."""
    return MAX_SKILL_RATING_CREATE + maximum_bonus.get(skill.name, 0)


def knowledge_active_points(character: Character) -> int:
    """The Active skill points the character's Knowledge/Language spend uses (WP125)."""
    selection = character.knowledge_selection
    return selection.active_points_used if selection is not None else 0


def skill_points_spent(
    skill_points: Mapping[str, int],
    specializations: Mapping[str, str],
    skills: Iterable[Skill],
    rules: SkillPurchaseRules = NO_PURCHASE_RULES,
) -> int:
    """Priority skill points a spend costs (WP117): a point per rating and per specialization,
    raised by the skill category's `point_cost_percent` -- an Etiquette 3 costs 6 with Uncouth.
    Legacy applies the multiplier to rating and specialization together."""
    by_id = {s.id: s for s in with_exotic_instances(skills, skill_points)}
    total = 0
    for skill_id in set(skill_points) | set(specializations):
        points = skill_points.get(skill_id, 0) + (1 if skill_id in specializations else 0)
        skill = by_id.get(skill_id)
        percent = rules.point_cost_percent.get(skill.category, 0) if skill is not None else 0
        total += _with_percent(points, percent)
    return total


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
    rules: SkillPurchaseRules = NO_PURCHASE_RULES,
    knowledge_active_points: int = 0,
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

    WP116: `rules.maximum_bonus` raises one skill's cap -- Aptitude's 7. A skill *group*'s cap
    stays 6: Aptitude names one skill.

    WP117: `rules` also doubles a Social skill's point cost for Uncouth (`skill_points_spent`),
    rejects a Social group for Uncouth, and rejects Incompetent's group and each of its skills.

    WP124: an exotic skill is keyed per named item (`exotic_skill_key`); its catalog id may not be
    bought on its own, and none of its instances may be specialized.

    WP125: `knowledge_active_points` -- the Knowledge/Language spend past its free pool
    (`KnowledgeSelection.active_points_used`, p. 88) -- counts against the individual-skill budget.
    """
    _check_skill_keys([*skill_points, *specializations], {s.id: s for s in skills})
    skills = with_exotic_instances(skills, [*skill_points, *specializations])
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
        maximum = purchase_maximum(skills_by_id[skill_id], rules.maximum_bonus)
        if points > maximum:
            raise ValueError(
                f"{skill_id}: {points} exceeds the chargen skill rating maximum of {maximum}"
            )
        group = skills_by_id[skill_id].skill_group
        blocked = rules.skill_blocked(skills_by_id[skill_id]) if points > 0 else None
        if blocked is not None:
            raise ValueError(blocked)
        if group is not None and group_points.get(group, 0) > 0:
            raise ValueError(
                f"{skill_id}: cannot spend points directly while its group {group!r} also has "
                f"points spent (strict skill groups)"
            )

    for group, points in group_points.items():
        if points < 0:
            raise ValueError(f"{group}: points spent must not be negative, got {points}")
        blocked = rules.group_blocked(group, skills) if points > 0 else None
        if blocked is not None:
            raise ValueError(blocked)
        if points > MAX_SKILL_RATING_CREATE:
            raise ValueError(
                f"{group}: {points} exceeds the chargen skill rating maximum of "
                f"{MAX_SKILL_RATING_CREATE}"
            )

    unknown_spec_skills = set(specializations) - set(skills_by_id)
    if unknown_spec_skills:
        raise ValueError(f"not a known skill id: {sorted(unknown_spec_skills)}")

    _check_exotic_specializations(specializations, skills_by_id)
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
    skills_spent = skill_points_spent(skill_points, specializations, skills, rules)
    if skills_spent + knowledge_active_points > budget.skills:
        knowledge_part = (
            f" and {knowledge_active_points} spent on Knowledge/Language skills"
            if knowledge_active_points
            else ""
        )
        raise ValueError(
            f"skill point spend {skills_spent} (including {len(specializations)} "
            f"specialization(s)){knowledge_part} exceeds Skills priority {letter}'s budget of "
            f"{budget.skills}"
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

    # WP124: exotic instances, from this submission and from the committed priority spend.
    _check_skill_keys([*karma_skill_points, *karma_specializations], {s.id: s for s in skills})
    skills = with_exotic_instances(
        skills, [*existing_skill_points, *karma_skill_points, *karma_specializations]
    )
    skills_by_id = {s.id: s for s in skills}
    group_names = {s.skill_group for s in skills if s.skill_group is not None}
    # WP116/WP117: Aptitude's cap, and Uncouth/Uneducated/Incompetent's costs and bans.
    rules = skill_purchase_rules(character)
    maximum_bonus = rules.maximum_bonus

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
        blocked = rules.skill_blocked(skill)
        if blocked is not None:
            raise ValueError(blocked)
        if group is not None and group in broken_groups:
            start_rating = existing_group_points.get(group, 0)
        else:
            start_rating = existing_skill_points.get(skill_id, 0)
        total = start_rating + points
        maximum = purchase_maximum(skill, maximum_bonus)
        if total > maximum:
            raise ValueError(
                f"{skill_id}: {total} exceeds the chargen skill rating maximum of {maximum}"
            )
        cost += _with_percent(
            karma_advancement_cost(start_rating, points, KARMA_SKILL_PER_RATING),
            rules.karma_cost_percent.get(skill.category, 0),
        )

    for group, points in karma_group_points.items():
        if points < 0:
            raise ValueError(f"{group}: Karma-funded points must not be negative, got {points}")
        if points == 0:
            continue
        blocked = rules.group_blocked(group, skills)
        if blocked is not None:
            raise ValueError(blocked)
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
        group_percent = max(
            (
                rules.group_karma_cost_percent.get(category, 0)
                for category in _group_categories(group, skills)
            ),
            default=0,
        )
        cost += _with_percent(
            karma_advancement_cost(start_rating, points, KARMA_SKILL_GROUP_PER_RATING),
            group_percent,
        )

    _check_exotic_specializations(karma_specializations, skills_by_id)
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
        cost += _with_percent(
            KARMA_SPECIALIZATION_COST,
            rules.specialization_karma_cost_percent.get(skill.category, 0),
        )

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


def natural_skill_rating(character: Character, allocation: SkillAllocation, skill: Skill) -> int:
    """WP82: the rating this skill was actually *bought* at -- its group's rating if its group has
    points spent, else its own points, priority-funded and Karma-funded summed, capped at
    `MAX_SKILL_RATING_CREATE` (one higher for an Aptitude skill, WP116). No Improvement adds to
    it; `SKILL_MAXIMUM` only moves the cap.

    This is `skill_rating` minus the `ImprovementType.SKILL` term, and it is the skill-side twin of
    `Character.natural_attribute_value` (WP81) -- with one deliberate asymmetry worth knowing
    before reusing it. The attribute split has exactly two clean sides: points bought from a budget,
    and Improvements that are all augmentations or adept powers. `ImprovementType.SKILL` is *not*
    that clean -- it currently carries the Magician/Adept Talent free-skill grant (a granted natural
    rating, routed through the Improvement index by WP25 purely as a convenience, see
    `chummer5.engine.magic.apply_magic_skill_grant_improvements`' own docstring), quality bonuses
    whose printed effect is a **dice-pool** modifier rather than a rating one (Catlike, Natural
    Athlete), and genuine rating augmentations (`Reflex Recorder`, p. 460). So "everything not in
    this function is an augmentation" is false, and WP82 deliberately does not build a display on
    that premise -- see `spec/worklogs/WP82.md` and `spec/decisions-log.md`'s 2026-08-01 entry.

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
    return min(points, MAX_SKILL_RATING_CREATE + _maximum_bonus(character, skill))


def _maximum_bonus(character: Character, skill: Skill) -> int:
    return character.improvements.resolve(ImprovementType.SKILL_MAXIMUM, skill.name)


def skill_rating(character: Character, allocation: SkillAllocation, skill: Skill) -> int:
    """`Skill.Rating`: `natural_skill_rating` plus Σ `SKILL` improvements, capped at
    `MAX_SKILL_RATING`.

    **WP82 moved that cap** from `MAX_SKILL_RATING_CREATE` (6) to `MAX_SKILL_RATING` (12). SR5's 6
    bounds what you may *buy* at character creation, not what an implant may add on top of it
    (p. 131's Skill Rating Table calls 6 "the maximum skill level for starting player characters"
    and then describes ratings 7-13); the old clamp silently swallowed the bonus of any skill
    augmentation bought for a skill already at 6 -- a `Reflex Recorder` for a rating-6 skill cost
    14,000 nuyen and 0.1 Essence and changed nothing. See `spec/decisions-log.md`, 2026-07-31
    (WP80's own finding) and 2026-08-01.

    The two purchase-side validators (`create_skill_allocation`, `create_karma_skill_selection`)
    are unaffected and were never in scope: both read purchased points directly rather than going
    through this function, so both are natural-only by construction and still reject a purchase
    above 6.
    """
    bonus = character.improvements.resolve(ImprovementType.SKILL, skill.name)
    ceiling = MAX_SKILL_RATING + _maximum_bonus(character, skill)  # WP116: 13 with Aptitude
    return min(natural_skill_rating(character, allocation, skill) + bonus, ceiling)


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

    WP117: an unaware skill (`is_unaware`) can't be defaulted on, so its pool at rating 0 is 0.

    WP115: `SKILL_POOL` (by skill name) and `SKILL_CATEGORY_POOL` (by category) modifiers are added
    to the pool, defaulting included -- Addiction's "-2 to all Social Tests" applies whether or not
    the skill is known. `SPECIALIZATION_DISABLED` (Loss of Confidence) drops the specialization's
    +2 even when `specialized=True` is passed.
    """
    if specialized is None:
        karma = character.karma_skill_selection
        specialized = skill.id in allocation.specializations or (
            karma is not None and skill.id in karma.specializations
        )
    index = character.improvements
    if index.resolve(ImprovementType.SPECIALIZATION_DISABLED, skill.name) > 0:
        specialized = False
    modifier = index.resolve(ImprovementType.SKILL_POOL, skill.name) + index.resolve(
        ImprovementType.SKILL_CATEGORY_POOL, skill.category
    )
    rating = skill_rating(character, allocation, skill)
    attribute_value = character.attribute_value(skill.attribute)
    if rating > 0:
        spec_bonus = SPECIALIZATION_BONUS if specialized and not skill.exotic else 0
        return max(0, rating + attribute_value + spec_bonus + modifier)
    if skill.can_default and not is_unaware(character, skill):
        return max(0, attribute_value + DEFAULT_MODIFIER + modifier)
    return 0


def is_unaware(character: Character, skill: Skill) -> bool:
    """Whether the character is "unaware" in `skill` when it has no rating, and so may not default
    on it (WP117, p. 131's Skill Rating Table). Uncouth blocks defaulting in Social skills,
    Uneducated in Technical ones, and Incompetent in every skill of its group."""
    index = character.improvements
    if index.resolve(ImprovementType.SKILL_CATEGORY_DEFAULTING_BLOCKED, skill.category) > 0:
        return True
    return (
        skill.skill_group is not None
        and index.resolve(ImprovementType.SKILL_GROUP_DISABLED, skill.skill_group) > 0
    )
