"""Reference data for Knowledge/Language skills (WP49) -- category list, linked attributes, and
rulebook-suggested example names.

Unlike every other loader under `chummer5.data`, this module parses no XML catalog: Knowledge and
Language skills are freeform by rulebook design (core rulebook p. 88, "COMMON KNOWLEDGE SKILLS IN
2075" sidebar: the examples given are illustrative, not exhaustive -- "you're free to take
practically any Knowledge skill you can think up for your character," p. 89). This module exists
only to surface the rulebook's own suggested examples/categories in the picker UI as hints, never to
constrain what a player can type -- see `chummer5.engine.knowledge.create_knowledge_selection` for
the (deliberately permissive) validation that actually gates a submission.

**Category names match `legacy/Chummer/data/skills.xml`'s own `<categories type="knowledge">` list
exactly** (`Academic`, `Interest`, `Language`, `Professional`, `Street`) -- confirmed directly
against that file rather than the rulebook prose, which pluralizes "Interests" in running text (p.
88-89) but never appears as data anywhere. `Language` is deliberately not one of the 4
`KnowledgeCategory` entries below: it's modeled as its own `LanguageSkillPick` shape in
`chummer5.engine.knowledge` (native-language handling has no equivalent for the other 4 categories),
matching the legacy schema's own even split (4 Knowledge categories + Language as a 5th, distinct
category) -- see `spec/rulebooks/learnings.md`'s WP49 entry for the citations this was checked
against.
"""

from __future__ import annotations

from dataclasses import dataclass

# Core rulebook p. 89, "KNOWLEDGE CATEGORY EXAMPLES" table -- LINKED ATTRIBUTE column, cross-checked
# against skills.xml's <categories type="knowledge"> list (see module docstring).
LOGIC = "LOG"
INTUITION = "INT"


@dataclass(frozen=True)
class KnowledgeCategory:
    name: str  # matches skills.xml's <category type="knowledge"> text exactly
    linked_attribute: str  # "LOG" or "INT"
    examples: tuple[str, ...]  # rulebook-suggested names; not exhaustive, not enforced


# Core rulebook p. 89 "KNOWLEDGE CATEGORY EXAMPLES" table, examples column split on ", ".
KNOWLEDGE_CATEGORIES: tuple[KnowledgeCategory, ...] = (
    KnowledgeCategory(
        name="Academic",
        linked_attribute=LOGIC,
        examples=(
            "Biology",
            "Medicine",
            "Magic Theory",
            "Politics",
            "Philosophy",
            "Literature",
            "History",
            "Music",
            "Parabotany",
            "Parazoology",
        ),
    ),
    KnowledgeCategory(
        name="Interest",
        linked_attribute=INTUITION,
        examples=(
            "Current Simsense Movies",
            "Popular Trideo Shows",
            "20th Century Trivia",
            "Elven Wine",
            "Urban Brawl",
            "Combat Biking",
            "Pop Music",
        ),
    ),
    KnowledgeCategory(
        name="Professional",
        linked_attribute=LOGIC,
        examples=("Journalism", "Business", "Law", "Military Service"),
    ),
    KnowledgeCategory(
        name="Street",
        linked_attribute=INTUITION,
        examples=("Gang Identification", "Criminal Organizations", "Smuggling Routes", "Fences"),
    ),
)

KNOWLEDGE_CATEGORY_NAMES: tuple[str, ...] = tuple(c.name for c in KNOWLEDGE_CATEGORIES)
_CATEGORY_BY_NAME = {c.name: c for c in KNOWLEDGE_CATEGORIES}

# Core rulebook p. 89: "Language skills use Intuition as their linked Attribute" -- confirmed
# against skills.xml's own <attribute> for the handful of individually-named Language skills that
# appear there too (Sperethiel, Or'zet). Every Language pick uses this attribute, not a per-entry
# lookup the way the 4 KnowledgeCategory entries above need one.
LANGUAGE_LINKED_ATTRIBUTE = INTUITION

# Core rulebook p. 88, "COMMON LANGUAGES IN 2075" sidebar -- suggested names only, not an enforced
# catalog (see module docstring).
SUGGESTED_LANGUAGES: tuple[str, ...] = (
    "Sperethiel",
    "Or'zet",
    "English",
    "Japanese",
    "Mandarin",
    "Russian",
    "French",
    "Italian",
    "German",
    "Aztlaner Spanish",
    "Spanish",
    "Lakota",
    "Dakota",
    "Diné (Navajo)",
)


def knowledge_category(name: str) -> KnowledgeCategory:
    """Look up one of the 4 `KNOWLEDGE_CATEGORIES` by name, raising `ValueError` for anything else
    (including `"Language"` -- see module docstring for why that's a separate mechanism).
    """
    category = _CATEGORY_BY_NAME.get(name)
    if category is None:
        raise ValueError(
            f"not a knowledge-skill category: {name!r} (expected one of "
            f"{KNOWLEDGE_CATEGORY_NAMES})"
        )
    return category
