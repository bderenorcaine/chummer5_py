"""What carries into play, and the starting-nuyen roll (WP133). Display only.

Step Six (p. 94): a character "may hold onto 5,000¥ or less and carry it over into starting nuyen
-- anything over 5,000¥ is lost". Step Seven (p. 98): "A player may carry a maximum of 7 Karma
unspent into the game." Phase X rules both **display caps**: nothing here limits spending, and the
sidebar keeps showing the true remaining amounts so the player can see what's left to spend. The
sheet shows what would carry over, and how much would be lost. WP135's validation panel lists these
notes as information, not as issues.

**Starting nuyen** (p. 95): "The rest of starting nuyen comes from rolling the dice formula for the
purchased Lifestyle", added to the carried-over nuyen. The formula follows the primary Lifestyle's
**tier**. A permanent purchase (p. 370) is the same tier bought outright, and the core book has no
roommate rule (WP132), so nothing else moves it. No rolling happens in-app: the roll belongs to the
start of play.
"""

from __future__ import annotations

from dataclasses import dataclass

from chummer5.engine.lifestyle import LifestyleSelection

MAX_CARRYOVER_NUYEN = 5000
MAX_CARRYOVER_KARMA = 7


@dataclass(frozen=True)
class Carryover:
    """`remaining` unspent at creation; `carried` into play; `lost` over the cap. A negative
    `remaining` (over budget) carries and loses nothing -- that is WP135's error, not a loss."""

    remaining: int
    cap: int

    @property
    def carried(self) -> int:
        return max(min(self.remaining, self.cap), 0)

    @property
    def lost(self) -> int:
        return max(self.remaining - self.cap, 0)


def nuyen_carryover(nuyen_remaining: int) -> Carryover:
    return Carryover(nuyen_remaining, MAX_CARRYOVER_NUYEN)


def karma_carryover(karma_remaining: int) -> Carryover:
    return Carryover(karma_remaining, MAX_CARRYOVER_KARMA)


@dataclass(frozen=True)
class StartingNuyenRoll:
    """`dice`D6 x `multiplier`¥, plus `carried` nuyen."""

    dice: int
    multiplier: int
    carried: int


def starting_nuyen_roll(
    lifestyle: LifestyleSelection | None, nuyen_remaining: int
) -> StartingNuyenRoll | None:
    """The primary Lifestyle's roll, or None before one is chosen."""
    if lifestyle is None or lifestyle.tier.starting_dice == 0:
        return None
    return StartingNuyenRoll(
        lifestyle.tier.starting_dice,
        lifestyle.tier.starting_multiplier,
        nuyen_carryover(nuyen_remaining).carried,
    )
