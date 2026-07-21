"""WP33: confirms `chummer5.io.legacy_import`'s new itemized cyberware/bioware blocking checks
against real per-item data in the Phase J intro's 8 real cyberware-bearing fixtures (`BLUE`,
`Barrett`, `Bastion`, `Blindfire`, `Fuzzy-chargen`, `Gentle Earthquake`, `Monomax (approved) 3`,
`SCSi`).

None of these 8 is `buildmethod == Priority` (all `SumtoTen` -- see the Phase J intro and
`tests/integration/test_cyberware_fixtures.py`'s identical precedent), so none can reach a full
successful import regardless of cyberware content -- every one is rejected on build-method grounds
alone, mirroring `tests/integration/test_legacy_import_fixtures.py`'s own `Barrett.chum5` case. This
file instead confirms the itemized reasons `import_chum5` raises for real cyberware/bioware content
are the specific, per-item ones WP33 introduces (rating-scaled/non-Standard-grade/non-SR5 cyberware;
Bioware entirely), not the old blanket "character has cyberware/bioware" message -- and that a real
Standard-grade flat item (Bastion's/Blindfire's own Datajack, Bastion's own Smartlink) is correctly
*not* itemized as rejected.
"""

from __future__ import annotations

import pytest
from tests.fixtures.mundane_chum5 import mundane_fixture_path

from chummer5.data.cyberware import load_cyberware
from chummer5.data.lifestyle import load_lifestyles
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import load_skills
from chummer5.io.legacy_import import UnsupportedLegacyCharacterError, import_chum5

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
QUALITIES = load_qualities()
LIFESTYLES = load_lifestyles()
CYBERWARE = load_cyberware()

_CYBERWARE_BEARING_FIXTURES = (
    "BLUE.chum5",
    "Barrett.chum5",
    "Bastion.chum5",
    "Blindfire.chum5",
    "Fuzzy-chargen.chum5",
    "Gentle Earthquake.chum5",
    "Monomax (approved) 3.chum5",
    "SCSi.chum5",
)


def _reasons(fixture_name: str) -> tuple[str, ...]:
    with pytest.raises(UnsupportedLegacyCharacterError) as exc_info:
        import_chum5(
            mundane_fixture_path(fixture_name),
            metatypes=METATYPES,
            priorities=PRIORITIES,
            skills=SKILLS,
            qualities=QUALITIES,
            lifestyles=LIFESTYLES,
            cyberware=CYBERWARE,
        )
    return exc_info.value.reasons


@pytest.mark.parametrize("fixture_name", _CYBERWARE_BEARING_FIXTURES)
def test_every_cyberware_bearing_fixture_is_rejected_with_itemized_reasons(
    fixture_name: str,
) -> None:
    """Every one of the 8 is SumtoTen-built, so it's rejected on build-method grounds regardless --
    but the itemized cyberware/bioware reasons must still appear distinctly (per real item),
    confirming WP33's classification logic actually runs and reports correctly even though nothing
    here can reach a full successful import (see module docstring).
    """
    reasons = _reasons(fixture_name)
    assert any("not Priority-built" in r for r in reasons)
    # Every one of these 8 fixtures carries real, unsupported cyberware or Bioware content per the
    # Phase J intro -- at least one itemized reason beyond the build-method one must appear.
    assert any("is Bioware" in r or "out of scope" in r for r in reasons)


def test_bastions_standard_grade_flat_items_are_not_itemized_as_rejected() -> None:
    """Bastion's real Smartlink + Datajack purchases (both Standard grade, both in WP31's flat
    catalog) must not appear among the itemized rejection reasons -- only her real Used-grade
    Cyberlimbs and Bioware content should.
    """
    reasons = _reasons("Bastion.chum5")
    assert not any("'Smartlink'" in r for r in reasons)
    assert not any("'Datajack'" in r for r in reasons)
    assert any("'Obvious Full Arm'" in r for r in reasons)  # bought at Used grade -- rejected
    assert any("is Bioware" in r for r in reasons)  # e.g. Cerebral Booster, Adapsin


def test_blindfires_standard_grade_datajack_is_not_itemized_as_rejected() -> None:
    reasons = _reasons("Blindfire.chum5")
    assert not any("'Datajack'" in r for r in reasons)
    assert any("'Obvious Full Arm'" in r for r in reasons)  # bought at Used grade -- rejected
