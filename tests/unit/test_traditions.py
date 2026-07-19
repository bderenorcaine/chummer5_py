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


def test_default_path_points_at_real_legacy_file() -> None:
    assert DEFAULT_TRADITIONS_PATH.name == "traditions.xml"
    assert DEFAULT_TRADITIONS_PATH.is_file()
