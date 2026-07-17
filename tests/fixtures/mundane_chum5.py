"""Registry of the curated mundane `.chum5` fixture corpus (WP4).

Referenced, not copied, from `legacy/Chummer.Tests/TestFiles/` — see `tests/fixtures/README.md` for
why (avoids ~9MB of duplicated, potentially-drifting XML) and for the corpus split this module
encodes: which fixtures back build-method-agnostic derived-stat assertions vs. priority-allocation
assertions specifically.
"""

from __future__ import annotations

from pathlib import Path

LEGACY_TESTFILES_DIR = (
    Path(__file__).resolve().parents[2] / "legacy" / "Chummer.Tests" / "TestFiles"
)

# The 11 of 34 legacy corpus fixtures with <magenabled>False</magenabled> — this project's
# established meaning of "mundane" (see spec/worklogs/WP2.md's source-data-reconnaissance note).
# Note this is *not* "no Resonance either": 5 of these 11 have <resenabled>True</resenabled>
# (technomancers) — see PRIORITY_BUILD_FIXTURE and spec/worklogs/WP4.md for why they're still valid
# fixtures for build-method-agnostic formulas even though a technomancer couldn't be *built* by
# MVP's chargen engine.
MUNDANE_FIXTURES: tuple[str, ...] = (
    "BLUE.chum5",
    "Barrett.chum5",
    "Bastion.chum5",
    "Blindfire.chum5",
    "Fuzzy-chargen.chum5",
    "Gentle Earthquake.chum5",
    "Monomax (approved) 3.chum5",
    "Rez0luti0n2.0.chum5",
    "SCSi.chum5",
    "Serpent.chum5",
    "Yeti-#ffffff2.chum5",
)

# The only mundane fixture with <buildmethod>Priority</buildmethod> (the other 10 use SumtoTen,
# out of MVP scope) — the one fixture that validates priority-table allocation logic itself, not
# just build-method-agnostic derived-stat formulas. See the Implementation Plan's corpus note.
PRIORITY_BUILD_FIXTURE = "Yeti-#ffffff2.chum5"


def mundane_fixture_path(name: str) -> Path:
    """Resolve a name from `MUNDANE_FIXTURES` to its path under `LEGACY_TESTFILES_DIR`."""
    return LEGACY_TESTFILES_DIR / name
