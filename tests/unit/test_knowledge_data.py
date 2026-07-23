"""Tests for `chummer5.data.knowledge` (WP49): category/attribute reference data, hand-checked
against `legacy/Chummer/data/skills.xml`'s own `<categories type="knowledge">` list and the core
rulebook's "KNOWLEDGE CATEGORY EXAMPLES" table (p. 89)."""

from __future__ import annotations

import pytest

from chummer5.data.knowledge import (
    KNOWLEDGE_CATEGORIES,
    KNOWLEDGE_CATEGORY_NAMES,
    LANGUAGE_LINKED_ATTRIBUTE,
    SUGGESTED_LANGUAGES,
    knowledge_category,
)


def test_four_knowledge_categories_match_skills_xml() -> None:
    # legacy/Chummer/data/skills.xml's <categories type="knowledge"> lists exactly 5 entries
    # (Academic, Interest, Language, Professional, Street) -- Language is modeled separately (see
    # module docstring), so only 4 remain here.
    assert KNOWLEDGE_CATEGORY_NAMES == ("Academic", "Interest", "Professional", "Street")
    assert len(KNOWLEDGE_CATEGORIES) == 4


def test_linked_attributes_match_rulebook_table() -> None:
    linked = {c.name: c.linked_attribute for c in KNOWLEDGE_CATEGORIES}
    assert linked == {
        "Academic": "LOG",
        "Interest": "INT",
        "Professional": "LOG",
        "Street": "INT",
    }


def test_every_category_has_suggested_examples() -> None:
    for category in KNOWLEDGE_CATEGORIES:
        assert len(category.examples) > 0


def test_language_linked_attribute_is_intuition() -> None:
    assert LANGUAGE_LINKED_ATTRIBUTE == "INT"


def test_suggested_languages_nonempty() -> None:
    assert len(SUGGESTED_LANGUAGES) > 0
    assert "English" in SUGGESTED_LANGUAGES


def test_knowledge_category_lookup() -> None:
    assert knowledge_category("Street").linked_attribute == "INT"


def test_knowledge_category_lookup_rejects_language() -> None:
    # Language is a separate mechanism (LanguageSkillPick), not one of the 4 lookup-able categories.
    with pytest.raises(ValueError, match="not a knowledge-skill category"):
        knowledge_category("Language")


def test_knowledge_category_lookup_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="not a knowledge-skill category"):
        knowledge_category("Nonsense")
