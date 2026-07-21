"""Synthetic tests for `chummer5.io.legacy_import`'s blocking-reason checks and the
excluded-vs-blocking split for qualities/skills -- proven against hand-built `LegacyCharacter`s
before any real fixture touches it, the same "prove the mechanism in isolation first" pattern WP5
used for the Improvement engine. The real end-to-end import path (against `Yeti-#ffffff2.chum5`) is
covered in `tests/integration/test_legacy_import.py`.
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from chummer5.data.bioware import load_bioware
from chummer5.data.cyberware import load_cyberware
from chummer5.data.lifestyle import load_lifestyles
from chummer5.data.metatypes import load_metatypes
from chummer5.data.powers import load_powers
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import BonusSupport, load_qualities
from chummer5.data.skills import load_skills
from chummer5.data.spells import load_spells
from chummer5.data.traditions import load_traditions
from chummer5.io.legacy_chum5 import (
    LegacyAttribute,
    LegacyCharacter,
    LegacyCyberware,
    LegacyLifestyle,
    LegacyPower,
    LegacyQuality,
    LegacySkill,
    LegacySpell,
    PrioritySelections,
)
from chummer5.io.legacy_import import (
    UnsupportedLegacyCharacterError,
    import_legacy_character,
)

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
QUALITIES = load_qualities()
LIFESTYLES = load_lifestyles()
TRADITIONS = load_traditions()
SPELLS = load_spells()
POWERS = load_powers()
CYBERWARE = load_cyberware()
BIOWARE = load_bioware()


def _priorities(
    heritage: str = "D",
    attributes: str = "A",
    skills: str = "C",
    resources: str = "B",
    talent: str = "E,0",
    talent_codename: str = "Mundane",
    talent_bonus_skills: tuple[str, ...] = (),
) -> PrioritySelections:
    return PrioritySelections(
        heritage=f"{heritage},1",
        attributes=f"{attributes},1",
        talent=talent,
        skills=f"{skills},1",
        resources=f"{resources},1",
        talent_codename=talent_codename,
        talent_bonus_skills=talent_bonus_skills,
    )


def _legacy_character(**overrides: object) -> LegacyCharacter:
    defaults: dict[str, object] = dict(
        metatype="Human",
        metatype_category="Metahuman",
        metavariant=None,
        build_method="Priority",
        game_option="Standard",
        magic_enabled=False,
        resonance_enabled=False,
        priorities=_priorities(),
        attributes=MappingProxyType({}),
        skills=(),
        skill_groups=(),
        qualities=(),
        contacts=(),
        contact_points_budget=0,
        cyberware=(),
        # A valid default primary Lifestyle (WP20) -- most tests here aren't about lifestyle at
        # all, so this keeps `_blocking_reasons`'s new lifestyle check from firing incidentally;
        # tests that specifically exercise that check override this field.
        lifestyles=(
            LegacyLifestyle(base_lifestyle="Low", months=1, monthly_cost=2000, source="SR5"),
        ),
        tradition_name="",
        spells=(),
        powers=(),
        karma_remaining=0,
        build_karma=25,
        nuyen_remaining=0.0,
        starting_nuyen=6000,
        karma_converted_to_nuyen=0,
    )
    defaults.update(overrides)
    return LegacyCharacter(**defaults)  # type: ignore[arg-type]


def _import(legacy: LegacyCharacter) -> None:
    import_legacy_character(
        legacy,
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
        traditions=TRADITIONS,
        spells=SPELLS,
        powers=POWERS,
        cyberware=CYBERWARE,
        bioware=BIOWARE,
    )


def test_valid_mundane_priority_character_imports_without_error() -> None:
    _import(_legacy_character())  # no exception


def test_karma_converted_to_nuyen_threads_through_to_the_built_resources_selection() -> None:
    """WP43: `<nuyenbp>` (`LegacyCharacter.karma_converted_to_nuyen`) is not blocking -- no
    `_blocking_reasons` check exists for it (a Standard-gameplay-option character, already required
    by `_blocking_reasons`, can never legally exceed the same 10-Karma cap `karma_to_nuyen` enforces
    -- see module docstring) -- it simply carries through into the built character's own committed
    Resources selection, the same "thread it through" treatment every other raw field gets.
    """
    result = import_legacy_character(
        _legacy_character(karma_converted_to_nuyen=6),
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
        traditions=TRADITIONS,
        spells=SPELLS,
        powers=POWERS,
        cyberware=CYBERWARE,
    )
    assert result.save.karma_converted == 6
    assert result.built.resources_selection is not None
    assert result.built.resources_selection.karma_converted == 6


def test_imports_the_first_lifestyle_entry_as_primary() -> None:
    """WP20: the *first* `<lifestyle>` in document order is treated as primary (the legacy format
    has no explicit "is this primary" flag -- see legacy_import's own module docstring); a second,
    out-of-scope entry (mirroring `BLUE.chum5`'s real shape) must not block the import.
    """
    result = import_legacy_character(
        _legacy_character(
            lifestyles=(
                LegacyLifestyle(base_lifestyle="Medium", months=1, monthly_cost=5000, source="SR5"),
                LegacyLifestyle(
                    base_lifestyle="Bolt Hole", months=1, monthly_cost=1000, source="RF"
                ),
            )
        ),
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
    )
    assert result.built.lifestyle_selection is not None
    assert result.built.lifestyle_selection.tier.name == "Medium"
    assert result.built.lifestyle_selection.total_cost == 5000


def test_sumtoten_build_method_with_all_priority_letters_present_imports_successfully() -> None:
    """WP44: `SumtoTen` is no longer rejected on build-method grounds alone -- a character with a
    real letter recorded for every one of the 5 categories imports exactly like a Priority-built
    one would (this project never validated the letter *assignment*'s shape -- bijection vs.
    Sum-to-Ten's own rule -- on import to begin with; see `chummer5.io.legacy_import`'s own
    docstring).
    """
    _import(_legacy_character(build_method="SumtoTen"))  # no exception


def test_rejects_karma_build_method() -> None:
    """`Karma`/`LifeModule` stay unsupported -- the Project Overview's 2026-07-21 ruling explicitly
    keeps the whole-character Karma-pool build method out of scope, unlike Sum-to-Ten.
    """
    with pytest.raises(
        UnsupportedLegacyCharacterError, match="build method 'Karma' is not supported"
    ):
        _import(_legacy_character(build_method="Karma"))


def test_rejects_missing_priority_letter() -> None:
    """WP44: a blank/unresolvable `<priority*>` field (the real Mundane-Talent-`SumtoTen`
    save-format gap confirmed against 6 real curated fixtures -- see
    `spec/rulebooks/learnings.md`'s WP44 entry) is rejected outright rather than reaching
    `create_skill_allocation` and crashing with a `KeyError`.
    """
    blank_skills_priorities = PrioritySelections(
        heritage="D,1",
        attributes="A,1",
        talent="E,0",
        skills="",  # the real BLUE/Barrett/Blindfire/... shape -- see learnings.md's WP44 entry
        resources="B,1",
        talent_codename="Mundane",
        talent_bonus_skills=(),
    )
    with pytest.raises(
        UnsupportedLegacyCharacterError, match="no priority letter recorded for Skills"
    ):
        _import(_legacy_character(build_method="SumtoTen", priorities=blank_skills_priorities))


def test_rejects_non_standard_gameplay_option() -> None:
    with pytest.raises(UnsupportedLegacyCharacterError, match="not Standard"):
        _import(_legacy_character(game_option="Prime Runner"))


def test_rejects_unsupported_talent_codename() -> None:
    """WP28 replaces the old blanket "Magic is enabled" rejection -- a Talent codename outside this
    project's offered set (Mystic Adept/Technomancer/A.I./Aspected Magician/etc.) is still
    unbuildable, just with a precise reason now.
    """
    with pytest.raises(
        UnsupportedLegacyCharacterError, match="Talent option 'Mystic Adept' is not supported"
    ):
        _import(
            _legacy_character(
                magic_enabled=True,
                priorities=_priorities(talent="A,1", talent_codename="Mystic Adept"),
            )
        )


def test_rejects_magician_with_unresolvable_tradition() -> None:
    """A Magician's tradition must resolve to one of the 2 SR5-core traditions this phase offers
    (Hermetic/Shamanic) -- there is no sensible "import without a tradition" fallback the way there
    is for a dropped quality/skill/spell/power, so this blocks the whole import. Confirmed against
    this phase's own real fixture: Miko (Elf Magician)'s own tradition is Shinto (`SG`-sourced), so
    she hits exactly this reason -- see spec/worklogs/WP28.md.
    """
    with pytest.raises(
        UnsupportedLegacyCharacterError,
        match="tradition 'Shinto' is not one of the SR5-core traditions",
    ):
        _import(
            _legacy_character(
                magic_enabled=True,
                priorities=_priorities(talent="A,1", talent_codename="Magician"),
                tradition_name="Shinto",
            )
        )


def test_accepts_magician_with_an_offered_tradition() -> None:
    """The positive case the two rejection tests above exist to contrast with -- a Magician whose
    tradition really is one of the 2 offered ones (Hermetic) must import cleanly. Letter C's
    Magician option grants no free skill (`skill_qty is None`), so this test doesn't also have to
    supply one -- see `test_talent_free_skill_grant_resolves_by_name_and_reaches_the_built_
    character` below for that path specifically.
    """
    result = import_legacy_character(
        _legacy_character(
            magic_enabled=True,
            priorities=_priorities(talent="C,1", talent_codename="Magician"),
            tradition_name="Hermetic",
        ),
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
        traditions=TRADITIONS,
        spells=SPELLS,
        powers=POWERS,
    )
    assert result.built.magic_type == "Magician"
    assert result.built.tradition is not None
    assert result.built.tradition.name == "Hermetic"
    magician_option = next(o for o in PRIORITIES.talent["C"].options if o.codename == "Magician")
    assert result.built.magic_rating == magician_option.magic


def test_accepts_adept_with_no_tradition_needed() -> None:
    """Unlike a Magician, an Adept doesn't pick a tradition at all -- `tradition_name` is simply
    never consulted for this codename (see `_blocking_reasons`). Letter D's Adept option grants no
    free skill either (`skill_qty is None`), keeping this test focused on the tradition question
    alone.
    """
    result = import_legacy_character(
        _legacy_character(
            magic_enabled=True,
            priorities=_priorities(talent="D,1", talent_codename="Adept"),
        ),
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
        traditions=TRADITIONS,
        spells=SPELLS,
        powers=POWERS,
    )
    assert result.built.magic_type == "Adept"
    assert result.built.tradition is None


def test_rejects_unsupported_cyberware_item() -> None:
    """WP33 replaces the old blanket "character has cyberware/bioware" rejection with a real,
    itemized check per real purchase -- a rating-scaled item (Wired Reflexes' real Essence cost is
    `FixedValues(2,3,5)`, not a bare literal, so it isn't in WP31's flat catalog at all) is rejected
    by name, not with a generic message.
    """
    with pytest.raises(UnsupportedLegacyCharacterError, match=r"'Wired Reflexes'.*rating-scaled"):
        _import(
            _legacy_character(
                cyberware=(
                    LegacyCyberware(
                        name="Wired Reflexes",
                        category="Bodyware",
                        grade="Standard",
                        source="SR5",
                        improvement_source="Cyberware",
                        cost="FixedValues(39000,149000,217000)",
                        essence="FixedValues(2,3,5)",
                    ),
                )
            )
        )


def test_rejects_non_standard_grade_cyberware() -> None:
    """A real WP31 catalog item (Datajack) bought at a non-Standard grade is still rejected --
    confirmed via real fixture data (`spec/worklogs/WP32.md`) that the legacy save format stores a
    Standard-grade item's raw `<ess>`/`<cost>` fields unchanged regardless of the grade actually
    purchased, so silently accepting a non-Standard grade here would misrepresent the character's
    real Essence/nuyen cost, not just approximate it.
    """
    with pytest.raises(UnsupportedLegacyCharacterError, match=r"'Datajack'.*non-Standard-grade"):
        _import(
            _legacy_character(
                cyberware=(
                    LegacyCyberware(
                        name="Datajack",
                        category="Headware",
                        grade="Alphaware",
                        source="SR5",
                        improvement_source="Cyberware",
                        cost="1000",
                        essence="0.1",
                    ),
                )
            )
        )


def test_rejects_unsupported_bioware_item() -> None:
    """WP45 resolves a Bioware entry the identical way a Cyberware entry already was, against
    `chummer5.data.bioware.load_bioware`'s own flat catalog -- a rating-scaled item (Mnemonic
    Enhancer's real cost is `Rating * 9000`, not a bare literal) is rejected by name, not with a
    generic "is Bioware" message.
    """
    with pytest.raises(
        UnsupportedLegacyCharacterError, match=r"'Mnemonic Enhancer'.*rating-scaled"
    ):
        _import(
            _legacy_character(
                cyberware=(
                    LegacyCyberware(
                        name="Mnemonic Enhancer",
                        category="Cultured",
                        grade="Standard",
                        source="SR5",
                        improvement_source="Bioware",
                        cost="Rating * 9000",
                        essence="Rating * 0.1",
                    ),
                )
            )
        )


def test_rejects_non_standard_grade_bioware() -> None:
    """A real WP45 catalog item (Platelet Factories) bought at a non-Standard grade is still
    rejected -- confirmed via real fixture data (`Bastion.chum5`, see `spec/worklogs/WP45.md`) that
    the legacy save format stores a Standard-grade item's raw `<ess>`/`<cost>` fields unchanged
    regardless of the grade actually purchased, mirroring cyberware's own WP32-era finding.
    """
    with pytest.raises(
        UnsupportedLegacyCharacterError, match=r"'Platelet Factories'.*non-Standard-grade"
    ):
        _import(
            _legacy_character(
                cyberware=(
                    LegacyCyberware(
                        name="Platelet Factories",
                        category="Basic",
                        grade="Used",
                        source="SR5",
                        improvement_source="Bioware",
                        cost="17000",
                        essence="0.2",
                    ),
                )
            )
        )


def test_accepts_standard_grade_flat_cyberware_item() -> None:
    """The positive case the rejection tests above exist to contrast with -- a real catalog
    item bought at Standard grade (mirroring Bastion.chum5's/Blindfire.chum5's own real Datajack
    purchases) imports cleanly and reaches the built character's `cyberware_selection`.
    """
    datajack = next(c for c in CYBERWARE if c.name == "Datajack")
    result = import_legacy_character(
        _legacy_character(
            cyberware=(
                LegacyCyberware(
                    name="Datajack",
                    category="Headware",
                    grade="Standard",
                    source="SR5",
                    improvement_source="Cyberware",
                    cost="1000",
                    essence="0.1",
                ),
            )
        ),
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
        cyberware=CYBERWARE,
    )
    assert result.save.cyberware_item_ids == (datajack.id,)
    assert result.built.cyberware_selection is not None
    assert datajack.id in {c.id for c in result.built.cyberware_selection.items}


def test_accepts_standard_grade_flat_bioware_item() -> None:
    """The bioware mirror of the cyberware test above -- a real WP45 catalog item (Reflex Recorder,
    mirroring `Barrett.chum5`'s own real purchase) bought at Standard grade imports cleanly and
    reaches the built character's `bioware_selection`.
    """
    reflex_recorder = next(b for b in BIOWARE if b.name == "Reflex Recorder")
    result = import_legacy_character(
        _legacy_character(
            cyberware=(
                LegacyCyberware(
                    name="Reflex Recorder",
                    category="Cultured",
                    grade="Standard",
                    source="SR5",
                    improvement_source="Bioware",
                    cost="14000",
                    essence="0.1",
                ),
            )
        ),
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
        bioware=BIOWARE,
    )
    assert result.save.bioware_item_ids == (reflex_recorder.id,)
    assert result.built.bioware_selection is not None
    assert reflex_recorder.id in {b.id for b in result.built.bioware_selection.items}


def test_rejects_karma_bought_attribute_points() -> None:
    """WP28: a real, previously-latent gap surfaced while researching Wesson's own fixture -- MVP's
    `create_character` only validates priority-derived attribute points against the priority
    budget, with no accommodation for a real, standard SR5 rule (spending Karma to buy extra
    attribute points at chargen, beyond the priority budget). `import_legacy_character`'s
    pre-existing `attribute_points` formula silently combined both sources before this WP; this
    test proves the new guard fires instead, mirroring cyberware/metavariant's treatment.
    """
    with pytest.raises(UnsupportedLegacyCharacterError, match="Karma-bought attribute points"):
        _import(
            _legacy_character(
                attributes=MappingProxyType(
                    {
                        "EDG": LegacyAttribute(
                            name="EDG",
                            metatype_min=2,
                            metatype_max=7,
                            metatype_aug_max=7,
                            base=1,
                            karma=1,
                            total_value=4,
                        )
                    }
                )
            )
        )


def test_rejects_karma_bought_mag_points() -> None:
    """Post-WP29 correction: MAG shares the same "no chargen-time Karma spend modeled" constraint
    as every other allocatable attribute once it's actually allocatable at all (`magic_enabled`).
    """
    with pytest.raises(UnsupportedLegacyCharacterError, match="Karma-bought attribute points"):
        _import(
            _legacy_character(
                magic_enabled=True,
                priorities=_priorities(talent="D,1", talent_codename="Adept"),
                attributes=MappingProxyType(
                    {
                        "MAG": LegacyAttribute(
                            name="MAG",
                            metatype_min=1,
                            metatype_max=6,
                            metatype_aug_max=6,
                            base=1,
                            karma=1,
                            total_value=4,
                        )
                    }
                ),
            )
        )


def test_does_not_reject_karma_on_mag_when_magic_is_not_enabled() -> None:
    """The MAG-specific karma check only fires when `legacy.magic_enabled` -- a Mundane character's
    raw `<attribute name="MAG">` (Resonance/Technomancer content sometimes carries a nonzero one,
    per WP28's own Yeti finding) must not spuriously block an otherwise-clean Mundane import.
    """
    _import(
        _legacy_character(
            attributes=MappingProxyType(
                {
                    "MAG": LegacyAttribute(
                        name="MAG",
                        metatype_min=1,
                        metatype_max=6,
                        metatype_aug_max=6,
                        base=0,
                        karma=1,
                        total_value=1,
                    )
                }
            ),
        )
    )  # no exception


def test_magic_attribute_points_resolves_from_legacys_mag_base() -> None:
    """Post-WP29 correction: `legacy.attributes["MAG"].base` -- the same field `attribute_points`
    already reads for EDG -- is the Special Attribute Points spent raising MAG beyond the
    Talent-granted starting rating. Letter D's Adept option grants Magic 2 (headroom to 6); Human's
    default Heritage-D special-attribute-points budget (3, hand-checked against `priorities.xml`)
    comfortably covers the 2 points spent here with none left over for EDG.
    """
    result = import_legacy_character(
        _legacy_character(
            magic_enabled=True,
            priorities=_priorities(talent="D,1", talent_codename="Adept"),
            attributes=MappingProxyType(
                {
                    "MAG": LegacyAttribute(
                        name="MAG",
                        metatype_min=1,
                        metatype_max=6,
                        metatype_aug_max=6,
                        base=2,
                        karma=0,
                        total_value=4,
                    )
                }
            ),
        ),
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
        traditions=TRADITIONS,
        spells=SPELLS,
        powers=POWERS,
    )
    assert result.built.magic_attribute_points == 2
    assert result.built.attribute_value("MAG") == 4
    assert result.built.power_points == 4


def test_rejects_metavariant() -> None:
    with pytest.raises(UnsupportedLegacyCharacterError, match="metavariant"):
        _import(_legacy_character(metavariant="Oni"))


def test_rejects_no_lifestyle() -> None:
    """WP20: SR5 requires selecting a primary Lifestyle; a legacy save with none is blocking, not
    silently defaulted to e.g. the free "Street" tier -- that would misrepresent a real choice.
    """
    with pytest.raises(UnsupportedLegacyCharacterError, match="no primary Lifestyle found"):
        _import(_legacy_character(lifestyles=()))


def test_rejects_out_of_scope_primary_lifestyle() -> None:
    """A primary Lifestyle outside the 6 core-rulebook starting tiers (e.g. an RF-sourced "Bolt
    Hole") is blocking for the same reason a metavariant is -- MVP's catalog can't represent it.
    """
    with pytest.raises(UnsupportedLegacyCharacterError, match="not one of the 6"):
        _import(
            _legacy_character(
                lifestyles=(
                    LegacyLifestyle(
                        base_lifestyle="Bolt Hole", months=1, monthly_cost=1000, source="RF"
                    ),
                )
            )
        )


def test_does_not_reject_resonance_enabled() -> None:
    """Resonance/Technomancer content is deliberately not blocking -- see module docstring for why
    (Yeti-#ffffff2.chum5, this project's own Priority-build golden fixture, is itself a
    Technomancer).
    """
    _import(_legacy_character(resonance_enabled=True))  # no exception


def test_itemizes_every_blocking_reason_in_one_pass() -> None:
    # `Karma` (not `SumtoTen`, which WP44 accepts) keeps this a genuine 3-reason case: build
    # method, Talent codename, and cyberware each independently blocking.
    legacy = _legacy_character(
        build_method="Karma",
        magic_enabled=True,
        priorities=_priorities(talent="A,1", talent_codename="Mystic Adept"),
        cyberware=(
            LegacyCyberware(
                name="Wired Reflexes",
                category="Bodyware",
                grade="Standard",
                source="SR5",
                improvement_source="Cyberware",
                cost="FixedValues(39000,149000,217000)",
                essence="FixedValues(2,3,5)",
            ),
        ),
    )
    with pytest.raises(UnsupportedLegacyCharacterError) as exc_info:
        _import(legacy)
    assert len(exc_info.value.reasons) == 3
    assert any("build method 'Karma' is not supported" in r for r in exc_info.value.reasons)
    assert any("Talent option 'Mystic Adept' is not supported" in r for r in exc_info.value.reasons)
    assert any("Wired Reflexes" in r for r in exc_info.value.reasons)


def test_unsupported_quality_is_dropped_and_reported_not_fatal() -> None:
    unsupported = next(q for q in QUALITIES if q.bonus_support == BonusSupport.NOT_YET_SUPPORTED)
    legacy_quality = LegacyQuality(
        id=unsupported.id,
        name=unsupported.name,
        extra="",
        karma=unsupported.karma,
        quality_type=unsupported.category,
        source=unsupported.source,
        quality_source="Selected",
    )
    result = import_legacy_character(
        _legacy_character(qualities=(legacy_quality,)),
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
    )
    assert result.dropped_qualities == (unsupported.name,)
    assert result.save.quality_ids == ()


def test_mvp_offered_quality_is_imported() -> None:
    catlike = next(q for q in QUALITIES if q.name == "Catlike")
    legacy_quality = LegacyQuality(
        id=catlike.id,
        name=catlike.name,
        extra="",
        karma=catlike.karma,
        quality_type=catlike.category,
        source=catlike.source,
        quality_source="Selected",
    )
    result = import_legacy_character(
        _legacy_character(qualities=(legacy_quality,)),
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
    )
    assert result.dropped_qualities == ()
    assert result.save.quality_ids == (catlike.id,)
    assert catlike.id in {q.id for q in result.built.quality_selection.qualities}


def test_metatype_granted_quality_is_neither_imported_nor_dropped() -> None:
    """WP23: an Elf's Low-Light Vision, present in the legacy save with `qualitysource=Metatype`,
    must not be treated as a player pick (double-counted as a karma spend now that WP22 made it
    MVP-offered) nor reported as dropped (nothing is actually lost -- `build_character` re-derives
    and re-grants it from the imported metatype itself).
    """
    low_light = next(q for q in QUALITIES if q.name == "Low-Light Vision")
    legacy_quality = LegacyQuality(
        id=low_light.id,
        name=low_light.name,
        extra="",
        karma=low_light.karma,
        quality_type=low_light.category,
        source=low_light.source,
        quality_source="Metatype",
    )
    result = import_legacy_character(
        _legacy_character(metatype="Elf", qualities=(legacy_quality,)),
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
    )
    assert result.dropped_qualities == ()
    assert result.save.quality_ids == ()
    assert "Low-Light Vision" in {q.name for q in result.built.metatype_qualities}
    # Not double-counted as a player pick either.
    assert result.built.quality_selection is not None
    assert "Low-Light Vision" not in {q.name for q in result.built.quality_selection.qualities}


def test_metatype_sourced_quality_not_matching_real_racial_list_still_dropped() -> None:
    """WP23's exclusion is name-gated against the *current* metatype's real racial-quality list,
    not a blanket `qualitysource == "Metatype"` skip -- confirmed directly against real data during
    this WP's research (`Yeti-#ffffff2.chum5`'s own Technomancer quality is
    `qualitysource=Metatype` despite Yeti being Human). A Human character with a
    `qualitysource=Metatype` quality that isn't actually one of Human's (empty) racial list must
    still flow through the normal offered/dropped check, not silently vanish.
    """
    unsupported = next(q for q in QUALITIES if q.bonus_support == BonusSupport.NOT_YET_SUPPORTED)
    legacy_quality = LegacyQuality(
        id=unsupported.id,
        name=unsupported.name,
        extra="",
        karma=unsupported.karma,
        quality_type=unsupported.category,
        source=unsupported.source,
        quality_source="Metatype",
    )
    result = import_legacy_character(
        _legacy_character(metatype="Human", qualities=(legacy_quality,)),
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
    )
    assert result.dropped_qualities == (unsupported.name,)


def test_unresolvable_skill_suid_is_dropped_and_reported_not_fatal() -> None:
    legacy_skill = LegacySkill(
        suid="not-a-real-suid",
        category="Combat Active",
        base=3,
        karma=0,
        bought_with_karma=False,
        specializations=(),
    )
    result = import_legacy_character(
        _legacy_character(skills=(legacy_skill,)),
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
    )
    assert result.dropped_skills == ("not-a-real-suid",)
    assert result.save.skill_points == {}


def test_talent_free_skill_grant_resolves_by_name_and_reaches_the_built_character() -> None:
    """`legacy.priorities.talent_bonus_skills` is a tuple of skill *names* -- this WP resolves each
    against `chummer5.data.skills.load_skills()` by name and passes the resulting ids through to
    `create_magic_selection`, the same free-skill-grant mechanism WP25 built.
    """
    result = import_legacy_character(
        _legacy_character(
            magic_enabled=True,
            priorities=_priorities(
                talent="A,1",
                talent_codename="Magician",
                talent_bonus_skills=("Spellcasting", "Counterspelling"),
            ),
            tradition_name="Hermetic",
        ),
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
        traditions=TRADITIONS,
        spells=SPELLS,
        powers=POWERS,
    )
    assert set(result.save.granted_skill_ids) == {
        next(s.id for s in SKILLS if s.name == "Spellcasting"),
        next(s.id for s in SKILLS if s.name == "Counterspelling"),
    }
    assert result.built.magic_granted_skill_ids == result.save.granted_skill_ids


def test_non_sr5_spell_is_dropped_and_reported_not_fatal() -> None:
    """Mirrors the quality/skill precedent exactly -- a spell that isn't `source == "SR5"` (this
    project's spell catalog scope, WP26) is excluded from the imported `CharacterSave` and reported
    via `ImportResult.dropped_spells`, not silently lost with no trace.
    """
    sr5_spell = next(s for s in SPELLS if s.name == "Manabolt")
    result = import_legacy_character(
        _legacy_character(
            magic_enabled=True,
            # Letter C's Magician option grants no free skill (skill_qty is None), keeping this
            # test focused on the spell question alone.
            priorities=_priorities(talent="C,1", talent_codename="Magician"),
            tradition_name="Hermetic",
            spells=(
                LegacySpell(name=sr5_spell.name, source="SR5"),
                LegacySpell(name="Calm Animal", source="SG"),
            ),
        ),
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
        traditions=TRADITIONS,
        spells=SPELLS,
        powers=POWERS,
    )
    assert result.dropped_spells == ("Calm Animal",)
    assert result.save.spell_ids == (sr5_spell.id,)
    assert sr5_spell.id in {s.id for s in result.built.spell_selection.spells}


def test_not_yet_supported_power_is_dropped_and_reported_not_fatal() -> None:
    """Mirrors the quality/skill/spell precedent -- a power that isn't in `mvp_power_catalog`
    (non-SR5-sourced, or SR5 but `NOT_YET_SUPPORTED`, per WP27) is excluded and reported via
    `ImportResult.dropped_powers`, never half-applied.
    """
    result = import_legacy_character(
        _legacy_character(
            magic_enabled=True,
            priorities=_priorities(talent="D,1", talent_codename="Adept"),
            powers=(
                LegacyPower(name="Attribute Boost", rating=1, levels=True, extra=""),
                LegacyPower(name="Not A Real Power", rating=1, levels=False, extra=""),
            ),
        ),
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
        traditions=TRADITIONS,
        spells=SPELLS,
        powers=POWERS,
    )
    assert set(result.dropped_powers) == {"Attribute Boost", "Not A Real Power"}
    assert result.save.power_picks == ()
    assert result.built.power_selection is not None
    assert result.built.power_selection.picks == ()


def test_flat_bonus_power_is_imported_with_its_rating() -> None:
    ipa = next(p for p in POWERS if p.name == "Improved Physical Attribute")
    result = import_legacy_character(
        _legacy_character(
            magic_enabled=True,
            priorities=_priorities(talent="D,1", talent_codename="Adept"),
            powers=(LegacyPower(name=ipa.name, rating=2, levels=True, extra="BOD"),),
        ),
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
        traditions=TRADITIONS,
        spells=SPELLS,
        powers=POWERS,
    )
    assert result.dropped_powers == ()
    assert result.save.power_picks == ((ipa.id, 2, "BOD"),)
    (pick,) = result.built.power_selection.picks
    assert pick.rating == 2
    assert pick.selected_attribute == "BOD"
