from chummer5.data.skills import DEFAULT_SKILLS_PATH, load_skills


def test_loads_all_active_skills() -> None:
    # legacy/Chummer/data/skills.xml has 76 <skill> entries under <skills>, all source == "SR5".
    skills = load_skills()
    assert len(skills) == 76
    assert all(s.source == "SR5" for s in skills)


def test_pistols_attribute_and_group() -> None:
    # Hand-checked against skills.xml's <skill><name>Pistols</name>.
    skills = load_skills()
    pistols = next(s for s in skills if s.name == "Pistols")
    assert pistols.attribute == "AGI"
    assert pistols.category == "Combat Active"
    assert pistols.skill_group == "Firearms"
    assert pistols.can_default is True


def test_skill_without_a_group_is_none() -> None:
    # Animal Handling has an empty <skillgroup/> element in the source data.
    skills = load_skills()
    animal_handling = next(s for s in skills if s.name == "Animal Handling")
    assert animal_handling.skill_group is None


def test_spellcasting_cannot_default() -> None:
    skills = load_skills()
    spellcasting = next(s for s in skills if s.name == "Spellcasting")
    assert spellcasting.can_default is False
    assert spellcasting.attribute == "MAG"
    assert spellcasting.skill_group == "Sorcery"


def test_exotic_skill_flagged() -> None:
    skills = load_skills()
    exotic_melee = next(s for s in skills if s.name == "Exotic Melee Weapon")
    assert exotic_melee.exotic is True
    pistols = next(s for s in skills if s.name == "Pistols")
    assert pistols.exotic is False


def test_specializations_parsed() -> None:
    skills = load_skills()
    pistols = next(s for s in skills if s.name == "Pistols")
    assert pistols.specializations == ("Holdouts", "Revolvers", "Semi-Automatics", "Tasers")


def test_default_path_points_at_real_legacy_file() -> None:
    assert DEFAULT_SKILLS_PATH.name == "skills.xml"
    assert DEFAULT_SKILLS_PATH.is_file()
