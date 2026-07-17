"""Cross-checks `chummer5.engine.character` against the WP4 legacy `.chum5` golden corpus.

Two different kinds of assertion, per the Implementation Plan's corpus note and
`tests/fixtures/README.md`:
- `Yeti-#ffffff2.chum5` (the corpus's only `buildmethod == Priority` fixture) validates the full
  priority-allocation path: `metatype_choices()` + `create_character()`'s budget checks, using
  Yeti's own recorded priority letters.
- The rest of the mundane corpus (`SumtoTen`-built) validates only `Character.attribute_value()`'s
  formula, build-method-agnostically, by constructing a `Character` directly from each fixture's
  recorded `base + karma` points -- bypassing `create_character()`'s budget validation, which is
  priority-build-specific and wouldn't mean anything against a SumToTen spend. See
  `spec/worklogs/WP6.md` for why `<totalvalue>` can't be used for every attribute of every
  fixture: it's the *augmented* value (includes cyberware/gear), and MVP doesn't model those, so
  only attributes with no such equipment are asserted per fixture.
"""

from __future__ import annotations

from types import MappingProxyType

from tests.fixtures.mundane_chum5 import (
    MUNDANE_FIXTURES,
    PRIORITY_BUILD_FIXTURE,
    mundane_fixture_path,
)

from chummer5.data.metatypes import Metatype, load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import (
    ALLOCATABLE_ATTRIBUTES,
    Character,
    create_character,
    metatype_choices,
    sr5_metatypes,
)
from chummer5.engine.improvements import ImprovementIndex
from chummer5.io.legacy_chum5 import load_chum5, priority_letter

METATYPES = load_metatypes()
PRIORITIES = load_priorities()


def test_yeti_priority_build_matches_engine_end_to_end() -> None:
    legacy = load_chum5(mundane_fixture_path(PRIORITY_BUILD_FIXTURE))
    assert legacy.build_method == "Priority"
    assert legacy.metatype == "Human"
    assert legacy.metavariant is None

    heritage_letter = priority_letter(legacy.priorities.heritage)
    attributes_letter = priority_letter(legacy.priorities.attributes)
    assert (heritage_letter, attributes_letter) == ("D", "A")

    heritage = PRIORITIES.heritage[heritage_letter]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )

    attribute_points = {
        code: legacy.attributes[code].base + legacy.attributes[code].karma
        for code in ALLOCATABLE_ATTRIBUTES
    }
    character = create_character(
        metatype_choice=human_choice,
        heritage_letter=heritage_letter,
        attributes_letter=attributes_letter,
        priorities=PRIORITIES,
        attribute_points=attribute_points,
    )

    for code in ALLOCATABLE_ATTRIBUTES:
        assert character.attribute_value(code) == legacy.attributes[code].total_value, code


def test_cross_corpus_attribute_value_matches_when_unaugmented() -> None:
    """For every mundane fixture with a plain (non-metavariant) SR5 base metatype, the
    `metatype minimum + base + karma` formula should reproduce `<totalvalue>` for any attribute
    that isn't also being boosted by cyberware/gear -- augmentation is out of MVP scope, so those
    specific attributes are skipped rather than asserted against a number this engine doesn't
    (yet) model the source of.
    """
    metatypes_by_name: dict[str, Metatype] = {m.name: m for m in sr5_metatypes(METATYPES)}
    checked_at_least_one = False

    for fixture_name in MUNDANE_FIXTURES:
        legacy = load_chum5(mundane_fixture_path(fixture_name))
        if legacy.metavariant is not None:
            # Metavariants override attribute ranges and are entirely out of MVP scope (see
            # spec/worklogs/WP6.md) -- the base metatype's ranges below would not apply.
            continue
        metatype = metatypes_by_name[legacy.metatype]

        character = Character(
            metatype=metatype,
            heritage_letter="",
            attributes_letter="",
            special_attribute_points=0,
            attribute_points=MappingProxyType(
                {
                    code: legacy.attributes[code].base + legacy.attributes[code].karma
                    for code in ALLOCATABLE_ATTRIBUTES
                }
            ),
            improvements=ImprovementIndex(),
        )

        for code in ALLOCATABLE_ATTRIBUTES:
            legacy_attribute = legacy.attributes[code]
            natural_value = (
                metatype.attributes[code].minimum + legacy_attribute.base + legacy_attribute.karma
            )
            if natural_value != legacy_attribute.total_value:
                # Augmented by cyberware/gear this WP doesn't model -- not a formula mismatch.
                continue
            checked_at_least_one = True
            assert character.attribute_value(code) == legacy_attribute.total_value, (
                fixture_name,
                code,
            )

    assert checked_at_least_one
