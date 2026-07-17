"""Synthetic tests for `chummer5.io.save_format`'s JSON (de)serialization, proving the wire format
round-trips exactly before any real fixture data touches it -- same "prove the mechanism in
isolation first" pattern WP5 used for the Improvement engine and WP7 used for the dice-pool
formula. The engine-reconstruction half (`build_character`) is covered against a real fixture in
`tests/integration/test_save_format.py`, mirroring the unit/integration split every prior WP used.
"""

from __future__ import annotations

import json

import pytest

from chummer5.engine.resources import Contact
from chummer5.io.save_format import (
    FORMAT_VERSION,
    CharacterSave,
    create_character_save,
    from_json,
    to_json,
)


def _sample_save() -> CharacterSave:
    return create_character_save(
        metatype_name="Human",
        heritage_letter="D",
        attributes_letter="A",
        attribute_points={"BOD": 3, "AGI": 2, "EDG": 1},
        skills_letter="C",
        skill_points={"skill-hacking": 2},
        group_points={"Firearms": 4},
        quality_ids=("qual-catlike",),
        contacts=(
            Contact(name="Fixer", connection=3, loyalty=3),
            Contact(name="GM Plot", connection=1, loyalty=1, free=True),
        ),
        resources_letter="B",
        gear_names=("Meta Link", "Combat Knife"),
    )


def test_json_round_trip_preserves_every_field() -> None:
    save = _sample_save()
    assert from_json(to_json(save)) == save


def test_json_round_trip_empty_selections() -> None:
    save = create_character_save(
        metatype_name="Elf",
        heritage_letter="A",
        attributes_letter="D",
        attribute_points={},
        skills_letter="E",
        skill_points={},
        group_points={},
        quality_ids=(),
        contacts=(),
        resources_letter="C",
        gear_names=(),
    )
    assert from_json(to_json(save)) == save


def test_to_json_produces_the_documented_wire_shape() -> None:
    """Spot-checks the actual JSON text, not just round-trip self-consistency -- a round trip alone
    wouldn't catch e.g. an accidentally-renamed key, since `from_json` would just fail loudly on
    that (still fine), but this pins the documented shape in a way a future reader can see without
    executing anything.
    """
    save = _sample_save()
    data = json.loads(to_json(save))
    assert data["format_version"] == FORMAT_VERSION
    assert data["metatype_name"] == "Human"
    assert data["attribute_points"] == {"BOD": 3, "AGI": 2, "EDG": 1}
    assert data["contacts"] == [
        {"name": "Fixer", "connection": 3, "loyalty": 3, "free": False},
        {"name": "GM Plot", "connection": 1, "loyalty": 1, "free": True},
    ]
    assert data["gear_names"] == ["Meta Link", "Combat Knife"]


def test_from_json_rejects_unknown_format_version() -> None:
    data = json.loads(to_json(_sample_save()))
    data["format_version"] = 99
    with pytest.raises(ValueError, match="unsupported save format version"):
        from_json(json.dumps(data))


def test_from_json_rejects_missing_format_version() -> None:
    data = json.loads(to_json(_sample_save()))
    del data["format_version"]
    with pytest.raises(ValueError, match="unsupported save format version"):
        from_json(json.dumps(data))
