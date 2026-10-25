"""Whole-character validation: the rulebook's closing checklist (WP135).

`validate` reports every rule a *finished* character must meet, so the player knows when it's
done. It never blocks anything: Phase X's convention is that per-action limits are enforced when
the action is taken (the `create_*` validators), and finish rules are reported here. A save or an
export goes through whatever this says.

**Severity.** `error` means a rule is broken (over budget, a second attribute at its natural
maximum, a quality prerequisite a later step undid). `warning` means something expected isn't done
yet (points left to spend, no Lifestyle, no contacts). Special Attribute points left over are a
warning with their own message, since p. 66 says they "disappear" rather than carry over.

**What this module can see.** Only the committed `Character`, the session's priority letters, and
the catalogs. The per-step WP19 "no longer fits" diagnostics are computed by the web layer's step
contexts (each re-runs its own `create_*` call against the current letters), so
`chummer5.web.shell.validation_issues` adds those to what this returns rather than this module
duplicating six re-validations.

**What it deliberately leaves out.** The per-contact 7-Karma cap stays unenforced (WP9: Yeti's own
legacy save breaks it). The WP133 carryover notes are information, not issues.

Each `Issue` names its step by the nav's page slug (and, for a composite page, its tab), and its
text by an i18n key plus parameters, so the Export page can list and link them.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal

from chummer5.data.priorities import PriorityTable
from chummer5.data.skills import Skill
from chummer5.engine.build_method import SUM_TO_TEN_BUILD_METHOD, validate_sum_to_ten_total
from chummer5.engine.character import PRIMARY_ATTRIBUTES, SPECIAL_ATTRIBUTES, Character
from chummer5.engine.knowledge import free_knowledge_points
from chummer5.engine.magic import ASPECTED_MAGICIAN
from chummer5.engine.qualities import (
    QUALITY_KARMA_LIMIT,
    later_step_facts,
    later_step_problem,
)
from chummer5.engine.resources import available_nuyen
from chummer5.engine.skills import (
    ADEPT_LOCKED_SKILL,
    ASPECT_MAGIC_GROUPS,
    knowledge_active_points,
    skill_point_budget,
    skill_points_spent,
    skill_purchase_rules,
)

Severity = Literal["error", "warning"]

PRIORITY_LETTERS = ("A", "B", "C", "D", "E")
INCOMPETENT_QUALITY = "Incompetent"


@dataclass(frozen=True)
class SessionLetters:
    """The session's confirmed priority letters and build method -- the part of a character's
    state `Character` itself doesn't hold."""

    heritage: str
    talent: str
    attributes: str
    skills: str
    resources: str
    build_method: str = "Priority"

    def as_tuple(self) -> tuple[str, ...]:
        return (self.heritage, self.talent, self.attributes, self.skills, self.resources)


@dataclass(frozen=True)
class Issue:
    """One finding. `step` is a nav page slug, `tab` a composite page's section slug (or None),
    `key` an i18n message key, and `params` its parameters."""

    severity: Severity
    step: str
    key: str
    params: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    tab: str | None = None


def _issue(severity: Severity, step: str, key: str, tab: str | None = None, **params: Any) -> Issue:
    return Issue(severity, step, key, MappingProxyType(dict(params)), tab)


def _points(
    issues: list[Issue], step: str, tab: str | None, pool_key: str, key: str, remaining: int
) -> None:
    """A point pool: unspent is a warning (`key`), overspent an error naming the pool by its label
    key. A parameter whose name ends in `_key` is itself an i18n key."""
    if remaining > 0:
        issues.append(_issue("warning", step, key, tab, count=remaining))
    elif remaining < 0:
        issues.append(
            _issue(
                "error", step, "Web_Validation_Overspent", tab, pool_key=pool_key, count=-remaining
            )
        )


def validate(
    character: Character,
    letters: SessionLetters,
    *,
    priorities: PriorityTable,
    skills: Iterable[Skill],
) -> tuple[Issue, ...]:
    """Every whole-character issue, in step order. See module docstring."""
    skills = tuple(skills)
    issues: list[Issue] = []

    # Priorities: each row once (Priority), or a total of exactly 10 (Sum-to-Ten).
    if letters.build_method == SUM_TO_TEN_BUILD_METHOD:
        try:
            validate_sum_to_ten_total(letters.as_tuple())
        except ValueError:
            issues.append(_issue("error", "priorities", "Web_Validation_SumToTen"))
    elif sorted(letters.as_tuple()) != list(PRIORITY_LETTERS):
        issues.append(_issue("error", "priorities", "Web_Validation_PriorityRows"))

    # Attributes: every point spent; Special points "disappear" (p. 66); one at natural maximum.
    primary_budget = priorities.attributes[letters.attributes].points
    primary_spent = sum(character.attribute_points.get(code, 0) for code in PRIMARY_ATTRIBUTES)
    _points(
        issues,
        "attributes",
        None,
        "String_AttributePoints",
        "Web_Validation_AttributePoints",
        primary_budget - primary_spent,
    )
    special_spent = (
        sum(character.attribute_points.get(code, 0) for code in SPECIAL_ATTRIBUTES)
        + character.magic_attribute_points
    )
    _points(
        issues,
        "attributes",
        None,
        "String_SpecialAttributePoints",
        "Web_Validation_SpecialPoints",
        character.special_attribute_points - special_spent,
    )
    at_maximum = [
        code
        for code in PRIMARY_ATTRIBUTES
        if character.natural_attribute_value(code) >= character.attribute_maximum(code)
    ]
    if len(at_maximum) > 1:
        issues.append(
            _issue(
                "error",
                "attributes",
                "Web_Validation_NaturalMaximum",
                attributes=", ".join(at_maximum),
            )
        )

    # Qualities: the 25-Karma caps (p. 71), and the prerequisites a later step can undo.
    selection = character.quality_selection
    if selection is not None:
        if selection.positive_karma > QUALITY_KARMA_LIMIT:
            issues.append(
                _issue(
                    "error",
                    "qualities",
                    "Web_Validation_PositiveCap",
                    karma=selection.positive_karma,
                )
            )
        if selection.negative_karma > QUALITY_KARMA_LIMIT:
            issues.append(
                _issue(
                    "error",
                    "qualities",
                    "Web_Validation_NegativeCap",
                    karma=selection.negative_karma,
                )
            )
        problem = later_step_problem(selection.qualities, later_step_facts(character, skills))
        if problem is not None:
            issues.append(_issue("error", "qualities", "Web_Validation_Rule", error=problem))
        if character.magic_type == ASPECTED_MAGICIAN:
            never = set(ASPECT_MAGIC_GROUPS) - {character.magic_aspect}
            for pick in selection.qualities:
                if pick.quality.name == INCOMPETENT_QUALITY and pick.choice in never:
                    issues.append(
                        _issue(
                            "error",
                            "qualities",
                            "Web_Validation_AspectIncompetent",
                            group=pick.choice,
                            aspect=character.magic_aspect,
                        )
                    )

    # Skills: every skill, group and free Knowledge point spent.
    allocation = character.skill_allocation
    budget = skill_point_budget(letters.skills, priorities)
    skill_points = allocation.skill_points if allocation is not None else {}
    group_points = allocation.group_points if allocation is not None else {}
    specializations = allocation.specializations if allocation is not None else {}
    spent = skill_points_spent(
        skill_points, specializations, skills, skill_purchase_rules(character)
    ) + knowledge_active_points(character)
    _points(
        issues,
        "skills",
        "active",
        "String_SkillPoints",
        "Web_Validation_SkillPoints",
        budget.skills - spent,
    )
    _points(
        issues,
        "skills",
        "group",  # WP148: the Skills page's Group tab
        "String_SkillGroupPoints",
        "Web_Validation_GroupPoints",
        budget.skill_groups - sum(group_points.values()),
    )
    knowledge = character.knowledge_selection
    knowledge_spent = knowledge.points_spent if knowledge is not None else 0
    knowledge_left = free_knowledge_points(character) - knowledge_spent
    if knowledge_left > 0:
        issues.append(
            _issue(
                "warning",
                "skills",
                "Web_Validation_KnowledgePoints",
                "knowledge",
                count=knowledge_left,
            )
        )

    # Magic: an Adept's free skill grant may not name Assensing without Astral Perception (p. 69).
    if character.magic_type == "Adept":
        banned = skill_purchase_rules(character).banned_skills
        granted = {s.name for s in skills if s.id in character.magic_granted_skill_ids}
        if ADEPT_LOCKED_SKILL in granted and ADEPT_LOCKED_SKILL in banned:
            issues.append(_issue("error", "magic", "Web_Validation_AdeptAssensing", "talent"))

    # Resources: a primary Lifestyle, and not over the nuyen budget.
    if character.lifestyle_selection is None:
        issues.append(_issue("warning", "equipment", "Web_Validation_NoLifestyle", "lifestyle"))
    karma_converted = (
        character.resources_selection.karma_converted
        if character.resources_selection is not None
        else 0
    )
    nuyen_left = (
        available_nuyen(letters.resources, priorities, karma_converted) - character.nuyen_spent
    )
    if nuyen_left < 0:
        issues.append(
            _issue("error", "equipment", "Web_Validation_NuyenOver", "gear", amount=-nuyen_left)
        )

    # Contacts: none is legal, but a runner without any is almost certainly unfinished.
    contacts = character.contact_selection
    if contacts is None or not contacts.contacts:
        issues.append(_issue("warning", "contacts", "Web_Validation_NoContacts"))

    # Karma: never negative.
    if character.karma_remaining < 0:
        issues.append(
            _issue("error", "export", "Web_Validation_KarmaOver", amount=-character.karma_remaining)
        )

    return tuple(issues)
