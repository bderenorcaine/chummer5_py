from chummer5.data.traditions import DEFAULT_TRADITIONS_PATH, load_traditions


def test_offers_exactly_hermetic_and_shamanic() -> None:
    # Hand-checked against traditions.xml: 3 source == "SR5" entries (Custom, Hermetic, Shamanic),
    # Custom excluded -- see module docstring.
    traditions = load_traditions()
    assert {t.name for t in traditions} == {"Hermetic", "Shamanic"}


def test_hermetic_drain_attributes() -> None:
    traditions = load_traditions()
    hermetic = next(t for t in traditions if t.name == "Hermetic")
    assert hermetic.drain_attributes == ("WIL", "LOG")
    assert hermetic.source == "SR5"
    assert hermetic.page == 279


def test_shamanic_drain_attributes() -> None:
    traditions = load_traditions()
    shamanic = next(t for t in traditions if t.name == "Shamanic")
    assert shamanic.drain_attributes == ("WIL", "CHA")


# -- WP46: <spirits> block -----------------------------------------------------------------------


def test_hermetic_spirit_affinities() -> None:
    # Hand-checked against traditions.xml's Hermetic entry.
    traditions = load_traditions()
    hermetic = next(t for t in traditions if t.name == "Hermetic")
    assert hermetic.spirits.combat == "Spirit of Fire"
    assert hermetic.spirits.detection == "Spirit of Air"
    assert hermetic.spirits.health == "Spirit of Man"
    assert hermetic.spirits.illusion == "Spirit of Water"
    assert hermetic.spirits.manipulation == "Spirit of Earth"
    assert hermetic.spirits.offered_types == (
        "Spirit of Fire",
        "Spirit of Air",
        "Spirit of Man",
        "Spirit of Water",
        "Spirit of Earth",
    )


def test_shamanic_spirit_affinities() -> None:
    # Hand-checked against traditions.xml's Shamanic entry.
    traditions = load_traditions()
    shamanic = next(t for t in traditions if t.name == "Shamanic")
    assert shamanic.spirits.combat == "Spirit of Beasts"
    assert shamanic.spirits.detection == "Spirit of Water"
    assert shamanic.spirits.health == "Spirit of Earth"
    assert shamanic.spirits.illusion == "Spirit of Air"
    assert shamanic.spirits.manipulation == "Spirit of Man"
    assert shamanic.spirits.offered_types == (
        "Spirit of Beasts",
        "Spirit of Water",
        "Spirit of Earth",
        "Spirit of Air",
        "Spirit of Man",
    )


def test_hermetic_and_shamanic_each_omit_a_different_core_spirit_type() -> None:
    # Confirmed against the Magic chapter's own "Spirits" section (p. 303): 6 core types exist
    # (Air/Beasts/Earth/Fire/Man/Water), but each tradition's <spirits> block only ever names 5 --
    # Hermetic never offers Beasts, Shamanic never offers Fire. See spec/rulebooks/learnings.md.
    traditions = load_traditions()
    hermetic = next(t for t in traditions if t.name == "Hermetic")
    shamanic = next(t for t in traditions if t.name == "Shamanic")
    assert "Spirit of Beasts" not in hermetic.spirits.offered_types
    assert "Spirit of Fire" not in shamanic.spirits.offered_types


def test_default_path_points_at_real_legacy_file() -> None:
    assert DEFAULT_TRADITIONS_PATH.name == "traditions.xml"
    assert DEFAULT_TRADITIONS_PATH.is_file()
