"""Loader for the Matrix-action names in `legacy/Chummer/data/actions.xml` (WP114).

Only what Codeslinger's pick needs: the SR5-core Matrix actions that have a test to add dice to
(p. 72, "must have an associated test"). Defense-test rows (`WIL Attack Defense`, ...) are the
defender's roll, not an action, and are left out. The mark variants of one action (`Brute Force (1
Mark)` / `(2 Marks)` / `(3 Marks)`) are one action for Codeslinger's purpose, so the suffix is
dropped and duplicates collapse.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

DEFAULT_ACTIONS_PATH = (
    Path(__file__).resolve().parents[3] / "legacy" / "Chummer" / "data" / "actions.xml"
)
CORE_RULEBOOK_SOURCE = "SR5"
_MARK_SUFFIX_RE = re.compile(r" \(\d Marks?\)$")


def load_matrix_action_names(xml_path: Path = DEFAULT_ACTIONS_PATH) -> tuple[str, ...]:
    """The SR5-core Matrix actions with an associated test, mark variants collapsed."""
    root = ET.parse(xml_path).getroot()
    names: dict[str, None] = {}
    for action in root.iter("action"):
        if action.findtext("category") != "Matrix" or action.findtext("source") != "SR5":
            continue
        name = action.findtext("name", "")
        if name.endswith(" Defense") or not action.findtext("test/dice"):
            continue
        names[_MARK_SUFFIX_RE.sub("", name)] = None
    return tuple(names)
