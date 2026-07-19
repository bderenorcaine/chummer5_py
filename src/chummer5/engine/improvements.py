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
    respectively (see `chummer5.data.qualities`/`chummer5.engine.qualities`).
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


class ImprovementSource(Enum):
    """What granted an Improvement, mirroring legacy `Improvement.ImprovementSource`.

    Limited to the three kinds of bonus the Project Overview's MVP scope names ("metatype bonuses,
    quality bonuses, priority-derived bonuses") rather than legacy's full ~40-member enum, which
    covers cyberware/vehicles/spells/etc. that are out of MVP scope entirely. WP25 (Phase I) adds a
    4th: `TALENT`, for the Talent-option free-skill grant (`chummer5.engine.magic
    .apply_magic_skill_grant_improvements`) — a real Improvement source, but not a "priority-derived
    bonus" in the WP5-era sense (`PRIORITY` has never had a real producer; see that member's own
    note), so it gets its own name rather than overloading `PRIORITY`.
    """

    METATYPE = auto()
    QUALITY = auto()
    PRIORITY = auto()
    TALENT = auto()


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
    """

    improvement_type: ImprovementType
    target: str
    value: int
    source_type: ImprovementSource
    source_id: str
    rating: int = 1
    unique_name: str | None = None


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
        """
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
