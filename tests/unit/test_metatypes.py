from chummer5.data.metatypes import DEFAULT_METATYPES_PATH, AttributeRange, load_metatypes


def test_loads_all_metatypes() -> None:
    metatypes = load_metatypes()
    # legacy/Chummer/data/metatypes.xml has 21 top-level <metatype> entries.
    assert len(metatypes) == 21


def test_human_attribute_ranges() -> None:
    # Hand-checked against legacy/Chummer/data/metatypes.xml <metatype><name>Human</name>.
    metatypes = load_metatypes()
    human = next(m for m in metatypes if m.name == "Human")
    assert human.category == "Metahuman"
    assert human.karma == 0
    assert human.id == "a53d885d-a4a4-443d-b6a6-b0a55b0a96c7"
    assert human.attributes["BOD"].minimum == 1
    assert human.attributes["BOD"].maximum == 6
    assert human.attributes["BOD"].augmented == 10
    assert human.attributes["EDG"].minimum == 2
    assert human.attributes["EDG"].maximum == 7
    assert human.attributes["EDG"].augmented == 7
    assert human.attributes["ESS"].minimum == 0
    assert human.attributes["ESS"].maximum == 6


def test_troll_has_higher_body_and_strength_than_human() -> None:
    metatypes = load_metatypes()
    human = next(m for m in metatypes if m.name == "Human")
    troll = next(m for m in metatypes if m.name == "Troll")
    assert troll.attributes["BOD"] == AttributeRange(minimum=5, maximum=10, augmented=14)
    assert troll.attributes["STR"].minimum == 5
    assert troll.attributes["STR"].maximum == 10
    assert human.attributes["STR"].minimum == 1
    assert human.attributes["STR"].maximum == 6


def test_human_metavariant_nartaki() -> None:
    metatypes = load_metatypes()
    human = next(m for m in metatypes if m.name == "Human")
    assert len(human.metavariants) == 1
    nartaki = human.metavariants[0]
    assert nartaki.name == "Nartaki"
    assert nartaki.karma == 40
    assert nartaki.qualities_positive == ("Shiva Arms (Pair)",)
    assert nartaki.qualities_negative == ("Striking Skin Pigmentation",)
    # Nartaki's attribute ranges are unchanged from base Human in the source data.
    assert nartaki.attributes["BOD"] == human.attributes["BOD"]


def test_dwarf_metavariant_karma_costs() -> None:
    metatypes = load_metatypes()
    dwarf = next(m for m in metatypes if m.name == "Dwarf")
    karma_by_name = {mv.name: mv.karma for mv in dwarf.metavariants}
    assert karma_by_name == {
        "Gnome": 50,
        "Hanuman": 100,
        "Koborokuru": 70,
        "Menehune": 50,
    }


def test_default_path_points_at_real_legacy_file() -> None:
    assert DEFAULT_METATYPES_PATH.name == "metatypes.xml"
    assert DEFAULT_METATYPES_PATH.is_file()
