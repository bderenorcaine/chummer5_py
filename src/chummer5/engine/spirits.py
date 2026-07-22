"""Bound Spirits (Phase M, WP46): a Magician's chargen-time Karma spend binding spirits.

Deliberately modeled as **roster entries plus a budget check only** -- no spirit stat block, no
skills, no powers (optional or otherwise), per the Implementation Plan's Phase M intro. A bound
spirit's Force is always exactly the caster's *current* Magic rating (not player-chosen); the only
two things a player picks are which spirit type and how many services, which sets the Karma cost
1:1 (core rulebook, "Additional Purchases & Restrictions" table, Step Seven, p. 98 -- see
`spec/rulebooks/learnings.md`'s WP46 entry for the full citation).

**Magician-only, enforced via `character.tradition`, not a separate `magic_type` check.** Only
Magicians have a tradition (Adepts don't cast or conjure at all -- confirmed directly against the
rulebook's own "Adepts" section, p. 308: "adepts still need the appropriate licenses to... cast
spells if they are that rare hybrid, the mystic adept", implying a non-mystic Adept never casts or
conjures; Mystic Adept itself is out of this project's scope entirely). Gating on `tradition is
None` ties the check to the actual data dependency (which spirit types are even offered comes from
the tradition) rather than duplicating a redundant `magic_type == "Magician"` test.

**Karma budget is a caller-supplied `int`, not something this module computes from `Character`.**
Per the Implementation Plan's own WP46/WP47 entries: no unified "leftover Karma" ledger exists yet
(Phase O, not yet built) -- `provisional_karma_budget` below is a minimal, deliberately-temporary
stand-in (starting Karma minus the only two Karma-costing selections that exist today: qualities
and contacts), not Phase O's future real ledger. It mirrors the shape Phase O's own WP51 intro
already sketches (`starting_karma - Σ every known Karma-spending selection's cost`) so retrofitting
is a rename, not a redesign, once WP51 lands -- at which point this function should be retired in
favor of the real one.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from chummer5.data.traditions import Tradition
from chummer5.engine.character import Character

# Core rulebook p. 64 ("All characters in Shadowrun start with 25 Karma they will use to improve
# themselves"), cross-checked against the Step Six worked example (James ends Step Four with 26
# Karma, not 25, having spent 19 on Positive Qualities and gained 20 from Negative ones -- i.e. the
# pool moves from this fixed starting point, it isn't itself variable).
STARTING_KARMA = 25

# Core rulebook, Step Seven's "Additional Purchases & Restrictions" table (p. 98): "1 Karma per
# service (Force of spirit is equal to Character's Magic Attribute rating)."
KARMA_PER_SERVICE = 1


def provisional_karma_budget(
    quality_karma_cost: int,
    contact_karma_cost: int,
    bound_spirit_karma_cost: int = 0,
    foci_karma_cost: int = 0,
) -> int:
    """`STARTING_KARMA` minus whatever qualities/contacts/Bound Spirits/Foci have already spent --
    see module docstring for why this is a WP46-local stand-in, not Phase O's eventual unified
    ledger. Callers pass each selection's own already-computed `karma_cost` (0 if not yet
    committed), mirroring how `create_resources_selection`'s `lifestyle_cost`/`cyberware_cost`
    parameters are each the *other* selection's own resolved cost, not something this function
    re-derives.

    **WP47 widens this from 2 terms to 4.** Bound Spirits and Foci (`chummer5.engine.foci`) are two
    independent Karma-costing selections competing for the same pool, with no inherent evaluation
    order between them (unlike cyberware/bioware's Essence-floor chaining -- see `chummer5.engine
    .foci`'s own module docstring) -- every caller resolves both new parameters symmetrically off
    `character.bound_spirit_selection`/`.foci_selection`'s own already-computed cost, the same way
    `chummer5.web.app`'s gear/Lifestyle/cyberware/bioware nuyen sections already read each other's
    committed spend rather than assuming a fixed order. Both default to `0` so every pre-WP47 call
    site (which never had Foci to account for) keeps working unchanged.
    """
    return (
        STARTING_KARMA
        - quality_karma_cost
        - contact_karma_cost
        - bound_spirit_karma_cost
        - foci_karma_cost
    )


def offered_spirit_types(tradition: Tradition) -> tuple[str, ...]:
    """The (up to 5) spirit type names `tradition` can summon/bind -- see `SpiritAffinities
    .offered_types`."""
    return tradition.spirits.offered_types


@dataclass(frozen=True)
class BoundSpirit:
    """One bound spirit: which type, at what Force (always the caster's current Magic rating, per
    the rulebook -- never player-chosen), and how many services it owes."""

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
    picks: Iterable[tuple[str, int]],
    character: Character,
    karma_budget: int,
) -> BoundSpiritSelection:
    """Build a `BoundSpiritSelection`, validating `picks` (`(spirit_type_name, services)` pairs)
    together.

    Validates: an empty `picks` is always fine, for any character (no Magician/tradition gate is
    applied until there's actually something to check -- mirrors `create_spell_selection`'s
    "budget=0 already rejects any pick" shape, just the empty-input direction of it); non-empty
    `picks` requires `character.tradition` to be set (Magician only -- see module docstring); the
    number of spirits doesn't exceed `character.attribute_value("CHA")` (rulebook: "Can only have a
    number of bound spirits equal to Charisma"); every `spirit_type` is one of `character.tradition
    .spirits.offered_types`; every `services` is at least 1 (a spirit bound for 0 services isn't
    actually bound to anything); and the summed `services * KARMA_PER_SERVICE` doesn't exceed
    `karma_budget`. Does not require the full budget to be spent or every Charisma slot filled,
    mirroring every other `create_*` function in this engine. Binding two spirits of the same type
    is a real, legal SR5 purchase (they're distinct individual spirits), so `picks` allows repeats.
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
    force = character.attribute_value("MAG")

    spirits: list[BoundSpirit] = []
    total_cost = 0
    for spirit_type, services in entries:
        if spirit_type not in offered:
            raise ValueError(
                f"{spirit_type!r} is not an offered spirit type for {character.tradition.name}: "
                f"must be one of {offered}"
            )
        if services < 1:
            raise ValueError(
                f"{spirit_type!r}: services must be at least 1, got {services}"
            )
        spirits.append(BoundSpirit(spirit_type=spirit_type, force=force, services=services))
        total_cost += services * KARMA_PER_SERVICE

    if total_cost > karma_budget:
        raise ValueError(
            f"{total_cost} Karma spent on Bound Spirits, exceeding the available budget of "
            f"{karma_budget}"
        )

    return BoundSpiritSelection(
        spirits=tuple(spirits), karma_cost=total_cost, karma_budget=karma_budget
    )
