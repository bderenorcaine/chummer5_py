"""Generic form-parsing/display helpers shared by 2+ `chummer5.web.routes` step modules.

**WP62**: split out of the former `chummer5.web.app` (see `spec/plan/phase-r-architecture-cleanup
.md`'s WP58 audit). A step-specific parser (`_parse_contacts`, `_parse_gear`, ...) used by exactly
one route module lives with that module instead -- only the ones with more than one caller belong
here.
"""

from __future__ import annotations

from collections.abc import Iterable

from starlette.datastructures import FormData

from chummer5.engine.resources import MAX_KARMA_TO_NUYEN, karma_to_nuyen


def parse_points(form: FormData, keys: Iterable[str], prefix: str) -> dict[str, int]:
    """Read `{prefix}{key}` fields off a submitted form into a sparse `{key: points}` dict.

    Sparse (zero/absent/unparseable entries are simply omitted) so the result matches the
    "absence means 0" convention `chummer5.engine.character`/`chummer5.engine.skills` already use
    for `attribute_points`/`skill_points`/`group_points`. Negative values are intentionally *not*
    filtered here -- they're passed through so `create_character`/`create_skill_allocation`'s own
    "points spent must not be negative" validation produces the error, rather than this silently
    clamping input the engine is already responsible for rejecting.
    """
    points: dict[str, int] = {}
    for key in keys:
        raw = form.get(f"{prefix}{key}")
        if raw is None:
            continue
        try:
            value = int(str(raw))
        except ValueError:
            continue
        if value != 0:
            points[key] = value
    return points


def parse_specializations(form: FormData, keys: Iterable[str], prefix: str) -> dict[str, str]:
    """Read `{prefix}{key}` fields off a submitted form into a sparse `{key: name}` dict (WP50).

    Sparse the same way `parse_points` is: a blank/absent field means "no specialization for this
    skill", not an error -- `create_skill_allocation`'s own validation is what rejects a genuinely
    invalid nonblank entry (unbought skill, group-purchased skill, budget overspend).
    """
    specializations: dict[str, str] = {}
    for key in keys:
        raw = form.get(f"{prefix}{key}")
        if raw is None:
            continue
        name = str(raw).strip()
        if name:
            specializations[key] = name
    return specializations


def display_karma_to_nuyen(karma_converted: int) -> int:
    """`karma_to_nuyen`, clamped to the valid 0-10 range first, so a context builder can compute a
    display number for an *out-of-range* submitted value (echoed back alongside a rejection
    message) without that computation itself raising -- `create_resources_selection`'s own call to
    the un-clamped `karma_to_nuyen` is what actually rejects it; this is purely for rendering.
    """
    return karma_to_nuyen(max(0, min(karma_converted, MAX_KARMA_TO_NUYEN)))
