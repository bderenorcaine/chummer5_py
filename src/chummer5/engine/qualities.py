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
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from chummer5.data.metatypes import Metatype
from chummer5.data.qualities import BonusSupport, Quality
from chummer5.engine.character import Character
from chummer5.engine.improvements import Improvement, ImprovementSource, ImprovementType

# CharacterSettings.QualityKarmaLimit (legacy default: `_intQualityKarmaLimit = 25`) -- the maximum
# karma a character may spend on Positive Qualities, and independently, the maximum karma it may
# refund from Negative Qualities, at creation. See spec/rulebooks/learnings.md's WP8 entry for the
# rulebook text and the legacy enforcement site.
QUALITY_KARMA_LIMIT = 25

_TARGET_KIND_TO_IMPROVEMENT_TYPE = {
    "attribute": ImprovementType.ATTRIBUTE,
    "skill": ImprovementType.SKILL,
    "mental_limit": ImprovementType.MENTAL_LIMIT,
    "physical_limit": ImprovementType.PHYSICAL_LIMIT,
    "social_limit": ImprovementType.SOCIAL_LIMIT,
}

# WP22: FLAT_BONUS has a real Improvement to apply; NO_EFFECT is offerable too -- it's a
# verified-inert quality (see chummer5.data.qualities module docstring) with an empty
# flat_bonuses tuple, so apply_quality_improvements is naturally a no-op for it, no special case.
_OFFERABLE_SUPPORT = (BonusSupport.FLAT_BONUS, BonusSupport.NO_EFFECT)


def mvp_quality_catalog(qualities: Iterable[Quality]) -> tuple[Quality, ...]:
    """Restrict a quality catalog to the ones MVP can actually offer a player.

    `chummer5.data.qualities.load_qualities()` already restricts to `source == "SR5"`; this narrows
    further to `BonusSupport.FLAT_BONUS` (a bonus shape MVP's Improvement engine can apply
    correctly) and `BonusSupport.NO_EFFECT` (a verified-inert quality -- no Improvement to apply,
    but no effect silently dropped either). A `NOT_YET_SUPPORTED` quality is excluded entirely
    rather than offered with its mechanical effect silently dropped, mirroring WP3's own "never
    partially apply a quality's effects" rule.
    """
    return tuple(q for q in qualities if q.bonus_support in _OFFERABLE_SUPPORT)


@dataclass(frozen=True)
class QualitySelection:
    """A validated set of selected qualities and their net karma effect.

    `positive_karma`/`negative_karma` are both non-negative magnitudes (independent of the source
    data's sign convention), so they compare directly against `QUALITY_KARMA_LIMIT`. `karma_cost` is
    the signed net karma delta of taking every selected quality (positive qualities cost karma,
    negative qualities refund it) -- `positive_karma - negative_karma`.
    """

    qualities: tuple[Quality, ...]
    positive_karma: int
    negative_karma: int
    karma_cost: int


def create_quality_selection(
    quality_ids: Iterable[str], catalog: Iterable[Quality]
) -> QualitySelection:
    """Build a `QualitySelection`, validating against the MVP-offered catalog and the karma cap.

    Validates: every id is one of `mvp_quality_catalog(catalog)`'s qualities; no quality is selected
    more than once (none of the 3 currently-offered qualities are repeatable); summed Positive-
    category karma doesn't exceed `QUALITY_KARMA_LIMIT`; summed Negative-category karma magnitude
    doesn't exceed it either, checked independently (see module docstring).
    """
    offered_by_id = {q.id: q for q in mvp_quality_catalog(catalog)}
    ids = list(quality_ids)

    unknown = sorted({qid for qid in ids if qid not in offered_by_id})
    if unknown:
        raise ValueError(f"not an MVP-offered quality id: {unknown}")

    duplicates = sorted({qid for qid in ids if ids.count(qid) > 1})
    if duplicates:
        raise ValueError(f"quality selected more than once: {duplicates}")

    selected = tuple(offered_by_id[qid] for qid in ids)
    positive_karma = sum(q.karma for q in selected if q.category == "Positive")
    negative_karma = -sum(q.karma for q in selected if q.category == "Negative")

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

    return QualitySelection(
        qualities=selected,
        positive_karma=positive_karma,
        negative_karma=negative_karma,
        karma_cost=positive_karma - negative_karma,
    )


def apply_quality_improvements(
    character: Character,
    qualities: Iterable[Quality],
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
    """
    for quality in qualities:
        for flat_bonus in quality.flat_bonuses:
            character.improvements.add(
                Improvement(
                    improvement_type=_TARGET_KIND_TO_IMPROVEMENT_TYPE[flat_bonus.target_kind],
                    target=flat_bonus.target_name,
                    value=flat_bonus.value,
                    source_type=source_type,
                    source_id=quality.id,
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
    """`mvp_quality_catalog` further restricted to what `character` can still choose to buy (WP23).

    Excludes whatever `character.metatype_qualities` already grants for free, so a player can never
    spend karma re-buying an inherent racial quality (e.g. an Elf "buying" Low-Light Vision, which
    WP22 made purchasable). Passing this narrowed catalog straight into `create_quality_selection`
    is sufficient to enforce the exclusion too -- no signature change needed there, since it already
    re-derives `mvp_quality_catalog` from whatever catalog it's given, and an already-excluded
    quality simply isn't in that input to begin with.
    """
    already_granted = {q.id for q in character.metatype_qualities}
    return tuple(q for q in mvp_quality_catalog(catalog) if q.id not in already_granted)
