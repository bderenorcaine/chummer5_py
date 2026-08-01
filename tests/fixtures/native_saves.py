"""Registry of on-disk fixtures in *this project's own* save format (Phase S / WP85).

The third fixture family, beside `mundane_chum5.py`'s legacy `.chum5` corpus and `synthetic.py`'s
in-code `SyntheticCharacter` literals. Where those two are respectively "someone else's engine
computed this" and "we describe the inputs in Python", this one is **a real file a player produced
through this project's own web UI**, kept byte-for-byte as it was downloaded.

That makes it the only regression guard the save *format* has ever had. Everything else exercises
`save_format` by constructing a `CharacterSave` in code and round-tripping it, which can only ever
prove the writer and the reader agree with each other — it cannot catch a change that makes both
agree on something a previously-written file no longer matches. A checked-in file written by an
older build can.

**Copied, not referenced** — the inverse of `mundane_chum5.py`'s own choice, and for the same
reason stated there in reverse: these files are *ours*, small (a few KB), and have no upstream
source of truth to drift from. `legacy/Chummer.Tests/TestFiles/` is a vendored third-party corpus
this repo already carries, so pointing at it avoids ~9MB of duplication; a native save has nowhere
else to live.
"""

from __future__ import annotations

from pathlib import Path

NATIVE_SAVES_DIR = Path(__file__).resolve().parent / "saves"

# Jacob "Tithe" Smith -- a Human Sum-to-Ten (E/B/A/B/E) street samurai chromed to Essence 0.10,
# authored in the web UI by a player rather than derived from the implementation plan. See
# `spec/plan/phase-s-test-fixtures.md` §6 for the six coverage gaps his build walks through that
# the phase's own §2 inventory never enumerated, and WP88 for the synthetic fixture authored from
# him.
RAZORBOY_SAVE = "razorboy.json"

NATIVE_SAVE_FIXTURES: tuple[str, ...] = (RAZORBOY_SAVE,)


def native_save_path(name: str) -> Path:
    """Resolve a name from `NATIVE_SAVE_FIXTURES` to its path under `NATIVE_SAVES_DIR`."""
    return NATIVE_SAVES_DIR / name
