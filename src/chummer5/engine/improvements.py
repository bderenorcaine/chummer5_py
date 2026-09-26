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
- No string-encoded conditions re-parsed at read time. WP5 didn't add a `condition` field at all
  (unlike the legacy class) — every MVP-supported quality bonus (see WP3) is unconditional, so
  there was no real consumer for one; the note there said to add it, compiled to a typed predicate
  at construction, "when a WP actually needs it, rather than carrying unused scaffolding now."
  **WP39 is that WP** — see "Conditional Improvements" below.
- `ImprovementIndex` stores a flat list plus a
  `dict[(ImprovementType, target)] -> list[Improvement]` index, fully rebuilt on every
  `add`/`remove_source` call instead of being individually invalidated per field mutation like the
  legacy cache.

See `spec/worklogs/WP5.md` for the full reasoning, including the legacy `ValueOf`/dedup algorithm
this was checked against.

## Conditional Improvements (WP39 — Phase K)

Some real bonuses apply only during a *specific kind of test*. The four confirmed instances in the
SR5 cyberware set (all `<limitmodifier>` nodes carrying a `<condition>`, all currently classified
`NOT_YET_SUPPORTED` by `chummer5.data.cyberware`):

- **Vision Enhancement** (Mental limit) — `LimitCondition_SkillsActivePerceptionVisual`,
  "Only for Perception (Visual)"
- **Audio Enhancement** (Mental limit) — `LimitCondition_SkillsActivePerceptionHearing`,
  "Only for Perception (Hearing)"
- **Spatial Recognizer** (Mental limit) — `LimitCondition_SkillsActivePerceptionSpatialRecognizer`,
  "Only for Perception to find the source of a sound"
- **Hydraulic Jacks** (Physical limit) — `LimitCondition_CyberwareHydraulicJacks`,
  "Only for Gymnastics (Jumping) and Running (Sprinting)"

(English text from `legacy/Chummer/lang/en-us.xml`; the item/limit/condition triples from
`legacy/Chummer/data/cyberware.xml`'s own `<limitmodifier>` nodes.)

**The design, and the three "decide & document" calls WP39's plan entry asks for:**

1. **A `Condition` is an `Enum` (`ImprovementCondition`), not a closure and not a tagged union.**
   A closure is uninspectable and unhashable-in-practice, which would break `Improvement`'s
   `frozen=True`/value-equality shape and make a saved or compared Improvement meaningless. A tagged
   union buys parameterization nothing here needs: every confirmed shape is the *unparameterized*
   statement "this bonus applies only during these tests." The enum is the compiled form — resolved
   once when the `Improvement` is constructed, never re-parsed from the legacy condition string at
   read time, which is the whole point of the Project Overview's critique of the legacy engine.
   This mirrors WP25's named-xpath-predicate precedent: classify the handful of real, named shapes;
   do **not** build a general condition-string interpreter.
2. **The call-site context is a single optional `ResolutionContext`**, the smallest shape that
   covers all four rows above. `ImprovementIndex.resolve(...)` grows a keyword-only `context`
   parameter
   defaulting to `None`, so this is **purely additive**: every existing call site is unchanged,
   and
   `context=None` means "resolve the plain, unconditional value," which is exactly what those call
   sites already computed. `condition=None` on an Improvement is likewise a true no-op — an
   unconditional Improvement contributes in *every* resolution, with or without a context.
3. **A condition maps to a *set* of `ResolutionContext`s, not to one.** Hydraulic Jacks is why:
   its single condition covers two unrelated activities (Gymnastics/Jumping *and*
   Running/Sprinting). Without that, the fourth row would have needed two Improvements for one
   bonus.

**No subsumption between conditions is modeled, deliberately.** Spatial Recognizer's "Perception to
find the source of a sound" is arguably a special case of Audio Enhancement's "Perception
(Hearing)", so one could argue a hearing-Perception resolution should also pick up a Spatial
Recognizer bonus. Matching is plain set membership instead — no hierarchy — because (a) nothing
establishes the containment as a rule rather than a reading, and (b) there is no legacy oracle to
check against: the legacy engine never auto-applies a conditional limit modifier at all. It builds a
`LimitModifier` object carrying the condition *string* and displays it on the character sheet as a
note for the player to apply by hand. This engine going further (actually evaluating the condition)
is a deliberate improvement on that, but it means any judgment call about which conditions overlap
is ours alone, and WP40 owns making one if real content ever needs it.

`ESSENCE` improvements are unconditional by construction — Essence cost is not a per-test thing.
`resolve_essence()` raises rather than silently ignoring a condition it finds, so that stays true.
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

    **WP49 adds an 11th, `NATIVE_LANGUAGE_LIMIT`**, for `chummer5.engine.knowledge
    .create_knowledge_selection` -- another single character-wide total (one native-language cap
    per character), resolved against `_GLOBAL_TARGET` the same way the Limit trio already is. The
    Bilingual quality (`<bonus><nativelanguagelimit>1</nativelanguagelimit></bonus>`) is its first
    real producer -- see `chummer5.data.qualities`'s module docstring for why this bare-numeric-leaf
    shape reuses the same flat-bonus classification the Indomitable trio already established.
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
    NATIVE_LANGUAGE_LIMIT = auto()
    # WP109 (Phase X): the four character-level numbers Finding 6 of the phase file lists, each a
    # character-wide total resolved against the `""` sentinel like the Limits. `CM_OVERFLOW` adds
    # Overflow boxes; `CM_THRESHOLD` changes how many boxes make one -1 wound modifier (Low Pain
    # Tolerance); `CM_THRESHOLD_OFFSET` ignores boxes on both tracks before the first modifier (High
    # Pain Tolerance); `CM_SHARED_THRESHOLD_OFFSET` does the same from one shared pool (Damage
    # Compensators). `ARMOR` adds to the worn armor rating, `DAMAGE_RESISTANCE` adds dice to the
    # Body + Armor pool. Names mirror legacy `CMOverflow`/`CMThreshold`/`CMThresholdOffset`/
    # `CMSharedThresholdOffset`/`Armor`/`DamageResistance`.
    CM_OVERFLOW = auto()
    CM_THRESHOLD = auto()
    CM_THRESHOLD_OFFSET = auto()
    CM_SHARED_THRESHOLD_OFFSET = auto()
    ARMOR = auto()
    DAMAGE_RESISTANCE = auto()
    # WP110: the character's Notoriety (p. 368), fed from quality `<notoriety>` nodes.
    NOTORIETY = auto()
    # WP112: raises one attribute's natural *and* augmented maximum (target: the attribute code) --
    # Exceptional Attribute and Lucky. Legacy `MaximumModifier`.
    ATTRIBUTE_MAXIMUM = auto()
    # WP113: a percent surcharge on Lifestyle costs (Dwarf +20, Troll +100; later Dependents), and
    # extra melee Reach (Troll +1).
    LIFESTYLE_COST = auto()
    REACH = auto()
    # WP114: dice added to the Memory pool (LOG + WIL) -- Photographic Memory.
    MEMORY = auto()
    # WP115: dice-pool modifiers that are *not* rating changes, unlike `SKILL`. `SKILL_POOL`
    # targets a skill name (Loss of Confidence's -2); `SKILL_CATEGORY_POOL` targets a skill
    # category (Addiction's -2/-3 to Social Active skills). `SPECIALIZATION_DISABLED` > 0 on a
    # skill name means its specialization bonus doesn't apply (Loss of Confidence).
    SKILL_POOL = auto()
    SKILL_CATEGORY_POOL = auto()
    SPECIALIZATION_DISABLED = auto()
    # WP116: raises one skill's purchase cap (6 at creation) and its rating ceiling (12) --
    # Aptitude, target: the skill name. Legacy folds the same thing into `Skill.RatingMaximum`.
    SKILL_MAXIMUM = auto()
    # WP117: the purchase-rule qualities. Cost changes are *extra percent* (Uncouth's 200% cost is
    # +100), summed, so two sources combine additively. Targets are skill categories ("Social
    # Active"), except `SKILL_GROUP_DISABLED` (a group name, Incompetent's choice) and the two
    # augmentation ones (`""`). The rest are flags: any value > 0 switches the rule on.
    SKILL_CATEGORY_POINT_COST_PERCENT = auto()
    SKILL_CATEGORY_KARMA_COST_PERCENT = auto()
    SKILL_CATEGORY_SPECIALIZATION_KARMA_COST_PERCENT = auto()
    SKILL_GROUP_CATEGORY_KARMA_COST_PERCENT = auto()
    SKILL_GROUP_CATEGORY_DISABLED = auto()
    SKILL_GROUP_DISABLED = auto()
    SKILL_CATEGORY_DEFAULTING_BLOCKED = auto()
    CYBERWARE_ESSENCE_PERCENT = auto()
    BIOWARE_DISABLED = auto()


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
    prior source name here was added ahead of its first real user. WP45 adds a 7th: `BIOWARE`, for
    `chummer5.engine.bioware.apply_bioware_improvements` — a separate source from `CYBERWARE`
    despite both ever only granting an `ESSENCE`/`FLAT_BONUS`-shaped Improvement, so
    `ImprovementIndex.remove_source` can retract one without touching the other (e.g. a
    bioware-only re-purchase shouldn't also strip already-committed cyberware). WP47 adds an 8th:
    `FOCUS`, for `chummer5.engine.foci.apply_foci_improvements` — a bonded focus's `FLAT_BONUS`
    skill bonus, keyed by the focus's own catalog id (mirrors `CYBERWARE`/`BIOWARE`'s per-item
    `source_id` convention). WP48 adds a 9th: `MENTOR_SPIRIT`, for `chummer5.engine.qualities
    .apply_mentor_spirit_improvements` — a picked archetype's General/Magician/Adept `FLAT_BONUS`
    slots, kept distinct from `QUALITY` (even though the Mentor Spirit quality itself is what
    gates offering an archetype pick at all) so `ImprovementIndex.remove_source` can retract the
    archetype's own bonuses independently of the blanket "remove every `QUALITY`-sourced
    Improvement, then reapply `selection.qualities`" pass `_replace_committed_qualities` already
    does — that pass has no reason to know about `QualitySelection.mentor_spirit` at all.
    """

    METATYPE = auto()
    QUALITY = auto()
    PRIORITY = auto()
    TALENT = auto()
    ADEPT_POWER = auto()
    CYBERWARE = auto()
    BIOWARE = auto()
    FOCUS = auto()
    MENTOR_SPIRIT = auto()


class ResolutionContext(Enum):
    """One specific test/activity a value is being resolved *for* — the call-site context a
    conditional Improvement is evaluated against (WP39).

    Deliberately the smallest vocabulary that covers the four real conditional bonuses listed in
    the module docstring, not a general "kind of test" taxonomy. A resolution that passes no
    context at all (`context=None`, the default) is asking for the plain, unconditional value; that
    is what every call site written before WP39 asks for, and it is what a character sheet's
    headline Mental Limit figure should show.

    Add a member when a real bonus needs one, the same way `ImprovementType` grew.

    (Named `ResolutionContext` rather than the more natural `TestContext` — SR5 calls these "tests"
    — purely because pytest tries to *collect* any importable class whose name starts with `Test`,
    which turns every test module importing it into a `PytestCollectionWarning`. Don't rename it
    back.)
    """

    PERCEPTION_VISUAL = auto()
    PERCEPTION_HEARING = auto()
    # "Perception to find the source of a sound" -- narrower than PERCEPTION_HEARING, but not
    # modeled as a subset of it; see the module docstring's "no subsumption" paragraph.
    PERCEPTION_SOUND_SOURCE = auto()
    GYMNASTICS_JUMPING = auto()
    RUNNING_SPRINTING = auto()


# Which TestContexts satisfy each condition. Module-private: the mapping is reachable through
# `ImprovementCondition.contexts`, which is the supported way to read it.
_CONDITION_CONTEXTS: dict[ImprovementCondition, frozenset[ResolutionContext]]


class ImprovementCondition(Enum):
    """A named, hardcoded predicate restricting when an Improvement applies (WP39).

    One member per confirmed real `<condition>` string in the SR5 data — see the module docstring
    for the table mapping each to its item, its legacy key and its English text, and for why this is
    an `Enum` rather than a closure or a tagged union. This is **not** a general condition language:
    an unrecognized legacy condition string has no member here and its bonus stays
    `NOT_YET_SUPPORTED` at the data layer, exactly as an unrecognized `<bonus>` shape already does.
    """

    PERCEPTION_VISUAL_ONLY = "perception_visual_only"
    PERCEPTION_HEARING_ONLY = "perception_hearing_only"
    PERCEPTION_SOUND_SOURCE_ONLY = "perception_sound_source_only"
    JUMPING_OR_SPRINTING_ONLY = "jumping_or_sprinting_only"

    @property
    def contexts(self) -> frozenset[ResolutionContext]:
        """The `ResolutionContext`s that satisfy this condition. A set, not a single value, because
        Hydraulic Jacks' one condition covers two activities — see the module docstring.
        """
        return _CONDITION_CONTEXTS[self]

    def is_met(self, context: ResolutionContext | None) -> bool:
        """True when `context` is one this condition allows. `None` (no context supplied) never
        satisfies a condition: a resolution that doesn't say which test it is for gets the plain,
        unconditional value.
        """
        return context is not None and context in self.contexts


_CONDITION_CONTEXTS = {
    ImprovementCondition.PERCEPTION_VISUAL_ONLY: frozenset({ResolutionContext.PERCEPTION_VISUAL}),
    ImprovementCondition.PERCEPTION_HEARING_ONLY: frozenset({ResolutionContext.PERCEPTION_HEARING}),
    ImprovementCondition.PERCEPTION_SOUND_SOURCE_ONLY: frozenset(
        {ResolutionContext.PERCEPTION_SOUND_SOURCE}
    ),
    ImprovementCondition.JUMPING_OR_SPRINTING_ONLY: frozenset(
        {ResolutionContext.GYMNASTICS_JUMPING, ResolutionContext.RUNNING_SPRINTING}
    ),
}


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

    **`condition` (WP39) restricts *when* this improvement applies.** `None` — the default, and the
    value every Improvement this engine produced through WP38 carries — means "always," identical
    in every respect to the pre-WP39 behaviour. A non-`None` `ImprovementCondition` means the
    improvement is counted only by a `resolve()` call that supplies a matching
    `ResolutionContext`; see the module docstring for the design and for the four real bonuses this
    exists for. The
    condition is a compiled enum member chosen when the Improvement is constructed, never a string
    re-interpreted at read time.
    """

    improvement_type: ImprovementType
    target: str
    value: int
    source_type: ImprovementSource
    source_id: str
    rating: int = 1
    unique_name: str | None = None
    essence_value: Decimal | None = None
    condition: ImprovementCondition | None = None


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

    def resolve(
        self,
        improvement_type: ImprovementType,
        target: str,
        *,
        context: ResolutionContext | None = None,
    ) -> int:
        """Sum every *applicable* Improvement targeting `(improvement_type, target)`, with dedup.

        Improvements with `unique_name = None` all stack additively. Improvements sharing a
        non-`None` `unique_name` collapse to their single highest `value` first — SR5's "highest
        bonus wins" — then that one value is added to the total once per distinct `unique_name`.

        **`context` (WP39) selects which conditional Improvements count.** An Improvement with
        `condition=None` always counts, context or not. One with a condition counts only when
        `context` satisfies it. Omitting `context` therefore resolves the plain, unconditional
        value — byte-identical to this method's pre-WP39 behaviour for every existing call site,
        none of which passes one. Condition filtering happens **before** the `unique_name` dedup
        pass, so an inapplicable conditional Improvement can't win a dedup group it shouldn't be
        competing in.

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
            if imp.condition is not None and not imp.condition.is_met(context):
                continue
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

        Takes no `context` (WP39), because an Essence cost is not a per-test thing: whatever you had
        implanted costs what it costs during every test alike. A conditional `ESSENCE` Improvement
        raises rather than being silently counted or silently skipped — nothing produces one, and
        the two ways of "handling" it quietly are both wrong.
        """
        total = Decimal(0)
        for imp in self._index.get((ImprovementType.ESSENCE, target), ()):
            assert imp.essence_value is not None, (
                "ESSENCE improvement missing essence_value -- see Improvement's own docstring"
            )
            if imp.condition is not None:
                raise ValueError(
                    f"ESSENCE improvement from {imp.source_type.name}/{imp.source_id} carries "
                    f"condition {imp.condition.name}; Essence cost is unconditional by "
                    f"construction (see ImprovementIndex.resolve_essence's docstring)"
                )
            total += imp.essence_value
        return total
