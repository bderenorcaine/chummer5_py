from pathlib import Path

from chummer5.data.qualities import (
    DEFAULT_QUALITIES_PATH,
    BonusSupport,
    FlatBonus,
    count_by_support,
    load_qualities,
)

_FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_only_sr5_sourced_qualities_are_loaded() -> None:
    # legacy/Chummer/data/qualities.xml has 803 <quality> entries total; 96 are source == "SR5".
    qualities = load_qualities()
    assert len(qualities) == 96
    assert all(q.source == "SR5" for q in qualities)


def test_positive_and_negative_split() -> None:
    qualities = load_qualities()
    assert sum(1 for q in qualities if q.category == "Positive") == 47
    assert sum(1 for q in qualities if q.category == "Negative") == 49


def test_negative_quality_karma_is_negative() -> None:
    # Hand-checked against qualities.xml's <quality><name>Addiction (Severe)</name>.
    qualities = load_qualities()
    addiction = next(q for q in qualities if q.name == "Addiction (Severe)")
    assert addiction.karma == -20
    assert addiction.category == "Negative"


def test_flat_skill_bonus_is_supported() -> None:
    # Hand-checked: <quality><name>Catlike</name> grants +2 Sneaking, unconditional.
    qualities = load_qualities()
    catlike = next(q for q in qualities if q.name == "Catlike")
    assert catlike.bonus_support == BonusSupport.FLAT_BONUS
    assert catlike.flat_bonuses == (
        FlatBonus(target_kind="skill", target_name="Sneaking", value=2),
    )


def test_flat_skill_bonus_multiple_targets_is_supported() -> None:
    # Natural Athlete grants two unconditional flat skill bonuses (Running, Gymnastics), both +2.
    qualities = load_qualities()
    natural_athlete = next(q for q in qualities if q.name == "Natural Athlete")
    assert natural_athlete.bonus_support == BonusSupport.FLAT_BONUS
    targets = {(b.target_kind, b.target_name, b.value) for b in natural_athlete.flat_bonuses}
    assert targets == {("skill", "Running", 2), ("skill", "Gymnastics", 2)}


def test_conditional_skill_bonus_is_not_yet_supported() -> None:
    # Analytical Mind's <skillattribute> bonus carries a narrative <condition> — MVP's flat-bonus
    # classifier only accepts unconditional <specificskill>/<specificattribute> nodes.
    qualities = load_qualities()
    analytical_mind = next(q for q in qualities if q.name == "Analytical Mind")
    assert analytical_mind.bonus_support == BonusSupport.NOT_YET_SUPPORTED
    assert analytical_mind.flat_bonuses == ()
    assert analytical_mind.raw_bonus is not None


def test_quality_with_no_bonus_element_is_not_yet_supported() -> None:
    # Gremlins uses <firstlevelbonus> instead of <bonus> — no <bonus> element is present at all.
    qualities = load_qualities()
    gremlins = next(q for q in qualities if q.name == "Gremlins")
    assert gremlins.bonus_support == BonusSupport.NOT_YET_SUPPORTED
    assert gremlins.raw_bonus is None


def test_supported_vs_unsupported_counts_are_visible() -> None:
    # WP22 widens FLAT_BONUS from 3 (Catlike, Double-Jointed, Natural Athlete) to 6 by adding
    # the Indomitable trio (Mental/Physical/Social), and introduces NO_EFFECT for 8
    # individually-verified qualities (Gearhead, Guts, Juryrigger, Natural Hardening,
    # Low-Light Vision, Thermographic Vision, Simsense Vertigo, Unsteady Hands). The rest
    # (select-a-target choices, category-wide/conditional bonuses, notoriety shifts,
    # multi-effect bonuses, attribute max/min changes, etc.) are NOT_YET_SUPPORTED: 96 - 6 - 8 = 82.
    qualities = load_qualities()
    counts = count_by_support(qualities)
    assert counts[BonusSupport.FLAT_BONUS] == 6
    assert counts[BonusSupport.NO_EFFECT] == 8
    assert counts[BonusSupport.NOT_YET_SUPPORTED] == 82


def test_indomitable_mental_limit_bonus_is_supported() -> None:
    # Hand-checked: <quality><name>Indomitable (Mental)</name> grants <mentallimit>1</mentallimit>,
    # unconditional, untargeted (only one Mental Limit per character).
    qualities = load_qualities()
    indomitable_mental = next(q for q in qualities if q.name == "Indomitable (Mental)")
    assert indomitable_mental.bonus_support == BonusSupport.FLAT_BONUS
    assert indomitable_mental.flat_bonuses == (
        FlatBonus(target_kind="mental_limit", target_name="", value=1),
    )


def test_indomitable_physical_and_social_limit_bonuses_are_supported() -> None:
    qualities = load_qualities()
    indomitable_physical = next(q for q in qualities if q.name == "Indomitable (Physical)")
    indomitable_social = next(q for q in qualities if q.name == "Indomitable (Social)")
    assert indomitable_physical.flat_bonuses == (
        FlatBonus(target_kind="physical_limit", target_name="", value=1),
    )
    assert indomitable_social.flat_bonuses == (
        FlatBonus(target_kind="social_limit", target_name="", value=1),
    )


def test_verified_no_effect_quality_has_no_flat_bonuses() -> None:
    # Gearhead's <bonus/> is empty -- like 14 other SR5 qualities -- but only the 8 individually
    # verified in WP22 (see chummer5.data.qualities._VERIFIED_NO_EFFECT_NAMES) are NO_EFFECT.
    qualities = load_qualities()
    gearhead = next(q for q in qualities if q.name == "Gearhead")
    assert gearhead.bonus_support == BonusSupport.NO_EFFECT
    assert gearhead.flat_bonuses == ()


def test_unverified_empty_bonus_quality_stays_not_yet_supported() -> None:
    # Human-Looking also has an empty <bonus/> but needs a "required metatype" check WP22 didn't
    # build (see Implementation Plan's WP22 entry) -- it must NOT be swept into NO_EFFECT just
    # because its <bonus> node happens to be empty too.
    qualities = load_qualities()
    human_looking = next(q for q in qualities if q.name == "Human-Looking")
    assert human_looking.bonus_support == BonusSupport.NOT_YET_SUPPORTED


def test_flat_attribute_bonus_shape_is_supported() -> None:
    # No in-scope SR5 quality currently uses an unconditional <specificattribute><val> bonus (the
    # one real example, Lucky, pairs <specificattribute><max> with a <notoriety> shift and is
    # therefore NOT_YET_SUPPORTED), so this exercises the shape against a hand-authored fixture
    # mirroring the real <quality> schema.
    qualities = load_qualities(_FIXTURE_DIR / "qualities_flat_attribute_bonus.xml")
    assert len(qualities) == 1
    quality = qualities[0]
    assert quality.bonus_support == BonusSupport.FLAT_BONUS
    assert quality.flat_bonuses == (FlatBonus(target_kind="attribute", target_name="BOD", value=1),)


def test_default_path_points_at_real_legacy_file() -> None:
    assert DEFAULT_QUALITIES_PATH.name == "qualities.xml"
    assert DEFAULT_QUALITIES_PATH.is_file()
