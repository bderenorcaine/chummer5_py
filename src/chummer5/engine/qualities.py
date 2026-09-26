"""Quality selection & minimal Improvement bonuses.

Composes WP3's quality catalog (`chummer5.data.qualities`) with WP5's Improvement engine and WP6's
`Character` into a buildable positive/negative quality spend. Mundane MVP scope only — see
`spec/Project Overview.md`.

**The offered catalog is restricted to `BonusSupport.FLAT_BONUS` and (since WP22) `NO_EFFECT`
qualities, not the full 96-entry SR5 catalog.** This follows directly from WP3's own docstring
for `chummer5.data.qualities` ("`NOT_YET_SUPPORTED` [qualities] are excluded from the offered
list rather than silently applied with their bonus dropped") and from the Implementation Plan's
WP8 acceptance criterion ("an explicit test that an unsupported-bonus quality is excluded from
the offered list rather than silently mis-applied"). Through WP8, this meant the *only* three
offerable qualities were Catlike, Double-Jointed, and Natural Athlete, all Positive (see
`spec/worklogs/WP8.md` for why no Negative quality qualified then) — so the negative-quality
karma cap below was real, general rules logic that no real-data selection could trigger, only
synthetic tests. WP22 widens the offered set to 14 (adding the Indomitable trio as new
`FLAT_BONUS` qualities, plus 8 verified-`NO_EFFECT` ones — see `chummer5.data.qualities`'s
module docstring and `spec/worklogs/WP22.md`), two of which (Simsense Vertigo, Unsteady Hands)
are MVP's first-ever offerable Negative qualities. Even together they only sum to 12 karma
(-5 + -7), well under the 25-karma cap, so the negative-karma-cap tests below still need
synthetic data to actually exercise the boundary — the "prove the rule before real content
exercises it" pattern WP5/WP7 established.

**Karma limit: 25 Karma worth of Positive Qualities, 25 Karma worth of Negative Qualities, checked
independently** — confirmed directly from the core rulebook text (see
`spec/rulebooks/learnings.md`'s WP8 entry) and cross-checked against the legacy engine
(`CharacterSettings.QualityKarmaLimit`, default 25; `Character.PositiveQualityLimitKarma`/
`NegativeQualityLimitKarma`, both enforced as hard caps by default in `CharacterCreate.cs`'s
character-validity check).

**WP48 (Phase M): the Mentor Spirit quality (`qualities.xml` id `ced3fecf-2277-4b20-b1e0-
894162ca9ae2`, 5 Karma, Positive) requires an archetype pick, a genuinely new shape none of the
other 96 SR5 qualities need.** Its own `<bonus>` is `<selectmentorspirit />` -- a placeholder tag
carrying no computed value, correctly classified `NOT_YET_SUPPORTED` by `chummer5.data.qualities`
(so it stays excluded from `mvp_quality_catalog`'s plain FLAT_BONUS/NO_EFFECT filter) -- the real
mechanical content lives entirely in whichever `chummer5.data.mentors.MentorSpiritArchetype` gets
picked alongside it. `offerable_quality_catalog` re-adds it specifically for magic-active
characters (mirroring WP23's own "widen what's offered per-character, not just per-catalog"
precedent); `create_quality_selection` gains the archetype-pick parameters and resolves a
`MentorSpiritPick` (General bonus option, chosen per the rulebook's own player choice when the
archetype offers one, p. 320-324; Magician-or-Adept slot, auto-selected from `magic_type` -- never
a player pick, since Mystic Adept, the only SR5 archetype that would need one, is out of this
project's scope entirely, see Project Overview's 2026-07-19 ruling) whenever "Mentor Spirit" is
among the selected quality ids. See `spec/rulebooks/learnings.md`'s WP48 entry for the full
per-archetype research.

**WP107 (Phase X): a selection is a tuple of `QualityPick` *instances*, not a set of unique ids.**
`<limit>` gives three shapes (see `Quality.max_rating`/`Quality.repeatable`): a rated quality is
one pick with a `rating` of 1..N and costs `karma x rating`; a repeatable quality may appear any
number of times, each instance distinguished by its `text`/`choice` (Home Ground's "a different
bonus each time", p. 74, generalized); everything else is taken at most once. `choice` is a typed
slot for the select-a-thing bonus shapes later Phase X WPs offer -- this module round-trips it but
never interprets it. **A rated quality's cap can span several catalog rows**
(`Quality.include_in_limit`): the data splits Indomitable into Mental/Physical/Social, each
`<limit>3`, and p. 74 caps the *total* at 3 levels, which the data expresses as each row's
`<includeinlimit>` naming the other two (see `spec/rulebooks/learnings/phase-x.md`).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from chummer5.data.actions import load_matrix_action_names
from chummer5.data.mentors import MentorChoice, MentorSpiritArchetype, gated_choice
from chummer5.data.metatypes import Metatype
from chummer5.data.qualities import BonusSupport, Quality, Requirement
from chummer5.data.skills import Skill, load_skills
from chummer5.data.traditions import load_core_spirit_types
from chummer5.engine.character import Character
from chummer5.engine.improvements import Improvement, ImprovementSource, ImprovementType
from chummer5.engine.skills import skill_rating

# CharacterSettings.QualityKarmaLimit (legacy default: `_intQualityKarmaLimit = 25`) -- the maximum
# karma a character may spend on Positive Qualities, and independently, the maximum karma it may
# refund from Negative Qualities, at creation. See spec/rulebooks/learnings.md's WP8 entry for the
# rulebook text and the legacy enforcement site.
QUALITY_KARMA_LIMIT = 25

# WP48: qualities.xml's own <name>, used to find the Mentor Spirit quality in whatever catalog is
# passed in, rather than hardcoding its id -- mirrors how every other by-name lookup in this
# project's engine layer (e.g. chummer5.engine.spirits) resolves against a catalog, not a literal
# GUID.
MENTOR_SPIRIT_QUALITY_NAME = "Mentor Spirit"

_TARGET_KIND_TO_IMPROVEMENT_TYPE = {
    "attribute": ImprovementType.ATTRIBUTE,
    "skill": ImprovementType.SKILL,
    "mental_limit": ImprovementType.MENTAL_LIMIT,
    "physical_limit": ImprovementType.PHYSICAL_LIMIT,
    "social_limit": ImprovementType.SOCIAL_LIMIT,
    # WP49: Bilingual's own <nativelanguagelimit> -- see chummer5.data.qualities' module docstring
    # for the classification, and chummer5.engine.knowledge.create_knowledge_selection for the one
    # consumer of ImprovementType.NATIVE_LANGUAGE_LIMIT.
    "native_language_limit": ImprovementType.NATIVE_LANGUAGE_LIMIT,
    # WP112: Exceptional Attribute / Lucky.
    "attribute_maximum": ImprovementType.ATTRIBUTE_MAXIMUM,
    # WP114: Toughness, Photographic Memory, High Pain Tolerance, Will to Live.
    "damage_resistance": ImprovementType.DAMAGE_RESISTANCE,
    "memory": ImprovementType.MEMORY,
    "cm_threshold_offset": ImprovementType.CM_THRESHOLD_OFFSET,
    "cm_overflow": ImprovementType.CM_OVERFLOW,
    # WP115: Low Pain Tolerance, Dependents, Addiction, Loss of Confidence.
    "cm_threshold": ImprovementType.CM_THRESHOLD,
    "lifestyle_cost": ImprovementType.LIFESTYLE_COST,
    "skill_category_pool": ImprovementType.SKILL_CATEGORY_POOL,
    "skill_pool": ImprovementType.SKILL_POOL,
    "specialization_disabled": ImprovementType.SPECIALIZATION_DISABLED,
    # WP116: Aptitude.
    "skill_maximum": ImprovementType.SKILL_MAXIMUM,
    # WP117: Uncouth, Uneducated, Incompetent, Sensitive System.
    "skill_category_point_cost_percent": ImprovementType.SKILL_CATEGORY_POINT_COST_PERCENT,
    "skill_category_karma_cost_percent": ImprovementType.SKILL_CATEGORY_KARMA_COST_PERCENT,
    "skill_category_specialization_karma_cost_percent": (
        ImprovementType.SKILL_CATEGORY_SPECIALIZATION_KARMA_COST_PERCENT
    ),
    "skill_group_category_karma_cost_percent": (
        ImprovementType.SKILL_GROUP_CATEGORY_KARMA_COST_PERCENT
    ),
    "skill_group_category_disabled": ImprovementType.SKILL_GROUP_CATEGORY_DISABLED,
    "skill_group_disabled": ImprovementType.SKILL_GROUP_DISABLED,
    "skill_category_defaulting_blocked": ImprovementType.SKILL_CATEGORY_DEFAULTING_BLOCKED,
    "cyberware_essence_percent": ImprovementType.CYBERWARE_ESSENCE_PERCENT,
    "bioware_disabled": ImprovementType.BIOWARE_DISABLED,
}

# WP114: Home Ground's five bonuses (p. 74), as stable ids -- the page translates each through
# `Web_HomeGround_<id>`. "Can be taken multiple times, choosing a different category each time."
HOME_GROUND_CHOICES = (
    "AstralAcclimation",
    "YouKnowAGuy",
    "DigitalTurf",
    "TheTransporter",
    "StreetPolitics",
)
MATRIX_ACTION_CHOICES = load_matrix_action_names()
SPIRIT_TYPE_CHOICES = load_core_spirit_types()

# WP115: the five rows of p. 83's Scorched Physical Side Effects Table, as stable ids translated
# through `Web_Scorched_<id>`.
SCORCHED_EFFECT_CHOICES = (
    "MemoryLossShortTerm",
    "MemoryLossLongTerm",
    "Blackout",
    "Migraines",
    "ParanoiaAnxiety",
)
# WP115: what a `choice_kind == "skill"` pick (Loss of Confidence) may name -- every active skill
# by name, Resonance skills left out with Resonance itself. The skill's own rating is checked
# separately, against `LaterStepFacts`.
SKILL_CHOICES = tuple(sorted(s.name for s in load_skills() if s.category != "Resonance Active"))
# WP117: what an Incompetent pick may name -- every active skill group but Resonance's. The magic
# groups are narrowed per character in `choice_options`.
_SKILL_GROUP_CATEGORIES: dict[str, set[str]] = {}
for _skill in load_skills():
    if _skill.skill_group is not None:
        _SKILL_GROUP_CATEGORIES.setdefault(_skill.skill_group, set()).add(_skill.category)
SKILL_GROUP_CHOICES = tuple(
    sorted(g for g, cats in _SKILL_GROUP_CATEGORIES.items() if "Resonance Active" not in cats)
)
_MAGIC_SKILL_GROUPS = frozenset(
    g for g, cats in _SKILL_GROUP_CATEGORIES.items() if "Magical Active" in cats
)
# p. 81: "A non-magician cannot take Incompetent in Sorcery, Conjuring, or Enchanting". An Adept
# can't learn them at all (p. 69), so only these Talents may name one.
_MAGIC_GROUP_TALENTS = frozenset({"Magician", "Aspected Magician"})
SCORCHED_QUALITY_NAME = "Scorched"
# WP115: an Addiction pick's detail naming one of these makes it a BTL addiction, the first of
# Scorched's two prerequisites (p. 83). Matched case-insensitively.
_BTL_WORDS = ("btl", "better-than-life", "better than life")
_CYBERDECK_GEAR_CATEGORY = "Cyberdecks"
_CYBERDECK_IMPLANT_NAME = "Cyberdeck"

# WP114: catalog rows only a metatype can grant. `Resistance to Pathogens/Toxins` is the Dwarf's
# racial "+2 dice vs. pathogen/toxin" as `metatypes.xml` encodes it; the purchasable quality is the
# three separate rows (p. 77's 4- or 8-Karma levels).
METATYPE_ONLY_QUALITY_NAMES = frozenset({"Resistance to Pathogens/Toxins"})

# WP112: what an Exceptional Attribute pick may name -- every Mental/Physical attribute, and Magic
# for a magic user (p. 72: "Physical, Mental, or Special attribute [...] Magic or Resonance"; Edge
# is excluded by the data and belongs to Lucky; Resonance is out of scope).
ATTRIBUTE_CHOICES = ("BOD", "AGI", "REA", "STR", "WIL", "LOG", "INT", "CHA", "MAG")

# WP22: FLAT_BONUS has a real Improvement to apply; NO_EFFECT is offerable too -- it's a
# verified-inert quality (see chummer5.data.qualities module docstring) with an empty
# flat_bonuses tuple, so apply_quality_improvements is naturally a no-op for it, no special case.
# WP55: SELECT_TEXT is offerable too, for the identical "empty flat_bonuses, no-op to apply" reason
# -- its only requirement (a free-text detail) is validated by create_quality_selection itself, not
# by apply_quality_improvements.
_OFFERABLE_SUPPORT = (BonusSupport.FLAT_BONUS, BonusSupport.NO_EFFECT, BonusSupport.SELECT_TEXT)


def _mentor_spirit_quality(catalog: Iterable[Quality]) -> Quality | None:
    return next((q for q in catalog if q.name == MENTOR_SPIRIT_QUALITY_NAME), None)


def _add_mentor_spirit_if_eligible(
    offered: dict[str, Quality], catalog: Iterable[Quality], magic_type: str | None
) -> dict[str, Quality]:
    """Widen an already-computed `{id: Quality}` offered map with Mentor Spirit, for a magic-active
    `magic_type` only ("Magician"/"Adept" -- Phase I's only two, per `chummer5.data.qualities`'s
    `required` gate on the real quality, narrowed to what this engine actually produces).

    A shared helper (not inlined at each call site) so `offerable_quality_catalog` (character-level,
    used by the web layer/save-format/legacy-import to decide what to *show*) and
    `create_quality_selection` (magic-type-level, used to decide what to *accept*) can never
    disagree about eligibility -- see module docstring.
    """
    if magic_type is None:
        return offered
    mentor_spirit = _mentor_spirit_quality(catalog)
    if mentor_spirit is None:
        return offered
    return {**offered, mentor_spirit.id: mentor_spirit}


# WP108: the talent qualities the legacy data names in `<required>`/`<forbidden>` blocks
# ("quality=Magician") mean "this character's Talent is X". In this engine that is
# `Character.magic_type`, whose values are the same strings, never a picked quality.
TALENT_QUALITY_NAMES = frozenset(
    {"Magician", "Adept", "Aspected Magician", "Mystic Adept", "Technomancer"}
)

# WP108: SR5-sourced catalog rows that are out of scope as catalog hygiene rather than as
# unsupported bonuses (see spec/plan/phase-x-rulebook-completeness.md's intro): the five Karma-build
# talent qualities (`CharacterBuildMethod.Karma` scaffolding, and not in the chapter's quality
# lists), Astral Perception as a *quality* (Pixie-only), and the two Infected critter powers.
# Excluded by name so a later WP widening `_OFFERABLE_SUPPORT` can never offer one by accident.
OUT_OF_SCOPE_QUALITY_NAMES = frozenset(
    {
        *TALENT_QUALITY_NAMES,
        "Astral Perception",
        "Infected Advanced Optional Power: Mimicry",
        "Infected Advanced Optional Power: Psychokinesis",
    }
)

# Used only to word a prerequisite failure: which of a requirement's names a player could act on.
_CORE_METATYPE_NAMES = frozenset({"Human", "Elf", "Dwarf", "Ork", "Troll"})
_PLAYABLE_TALENT_NAMES = frozenset({"Magician", "Adept", "Aspected Magician"})


@dataclass(frozen=True)
class GateContext:
    """What a quality's `<required>`/`<forbidden>` conditions are evaluated against (WP108).

    `quality_names` is every quality the character holds: its picks and its metatype's free ones.
    `metatype_name` is `None` when the caller doesn't know it, and then every `metatype=` condition
    is unmet -- a metatype-gated quality fails closed rather than slipping through.
    """

    metatype_name: str | None
    magic_type: str | None
    quality_names: frozenset[str] = frozenset()
    # WP119: the adept powers held -- High Pain Tolerance forbids the Pain Resistance power.
    power_names: frozenset[str] = frozenset()


def _condition_met(kind: str, value: str, context: GateContext) -> bool:
    """One `(kind, value)` condition. Kinds this project never produces (`metatypecategory`,
    `critterpower`, `resenabled`, `depenabled`, ...) are never met, so a gate built only from
    them -- Astral Perception's `metatype=Pixie`, say -- can't be satisfied, which is correct: no
    core character can take it."""
    if kind == "metatype":
        return value == context.metatype_name
    if kind == "quality":
        if value in TALENT_QUALITY_NAMES:
            return value == context.magic_type
        return value in context.quality_names
    if kind == "magenabled":
        return context.magic_type is not None
    if kind == "power":
        return value in context.power_names
    return False


def _group_met(requirement: Requirement, context: GateContext) -> bool:
    results = [_condition_met(kind, value, context) for kind, value in requirement.conditions]
    return all(results) if requirement.mode == "allof" else any(results)


def _describe_requirement(requirement: Requirement) -> str:
    names: list[str] = []
    for kind, value in requirement.conditions:
        if kind == "metatype" and value in _CORE_METATYPE_NAMES:
            names.append(value)
        elif kind == "quality" and value in _PLAYABLE_TALENT_NAMES:
            names.append(value)
        elif kind == "magenabled":
            names.append("a Magic rating")
    joiner = " and " if requirement.mode == "allof" else " or "
    return joiner.join(dict.fromkeys(names)) or "nothing a core character can have"


def requirement_failure(quality: Quality, context: GateContext) -> str | None:
    """Why `quality` can't be held in `context`, or `None` if it can (WP108).

    Every `required` group must be met and no `forbidden` group may be. Talent names resolve against
    `context.magic_type` (see `TALENT_QUALITY_NAMES`), so Magic Resistance's `forbidden` list makes
    it unavailable to any Awakened character (p. 76) with no special case. A `forbidden` group that
    names only other *qualities* is WP55's mutual exclusion, reported with its existing wording.
    """
    for requirement in quality.required:
        if not _group_met(requirement, context):
            return f"{quality.name} requires {_describe_requirement(requirement)}"
    for requirement in quality.forbidden:
        if not _group_met(requirement, context):
            continue
        conflicts = sorted(
            value
            for kind, value in requirement.conditions
            if kind == "quality"
            and value not in TALENT_QUALITY_NAMES
            and value in context.quality_names
        )
        conflicts += sorted(
            value
            for kind, value in requirement.conditions
            if kind == "power" and value in context.power_names
        )
        if conflicts:
            return f"{quality.name} cannot be taken together with: {conflicts}"
        return f"{quality.name} is not available to a {context.magic_type or 'mundane'} character"
    return None


def mvp_quality_catalog(qualities: Iterable[Quality]) -> tuple[Quality, ...]:
    """Restrict a quality catalog to the ones MVP can actually offer a player.

    `chummer5.data.qualities.load_qualities()` already restricts to `source == "SR5"`; this narrows
    further to `BonusSupport.FLAT_BONUS` (a bonus shape MVP's Improvement engine can apply
    correctly) and `BonusSupport.NO_EFFECT` (a verified-inert quality -- no Improvement to apply,
    but no effect silently dropped either). A `NOT_YET_SUPPORTED` quality is excluded entirely
    rather than offered with its mechanical effect silently dropped, mirroring WP3's own "never
    partially apply a quality's effects" rule.
    """
    return tuple(
        q
        for q in qualities
        if q.bonus_support in _OFFERABLE_SUPPORT
        and q.name not in OUT_OF_SCOPE_QUALITY_NAMES
        and q.name not in METATYPE_ONLY_QUALITY_NAMES
    )


@dataclass(frozen=True)
class MentorSpiritPick:
    """A resolved Mentor Spirit archetype pick (WP48): which archetype, which General-slot option
    (the player's choice when the archetype offers one -- e.g. Cat's Gymnastics-or-Sneaking pick;
    otherwise the archetype's sole option), and which Magician-or-Adept slot (auto-resolved from
    `magic_type`, never a player pick -- see module docstring)."""

    archetype: MentorSpiritArchetype
    general_choice: MentorChoice
    gated_choice: MentorChoice


@dataclass(frozen=True)
class QualityPickRequest:
    """One quality instance as a player, a save file or a legacy import asks for it (WP107).

    The unresolved twin of `QualityPick` -- an id instead of a catalog `Quality`, the same split
    `chummer5.engine.cyberware_subsystems.CyberwarePurchaseRequest` makes for purchase trees.
    """

    quality_id: str
    rating: int = 1
    text: str | None = None
    choice: str | None = None


@dataclass(frozen=True)
class QualityPick:
    """One validated quality instance (WP107): which quality, at which level, with which detail.

    `rating` is 1 for every unrated quality. `text` is the free-text detail a `SELECT_TEXT` quality
    requires (which SIN, which substance) and `None` for every other. `choice` is the typed slot for
    a select-a-thing bonus (a skill, an attribute, a Matrix action) -- carried, not interpreted, by
    this module.
    """

    quality: Quality
    rating: int = 1
    text: str | None = None
    choice: str | None = None

    @property
    def karma(self) -> int:
        """Signed Karma for this instance (the source data's sign convention): `karma x rating`."""
        return self.quality.karma * self.rating

    def to_request(self) -> QualityPickRequest:
        return QualityPickRequest(
            quality_id=self.quality.id, rating=self.rating, text=self.text, choice=self.choice
        )


def attribute_choices(quality: Quality, magic_type: str | None) -> tuple[str, ...]:
    """The attributes a `choice_kind == "attribute"` pick of `quality` may name (WP112)."""
    return tuple(
        code
        for code in ATTRIBUTE_CHOICES
        if code not in quality.choice_excludes and (code != "MAG" or magic_type is not None)
    )


def _validate_choice(quality: Quality, choice: str | None, magic_type: str | None) -> None:
    """WP112: a quality with a `choice_kind` needs a valid choice; one without must carry none (the
    same "don't silently ignore a stale/tampered field" rule the free-text detail follows)."""
    if quality.choice_kind is None:
        if choice is not None:
            raise ValueError(f"{quality.name} takes no choice, got {choice!r}")
        return
    allowed = choice_options(quality, magic_type)
    if choice not in allowed:
        raise ValueError(f"{quality.name} needs one of {list(allowed)}, got {choice!r}")


def choice_options(quality: Quality, magic_type: str | None) -> tuple[str, ...]:
    """Every value a pick of `quality` may name in `choice` (WP112/WP114), or `()` for a quality
    that takes none."""
    if quality.choice_kind == "attribute":
        return attribute_choices(quality, magic_type)
    if quality.choice_kind == "matrix_action":
        return MATRIX_ACTION_CHOICES
    if quality.choice_kind == "home_ground":
        return HOME_GROUND_CHOICES
    if quality.choice_kind == "spirit_type":
        return SPIRIT_TYPE_CHOICES
    if quality.choice_kind == "scorched_effect":
        return SCORCHED_EFFECT_CHOICES
    if quality.choice_kind == "skill":
        return SKILL_CHOICES
    if quality.choice_kind == "skill_group":
        return tuple(
            g
            for g in SKILL_GROUP_CHOICES
            if g not in _MAGIC_SKILL_GROUPS or magic_type in _MAGIC_GROUP_TALENTS
        )
    if quality.choice_kind is None:
        return ()
    raise ValueError(f"{quality.name}: unsupported choice kind {quality.choice_kind!r}")


def requested_attribute_maximum_bonuses(
    picks: Iterable[str | QualityPickRequest], catalog: Iterable[Quality]
) -> dict[str, int]:
    """WP112: the attribute-maximum raises a set of *unvalidated* pick requests asks for.

    `create_character` has to know them before any quality is committed -- a saved Troll with STR
    11 and Exceptional Attribute (STR) is rebuilt attributes first -- so this reads them straight
    off the requests. `create_quality_selection` validates the same requests afterwards; an invalid
    one fails there, so trusting it here for one step changes no outcome.
    """
    by_id = {q.id: q for q in catalog}
    bonuses: dict[str, int] = {}
    for request in (_as_request(p) for p in picks):
        quality = by_id.get(request.quality_id)
        if quality is None:
            continue
        for bonus in quality.flat_bonuses:
            if bonus.target_kind != "attribute_maximum":
                continue
            code = bonus.target_name or request.choice
            if code:
                bonuses[code] = bonuses.get(code, 0) + bonus.value * request.rating
    return bonuses


@dataclass(frozen=True)
class LaterStepFacts:
    """What a quality pick needs from steps resolved *after* qualities (WP115).

    Two negative qualities have prerequisites outside the quality step: Loss of Confidence names a
    skill that must already be at rating 4+ (p. 82), and Scorched needs a BTL Addiction or being a
    decker (p. 83), which this project reads as owning a cyberdeck. A save and a legacy import
    resolve qualities before skills and gear, so they pass no facts and these two checks are
    skipped there; the web route passes them at pick time and on every re-render, which is where
    the WP19 "no longer fits" warning surfaces a pick a later edit broke.
    """

    skill_ratings: Mapping[str, int]  # by skill name
    owns_cyberdeck: bool


def later_step_facts(character: Character, skills: Iterable[Skill]) -> LaterStepFacts:
    """The `LaterStepFacts` of `character` as it stands (WP115)."""
    allocation = character.skill_allocation
    ratings = (
        {skill.name: skill_rating(character, allocation, skill) for skill in skills}
        if allocation is not None
        else {}
    )
    gear = character.resources_selection.gear if character.resources_selection is not None else ()
    implants = (
        character.cyberware_selection.walk() if character.cyberware_selection is not None else ()
    )
    owns_cyberdeck = any(item.category == _CYBERDECK_GEAR_CATEGORY for item in gear) or any(
        node.item.name == _CYBERDECK_IMPLANT_NAME for node in implants
    )
    return LaterStepFacts(skill_ratings=ratings, owns_cyberdeck=owns_cyberdeck)


def _check_later_step_prerequisites(
    picks: Iterable[QualityPick], later_steps: LaterStepFacts
) -> None:
    """WP115: Loss of Confidence's skill rating and Scorched's BTL-or-decker prerequisite."""
    picks = tuple(picks)
    for pick in picks:
        minimum = pick.quality.choice_minimum_rating
        if minimum and pick.choice is not None:
            rating = later_steps.skill_ratings.get(pick.choice, 0)
            if rating < minimum:
                raise ValueError(
                    f"{pick.quality.name} needs a skill at rating {minimum} or higher; "
                    f"{pick.choice} is at {rating}"
                )
    if not any(p.quality.name == SCORCHED_QUALITY_NAME for p in picks):
        return
    btl_addiction = any(
        p.quality.name.startswith("Addiction (")
        and p.text is not None
        and any(word in p.text.lower() for word in _BTL_WORDS)
        for p in picks
    )
    if not btl_addiction and not later_steps.owns_cyberdeck:
        raise ValueError(
            "Scorched requires an Addiction to BTLs (name BTLs in its detail) or a cyberdeck"
        )


def _as_request(pick: str | QualityPickRequest) -> QualityPickRequest:
    """A bare id means "this quality, once, at rating 1, with no detail" -- the shorthand every
    caller with nothing to choose keeps using (the same convention `create_bioware_selection`
    follows for its own requests)."""
    return QualityPickRequest(quality_id=pick) if isinstance(pick, str) else pick


@dataclass(frozen=True)
class QualitySelection:
    """A validated set of selected qualities and their net karma effect.

    `positive_karma`/`negative_karma` are both non-negative magnitudes (independent of the source
    data's sign convention), so they compare directly against `QUALITY_KARMA_LIMIT`. `karma_cost` is
    the signed net karma delta of taking every selected quality (positive qualities cost karma,
    negative qualities refund it) -- `positive_karma - negative_karma`.

    `mentor_spirit` (WP48) is `None` unless "Mentor Spirit" is among `qualities` -- see
    `create_quality_selection`'s own docstring for how it's resolved and validated.

    `qualities` (WP107) is a tuple of `QualityPick` instances in submission order. WP55's
    `quality_text` map folded into `QualityPick.text`: an id-keyed map cannot tell two Addictions
    apart.
    """

    qualities: tuple[QualityPick, ...]
    positive_karma: int
    negative_karma: int
    karma_cost: int
    mentor_spirit: MentorSpiritPick | None = None

    def to_requests(self) -> tuple[QualityPickRequest, ...]:
        return tuple(pick.to_request() for pick in self.qualities)


def create_quality_selection(
    picks: Iterable[str | QualityPickRequest],
    catalog: Iterable[Quality],
    *,
    magic_type: str | None = None,
    mentor_catalog: Iterable[MentorSpiritArchetype] = (),
    mentor_spirit_archetype_id: str | None = None,
    mentor_spirit_general_choice_id: str | None = None,
    metatype_name: str | None = None,
    granted_quality_names: Iterable[str] = (),
    later_steps: LaterStepFacts | None = None,
    power_names: Iterable[str] = (),
) -> QualitySelection:
    """Build a `QualitySelection`, validating against the MVP-offered catalog and the karma cap.

    Validates: every id is one of `mvp_quality_catalog(catalog)`'s qualities, widened by Mentor
    Spirit itself when `magic_type` is `"Magician"`/`"Adept"` (see
    `_add_mentor_spirit_if_eligible`); no quality is selected more than once; no two selected
    qualities forbid each other (WP55, `Quality.forbidden_names`, e.g. SINner's 4-way mutual
    exclusion); summed Positive-category karma doesn't exceed `QUALITY_KARMA_LIMIT`; summed
    Negative-category karma magnitude doesn't exceed it either, checked independently (see module
    docstring).

    **WP55, per instance since WP107**: a `SELECT_TEXT` pick needs a non-blank `text`, and a pick of
    any other quality must carry none (the same "don't silently ignore a stale/tampered field" rule
    `mentor_spirit_archetype_id` already follows). Text is stored stripped.

    **WP107**: a bare `str` in `picks` means `QualityPickRequest(that_id)`. A quality that is
    neither rated nor repeatable may appear once; a rated one once, at a `rating` within
    `1..Quality.max_rating`; a repeatable one any number of times, but never twice with the same
    `(text, choice)`. An unrated quality's `rating` must be 1. Both 25-Karma caps sum
    `karma x rating` per pick, and rows linked by `include_in_limit` share one level cap.

    **WP48**: if `MENTOR_SPIRIT_QUALITY_NAME` is among `quality_ids`, `mentor_spirit_archetype_id`
    must resolve against `mentor_catalog`, `magic_type` must be `"Magician"` or `"Adept"` (Mentor
    Spirit's own `required` gate, narrowed to this engine's two magic-active types), and
    `mentor_spirit_general_choice_id`, if given, must resolve to one of the archetype's own
    `general_options` (whether it has one or two); if omitted, it's only accepted when the
    archetype has exactly one option (auto-selected), and rejected as "a General bonus option must
    be chosen" otherwise. Deliberately accepts an *explicit* id even for a single-option archetype
    (as long as it matches that one option) rather than requiring it be omitted -- a save/load
    round trip always persists whatever `general_choice.id` was actually resolved (see
    `chummer5.io.save_format`'s own WP48 docstring paragraph), so a stricter "must be `None`" rule
    here would reject every single-option archetype's own reloaded save. If Mentor Spirit is *not*
    selected, `mentor_spirit_archetype_id` must be `None` -- an orphaned archetype pick with no
    quality backing it is rejected the same "don't silently ignore a stale/tampered field" way
    `create_foci_selection` rejects an unknown catalog id.

    **WP115**: `later_steps`, when given, checks the two prerequisites that live in later steps
    (see `LaterStepFacts`); `None` skips them.
    """
    offered_by_id = _add_mentor_spirit_if_eligible(
        {q.id: q for q in mvp_quality_catalog(catalog)}, catalog, magic_type
    )
    requests = [_as_request(p) for p in picks]

    unknown = sorted({r.quality_id for r in requests if r.quality_id not in offered_by_id})
    if unknown:
        raise ValueError(f"not an MVP-offered quality id: {unknown}")

    resolved: list[QualityPick] = []
    for request in requests:
        quality = offered_by_id[request.quality_id]
        if not 1 <= request.rating <= quality.max_rating:
            raise ValueError(
                f"{quality.name}: rating {request.rating} is outside 1-{quality.max_rating}"
            )
        _validate_choice(quality, request.choice, magic_type)
        text = request.text.strip() if request.text is not None else None
        if quality.bonus_support == BonusSupport.SELECT_TEXT:
            if not text:
                raise ValueError(f"quality requires a free-text detail: {[quality.name]}")
        elif text:
            raise ValueError(
                f"free-text detail supplied for a quality that doesn't use one: {[quality.name]}"
            )
        else:
            text = None
        resolved.append(
            QualityPick(quality=quality, rating=request.rating, text=text, choice=request.choice)
        )

    ids = [pick.quality.id for pick in resolved]
    duplicates = sorted(
        {
            pick.quality.id
            for pick in resolved
            if not pick.quality.repeatable and ids.count(pick.quality.id) > 1
        }
    )
    if duplicates:
        raise ValueError(f"quality selected more than once: {duplicates}")
    instance_keys = [(p.quality.id, p.text, p.choice) for p in resolved if p.quality.repeatable]
    repeated = sorted(
        {
            offered_by_id[qid].name
            for qid, text, choice in instance_keys
            if instance_keys.count((qid, text, choice)) > 1
        }
    )
    if repeated:
        raise ValueError(f"the same quality instance was selected twice: {repeated}")

    for pick in resolved:
        if not pick.quality.include_in_limit:
            continue
        shared = {pick.quality.name, *pick.quality.include_in_limit}
        levels = sum(p.rating for p in resolved if p.quality.name in shared)
        if levels > pick.quality.max_rating:
            raise ValueError(
                f"{sorted(shared)} have {levels} levels between them, exceeding the shared "
                f"{pick.quality.max_rating}-level maximum"
            )

    selected = tuple(pick.quality for pick in resolved)

    # WP55 mutual exclusion and WP108 prerequisites, both through `requirement_failure`: checked by
    # name, not id, since a forbidden name need not itself be offered for the check to matter.
    context = GateContext(
        metatype_name=metatype_name,
        magic_type=magic_type,
        quality_names=frozenset({q.name for q in selected} | set(granted_quality_names)),
        power_names=frozenset(power_names),
    )
    for quality in dict.fromkeys(selected):
        failure = requirement_failure(quality, context)
        if failure is not None:
            raise ValueError(failure)

    if later_steps is not None:
        _check_later_step_prerequisites(resolved, later_steps)

    positive_karma = sum(p.karma for p in resolved if p.quality.category == "Positive")
    negative_karma = -sum(p.karma for p in resolved if p.quality.category == "Negative")

    if positive_karma > QUALITY_KARMA_LIMIT:
        raise ValueError(
            f"Positive Qualities cost {positive_karma} karma, exceeding the "
            f"{QUALITY_KARMA_LIMIT}-karma limit"
        )
    if negative_karma > QUALITY_KARMA_LIMIT:
        raise ValueError(
            f"Negative Qualities grant {negative_karma} karma, exceeding the "
            f"{QUALITY_KARMA_LIMIT}-karma limit"
        )

    mentor_spirit_selected = any(q.name == MENTOR_SPIRIT_QUALITY_NAME for q in selected)
    mentor_spirit_pick: MentorSpiritPick | None = None
    if mentor_spirit_selected:
        if mentor_spirit_archetype_id is None:
            raise ValueError("Mentor Spirit requires an archetype to be selected")
        if magic_type not in ("Magician", "Adept", "Aspected Magician"):
            raise ValueError("Mentor Spirit requires a magic-active character")
        archetype_by_id = {a.id: a for a in mentor_catalog}
        archetype = archetype_by_id.get(mentor_spirit_archetype_id)
        if archetype is None:
            raise ValueError(f"not a Mentor Spirit archetype id: {mentor_spirit_archetype_id!r}")
        general_choice: MentorChoice
        if mentor_spirit_general_choice_id is None:
            if len(archetype.general_options) > 1:
                raise ValueError(f"{archetype.name}: a General bonus option must be chosen")
            general_choice = archetype.general_options[0]
        else:
            general_by_id = {c.id: c for c in archetype.general_options}
            resolved_choice = general_by_id.get(mentor_spirit_general_choice_id)
            if resolved_choice is None:
                raise ValueError(
                    f"{archetype.name}: not a General bonus option: "
                    f"{mentor_spirit_general_choice_id!r}"
                )
            general_choice = resolved_choice
        mentor_spirit_pick = MentorSpiritPick(
            archetype=archetype,
            general_choice=general_choice,
            gated_choice=gated_choice(archetype, magic_type),
        )
    elif mentor_spirit_archetype_id is not None:
        raise ValueError("a Mentor Spirit archetype was picked without the Mentor Spirit quality")

    return QualitySelection(
        qualities=tuple(resolved),
        positive_karma=positive_karma,
        negative_karma=negative_karma,
        karma_cost=positive_karma - negative_karma,
        mentor_spirit=mentor_spirit_pick,
    )


def apply_quality_improvements(
    character: Character,
    qualities: Iterable[Quality | QualityPick],
    *,
    source_type: ImprovementSource = ImprovementSource.QUALITY,
) -> None:
    """Add every given quality's `FlatBonus`es to `character.improvements` as `Improvement`s.

    Takes a plain `Iterable[Quality]` rather than a `QualitySelection` (WP23) so the same function
    serves both a player's chosen `selection.qualities` and a metatype's auto-granted `character
    .metatype_qualities` -- neither is `FLAT_BONUS`-only by construction (a metatype-granted quality
    can be `NOT_YET_SUPPORTED`, e.g. Resistance to Pathogens/Toxins), but that's fine: a quality
    with no recognized `<bonus>` shape simply has an empty `flat_bonuses` tuple regardless of why,
    so this loop is naturally a no-op for it either way -- never a partial or incorrect application.
    `source_id` is the quality's own id, so a future removal (e.g. an undo in the UI, or a metatype
    change) can use `ImprovementIndex.remove_source(source_type, quality.id)` to cleanly retract
    exactly what one quality granted. `source_type` defaults to `ImprovementSource.QUALITY` (every
    pre-WP23 caller passes a player's chosen qualities); WP23 passes `ImprovementSource.METATYPE`
    for metatype-granted ones, so the two are independently retractable.

    **WP110**: a quality with a Notoriety shift also adds a `NOTORIETY` Improvement, grouped so
    each listed quality counts once however many instances are held (see `_notoriety_group`).

    **WP107**: a `QualityPick` applies each flat bonus `x rating` (Indomitable (Mental) 2 is +2
    Mental limit); a bare `Quality` counts as rating 1. Every instance of a repeatable quality
    shares its `source_id`, which is fine: removal is always wholesale per quality.
    """
    for item in qualities:
        pick = item if isinstance(item, QualityPick) else QualityPick(quality=item)
        if pick.quality.notoriety:
            character.improvements.add(
                Improvement(
                    improvement_type=ImprovementType.NOTORIETY,
                    target="",
                    value=pick.quality.notoriety,
                    source_type=source_type,
                    source_id=pick.quality.id,
                    unique_name=_notoriety_group(pick.quality),
                )
            )
        for flat_bonus in pick.quality.flat_bonuses:
            character.improvements.add(
                Improvement(
                    improvement_type=_TARGET_KIND_TO_IMPROVEMENT_TYPE[flat_bonus.target_kind],
                    # WP112: an empty target on a choice-bearing bonus means "what was chosen".
                    target=flat_bonus.target_name or (pick.choice or ""),
                    value=flat_bonus.value * pick.rating,
                    source_type=source_type,
                    source_id=pick.quality.id,
                )
            )


def _notoriety_group(quality: Quality) -> str:
    """WP110: the dedup group that makes each p. 368-listed quality count once.

    p. 368 lists "Addiction", not its four severities, and says a character "cannot earn a
    Notoriety point for something for which they have already received a point". So every Addiction
    row and every repeated instance of any quality share one group, and `ImprovementIndex`'s
    highest-wins pass keeps one point.
    """
    family = quality.name
    if family.startswith("Addiction ("):
        family = "Addiction"
    return f"notoriety:{family}"


def apply_mentor_spirit_improvements(character: Character, pick: MentorSpiritPick) -> None:
    """Add a picked Mentor Spirit archetype's General + Magician-or-Adept `FLAT_BONUS` slots to
    `character.improvements` as `Improvement`s, under `ImprovementSource.MENTOR_SPIRIT` (WP48).

    `source_id` is the archetype's own id (not the Mentor Spirit quality's), so
    `ImprovementIndex.remove_source(ImprovementSource.MENTOR_SPIRIT, pick.archetype.id)` cleanly
    retracts exactly what one archetype pick granted -- independent of whatever `QUALITY`-sourced
    Improvements the Mentor Spirit quality's own (always-empty) `flat_bonuses` would apply via
    `apply_quality_improvements`. A no-op for the `NOT_YET_SUPPORTED`/`NO_EFFECT` slots most
    archetypes have at least one of -- see `chummer5.data.mentors`'s own docstring for the full
    per-archetype classification.
    """
    for choice in (pick.general_choice, pick.gated_choice):
        for flat_bonus in choice.flat_bonuses:
            character.improvements.add(
                Improvement(
                    improvement_type=_TARGET_KIND_TO_IMPROVEMENT_TYPE[flat_bonus.target_kind],
                    target=flat_bonus.target_name,
                    value=flat_bonus.value,
                    source_type=ImprovementSource.MENTOR_SPIRIT,
                    source_id=pick.archetype.id,
                )
            )


def apply_metatype_bonus_improvements(character: Character) -> None:
    """WP113: the metatype's racial `<bonus>` as `METATYPE`-sourced Improvements, keyed by the
    metatype's id: the Lifestyle surcharge (`LIFESTYLE_COST`), extra Reach (`REACH`), and racial
    dermal armor (`ARMOR`, in its dedup group so Dermal Plating/Orthoskin replace rather than stack
    with it -- WP129 confirms which wins)."""
    metatype = character.metatype
    for improvement_type, value, unique_name in (
        (ImprovementType.LIFESTYLE_COST, metatype.lifestyle_cost_percent, None),
        (ImprovementType.REACH, metatype.reach, None),
        (ImprovementType.ARMOR, metatype.armor, metatype.armor_group),
    ):
        if value:
            character.improvements.add(
                Improvement(
                    improvement_type=improvement_type,
                    target="",
                    value=value,
                    source_type=ImprovementSource.METATYPE,
                    source_id=metatype.id,
                    unique_name=unique_name,
                )
            )


def resolve_metatype_qualities(
    metatype: Metatype, catalog: Iterable[Quality]
) -> tuple[Quality, ...]:
    """Resolve a metatype's free-quality names (WP23) against the full SR5-scoped quality catalog.

    Unlike `mvp_quality_catalog`, this is **not** restricted to `FLAT_BONUS`/`NO_EFFECT` --
    granting is unconditional SR5 rules, not a player purchase a karma cap needs to protect. A
    `NOT_YET_SUPPORTED` metatype quality (e.g. Dwarf's Resistance to Pathogens/Toxins, whose
    toxin-resist effect this project models nowhere) is still granted and recorded on the
    character; its `flat_bonuses` tuple is simply empty, so `apply_quality_improvements` naturally
    applies zero Improvements for it -- the same "verified, not silently wrong" shape WP22's
    `NO_EFFECT` tranche already established for qualities whose real effect lands outside this
    engine's modeled systems.

    Raises `ValueError` if a name doesn't resolve against `catalog` -- these names are fixed by the
    shipped SR5 XML, so a lookup failure means a real data bug (e.g. `catalog` wasn't SR5-scoped),
    not an expected runtime edge case.
    """
    by_name = {q.name: q for q in catalog}
    names = (*metatype.qualities_positive, *metatype.qualities_negative)
    unknown = [name for name in names if name not in by_name]
    if unknown:
        raise ValueError(
            f"{metatype.name}: metatype-granted quality not found in the catalog: {unknown}"
        )
    return tuple(by_name[name] for name in names)


def offerable_quality_catalog(
    character: Character, catalog: Iterable[Quality]
) -> tuple[Quality, ...]:
    """`mvp_quality_catalog` further restricted to what `character` can still choose to buy (WP23),
    widened by Mentor Spirit for a magic-active `character` (WP48).

    **WP108**: also excludes every quality whose `<required>`/`<forbidden>` gate this character's
    metatype or Talent fails (Human-Looking for a Human, Magic Resistance for a Magician).

    Excludes whatever `character.metatype_qualities` already grants for free, so a player can never
    spend karma re-buying an inherent racial quality (e.g. an Elf "buying" Low-Light Vision, which
    WP22 made purchasable). Passing this narrowed catalog straight into `create_quality_selection`
    is sufficient to enforce the exclusion too -- no signature change needed there for *this* part,
    since it already re-derives `mvp_quality_catalog` from whatever catalog it's given, and an
    already-excluded quality simply isn't in that input to begin with. Mentor Spirit eligibility is
    a separate concern (WP48): `create_quality_selection` re-derives it independently from its own
    `magic_type` parameter via `_add_mentor_spirit_if_eligible` (the same helper this function
    calls), so the two never disagree even though this function's caller and
    `create_quality_selection`'s caller aren't always the same code path.
    """
    already_granted = {q.id for q in character.metatype_qualities}
    context = GateContext(
        metatype_name=character.metatype.name,
        magic_type=character.magic_type,
        quality_names=frozenset(q.name for q in character.metatype_qualities),
        power_names=frozenset(
            p.power.name
            for p in (character.power_selection.picks if character.power_selection else ())
        ),
    )
    offered = {
        q.id: q
        for q in mvp_quality_catalog(catalog)
        if q.id not in already_granted and _available_alone(q, context)
    }
    offered = _add_mentor_spirit_if_eligible(offered, catalog, character.magic_type)
    return tuple(offered.values())


def _available_alone(quality: Quality, context: GateContext) -> bool:
    """`requirement_failure` with the picks themselves left out: a quality is still *offered* even
    when it conflicts with another offered quality (the player picks one of the pair, and
    `create_quality_selection` rejects taking both). Only the metatype/Talent side of a gate --
    things the player can't fix on this page -- hides a row."""
    return requirement_failure(quality, context) is None
