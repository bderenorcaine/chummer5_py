"""Hand-authored synthetic whole-character fixtures (Phase S / WP72+).

Each fixture is a `SyntheticCharacter` (see `synthetic.py`) whose `expected` values are hand-derived
from the rulebook / `priorities.xml` / legacy C#, with an inline `citations` entry for every one.
WP72 lands the substrate plus the single reference fixture below; WP73-76 append their
interaction-covering fixtures here (cyberware/bioware, magician+cyberware, leftover-Karma,
Sum-to-Ten) as they extend the harness.

All figures below are cross-checked as follows:
- Priority budgets: `legacy/Chummer/data/priorities.xml` (Attributes A = 24 points; Skills B = 36
  skill + 5 group points; Heritage C / Human = 5 special-attribute points; Resources D = 50000¥).
- Human attribute ranges: `metatypes.xml` — every primary attribute 1-6, EDG 2-7.
- Derived-stat formulas: `spec/rulebooks/learnings/phase-d.md` (WP10), mirroring
  `chummer5.engine.derived`'s own docstring citations to `Character.cs`'s
  `LimitPhysical`/`LimitMental`/`LimitSocial`/`PhysicalCM`/`StunCM`/`InitiativeValue`.
- Catlike's +2 Sneaking: `qualities.xml` (`<bonus>` grants `skillcategory`/skill bonus; WP8/WP22
  classify it `FLAT_BONUS`), karma 7. Simsense Vertigo: `qualities.xml`, Negative, -5 karma.
- Karma ledger: core rulebook p.64 "start with 25 Karma" (`STARTING_KARMA`); qualities net signed.
"""

from __future__ import annotations

from tests.fixtures.synthetic import SyntheticCharacter

# --------------------------------------------------------------------------------------------------
# WP72 reference fixture — a full mundane Human Priority build.
#
# Priorities (Talent forced to E, mundane): Attributes A, Skills B, Heritage C, Resources D.
#
# Attribute-point spend (Attributes A = 24 primary points, all spent):
#   BOD +3, AGI +4, REA +3, STR +2, CHA +2, INT +4, LOG +3, WIL +3  = 24
#   EDG +2 (from Heritage C / Human's 5 special-attribute points)
# Resulting attribute values (Human min 1 primary, EDG min 2):
#   BOD 4, AGI 5, REA 4, STR 3, CHA 3, INT 5, LOG 4, WIL 4, EDG 4
#
# Skills (Skills B = 36 skill + 5 group points):
#   Firearms group = 5 -> Automatics rating 5
#   Sneaking (Stealth group, unbought) 3 pts -> rating 3, +2 Catlike = 5
#   Hacking (Cracking group, unbought) 3 pts -> rating 3
#   Perception (no group) 2 pts + "Visual" specialization (1 pt)
#   skill points used: 3 + 3 + 2 + 1(spec) = 9 <= 36 ; group points: 5 <= 5
#
# Qualities: Catlike (+7, +2 Sneaking) and Simsense Vertigo (-5) -> net +2 karma spent.
# --------------------------------------------------------------------------------------------------

REFERENCE_MUNDANE_FIXTURE = SyntheticCharacter(
    name="WP72 reference — mundane Human Priority build",
    metatype="Human",
    heritage_letter="C",
    attributes_letter="A",
    skills_letter="B",
    resources_letter="D",
    attribute_points={
        "BOD": 3,
        "AGI": 4,
        "REA": 3,
        "STR": 2,
        "CHA": 2,
        "INT": 4,
        "LOG": 3,
        "WIL": 3,
        "EDG": 2,
    },
    skill_points={"Sneaking": 3, "Hacking": 3, "Perception": 2},
    group_points={"Firearms": 5},
    specializations={"Perception": "Visual"},
    qualities=("Catlike", "Simsense Vertigo"),
    expected={
        # Attribute totals: metatype minimum + points spent.
        "attr:BOD": 4,
        "attr:AGI": 5,
        "attr:REA": 4,
        "attr:STR": 3,
        "attr:CHA": 3,
        "attr:INT": 5,
        "attr:LOG": 4,
        "attr:WIL": 4,
        "attr:EDG": 4,
        # Skill ratings (group / individual + Catlike improvement).
        "rating:Automatics": 5,
        "rating:Sneaking": 5,
        "rating:Hacking": 3,
        "rating:Perception": 2,
        # Dice pools: rating + linked attribute (+2 if specialized).
        "pool:Automatics": 10,  # 5 + AGI 5
        "pool:Sneaking": 10,  # 5 + AGI 5
        "pool:Hacking": 7,  # 3 + LOG 4
        "pool:Perception": 9,  # 2 + INT 5 + 2 (Visual specialization)
        # Derived stats.
        "initiative": 9,  # REA 4 + INT 5
        "initiative_dice": 1,
        "limit:physical": 5,  # ceil((STR*2 + BOD + REA)/3) = ceil((6+4+4)/3) = ceil(14/3)
        "limit:mental": 6,  # ceil((LOG*2 + INT + WIL)/3) = ceil((8+5+4)/3) = ceil(17/3)
        "limit:social": 6,  # ceil((CHA*2 + WIL + ceil(ESS))/3) = ceil((6+4+6)/3) = ceil(16/3)
        "cm:physical": 10,  # 8 + ceil(BOD/2) = 8 + 2
        "cm:stun": 10,  # 8 + ceil(WIL/2) = 8 + 2
        "essence": 6,  # no cyberware/bioware
        # Karma ledger: Catlike +7, Simsense Vertigo -5 -> net +2 spent of the 25 starting.
        "karma_spent": 2,
        "karma_remaining": 23,
    },
    citations={
        "attr:BOD": "priorities.xml Attributes A = 24 pts; metatypes.xml Human BOD min 1 (+3)",
        "attr:AGI": "priorities.xml Attributes A; Human AGI min 1 (+4)",
        "attr:REA": "priorities.xml Attributes A; Human REA min 1 (+3)",
        "attr:STR": "priorities.xml Attributes A; Human STR min 1 (+2)",
        "attr:CHA": "priorities.xml Attributes A; Human CHA min 1 (+2)",
        "attr:INT": "priorities.xml Attributes A; Human INT min 1 (+4)",
        "attr:LOG": "priorities.xml Attributes A; Human LOG min 1 (+3)",
        "attr:WIL": "priorities.xml Attributes A; Human WIL min 1 (+3)",
        "attr:EDG": "priorities.xml Heritage C/Human = 5 special pts; Human EDG min 2 (+2)",
        "rating:Automatics": "priorities.xml Skills B = 5 group pts -> Firearms group rating 5",
        "rating:Sneaking": "Skills B skill pts; 3 base + 2 Catlike improvement (qualities.xml)",
        "rating:Hacking": "Skills B skill pts; 3 base, Cracking group unbought",
        "rating:Perception": "Skills B skill pts; 2 base",
        "pool:Automatics": "learnings/phase-d.md (WP7 dice pool): rating 5 + AGI 5",
        "pool:Sneaking": "learnings/phase-d.md: rating 5 + AGI 5",
        "pool:Hacking": "learnings/phase-d.md: rating 3 + LOG 4",
        "pool:Perception": "learnings/phase-d.md: rating 2 + INT 5 + 2 spec (Visual)",
        "initiative": "learnings/phase-d.md (Character.cs InitiativeValue): REA 4 + INT 5",
        "initiative_dice": "learnings/phase-d.md: base 1 (no matrix/astral)",
        "limit:physical": "learnings/phase-d.md LimitPhysical: ceil((STR*2+BOD+REA)/3)=ceil(14/3)",
        "limit:mental": "learnings/phase-d.md LimitMental: ceil((LOG*2+INT+WIL)/3)=ceil(17/3)",
        "limit:social": "learnings/phase-d.md LimitSocial: ceil((CHA*2+WIL+ceilESS)/3)=ceil(16/3)",
        "cm:physical": "learnings/phase-d.md (PhysicalCM): 8 + ceil(BOD/2)",
        "cm:stun": "learnings/phase-d.md (StunCM): 8 + ceil(WIL/2)",
        "essence": "derived.py BASE_ESSENCE = 6 (metatypes.xml Human essmax 6); no augmentation",
        "karma_spent": "core rulebook p.64 (25 Karma); Catlike +7, Simsense Vertigo -5 -> net 2",
        "karma_remaining": "STARTING_KARMA 25 - karma_spent 2",
    },
)


# Every synthetic fixture, for the parametrized regression test. WP73-76 append their fixtures here.
SYNTHETIC_FIXTURES = (REFERENCE_MUNDANE_FIXTURE,)
