"""Tests for `chummer5.data.cyberware_formula` (WP36's rating-formula resolver).

Two layers, deliberately:

1. **Hand-checked rulebook values** -- every `FormulaKind` resolved against a value transcribed from
   the printed core-rulebook tables (pp. 453, 454, 456, 457; see
   `spec/rulebooks/learnings/phase-k.md`'s WP36 entry), not from the XML the formula was read from.
   A formula that merely round-trips its own XML proves nothing about whether the arithmetic matches
   the rules.
2. **Whole-data-set coverage** -- every `<cost>`/`<ess>`/`<capacity>` string on all 87 SR5-sourced
   `cyberware.xml` entries parses, and every `FormulaKind` is actually exercised by real data. This
   is what locks WP36's shape survey against future data drift: a new shape appearing in the XML
   fails here rather than silently reaching WP37's loader.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from decimal import Decimal

import pytest

from chummer5.data.cyberware import CORE_RULEBOOK_SOURCE, DEFAULT_CYBERWARE_PATH
from chummer5.data.cyberware_formula import (
    CyberwareFormula,
    FormulaKind,
    UnsupportedCyberwareFormulaError,
    parse_cyberware_formula,
    resolve_cyberware_formula,
)


def _resolve(formula: str, rating: int, min_rating: int | None = None) -> Decimal:
    return resolve_cyberware_formula(formula, rating=rating, min_rating=min_rating)


# --------------------------------------------------------------------------------------------
# Layer 1: hand-checked rulebook-table values, one group per FormulaKind.
# --------------------------------------------------------------------------------------------


def test_literal_shape_resolves_regardless_of_rating() -> None:
    # Datajack: 1,000¥ / 0.1 Essence flat (p. 453) -- no <rating> tag at all, so any rating resolves
    # to the same value. Bare-int <capacity> budgets (Synthetic Full Arm's 8, p. 457) are the same
    # shape.
    assert _resolve("1000", rating=1) == Decimal(1000)
    assert _resolve("1000", rating=6) == Decimal(1000)
    assert _resolve("0.1", rating=3) == Decimal("0.1")
    assert _resolve("8", rating=1) == Decimal(8)
    # Negative literals occur in the data family (Essence Antihole's per-rating multiplier) and are
    # accepted as literals too.
    assert _resolve("-0.5", rating=2) == Decimal("-0.5")


def test_bare_rating_shape() -> None:
    # Vision Enhancement's <capacity> is "[Rating]" -- Capacity cost == chosen rating (p. 454).
    # Brackets are the caller's to strip (see module docstring); the inner shape is a bare Rating.
    assert _resolve("Rating", rating=1) == Decimal(1)
    assert _resolve("Rating", rating=3) == Decimal(3)


def test_rating_times_shape_against_printed_tables() -> None:
    # Vision Enhancement (Rating 1-3), p. 454: cost "Rating x 4,000¥".
    assert _resolve("Rating * 4000", rating=1) == Decimal(4000)
    assert _resolve("Rating * 4000", rating=2) == Decimal(8000)
    assert _resolve("Rating * 4000", rating=3) == Decimal(12000)
    # Muscle Replacement (Rating 1-4), p. 456: "Rating x 25,000¥", Essence "Rating x 1".
    assert _resolve("Rating * 25000", rating=4) == Decimal(100000)
    assert _resolve("Rating * 1", rating=4) == Decimal(4)
    # Dermal Plating (Rating 1-6), p. 456: Essence "Rating x 0.5".
    assert _resolve("Rating * 0.5", rating=6) == Decimal(3)
    # Skillwires (Rating 1-6), p. 456: Essence "Rating x 0.1", cost "Rating x 20,000¥".
    assert _resolve("Rating * 0.1", rating=3) == Decimal("0.3")
    assert _resolve("Rating * 20000", rating=6) == Decimal(120000)
    # Essence Antihole's negative per-rating multiplier (no printed table -- a Chummer bookkeeping
    # item; checked against the XML's own arithmetic intent, which is all it has).
    assert _resolve("Rating * -0.01", rating=50) == Decimal("-0.5")


def test_rating_times_shape_tolerates_redundant_parentheses() -> None:
    # Cybereyes Basic System's <capacity> is "(Rating * 4)"; Cyberears' is "Rating * 4" -- the same
    # shape, written two ways in the same file.
    assert _resolve("(Rating * 4)", rating=3) == Decimal(12)
    assert _resolve("Rating * 4", rating=3) == Decimal(12)
    assert parse_cyberware_formula("(Rating * 4)") == CyberwareFormula(
        kind=FormulaKind.RATING_TIMES, raw="(Rating * 4)", params=(Decimal(4),)
    )


def test_rating_times_plus_shape_matches_the_cybereyes_earware_essence_column() -> None:
    # Cybereyes Basic System and Cyberears share <ess> "(Rating * 0.1) + 0.1"; both tables print
    # Essence 0.2 / 0.3 / 0.4 / 0.5 for Ratings 1-4 (p. 454).
    essence = "(Rating * 0.1) + 0.1"
    assert [_resolve(essence, rating=r) for r in (1, 2, 3, 4)] == [
        Decimal("0.2"),
        Decimal("0.3"),
        Decimal("0.4"),
        Decimal("0.5"),
    ]


def test_fixed_values_shape_matches_the_wired_reflexes_table() -> None:
    # Wired Reflexes (Rating 1-3), p. 456: 39,000¥ / 149,000¥ / 217,000¥, Essence 2 / 3 / 5.
    cost = "FixedValues(39000,149000,217000)"
    assert [_resolve(cost, rating=r) for r in (1, 2, 3)] == [
        Decimal(39000),
        Decimal(149000),
        Decimal(217000),
    ]
    essence = "FixedValues(2,3,5)"
    assert [_resolve(essence, rating=r) for r in (1, 2, 3)] == [Decimal(2), Decimal(3), Decimal(5)]


def test_fixed_values_clamps_a_rating_past_the_last_entry() -> None:
    # Legacy behaviour, read from StringExtensions.ProcessFixedValuesStringCore -- see the resolver
    # module's docstring. No real SR5 item can be bought past its <rating> cap, so this is
    # defensive, not a rules case; it matters only that this engine agrees with the legacy oracle.
    assert _resolve("FixedValues(2,3,5)", rating=9) == Decimal(5)
    # Control Rig (Rating 1-3), p. 453: 43,000¥ / 97,000¥ / 208,000¥ (Essence 1 / 2 / 3).
    assert _resolve("FixedValues(43000,97000,208000)", rating=1) == Decimal(43000)
    assert _resolve("FixedValues(43000,97000,208000)", rating=3) == Decimal(208000)


def test_rating_above_min_times_shape_matches_the_cyberlimb_customization_row() -> None:
    # Customized Agility/Strength, p. 457: "Each STR or AGI point above 3 ... +5,000¥". A
    # cyberlimb's base STR/AGI is 3, so the lowest *purchasable* rating is 4 -- making
    # (Rating - MinRating + 1) an inclusive count of purchased points.
    formula = "(Rating - MinRating + 1) * 5000"
    assert _resolve(formula, rating=4, min_rating=4) == Decimal(5000)  # one point (4)
    assert _resolve(formula, rating=6, min_rating=4) == Decimal(15000)  # three points (4, 5, 6)
    assert _resolve(formula, rating=9, min_rating=4) == Decimal(30000)  # six points (4-9, a troll)


def test_rating_above_min_times_requires_an_explicit_min_rating() -> None:
    # Deliberately not defaulted to 0: that would silently overcharge by MinRating * 5000 nuyen.
    formula = "(Rating - MinRating + 1) * 5000"
    assert parse_cyberware_formula(formula) is not None
    parsed = parse_cyberware_formula(formula)
    assert parsed is not None and parsed.requires_min_rating
    with pytest.raises(ValueError, match="needs a min_rating"):
        _resolve(formula, rating=6)


def test_cybereyes_basic_system_cost_one_off_matches_the_eyeware_table() -> None:
    # p. 454: Rating 1-4 -> 4,000¥ / 6,000¥ / 10,000¥ / 14,000¥ (the "- 2000 * number(Rating > 1)"
    # term is why the Rating-2 price is 6,000¥ rather than a straight 8,000¥).
    cost = "4000 * Rating - 2000 * number(Rating > 1)"
    assert [_resolve(cost, rating=r) for r in (1, 2, 3, 4)] == [
        Decimal(4000),
        Decimal(6000),
        Decimal(10000),
        Decimal(14000),
    ]


def test_cyberears_cost_one_off_matches_the_earware_table() -> None:
    # p. 454: Rating 1-4 -> 3,000¥ / 4,500¥ / 7,500¥ / 11,000¥.
    cost = "3000 + 500 * ((Rating - 1) * (Rating + 1) + number(Rating > 2))"
    assert [_resolve(cost, rating=r) for r in (1, 2, 3, 4)] == [
        Decimal(3000),
        Decimal(4500),
        Decimal(7500),
        Decimal(11000),
    ]


def test_one_off_formulas_are_keyed_by_verbatim_text_not_item_name() -> None:
    # The decision recorded in the module docstring: no item identity is threaded through the
    # resolver, and a changed expression fails loudly instead of resolving with stale arithmetic.
    assert parse_cyberware_formula("4000 * Rating - 2000 * number(Rating > 2)") is None
    # Whitespace differences are still tolerated (the XML's own formatting isn't load-bearing).
    assert _resolve("4000 * Rating   -  2000 * number(Rating > 1)", rating=3) == Decimal(10000)


def test_the_wp36_acceptance_criteria_values() -> None:
    """The two worked examples WP36's own plan entry names, in one place."""
    # Vision Enhancement Rating 2 -> Capacity cost 2, Essence 0.1, nuyen cost 8,000 (p. 454).
    assert _resolve("Rating", rating=2) == Decimal(2)
    assert _resolve("0.1", rating=2) == Decimal("0.1")
    assert _resolve("Rating * 4000", rating=2) == Decimal(8000)
    # Cybereyes Basic System Rating 3 -> nuyen cost 10,000, Essence 0.4 (p. 454).
    assert _resolve("4000 * Rating - 2000 * number(Rating > 1)", rating=3) == Decimal(10000)
    assert _resolve("(Rating * 0.1) + 0.1", rating=3) == Decimal("0.4")


# --------------------------------------------------------------------------------------------
# Rejections: brackets, `[*]`, unsupported shapes, invalid ratings.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("bracketed", ["[2]", "[Rating]", "[Rating * 1]", "[0]", "[15]"])
def test_bracketed_capacity_values_are_rejected_not_stripped(bracketed: str) -> None:
    # WP36's documented decision: brackets carry budget-vs-cost *semantics*, which WP37/38 own. The
    # resolver refuses them so "resolved a plugin's Capacity cost as a parent's budget" can't be a
    # silent mistake here.
    assert parse_cyberware_formula(bracketed) is None
    with pytest.raises(UnsupportedCyberwareFormulaError, match="brackets"):
        _resolve(bracketed, rating=2)


def test_bundled_free_capacity_marker_is_not_a_formula() -> None:
    # Image Link / Sound Link carry <capacity>[*]</capacity>: bundled free with the parent system
    # (p. 454's eyeware-table footnote, "* Included in the basic cybereyes system"). Nothing to
    # resolve -- WP37/38 model it as a flag.
    assert parse_cyberware_formula("[*]") is None


@pytest.mark.parametrize(
    "unsupported",
    [
        "",
        "   ",
        "Rating + 2",  # a real <avail> shape, deliberately out of this resolver's scope
        "{AGIMaximum}",  # a <rating> bound placeholder, not a cost/ess/capacity formula
        "{AGIMinimum}+1",  # a <minrating> bound placeholder, same
        "+Rating - MinRating + 1",  # Customized Agility's <avail> modifier, not its cost
        "Variable(100-1000)",  # a gear.xml shape with no cyberware occurrence
        "Rating * ",
        "Rating * Rating",
        "Force * 5000",
    ],
)
def test_unsupported_shapes_fail_closed(unsupported: str) -> None:
    assert parse_cyberware_formula(unsupported) is None
    with pytest.raises(UnsupportedCyberwareFormulaError):
        _resolve(unsupported, rating=2)


@pytest.mark.parametrize("rating", [0, -1])
def test_rating_below_one_is_rejected(rating: int) -> None:
    with pytest.raises(ValueError, match="rating must be >= 1"):
        _resolve("Rating * 4000", rating=rating)


def test_results_are_exact_decimals_never_floats() -> None:
    # Essence arithmetic has to stay exact -- 3 * 0.1 as a float is 0.30000000000000004, which would
    # drift a character's Essence total (and, through it, Magic loss) by construction.
    assert _resolve("Rating * 0.1", rating=3) == Decimal("0.3")
    assert str(_resolve("Rating * 0.1", rating=3)) == "0.3"
    assert isinstance(_resolve("Rating * 0.1", rating=3), Decimal)


# --------------------------------------------------------------------------------------------
# Layer 2: the whole SR5 data set parses, and every shape is exercised by real data.
# --------------------------------------------------------------------------------------------

_FORMULA_FIELDS = ("cost", "ess", "capacity")


def _sr5_entries() -> list[ET.Element]:
    root = ET.parse(DEFAULT_CYBERWARE_PATH).getroot()
    cyberwares = root.find("cyberwares")
    assert cyberwares is not None
    return [
        c for c in cyberwares.findall("cyberware") if c.findtext("source") == CORE_RULEBOOK_SOURCE
    ]


def _strip_capacity_brackets(text: str) -> str | None:
    """Strip a `<capacity>` value's brackets, or return None for the `[*]` bundled-free marker.

    A stand-in for what WP37's loader will own -- see the resolver module's bracket decision. Kept
    here (not in `chummer5.data`) precisely because WP36 deliberately doesn't ship it.
    """
    text = text.strip()
    if text == "[*]":
        return None
    if text.startswith("[") and text.endswith("]"):
        return text[1:-1].strip()
    return text


def test_every_sr5_cost_essence_and_capacity_value_parses() -> None:
    entries = _sr5_entries()
    assert len(entries) == 87, "WP31's confirmed SR5 entry count"

    unparsed: list[tuple[str, str, str]] = []
    for entry in entries:
        name = entry.findtext("name", "")
        for field in _FORMULA_FIELDS:
            raw = entry.findtext(field)
            if raw is None:
                continue
            text = _strip_capacity_brackets(raw) if field == "capacity" else raw.strip()
            if text is None:  # the [*] bundled-free marker
                continue
            if parse_cyberware_formula(text) is None:
                unparsed.append((name, field, raw))
    assert unparsed == []


def test_every_formula_kind_is_exercised_by_real_sr5_data() -> None:
    """No dead branches: each whitelisted shape exists because real data uses it."""
    seen: set[FormulaKind] = set()
    for entry in _sr5_entries():
        for field in _FORMULA_FIELDS:
            raw = entry.findtext(field)
            if raw is None:
                continue
            text = _strip_capacity_brackets(raw) if field == "capacity" else raw.strip()
            if text is None:
                continue
            parsed = parse_cyberware_formula(text)
            if parsed is not None:
                seen.add(parsed.kind)
    assert seen == set(FormulaKind)


def test_scales_with_rating_splits_the_sr5_set_the_way_wp31s_filter_did() -> None:
    """Cross-check against already-shipped behaviour: exactly the 27 entries WP31 excluded are the
    ones whose `<cost>` or `<ess>` is rating-dependent -- and every one of those carries a
    `<rating>` cap, while none of WP31's 60 flat items does. Confirms this resolver's own shape
    classification agrees with the loader filter Phase J shipped, rather than drawing the line
    somewhere new.
    """
    rating_scaled: list[ET.Element] = []
    flat: list[ET.Element] = []
    for entry in _sr5_entries():
        formulas = [
            parse_cyberware_formula(entry.findtext(field, "").strip()) for field in ("cost", "ess")
        ]
        assert all(f is not None for f in formulas), entry.findtext("name")
        if any(f is not None and f.scales_with_rating for f in formulas):
            rating_scaled.append(entry)
        else:
            flat.append(entry)

    assert len(rating_scaled) == 27
    assert all(e.findtext("rating") is not None for e in rating_scaled)
    assert len(flat) == 60
    assert all(e.findtext("rating") is None for e in flat)
