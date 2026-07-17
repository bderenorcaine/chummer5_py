"""Quality selection & minimal Improvement bonuses.

Composes WP3's quality catalog (`chummer5.data.qualities`) with WP5's Improvement engine and WP6's
`Character` into a buildable positive/negative quality spend. Mundane MVP scope only — see
`spec/Project Overview.md`.

**The offered catalog is restricted to `BonusSupport.FLAT_BONUS` qualities, not the full 96-entry
SR5 catalog.** This follows directly from WP3's own docstring for `chummer5.data.qualities`
("WP8 offers only `FLAT_BONUS` qualities to the player; `NOT_YET_SUPPORTED` ones are excluded from
the offered list rather than silently applied with their bonus dropped") and from the Implementation
Plan's WP8 acceptance criterion ("an explicit test that an unsupported-bonus quality is excluded
from the offered list rather than silently mis-applied"). Concretely, this means the *only* three
qualities MVP can offer today are Catlike, Double-Jointed, and Natural Athlete — all three are
Positive category (see `spec/worklogs/WP8.md` for why no Negative quality currently qualifies) — so
the negative-quality karma cap below is real, general rules logic that no *current* real-data
selection can trigger, only synthetic tests (same "prove the rule before real content exercises it"
pattern WP5 used for the Improvement engine's dedup and WP7 used for the dice-pool formula).

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
}


def mvp_quality_catalog(qualities: Iterable[Quality]) -> tuple[Quality, ...]:
    """Restrict a quality catalog to the ones MVP can actually offer a player.

    `chummer5.data.qualities.load_qualities()` already restricts to `source == "SR5"`; this narrows
    further to `BonusSupport.FLAT_BONUS` -- the only bonus shape MVP's Improvement engine can apply
    correctly. A `NOT_YET_SUPPORTED` quality is excluded entirely rather than offered with its
    mechanical effect silently dropped, mirroring WP3's own "never partially apply a quality's
    effects" rule.
    """
    return tuple(q for q in qualities if q.bonus_support == BonusSupport.FLAT_BONUS)


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


def apply_quality_improvements(character: Character, selection: QualitySelection) -> None:
    """Add every selected quality's `FlatBonus`es to `character.improvements` as `Improvement`s.

    Every quality in `selection.qualities` is `FLAT_BONUS` by construction
    (`create_quality_selection` only ever selects from `mvp_quality_catalog`), so this never has an
    unsupported bonus to skip. `source_id` is the quality's own id, so a future removal (e.g. an
    undo in the UI) can use
    `ImprovementIndex.remove_source(ImprovementSource.QUALITY, quality.id)` to cleanly retract
    exactly what one quality granted.
    """
    for quality in selection.qualities:
        for flat_bonus in quality.flat_bonuses:
            character.improvements.add(
                Improvement(
                    improvement_type=_TARGET_KIND_TO_IMPROVEMENT_TYPE[flat_bonus.target_kind],
                    target=flat_bonus.target_name,
                    value=flat_bonus.value,
                    source_type=ImprovementSource.QUALITY,
                    source_id=quality.id,
                )
            )
