"""String catalogs for the UI's i18n key layer (WP101): `<locale>.xml` files in the legacy
`legacy/Chummer/lang/` schema -- `<chummer><strings><string><key/><text/></string>...` -- parsed
once into frozen `key -> text` mappings, the same "parse legacy XML once at startup" shape as every
other `chummer5.data` loader.

A locale's catalog is two layers, the second overriding the first:

1. **Legacy** -- `legacy/Chummer/lang/<locale>.xml`, which carries 2,767 English keys and real
   translations for de-de/fr-fr/ja-jp/pt-br/zh-cn. Reusing a legacy key where its text fits is
   how this project inherits those translations for free (see `src/chummer5/lang/README.md`).
   Legacy texts are WinForms control captions, so they are normalised on load: `&&` is an escaped
   literal `&` and a lone `&` marks a keyboard mnemonic, which a web page has no use for.
2. **Project** -- `src/chummer5/lang/<locale>.xml`, the same schema, holding the keys this project
   added itself (`Web_*`). Texts here are literal: no mnemonic convention applies.

A locale with neither file loads as an empty catalog; the caller's fallback (to English, then to a
visible missing-key marker -- see `chummer5.web.i18n`) is what handles it.

**Game-data terms (WP103)** come from a different legacy file, `<locale>_data.xml`: one
`<chummer file="skills.xml">` section per data file, translating that file's own entries. Two
shapes occur, and `load_data_terms` indexes both:

- an item -- `<skill><id>…</id><name>Pistols</name><translate>Pistolen</translate></skill>` --
  indexed by its GUID *and* by `(file, English name)`;
- an attribute-translated text -- `<category translate="Kampf-Aktionsfertigkeiten">Combat
  Active</category>`, also skill groups and specializations -- indexed by `(file, English text)`;
- an item's long-text field -- `<altadvantage>…</altadvantage>` on a mentor, the translation of
  its `<advantage>` -- indexed by `(GUID, field)`, the field being the tag minus `alt`.

These are display names only. Nothing here is ever an identity: see `chummer5.web.i18n.data_term`.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

LEGACY_LANG_DIR = Path(__file__).resolve().parents[3] / "legacy" / "Chummer" / "lang"
PROJECT_LANG_DIR = Path(__file__).resolve().parents[1] / "lang"

# A lone `&` before a character is a WinForms mnemonic marker; `&&` is an escaped literal `&`.
_MNEMONIC = re.compile(r"&(&)|&(?=\S)")


def normalise_winforms_text(text: str) -> str:
    """`"&Add && More"` -> `"Add & More"`: drop mnemonic markers, unescape `&&`."""
    return _MNEMONIC.sub(lambda m: m.group(1) or "", text)


def load_string_file(path: Path) -> dict[str, str]:
    """Every `<string>` in one catalog file, as `{key: text}`. An entry with an empty `<text/>` is
    kept as `""` -- an intentionally blank string is a real translation, not a missing one."""
    root = ET.parse(path).getroot()
    strings: dict[str, str] = {}
    for entry in root.iter("string"):
        key = entry.findtext("key")
        if key:
            strings[key] = entry.findtext("text") or ""
    return strings


def load_locale_strings(
    locale: str,
    legacy_dir: Path = LEGACY_LANG_DIR,
    project_dir: Path = PROJECT_LANG_DIR,
) -> Mapping[str, str]:
    """`locale`'s whole catalog: the legacy layer (normalised) with the project layer over it."""
    strings: dict[str, str] = {}
    legacy = legacy_dir / f"{locale}.xml"
    if legacy.is_file():
        strings.update(
            (key, normalise_winforms_text(text)) for key, text in load_string_file(legacy).items()
        )
    project = project_dir / f"{locale}.xml"
    if project.is_file():
        strings.update(load_string_file(project))
    return MappingProxyType(strings)


@dataclass(frozen=True)
class DataTerms:
    """One locale's game-data translations (WP103): `by_id` maps a legacy GUID to
    `{English name: translation}`; `by_file` maps a data file's name to `{English text:
    translation}`; `fields` maps `(GUID, field)` to a translated long-text field (a mentor's
    `advantage`, …).

    **`by_id` is keyed by name too because the legacy files reuse GUIDs.** Every `_data.xml`
    carries a handful of ids under two English names -- de-de has 26, e.g. the Pistols skill's id
    also on "Handguns" (translated "Handfeuerwaffen", not the SR5 skill's "Pistolen") -- so an id
    alone can name the wrong entry. See `chummer5.web.i18n.data_term` for how a lookup picks."""

    by_id: Mapping[str, Mapping[str, str]]
    by_file: Mapping[str, Mapping[str, str]]
    fields: Mapping[tuple[str, str], str]


EMPTY_DATA_TERMS = DataTerms(MappingProxyType({}), MappingProxyType({}), MappingProxyType({}))

# `alt*` children that are not a translated text field.
_NOT_TEXT_FIELDS = frozenset({"altpage"})


def load_data_terms(locale: str, legacy_dir: Path = LEGACY_LANG_DIR) -> DataTerms:
    """Index `legacy_dir/<locale>_data.xml` (see the module docstring). A locale without the file --
    including `en-us`, which has none because English *is* the data -- gets `EMPTY_DATA_TERMS`."""
    path = legacy_dir / f"{locale}_data.xml"
    if not path.is_file():
        return EMPTY_DATA_TERMS
    by_id: dict[str, dict[str, str]] = {}
    by_file: dict[str, dict[str, str]] = {}
    fields: dict[tuple[str, str], str] = {}
    for section in ET.parse(path).getroot().findall("chummer"):
        terms = by_file.setdefault(section.get("file", ""), {})
        for element in section.iter():
            attribute = element.get("translate")
            if attribute and element.text and element.text.strip():
                terms.setdefault(element.text.strip(), attribute)
            translated = element.findtext("translate")
            name = element.findtext("name")
            if translated and name:
                # An item's own name outranks an attribute-translated text with the same English
                # (skills.xml's `<spec translate="Pistolen">Pistols</spec>` under another skill
                # must not become the Pistols *skill*'s name), so it overwrites; those use
                # `setdefault` and never displace an item.
                terms[name] = translated
                guid = element.findtext("id")
                if guid:
                    by_id.setdefault(guid.lower(), {})[name] = translated
                    for child in element:
                        if (
                            child.tag.startswith("alt")
                            and child.tag not in _NOT_TEXT_FIELDS
                            and child.text
                        ):
                            fields[(guid.lower(), child.tag[3:])] = child.text.strip()
    return DataTerms(
        MappingProxyType({guid: MappingProxyType(names) for guid, names in by_id.items()}),
        MappingProxyType({file: MappingProxyType(terms) for file, terms in by_file.items()}),
        MappingProxyType(fields),
    )
