from chummer5.data.priorities import DEFAULT_PRIORITIES_PATH, load_priorities


def test_heritage_letters_present() -> None:
    priorities = load_priorities()
    assert set(priorities.heritage) == {"A", "B", "C", "D", "E"}


def test_heritage_priority_a_human_and_troll() -> None:
    # Hand-checked against legacy/Chummer/data/priorities.xml, <priority><category>Heritage
    # </category><value>A</value> — "A - Any metatype".
    priorities = load_priorities()
    priority_a = priorities.heritage["A"]
    assert priority_a.name == "A - Any metatype"

    metatypes_by_name = {mt.name: mt for mt in priority_a.metatypes}
    human = metatypes_by_name["Human"]
    assert human.special_attribute_points == 9
    assert human.karma == 0

    troll = metatypes_by_name["Troll"]
    assert troll.special_attribute_points == 5
    assert troll.karma == 0


def test_heritage_priority_e_only_offers_human() -> None:
    # "E - Human" is the most restrictive Heritage letter.
    priorities = load_priorities()
    priority_e = priorities.heritage["E"]
    assert priority_e.name == "E - Human"
    assert [mt.name for mt in priority_e.metatypes] == ["Human"]
    assert priority_e.metatypes[0].special_attribute_points == 1


def test_heritage_metavariant_karma() -> None:
    priorities = load_priorities()
    priority_a = priorities.heritage["A"]
    human = next(mt for mt in priority_a.metatypes if mt.name == "Human")
    nartaki = next(mv for mv in human.metavariants if mv.name == "Nartaki")
    assert nartaki.special_attribute_points == 8
    assert nartaki.karma == 0


def test_attributes_priority_points() -> None:
    # "A - 24 (12) Attributes" through "E - 12 (6) Attributes".
    priorities = load_priorities()
    assert priorities.attributes["A"].points == 24
    assert priorities.attributes["E"].points == 12


def test_skills_priority_counts() -> None:
    # "A - 46 Skills/10 Skill Groups" through "E - 18 Skills/0 Skill Groups".
    priorities = load_priorities()
    assert priorities.skills["A"].skills == 46
    assert priorities.skills["A"].skill_groups == 10
    assert priorities.skills["E"].skills == 18
    assert priorities.skills["E"].skill_groups == 0


def test_resources_priority_is_standard_table_only() -> None:
    # Standard table: A=450000 ... E=6000. Prime Runner/Street Level values must not leak in.
    priorities = load_priorities()
    assert priorities.resources["A"].nuyen == 450_000
    assert priorities.resources["B"].nuyen == 275_000
    assert priorities.resources["C"].nuyen == 140_000
    assert priorities.resources["D"].nuyen == 50_000
    assert priorities.resources["E"].nuyen == 6_000
    assert len(priorities.resources) == 5


def test_mundane_talent() -> None:
    priorities = load_priorities()
    mundane = priorities.mundane_talent()
    assert mundane.name == "Mundane"
    assert mundane.magic is None
    assert mundane.resonance is None
    assert mundane.skill_qty is None


def test_talent_letters_present_but_only_e_is_mvp_consumed() -> None:
    priorities = load_priorities()
    assert set(priorities.talent) == {"A", "B", "C", "D", "E"}
    magician_options = {opt.codename for opt in priorities.talent["A"].options}
    assert "Magician" in magician_options


def test_default_path_points_at_real_legacy_file() -> None:
    assert DEFAULT_PRIORITIES_PATH.name == "priorities.xml"
    assert DEFAULT_PRIORITIES_PATH.is_file()
