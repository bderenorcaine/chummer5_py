"""Improvement engine core: the base+improvements composition mechanism.

Mirrors the legacy model (`legacy/Chummer/Backend/Improvements/Improvement.cs` +
`.../Static/Managers/ImprovementManager.cs`, read directly to confirm this): every derived value
(`attribute.Value`, `skill.Pool`, ...) equals a base term plus the sum of whatever `Improvement`
records currently target it. `ImprovementType`/`ImprovementSource` names are kept parallel to the
legacy `Improvement.ImprovementType`/`ImprovementSource` enums (same names, a small MVP-only subset
of legacy's much larger member lists) so a reader cross-referencing the C# isn't working from
different vocabulary.

Deliberately changes *how* it's evaluated, not the shape, per the Project Overview's Improvement
engine design notes:
- No string-encoded conditions re-parsed at read time. WP5 doesn't add a `condition` field at all
  (unlike the legacy class) — every MVP-supported quality bonus (see WP3) is unconditional, so
  there is no real consumer for one yet; add it, compiled to a typed predicate at construction,
  when a WP actually needs it, rather than carrying unused scaffolding now.
- `ImprovementIndex` stores a flat list plus a
  `dict[(ImprovementType, target)] -> list[Improvement]` index, fully rebuilt on every
  `add`/`remove_source` call instead of being individually invalidated per field mutation like the
  legacy cache.

See `spec/worklogs/WP5.md` for the full reasoning, including the legacy `ValueOf`/dedup algorithm
this was checked against.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, auto


class ImprovementType(Enum):
    """What kind of thing an Improvement targets.

    `ATTRIBUTE`/`SKILL` are the two kinds the Project Overview names as composition examples
    (`attribute.Value`, `skill.Pool`); the other 7 were added in WP10 for `chummer5.engine.derived`
    (initiative, the three Limits, the two condition monitors), per the Project Overview's own
    "more are added when a later WP's derived stat actually needs one (e.g. initiative, limits in
    WP10)" note. Each is a character-wide total, not per-attribute/per-skill like `ATTRIBUTE`/
    `SKILL` — legacy's own `ImprovementManager.ValueOf` calls for these
    (`Improvement.ImprovementType.PhysicalLimit` etc.) take no target parameter either, since
    there's only ever one Physical Limit per character. `ImprovementIndex` still requires a
    `target` key per its `(type, target)` index shape, so `chummer5.engine.derived` resolves these
    against a fixed sentinel target (`""`) rather than adding a second, untargeted resolution path
    to the index for a distinction nothing in MVP scope currently needs. Through WP21, no
    MVP-supported quality (WP3/WP8's `FLAT_BONUS` classifier only recognized flat attribute/skill
    bonuses) or metatype bonus produced any of these 7 -- threaded through for the same reason WP6
    threaded `Character.improvements` through before any metatype bonus existed to use it. WP22 is
    the first real producer: the Indomitable trio's `<mentallimit>`/`<physicallimit>`/
    `<sociallimit>` bonus nodes resolve to `MENTAL_LIMIT`/`PHYSICAL_LIMIT`/`SOCIAL_LIMIT`
    respectively (see `chummer5.data.qualities`/`chummer5.engine.qualities`). WP28 adds an 8th,
    `DRAIN_RESISTANCE`, for `chummer5.engine.derived.drain_resistance` -- another character-wide
    total (one Drain Resistance pool per character, same as the others above), threaded through for
    the same "no current producer, but the derived stat itself needs somewhere to resolve Σ
    improvements against" reason as every other member here; nothing in this project's scope
    produces one yet (checked directly -- no SR5-core quality/power's `<bonus>` targets Drain).

    **WP30 adds a 9th, `ESSENCE`**, for `chummer5.engine.derived.essence` -- also a single
    character-wide total resolved against `_GLOBAL_TARGET`, but genuinely different in kind from
    the 8 above: every one of those resolves through the ordinary `int`-valued `resolve()` method,
    while `ESSENCE` improvements carry their value in the dedicated `Improvement.essence_value`
    field instead (see that field's own docstring for why) and must be summed via the dedicated
    `ImprovementIndex.resolve_essence()` -- `resolve()` itself rejects `ESSENCE` outright rather
    than silently returning 0 for every such improvement (their real `value` field is unused/`0`
    by convention). Threaded through before any real producer exists yet, same as every other
    member here at its own introduction -- WP31/WP32 (cyberware) are the first real producer.
    """

    ATTRIBUTE = auto()
    SKILL = auto()
    INITIATIVE = auto()
    INITIATIVE_DICE = auto()
    PHYSICAL_LIMIT = auto()
    MENTAL_LIMIT = auto()
    SOCIAL_LIMIT = auto()
    PHYSICAL_CM = auto()
    STUN_CM = auto()
    DRAIN_RESISTANCE = auto()
    ESSENCE = auto()


class ImprovementSource(Enum):
    """What granted an Improvement, mirroring legacy `Improvement.ImprovementSource`.

    Limited to the three kinds of bonus the Project Overview's MVP scope names ("metatype bonuses,
    quality bonuses, priority-derived bonuses") rather than legacy's full ~40-member enum, which
    covers cyberware/vehicles/spells/etc. that are out of MVP scope entirely. WP25 (Phase I) adds a
    4th: `TALENT`, for the Talent-option free-skill grant (`chummer5.engine.magic
    .apply_magic_skill_grant_improvements`) — a real Improvement source, but not a "priority-derived
    bonus" in the WP5-era sense (`PRIORITY` has never had a real producer; see that member's own
    note), so it gets its own name rather than overloading `PRIORITY`. WP27 adds a 5th:
    `ADEPT_POWER`, for `chummer5.engine.magic.apply_power_improvements` — each selected power is
    its own source instance (keyed by the power's own id, mirroring `QUALITY`'s per-quality
    `source_id`), distinct from `TALENT`'s single shared grant. WP30 adds a 6th: `CYBERWARE`, for
    the Essence-cost `Improvement` each purchased cyberware item will grant once WP31/WP32 build
    the actual catalog/selection -- threaded through now (no real producer yet) the same way every
    prior source name here was added ahead of its first real user.
    """

    METATYPE = auto()
    QUALITY = auto()
    PRIORITY = auto()
    TALENT = auto()
    ADEPT_POWER = auto()
    CYBERWARE = auto()


@dataclass(frozen=True)
class Improvement:
    """One `target += value` record.

    `source_type`/`source_id` together identify what granted this improvement — `source_id` is
    that specific instance's id (e.g. one quality's id on one character), not just its kind — so
    `ImprovementIndex.remove_source` can cleanly remove every Improvement a single source granted
    without any other bookkeeping. `unique_name` implements SR5's "highest bonus wins" stacking
    rule (confirmed against legacy `ImprovementManager`'s `UniqueName` dedup pass): Improvements
    that share a `unique_name` *and* target the same `(improvement_type, target)` key collapse to
    their single highest `value` before being added to the total; Improvements with `unique_name =
    None` always stack additively instead. `rating` is carried as part of the shape (matching the
    legacy field) but is not consumed by `resolve()` — nothing in MVP's scope computes a value from
    rating at resolve time; whatever constructs an `Improvement` is responsible for having already
    folded any rating-dependent math into `value`.

    **`essence_value` (WP30) is a second, parallel value field, meaningful only when
    `improvement_type is ImprovementType.ESSENCE`; `value` stays `0` (unused) on those instances by
    convention.** This is a real design decision, not an oversight -- recorded in
    `spec/worklogs/WP30.md` with the two alternatives it was weighed against: (a) widening `value`
    itself to `Decimal`/`float` engine-wide, which would ripple `resolve()`'s `int` return type (and
    every one of its arithmetic-heavy callers in `chummer5.engine.derived`/`character`) into a
    fractional type for the 8 existing `ImprovementType` members that are correctly integer-only
    forever (an attribute point, a Limit bonus, a condition-monitor box are never fractional in
    SR5); (c) tracking Essence in an implicit fixed-point unit (e.g. hundredths) inside the existing
    `int value` field, rejected because real `cyberware.xml` Essence costs go to 3 decimal places
    (`1.125`, confirmed directly -- see this WP's worklog), one more digit of precision than a
    hundredths encoding would preserve losslessly. `Decimal` avoids the binary-float representation
    error a `float` field would introduce for exactly the repeating-fraction values (`0.3`, `0.1`,
    ...) this catalog actually contains, and keeps every other `ImprovementType`'s `resolve()` path
    completely untouched. `None` for every non-`ESSENCE` improvement.
    """

    improvement_type: ImprovementType
    target: str
    value: int
    source_type: ImprovementSource
    source_id: str
    rating: int = 1
    unique_name: str | None = None
    essence_value: Decimal | None = None


class ImprovementIndex:
    """Holds a set of Improvements, indexed for `resolve()` lookups.

    Per the Project Overview: no manual per-field cache invalidation — the (cheap,
    character-sized) index is fully rebuilt on every `add`/`remove_source` call instead of being
    individually patched.
    """

    def __init__(self) -> None:
        self._improvements: list[Improvement] = []
        self._index: dict[tuple[ImprovementType, str], list[Improvement]] = {}

    @property
    def improvements(self) -> tuple[Improvement, ...]:
        """Every currently-held Improvement, in insertion order."""
        return tuple(self._improvements)

    def add(self, improvement: Improvement) -> None:
        self._improvements.append(improvement)
        self._reindex()

    def remove_source(self, source_type: ImprovementSource, source_id: str) -> None:
        """Remove every Improvement granted by one source instance (e.g. one quality)."""
        self._improvements = [
            imp
            for imp in self._improvements
            if not (imp.source_type == source_type and imp.source_id == source_id)
        ]
        self._reindex()

    def _reindex(self) -> None:
        index: dict[tuple[ImprovementType, str], list[Improvement]] = {}
        for imp in self._improvements:
            index.setdefault((imp.improvement_type, imp.target), []).append(imp)
        self._index = index

    def resolve(self, improvement_type: ImprovementType, target: str) -> int:
        """Sum every Improvement targeting `(improvement_type, target)`, applying dedup.

        Improvements with `unique_name = None` all stack additively. Improvements sharing a
        non-`None` `unique_name` collapse to their single highest `value` first — SR5's "highest
        bonus wins" — then that one value is added to the total once per distinct `unique_name`.

        Rejects `ImprovementType.ESSENCE` outright (WP30) rather than silently summing zeros: an
        `ESSENCE` improvement's real magnitude lives in `essence_value`, not `value` (see that
        field's docstring), so calling this method on it would look like it worked while always
        returning 0 -- use `resolve_essence()` instead.
        """
        if improvement_type is ImprovementType.ESSENCE:
            raise ValueError(
                "ESSENCE improvements carry their value in essence_value, not value -- "
                "use resolve_essence() instead"
            )
        best_by_unique_name: dict[str, int] = {}
        total = 0
        for imp in self._index.get((improvement_type, target), ()):
            if imp.unique_name is None:
                total += imp.value
            else:
                current = best_by_unique_name.get(imp.unique_name)
                if current is None or imp.value > current:
                    best_by_unique_name[imp.unique_name] = imp.value
        return total + sum(best_by_unique_name.values())

    def resolve_essence(self, target: str) -> Decimal:
        """Sum every `ESSENCE`-typed Improvement's `essence_value` targeting `target`.

        No `unique_name` dedup here, unlike `resolve()` -- SR5 has no "highest cost wins" rule for
        Essence the way "highest bonus wins" exists for stacking bonuses (that rule exists to stop
        a player double-dipping on *bonuses*; an Essence cost is a plain sum of whatever cyberware/
        bioware was actually bought, confirmed against the legacy engine's own `Character.Essence()`
        -- see `spec/worklogs/WP30.md`). `unique_name` is therefore not consulted at all here.
        """
        total = Decimal(0)
        for imp in self._index.get((ImprovementType.ESSENCE, target), ()):
            assert imp.essence_value is not None, (
                "ESSENCE improvement missing essence_value -- see Improvement's own docstring"
            )
            total += imp.essence_value
        return total
