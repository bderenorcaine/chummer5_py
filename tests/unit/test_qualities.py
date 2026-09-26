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


def test_conditional_skill_bonus_is_registered_not_applied() -> None:
    # Analytical Mind's <skillattribute> bonus carries a narrative <condition> -- the flat-bonus
    # classifier still doesn't parse it, but since WP114 the quality is offered as a name-gated
    # NO_EFFECT row with its whole (in-play) effect in its unmodeled-effect note.
    qualities = load_qualities()
    analytical_mind = next(q for q in qualities if q.name == "Analytical Mind")
    assert analytical_mind.bonus_support == BonusSupport.NO_EFFECT
    assert analytical_mind.flat_bonuses == ()
    assert analytical_mind.raw_bonus is not None
    assert analytical_mind.unmodeled_effect_note


def test_quality_with_no_bonus_element_is_not_yet_supported() -> None:
    # Gremlins uses <firstlevelbonus> instead of <bonus> — no <bonus> element is present at all.
    qualities = load_qualities()
    gremlins = next(q for q in qualities if q.name == "Gremlins")
    assert gremlins.bonus_support == BonusSupport.NOT_YET_SUPPORTED
    assert gremlins.raw_bonus is None


def test_select_text_quality_is_classified_correctly() -> None:
    # Hand-checked: SINner (National)'s <bonus> is a bare <selecttext/>, no other children.
    qualities = load_qualities()
    sinner_national = next(q for q in qualities if q.name == "SINner (National)")
    assert sinner_national.bonus_support == BonusSupport.SELECT_TEXT
    assert sinner_national.flat_bonuses == ()
    assert sinner_national.karma == -5


def test_select_text_quality_with_a_notoriety_sibling_is_still_select_text() -> None:
    # SINner (Criminal)'s <bonus> carries both <notoriety>1</notoriety> and <selecttext/> -- the
    # Notoriety side is unmodeled (Project Overview's "Unmodeled real effects" table), not a second
    # thing this classifier needs to recognize structurally; name-gating (like NO_EFFECT) sidesteps
    # needing to parse <notoriety> at all.
    qualities = load_qualities()
    sinner_criminal = next(q for q in qualities if q.name == "SINner (Criminal)")
    assert sinner_criminal.bonus_support == BonusSupport.SELECT_TEXT
    assert sinner_criminal.flat_bonuses == ()


def test_sinner_variants_forbid_each_other() -> None:
    # Hand-checked: qualities.xml's <forbidden><oneof> block for each of the 4 SINner variants
    # names the other 3.
    qualities = load_qualities()
    by_name = {q.name for q in qualities}
    for name in (
        "SINner (National)",
        "SINner (Corporate Limited)",
        "SINner (Criminal)",
        "SINner (Corporate)",
    ):
        quality = next(q for q in qualities if q.name == name)
        assert set(quality.forbidden_names) == {
            n
            for n in (
                "SINner (National)",
                "SINner (Corporate Limited)",
                "SINner (Criminal)",
                "SINner (Corporate)",
            )
            if n != name
        }
    assert {"SINner (National)", "SINner (Corporate Limited)", "SINner (Criminal)"} <= by_name


def test_natural_immunity_forbids_weak_immune_system() -> None:
    # Hand-checked: both Natural Immunity variants forbid Weak Immune System (itself NOT_YET_
    # SUPPORTED -- not offered by mvp_quality_catalog -- so this exclusion is unreachable via the
    # offered catalog today; still parsed correctly, per WP55's "implement it correctly even though
    # it currently can't fire" instruction).
    qualities = load_qualities()
    for name in ("Natural Immunity (Natural)", "Natural Immunity (Synthetic)"):
        quality = next(q for q in qualities if q.name == name)
        assert quality.forbidden_names == ("Weak Immune System",)
    weak_immune_system = next(q for q in qualities if q.name == "Weak Immune System")
    assert weak_immune_system.bonus_support == BonusSupport.NOT_YET_SUPPORTED


def test_quality_with_no_forbidden_block_has_empty_forbidden_names() -> None:
    qualities = load_qualities()
    catlike = next(q for q in qualities if q.name == "Catlike")
    assert catlike.forbidden_names == ()


# --- WP56: unmodeled_effect_note --------------------------------------------------------------


def test_no_effect_and_select_text_qualities_carry_an_unmodeled_effect_note() -> None:
    # All 8 NO_EFFECT (WP22) + 9 SELECT_TEXT (WP55) qualities are individually verified to have
    # exactly one real, unmodeled SR5 effect each -- every one of them must carry a note.
    qualities = load_qualities()
    by_name = {q.name: q for q in qualities}
    for name in (
        "Gearhead",
        "Guts",
        "Juryrigger",
        "Natural Hardening",
        "Low-Light Vision",
        "Thermographic Vision",
        "Simsense Vertigo",
        "Unsteady Hands",
        "SINner (National)",
        "SINner (Corporate Limited)",
        "SINner (Criminal)",
        "SINner (Corporate)",
        "Code of Honor",
        "Codeblock",
        "Social Stress",
        "Natural Immunity (Natural)",
        "Natural Immunity (Synthetic)",
    ):
        quality = by_name[name]
        assert quality.unmodeled_effect_note, f"{name} should carry a WP56 disclosure note"


def test_resistance_to_pathogens_carries_a_note_despite_being_not_yet_supported() -> None:
    # WP23: metatype-granted, never player-purchasable, and NOT_YET_SUPPORTED -- but still has a
    # real unmodeled effect (a Resistance Test dice-pool bonus), so it needs the note too. Confirms
    # the note is independent of bonus_support/offerability (see module docstring).
    qualities = load_qualities()
    resistance = next(q for q in qualities if q.name == "Resistance to Pathogens/Toxins")
    assert resistance.bonus_support == BonusSupport.NOT_YET_SUPPORTED
    assert resistance.unmodeled_effect_note
    assert "toxin/pathogen" in resistance.unmodeled_effect_note


def test_flat_bonus_quality_has_no_unmodeled_effect_note() -> None:
    # Catlike's skill bonus is fully modeled -- nothing to disclose.
    qualities = load_qualities()
    catlike = next(q for q in qualities if q.name == "Catlike")
    assert catlike.bonus_support == BonusSupport.FLAT_BONUS
    assert catlike.unmodeled_effect_note is None


def test_supported_vs_unsupported_counts_are_visible() -> None:
    # WP22 widens FLAT_BONUS from 3 (Catlike, Double-Jointed, Natural Athlete) to 6 by adding
    # the Indomitable trio (Mental/Physical/Social), and introduces NO_EFFECT for 8
    # individually-verified qualities (Gearhead, Guts, Juryrigger, Natural Hardening,
    # Low-Light Vision, Thermographic Vision, Simsense Vertigo, Unsteady Hands). WP49 adds a 7th
    # FLAT_BONUS: Bilingual's own <nativelanguagelimit> (see spec/rulebooks/learnings.md's WP49
    # entry -- Bilingual was NOT_YET_SUPPORTED before this WP, despite the Implementation Plan's own
    # WP49 entry assuming it was already offered). WP55 introduces SELECT_TEXT for 9 individually
    # verified qualities (SINner x4, Code of Honor, Codeblock, Social Stress, Natural Immunity x2).
    # The rest (select-a-target choices with a real computed effect, category-wide/conditional
    # bonuses, notoriety shifts, multi-effect bonuses, attribute max/min changes, etc.) are
    # NOT_YET_SUPPORTED: 96 - 7 - 8 - 9 = 72. WP112 adds 2 FLAT_BONUS attribute-maximum raises
    # (Exceptional Attribute, Lucky): 9 FLAT_BONUS, 70 NOT_YET_SUPPORTED. WP114 adds 4 FLAT_BONUS
    # (Toughness, High Pain Tolerance, Will to Live, Photographic Memory) and 15 NO_EFFECT (12
    # registry rows + 3 choice rows): 13 FLAT_BONUS, 23 NO_EFFECT, 51 NOT_YET_SUPPORTED.
    qualities = load_qualities()
    counts = count_by_support(qualities)
    assert counts[BonusSupport.FLAT_BONUS] == 13
    assert counts[BonusSupport.NO_EFFECT] == 23
    assert counts[BonusSupport.SELECT_TEXT] == 9
    assert counts[BonusSupport.NOT_YET_SUPPORTED] == 51


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


def test_empty_bonus_quality_is_no_effect_only_by_name() -> None:
    # Human-Looking has an empty <bonus/> and needed the metatype gate WP108 built; WP114 then
    # name-gated it NO_EFFECT with a note. Gremlins, whose effect is not yet registered (WP115),
    # shows an empty/absent <bonus> is still not swept in on shape alone.
    qualities = load_qualities()
    human_looking = next(q for q in qualities if q.name == "Human-Looking")
    assert human_looking.bonus_support == BonusSupport.NO_EFFECT
    assert human_looking.unmodeled_effect_note
    gremlins = next(q for q in qualities if q.name == "Gremlins")
    assert gremlins.bonus_support == BonusSupport.NOT_YET_SUPPORTED


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
