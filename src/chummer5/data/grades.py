"""The implant grades a character may buy at creation (WP127): Standard, Alphaware and Used.

Core rulebook p. 451, "Cyberware and Bioware Grades": "Only standard, alphaware, and used implants
are available for purchase at character creation." The grade scales an implant's Essence and
nuyen cost and shifts its Availability. The numbers come from `cyberware.xml`'s `<grades>` block;
`bioware.xml`'s carries the same three rows with the same values (only `<devicerating>` differs,
which nothing here reads), so one table serves both. `tests/unit/test_implant_grades_wp127.py`
pins it against the printed table:

| Grade     | Essence | Cost  | Availability |
|-----------|---------|-------|--------------|
| Standard  | × 1     | × 1   | +0           |
| Alphaware | × 0.8   | × 1.2 | +2           |
| Used      | × 1.25  | × 0.75| −4           |

Betaware, Deltaware and the sourcebook grades (Burnout's Way, Omegaware, ...) are not loaded:
none may be bought at creation.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from decimal import Decimal
from functools import cache
from pathlib import Path

DEFAULT_CYBERWARE_PATH = (
    Path(__file__).resolve().parents[3] / "legacy" / "Chummer" / "data" / "cyberware.xml"
)

STANDARD_GRADE = "Standard"
# p. 451, in the order a picker lists them.
CHARGEN_GRADE_NAMES = (STANDARD_GRADE, "Alphaware", "Used")


@dataclass(frozen=True)
class ImplantGrade:
    name: str
    essence_multiplier: Decimal
    cost_multiplier: Decimal
    availability_modifier: int

    def nuyen(self, cost: Decimal | int) -> int:
        """`cost` at this grade, in whole nuyen. Legacy keeps the fraction (a Used Damper is
        1,687.50¥); this project stores whole nuyen, so half a nuyen rounds up."""
        scaled = Decimal(cost) * self.cost_multiplier
        return int(scaled.to_integral_value(rounding="ROUND_HALF_UP"))


def _parse_grades(path: Path) -> dict[str, ImplantGrade]:
    root = ET.parse(path).getroot()
    grades: dict[str, ImplantGrade] = {}
    for elem in root.findall("grades/grade"):
        name = elem.findtext("name", "")
        if name not in CHARGEN_GRADE_NAMES or elem.findtext("source") != "SR5":
            continue
        grades[name] = ImplantGrade(
            name=name,
            essence_multiplier=Decimal(elem.findtext("ess", "1")),
            cost_multiplier=Decimal(elem.findtext("cost", "1")),
            availability_modifier=int(elem.findtext("avail", "0")),
        )
    missing = set(CHARGEN_GRADE_NAMES) - set(grades)
    if missing:
        raise ValueError(f"{path.name} has no SR5 grade row for {sorted(missing)}")
    return grades


@cache
def implant_grades() -> dict[str, ImplantGrade]:
    """The three creation grades, by name. Parsed once."""
    return _parse_grades(DEFAULT_CYBERWARE_PATH)


def implant_grade(name: str) -> ImplantGrade:
    """The creation grade called `name`; raises for any other grade."""
    grade = implant_grades().get(name)
    if grade is None:
        raise ValueError(
            f"{name!r} is not a grade available at character creation "
            f"(p. 451: {', '.join(CHARGEN_GRADE_NAMES)})"
        )
    return grade
