"""Legacy `.chum5` import: turns WP4's raw-field `LegacyCharacter` into a real, buildable character
through this project's own machinery (WP11's `CharacterSave` + `build_character()`), for MVP-covered
content only. Read-only, one-way (legacy -> native), per the Project Overview's "Data & save format"
section — the new engine never needs to write legacy XML back out.

**Two different responses to "this file has content MVP doesn't model", not one.** WP3/WP8 already
established the precedent for one shape of this problem (a quality whose `<bonus>` isn't a flat
skill/attribute bonus is excluded from the *offered* catalog, not silently mis-applied); this module
extends the same "exclude cleanly, never half-apply" discipline to *importing an existing
character's selections*, but splits it into two tiers by how much it actually distorts the imported
result:

- **Excluded and reported, not fatal.** A quality the character already has that isn't one of WP8's
  3 MVP-offered (`FLAT_BONUS`) qualities (e.g. Yeti's own Technomancer/Infirm/Impassive/Paranoia/
  Faceless/Data Anomaly — none overlap the offered catalog, confirmed in WP9/WP10) is dropped from
  the imported `CharacterSave`, and its name is collected in `ImportResult.dropped_qualities` so the
  caller can show the player exactly what didn't come across, instead of the import silently
  producing a character with fewer qualities than it should have with no indication why. Same
  treatment for a skill whose `<suid>` doesn't resolve against the loaded skill catalog
  (`ImportResult.dropped_skills`) — in practice this doesn't fire for any curated fixture (every
  `skills.xml` entry is `source == "SR5"`, so every legitimate active-skill `<suid>` resolves), but
  the reporting exists for the same "don't let something vanish with no trace" reason. **WP28**
  extends this same treatment to a Magician's spells (`ImportResult.dropped_spells` — a spell has no
  chargen-time computed effect, so dropping one that isn't `source == "SR5"` loses nothing an
  MVP-covered value depends on, mirroring the quality/skill precedent exactly) and an Adept's powers
  (`ImportResult.dropped_powers` — a power not in `mvp_power_catalog` (non-SR5-sourced, or SR5 but
  `NOT_YET_SUPPORTED`) is dropped the same way an unsupported quality is, not half-applied).
- **Blocking, itemized, fatal.** Content that would make an *already-imported* value silently wrong,
  not just incomplete, is rejected outright via `UnsupportedLegacyCharacterError` before any
  selection is built at all: a non-Priority build method (MVP's engine only understands
  priority-letter budgets — a SumToTen character's `<priority*>` fields are mostly empty per WP4's
  own finding, so there's no budget to validate against), a non-`Standard` `<gameplayoption>` (WP2's
  `load_priorities()` only loads the Standard resources table, so a Prime Runner/Street Level
  character's nuyen budget would silently resolve to the *Standard* table's number for the same
  letter — wrong, not just incomplete), cyberware/bioware presence (WP10's own finding: MVP's
  `BASE_ESSENCE = 6` constant is only valid for an augmentation-free character — importing one with
  cyberware and still assuming Essence 6 would silently corrupt Social Limit), a metavariant (out of
  MVP scope per WP6's metatype filter -- the base metatype's attribute ranges the rest of the import
  would use don't apply to it), and (WP20) a primary Lifestyle that's either missing entirely or not
  one of the 6 core-rulebook starting tiers `chummer5.data.lifestyle` offers -- silently defaulting
  to a tier the character never actually chose (e.g. free "Street") would misrepresent a real nuyen
  spend, not just omit one, so this is blocking rather than excluded-and-reported like a dropped
  quality/skill. **WP28** replaces the old blanket "Magic is enabled" rejection with two narrower,
  itemized checks fired only when `legacy.magic_enabled`: a Talent codename outside this project's
  offered set (`chummer5.engine.magic.OFFERED_TALENT_CODENAMES` — Mystic Adept/Technomancer/A.I./
  Aspected Magician/etc. are all still unrepresentable, exactly as unbuildable as before, just with
  a precise reason now); and, Magician-specific, a tradition name that isn't one of the 2 SR5-core
  traditions this phase offers (Hermetic/Shamanic) — unlike a dropped quality, there is no sensible
  "import without a tradition" fallback for a Magician (`chummer5.engine.magic
  .create_magic_selection` itself requires one), so an unresolvable tradition blocks the whole
  import rather than being silently dropped. **Confirmed against this phase's own two real
  fixtures**: Miko (Elf Magician) hits exactly this second check — her tradition, Shinto, is
  `SG`-sourced, not one of the 2 offered — so she is *still* rejected after this WP, just with an
  honest, specific reason instead of a blanket one (see `spec/worklogs/WP28.md` for why this
  corrects the Implementation Plan's own more optimistic acceptance text). Wesson (Human Adept)
  needs no tradition at all and imports cleanly.
  `UnsupportedLegacyCharacterError.reasons` collects *every* blocking issue found in one pass, not
  just the first, so a caller gets one itemized report rather than a fix-one-rerun-find-the-next
  loop.

**Which `<lifestyle>` entry counts as "primary" (WP20).** The legacy save format has no explicit
"is this the primary Lifestyle" flag (confirmed: no such field exists anywhere in `Lifestyle.cs`,
only a general `LifestyleType.Standard` -- see `spec/rulebooks/learnings.md`'s WP20 entry). This
module treats the *first* `<lifestyle>` child in document order as primary, matching every one of
the 11 curated mundane fixtures (including `BLUE.chum5`, the only one with more than one entry --
its in-scope Medium tier appears first, its out-of-scope `RF`-sourced "Bolt Hole" second). A
character's other, non-primary lifestyles (if any) are simply not imported -- consistent with the
core rulebook's own framing of them as optional extras beyond the one mandatory primary choice.

**Deliberately not blocking: `<resenabled>True</resenabled>` (Resonance/Technomancer).** This is the
one place this module's scope cut doesn't match the Project Overview's "no magic/resonance" MVP
framing literally. `Yeti-#ffffff2.chum5` — this project's sole `buildmethod == Priority` fixture and
therefore the only real corpus member this import path can exercise past the build-method gate — is
itself a Technomancer (`resenabled == True`). WP6-WP10 already set this precedent repeatedly: they
build a `Character` from Yeti's data by simply never consuming anything Resonance-specific (RES
isn't in `ALLOCATABLE_ATTRIBUTES`, no Resonance-linked skill gets special handling, the
Technomancer quality isn't MVP-offered so it's excluded the same as any other unsupported quality).
Import follows the same rule rather than inventing a stricter one Yeti itself couldn't pass:
nothing about a Technomancer's *mundane-shaped* subset of data (metatype, primary attributes,
active skills, karma, nuyen, contacts) is silently wrong by ignoring Resonance — unlike cyberware,
there's no MVP-computed value Resonance content would corrupt if left unconsumed.

**Import validates by actually building, not just by shape.** `import_chum5`/
`import_legacy_character` call straight into WP11's `build_character()` before returning, so
"successfully imports" means "this `CharacterSave` reconstructs into a real `Character` (carrying
its own `skill_allocation`/`quality_selection`/`contact_selection`/`resources_selection`, per WP18's
fold) that passes every one of `create_*`'s own validations" — not merely "the fields were
extracted into the right shape." Any `create_*` rejection (e.g. a corpus file with a real rules
violation this module's own checks don't anticipate) surfaces as `build_character`'s own
`ValueError`, unchanged; this module does not catch or reinterpret it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from chummer5.data.lifestyle import STARTING_TIER_NAMES, LifestyleTier
from chummer5.data.metatypes import Metatype
from chummer5.data.powers import Power
from chummer5.data.priorities import PriorityTable
from chummer5.data.qualities import Quality
from chummer5.data.skills import Skill
from chummer5.data.spells import Spell
from chummer5.data.traditions import Tradition
from chummer5.engine.character import ALLOCATABLE_ATTRIBUTES, Character, sr5_metatypes
from chummer5.engine.magic import OFFERED_TALENT_CODENAMES, mvp_power_catalog
from chummer5.engine.qualities import mvp_quality_catalog
from chummer5.engine.resources import Contact
from chummer5.io.legacy_chum5 import LegacyCharacter, load_chum5, priority_letter
from chummer5.io.save_format import (
    DEFAULT_TALENT_CODENAME,
    DEFAULT_TALENT_LETTER,
    CharacterSave,
    build_character,
    create_character_save,
)

# load_priorities() only loads the Standard prioritytable's Resources category (see
# chummer5.data.priorities); a character built under a different gameplay option would silently
# resolve its nuyen budget against the wrong table for the same letter if this weren't checked.
STANDARD_GAME_OPTION = "Standard"

PRIORITY_BUILD_METHOD = "Priority"


class UnsupportedLegacyCharacterError(ValueError):
    """A `.chum5` file uses content MVP's engine cannot represent at all.

    `reasons` enumerates every blocking issue found in one pass (see module docstring) -- itemized,
    not just the first one hit, so a caller doesn't have to fix-and-retry one at a time.
    """

    def __init__(self, reasons: tuple[str, ...]) -> None:
        self.reasons = reasons
        super().__init__("cannot import: " + "; ".join(reasons))


def _blocking_reasons(
    legacy: LegacyCharacter, traditions: tuple[Tradition, ...]
) -> tuple[str, ...]:
    reasons = []
    if legacy.build_method != PRIORITY_BUILD_METHOD:
        reasons.append(
            f"build method {legacy.build_method!r} is not Priority-built; MVP import only "
            "supports Priority-built characters"
        )
    if legacy.game_option != STANDARD_GAME_OPTION:
        reasons.append(
            f"gameplay option {legacy.game_option!r} is not Standard; MVP's priority tables are "
            "Standard-only"
        )
    if legacy.magic_enabled:
        codename = legacy.priorities.talent_codename
        if codename not in OFFERED_TALENT_CODENAMES:
            reasons.append(
                f"Talent option {codename!r} is not supported; MVP magic chargen only supports "
                "Magician and Adept"
            )
        elif codename == "Magician":
            tradition_names = {t.name for t in traditions}
            if legacy.tradition_name not in tradition_names:
                reasons.append(
                    f"tradition {legacy.tradition_name!r} is not one of the SR5-core traditions "
                    "MVP offers (Hermetic, Shamanic)"
                )
    if legacy.has_cyberware:
        reasons.append(
            "character has cyberware/bioware; MVP does not model Essence-reducing augmentation"
        )
    if legacy.metavariant is not None:
        reasons.append(f"metavariant {legacy.metavariant!r} is out of MVP scope")
    karma_bought_attributes = sorted(
        code
        for code in ALLOCATABLE_ATTRIBUTES
        if code in legacy.attributes and legacy.attributes[code].karma > 0
    )
    if karma_bought_attributes:
        reasons.append(
            "character has Karma-bought attribute points beyond the priority budget on "
            f"{', '.join(karma_bought_attributes)}; MVP's engine only models priority-derived "
            "attribute points, not chargen-time Karma spend on attributes"
        )
    if not legacy.lifestyles:
        reasons.append(
            "no primary Lifestyle found; SR5 requires selecting one at character creation"
        )
    elif legacy.lifestyles[0].base_lifestyle not in STARTING_TIER_NAMES:
        reasons.append(
            f"primary Lifestyle {legacy.lifestyles[0].base_lifestyle!r} is not one of the 6 "
            "core-rulebook starting tiers MVP offers"
        )
    return tuple(reasons)


@dataclass(frozen=True)
class ImportResult:
    """A successfully imported legacy character: the native `CharacterSave`, the `Character` that
    save reconstructs into (proving the import is actually buildable, not just shaped right; see
    `chummer5.io.save_format.build_character` -- `Character` itself carries the resulting
    `skill_allocation`/`quality_selection`/`contact_selection`/`resources_selection` since WP18's
    fold, so no separate wrapper type is needed here either), and what got excluded along the way
    -- see module docstring for the excluded-vs-blocking split.
    """

    save: CharacterSave
    built: Character
    dropped_qualities: tuple[str, ...]
    dropped_skills: tuple[str, ...]
    dropped_spells: tuple[str, ...]  # WP28: non-SR5-sourced spells, dropped and reported
    dropped_powers: tuple[str, ...]  # WP28: non-SR5-sourced or NOT_YET_SUPPORTED powers, likewise


def import_legacy_character(
    legacy: LegacyCharacter,
    *,
    metatypes: tuple[Metatype, ...],
    priorities: PriorityTable,
    skills: tuple[Skill, ...],
    qualities: tuple[Quality, ...],
    lifestyles: tuple[LifestyleTier, ...],
    traditions: tuple[Tradition, ...] = (),
    spells: tuple[Spell, ...] = (),
    powers: tuple[Power, ...] = (),
) -> ImportResult:
    """Convert an already-parsed `LegacyCharacter` into a validated, built native character.

    Raises `UnsupportedLegacyCharacterError` for blocking content (see module docstring). Excludes
    (and reports via `ImportResult.dropped_*`) qualities, skills, spells, and powers MVP's engine
    doesn't otherwise model, then builds the result through WP11's `build_character()` so a caller
    gets back a ready-to-use character, not just a save file.

    `traditions`/`spells`/`powers` default to `()`, mirroring `build_character`'s own WP28 defaults
    -- a Mundane legacy character (`legacy.magic_enabled is False`, every fixture this project
    imported before WP28) never touches any of the three.
    """
    reasons = _blocking_reasons(legacy, traditions)
    if reasons:
        raise UnsupportedLegacyCharacterError(reasons)

    # `.base` only, not `+ legacy_attribute.karma` -- `_blocking_reasons` above already rejects any
    # character with a nonzero `karma` on an allocatable attribute (a real, separately-discovered
    # WP28 finding: MVP's `create_character` only validates priority-derived points against the
    # priority budget, with no accommodation for chargen-time Karma spend on top of it -- see this
    # WP's own worklog), so `karma` is always `0` for every attribute reaching this point; keeping
    # both terms here would silently reintroduce the bug this WP's blocking check exists to prevent.
    attribute_points = {
        code: legacy.attributes[code].base
        for code in ALLOCATABLE_ATTRIBUTES
        if code in legacy.attributes
    }

    # Same allocation logic WP6/WP7/WP10's fixture tests already validated against Yeti: a skill
    # only contributes its own base points if its group wasn't also bought (the "strict skill
    # groups" rule `create_skill_allocation` enforces) and its <suid> resolves to a known skill.
    skills_by_id = {s.id: s for s in skills}
    bought_groups = {g.name: g.base for g in legacy.skill_groups if g.base > 0}
    skill_points: dict[str, int] = {}
    dropped_skills: list[str] = []
    for legacy_skill in legacy.skills:
        if legacy_skill.base <= 0:
            continue
        skill = skills_by_id.get(legacy_skill.suid)
        if skill is None:
            dropped_skills.append(legacy_skill.suid)
            continue
        if skill.skill_group is not None and skill.skill_group in bought_groups:
            continue
        skill_points[skill.id] = legacy_skill.base

    # WP23: `<qualitysource>Metatype</qualitysource>` isn't exclusively "this metatype's real
    # racial quality" in the legacy data -- it's the broader "auto-granted at character creation,
    # not manually picked from the quality list" tag, which also covers e.g. a Talent selection's
    # Technomancer/Adept/Magician quality (confirmed directly: `Yeti-#ffffff2.chum5`'s own
    # Technomancer quality is `qualitysource=Metatype` despite Yeti being Human, whose
    # `qualities_positive`/`qualities_negative` are both empty). Only skip (silently, since
    # `build_character` re-derives and re-grants it) a `Metatype`-sourced quality whose *name*
    # actually matches this character's real metatype's racial-quality list -- anything else
    # `qualitysource=Metatype` still flows through the normal offered/dropped check below, so it
    # doesn't just vanish with no trace (the module docstring's own rule).
    metatype_obj = next(
        (m for m in sr5_metatypes(metatypes) if m.name == legacy.metatype),
        None,
    )
    metatype_quality_names = (
        frozenset((*metatype_obj.qualities_positive, *metatype_obj.qualities_negative))
        if metatype_obj is not None
        else frozenset[str]()
    )

    offered_qualities = {q.id: q for q in mvp_quality_catalog(qualities)}
    quality_ids: list[str] = []
    dropped_qualities: list[str] = []
    for legacy_quality in legacy.qualities:
        if (
            legacy_quality.quality_source == "Metatype"
            and legacy_quality.name in metatype_quality_names
        ):
            continue
        if legacy_quality.id in offered_qualities:
            quality_ids.append(legacy_quality.id)
        else:
            dropped_qualities.append(legacy_quality.name)

    contacts = tuple(
        Contact(name=c.name, connection=c.connection, loyalty=c.loyalty, free=c.free)
        for c in legacy.contacts
    )

    # WP28: Talent/tradition/free-skill grant. Only trust the legacy save's own `talent_letter`/
    # `talent_codename` (and its free-skill grant) when `legacy.magic_enabled` -- a Resonance
    # character (Technomancer/A.I.) carries a real, non-"Mundane" `talent_codename` at a letter that
    # doesn't even offer "Mundane" as an option (e.g. Yeti-#ffffff2.chum5's own "Technomancer" at
    # letter B) plus a Resonance-flavored free-skill grant, despite `magic_enabled` being `False`,
    # and none of it is something `chummer5.engine.magic` models at all (Resonance is out of scope
    # per the Project Overview; see `chummer5.io.legacy_import`'s own module docstring on
    # `resonance_enabled` not being blocking). Forcing both fields to their Mundane defaults for any
    # non-magic-enabled character is the same "ignore Resonance content, don't half-model it" rule
    # WP6-WP10 already established for Yeti, just applied to this WP's new Talent fields instead of
    # silently working by never reading them. `_blocking_reasons` above already guarantees a
    # Magician's tradition resolves against `traditions` (there's no sensible "import without a
    # tradition" fallback), so that lookup cannot fail here.
    if legacy.magic_enabled:
        talent_letter = priority_letter(legacy.priorities.talent)
        talent_codename = legacy.priorities.talent_codename
    else:
        talent_letter = DEFAULT_TALENT_LETTER
        talent_codename = DEFAULT_TALENT_CODENAME
    tradition_id = None
    if talent_codename == "Magician":
        tradition_id = next(t.id for t in traditions if t.name == legacy.tradition_name)

    # Every name here comes from `priorities.xml`'s own Talent free-skill grant, cross-referencing
    # `chummer5.data.skills.load_skills()` -- a catalog that's already 100% SR5-sourced (WP3), so an
    # unresolvable name would mean a real data-integrity bug, not an expected edge case (mirrors
    # `chummer5.engine.qualities.resolve_metatype_qualities`'s identical "raise, don't drop"
    # reasoning for the same kind of fixed, catalog-guaranteed cross-reference). Skipped entirely
    # for a non-magic-enabled character -- see the paragraph above.
    skills_by_name = {s.name: s for s in skills}
    granted_skill_ids: list[str] = []
    if legacy.magic_enabled:
        for bonus_skill_name in legacy.priorities.talent_bonus_skills:
            bonus_skill = skills_by_name.get(bonus_skill_name)
            if bonus_skill is None:
                raise ValueError(
                    f"Talent free-skill grant name {bonus_skill_name!r} does not resolve against "
                    "the SR5 skill catalog"
                )
            granted_skill_ids.append(bonus_skill.id)

    # WP28: spells -- excluded-and-reported like a dropped quality/skill, never fatal (a spell has
    # no chargen-time computed effect; see chummer5.engine.magic's module docstring).
    spells_by_name = {s.name: s for s in spells}
    spell_ids: list[str] = []
    dropped_spells: list[str] = []
    for legacy_spell in legacy.spells:
        spell = spells_by_name.get(legacy_spell.name)
        if spell is None:
            dropped_spells.append(legacy_spell.name)
        else:
            spell_ids.append(spell.id)

    # WP28: powers -- same excluded-and-reported treatment, restricted to `mvp_power_catalog`
    # (FLAT_BONUS only; a non-SR5-sourced or NOT_YET_SUPPORTED power is dropped, not half-applied).
    # A `select_attribute`-shaped power (only Improved Physical Attribute among the offered set)
    # needs its purchased target too -- carried in the legacy save's own `<extra>` field; if that
    # doesn't resolve to one of the power's real eligible attributes, the whole pick is dropped
    # rather than guessed at.
    offered_powers_by_name = {p.name: p for p in mvp_power_catalog(powers)}
    power_picks: list[tuple[str, int, str | None]] = []
    dropped_powers: list[str] = []
    for legacy_power in legacy.powers:
        power = offered_powers_by_name.get(legacy_power.name)
        if power is None:
            dropped_powers.append(legacy_power.name)
            continue
        select_attribute_bonus = next(
            (fb for fb in power.flat_bonuses if fb.target_kind == "select_attribute"), None
        )
        selected_attribute: str | None = None
        if select_attribute_bonus is not None:
            if legacy_power.extra not in select_attribute_bonus.attribute_options:
                dropped_powers.append(legacy_power.name)
                continue
            selected_attribute = legacy_power.extra
        power_picks.append((power.id, legacy_power.rating, selected_attribute))

    save = create_character_save(
        metatype_name=legacy.metatype,
        heritage_letter=priority_letter(legacy.priorities.heritage),
        attributes_letter=priority_letter(legacy.priorities.attributes),
        attribute_points=attribute_points,
        skills_letter=priority_letter(legacy.priorities.skills),
        skill_points=skill_points,
        group_points=bought_groups,
        quality_ids=quality_ids,
        contacts=contacts,
        resources_letter=priority_letter(legacy.priorities.resources),
        # No general gear-catalog import -- WP9's STARTER_GEAR_CATALOG is a deliberately minimal
        # stub, and WP10 already found Yeti's real gear purchases aren't reconstructable from it.
        # Not "silently dropped": MVP's own scope explicitly excludes "the full gear catalog beyond
        # a basic purchase flow" (Project Overview), so there is nothing this import path was ever
        # going to represent here.
        gear_names=(),
        # WP20: unlike gear, the lifestyle catalog *is* a complete, real SR5 catalog (all 6
        # starting tiers), so the character's actual primary Lifestyle is faithfully
        # reconstructable -- `_blocking_reasons` above already rejected anything this can't
        # represent (missing, or not one of the 6 tiers).
        lifestyle_tier_name=legacy.lifestyles[0].base_lifestyle,
        lifestyle_months=legacy.lifestyles[0].months,
        talent_letter=talent_letter,
        talent_codename=talent_codename,
        tradition_id=tradition_id,
        granted_skill_ids=granted_skill_ids,
        spell_ids=spell_ids,
        power_picks=power_picks,
    )

    built = build_character(
        save,
        metatypes=metatypes,
        priorities=priorities,
        skills=skills,
        qualities=qualities,
        lifestyles=lifestyles,
        traditions=traditions,
        spells=spells,
        powers=powers,
    )

    return ImportResult(
        save=save,
        built=built,
        dropped_qualities=tuple(dropped_qualities),
        dropped_skills=tuple(dropped_skills),
        dropped_spells=tuple(dropped_spells),
        dropped_powers=tuple(dropped_powers),
    )


def import_chum5(
    path: Path,
    *,
    metatypes: tuple[Metatype, ...],
    priorities: PriorityTable,
    skills: tuple[Skill, ...],
    qualities: tuple[Quality, ...],
    lifestyles: tuple[LifestyleTier, ...],
    traditions: tuple[Tradition, ...] = (),
    spells: tuple[Spell, ...] = (),
    powers: tuple[Power, ...] = (),
) -> ImportResult:
    """Parse a `.chum5` file (WP4's `load_chum5`) and import it (see `import_legacy_character`)."""
    return import_legacy_character(
        load_chum5(path),
        metatypes=metatypes,
        priorities=priorities,
        skills=skills,
        qualities=qualities,
        lifestyles=lifestyles,
        traditions=traditions,
        spells=spells,
        powers=powers,
    )
