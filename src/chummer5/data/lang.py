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
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping
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
