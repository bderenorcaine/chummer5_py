"""Bound Spirits (Phase M, WP46): a Magician's chargen-time Karma spend binding spirits.

Deliberately modeled as **roster entries plus a budget check only** -- no spirit stat block, no
skills, no powers (optional or otherwise), per the Implementation Plan's Phase M intro. A player
picks three things per spirit: which type, at what Force, and how many services.

**Force is player-chosen, from 1 up to the caster's current Magic rating (WP70).** Through WP46-WP69
this engine pinned Force to exactly the Magic rating (the Step Seven "Additional Purchases &
Restrictions" table, p. 98, phrases the chargen shortcut as "Force = character's Magic rating"), so
`force` was recomputed live rather than stored. WP70 relaxes that: a player may bind a spirit at any
Force from 1 to Magic (the general summoning rule allows up to Magic x 2, p. 300 -- but the chargen
table takes Magic as the reference, and WP70's scope is Force <= Magic). A pick's `force` of `None`
still means "default to the current Magic rating", which is both the UI default and how a pre-WP70
save (which never stored `force`) round-trips unchanged. **Crucially, the chargen Karma cost does
*not* scale with Force**: the p. 98 table is a flat "1 Karma per service" regardless of the Force
chosen (verified against the rulebook for WP70 -- see `spec/rulebooks/learnings.md`'s WP70 entry;
`KARMA_PER_SERVICE` stays 1). The only two things Force affects here are which binds are legal
(1 <= force <= Magic) and what's displayed/persisted, not the cost.

**Magician-only, enforced via `character.tradition`, not a separate `magic_type` check.** Only
Magicians have a tradition (Adepts don't cast or conjure at all -- confirmed directly against the
rulebook's own "Adepts" section, p. 308: "adepts still need the appropriate licenses to... cast
spells if they are that rare hybrid, the mystic adept", implying a non-mystic Adept never casts or
conjures; Mystic Adept itself is out of this project's scope entirely). Gating on `tradition is
None` ties the check to the actual data dependency (which spirit types are even offered comes from
the tradition) rather than duplicating a redundant `magic_type == "Magician"` test.

**Karma budget is a caller-supplied `int`, resolved from `Character.karma_remaining` (Phase O's
unified ledger, WP51) plus whatever this selection's own already-committed cost needs adding back
in for a re-validation -- not something this module computes itself.** Through WP47, this module
used to expose its own `provisional_karma_budget` stand-in (starting Karma minus whichever of
qualities/contacts/Bound Spirits/Foci existed by then) -- retired now that `Character.karma_
remaining` is the real thing it was standing in for; see that property's own docstring.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from chummer5.data.traditions import Tradition
from chummer5.engine.character import STARTING_KARMA, Character

__all__ = [
    "STARTING_KARMA",
    "BoundSpirit",
    "BoundSpiritSelection",
    "create_bound_spirit_selection",
    "offered_spirit_types",
]

# Core rulebook, Step Seven's "Additional Purchases & Restrictions" table (p. 98): "1 Karma per
# service" -- a flat cost that does not scale with the spirit's Force (WP70 verified this against
# the rulebook; the table's parenthetical "Force = character's Magic rating" describes the default
# Force, not a cost multiplier).
KARMA_PER_SERVICE = 1


def offered_spirit_types(tradition: Tradition) -> tuple[str, ...]:
    """The (up to 5) spirit type names `tradition` can summon/bind -- see `SpiritAffinities
    .offered_types`."""
    return tradition.spirits.offered_types


@dataclass(frozen=True)
class BoundSpirit:
    """One bound spirit: which type, at what Force (player-chosen from 1 to the caster's Magic
    rating, WP70 -- defaulting to Magic when the player doesn't narrow it), and how many services
    it owes."""

    spirit_type: str
    force: int
    services: int


@dataclass(frozen=True)
class BoundSpiritSelection:
    """A validated set of bound spirits and their total Karma cost."""

    spirits: tuple[BoundSpirit, ...]
    karma_cost: int
    karma_budget: int


def create_bound_spirit_selection(
    picks: Iterable[tuple[str, int | None, int]],
    character: Character,
    karma_budget: int,
) -> BoundSpiritSelection:
    """Build a `BoundSpiritSelection`, validating `picks` (`(spirit_type_name, force, services)`
    triples) together.

    A pick's `force` of `None` means "use the character's current Magic rating" -- the UI default,
    and how a pre-WP70 save (which never stored a Force) resolves. An explicit `force` must be
    between 1 and the Magic rating inclusive (WP70; see module docstring for the Force cap's
    rulebook basis).

    Validates: an empty `picks` is always fine, for any character (no Magician/tradition gate is
    applied until there's actually something to check -- mirrors `create_spell_selection`'s
    "budget=0 already rejects any pick" shape, just the empty-input direction of it); non-empty
    `picks` requires `character.tradition` to be set (Magician only -- see module docstring); the
    number of spirits doesn't exceed `character.attribute_value("CHA")` (rulebook: "Can only have a
    number of bound spirits equal to Charisma"); every `spirit_type` is one of `character.tradition
    .spirits.offered_types`; every `force` is between 1 and the Magic rating; every `services` is at
    least 1 (a spirit bound for 0 services isn't actually bound to anything); and the summed
    `services * KARMA_PER_SERVICE` doesn't exceed `karma_budget` (the cost is a flat 1 Karma per
    service -- it does *not* scale with Force, see module docstring). Does not require the full
    budget to be spent or every Charisma slot filled, mirroring every other `create_*` function in
    this engine. Binding two spirits of the same type is a real, legal SR5 purchase (they're
    distinct individual spirits), so `picks` allows repeats.
    """
    entries = list(picks)
    if not entries:
        return BoundSpiritSelection(spirits=(), karma_cost=0, karma_budget=karma_budget)

    if character.tradition is None:
        raise ValueError(
            "Bound Spirits require a Magician's tradition to know which spirit types are eligible"
        )

    max_count = character.attribute_value("CHA")
    if len(entries) > max_count:
        raise ValueError(
            f"{len(entries)} bound spirits selected, exceeding the Charisma limit of {max_count}"
        )

    offered = offered_spirit_types(character.tradition)
    magic_rating = character.attribute_value("MAG")

    spirits: list[BoundSpirit] = []
    total_cost = 0
    for spirit_type, force, services in entries:
        if spirit_type not in offered:
            raise ValueError(
                f"{spirit_type!r} is not an offered spirit type for {character.tradition.name}: "
                f"must be one of {offered}"
            )
        resolved_force = magic_rating if force is None else force
        if resolved_force < 1 or resolved_force > magic_rating:
            raise ValueError(
                f"{spirit_type!r}: Force must be between 1 and the Magic rating of {magic_rating}, "
                f"got {resolved_force}"
            )
        if services < 1:
            raise ValueError(
                f"{spirit_type!r}: services must be at least 1, got {services}"
            )
        spirits.append(
            BoundSpirit(spirit_type=spirit_type, force=resolved_force, services=services)
        )
        total_cost += services * KARMA_PER_SERVICE

    if total_cost > karma_budget:
        raise ValueError(
            f"{total_cost} Karma spent on Bound Spirits, exceeding the available budget of "
            f"{karma_budget}"
        )

    return BoundSpiritSelection(
        spirits=tuple(spirits), karma_cost=total_cost, karma_budget=karma_budget
    )
