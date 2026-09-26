"""WP102: no template carries user-facing text outside a `_()` call.

The property is *enforced* here, not asserted once: any future template edit that adds a bare
English word to the page fails this test, naming the template, the line, and the text.

**What counts as user-facing text:** HTML text nodes, plus the attributes a browser shows or reads
aloud (`title`, `placeholder`, `aria-label`, `alt`, and a button-like `<input>`'s `value`). Jinja
expressions (`{{ ... }}`) are values, not text, and are blanked before checking. Tags (`{% %}`),
comments (`{# #}`), and `<script>`/`<style>` bodies are removed; the scripts' own user-visible
strings are checked separately below. A chunk is bare text if a letter survives, in any script,
including CJK. Digits, punctuation, and symbols such as `¥ — / × ⚠` are layout and are allowed.
"""

from __future__ import annotations

import ast
import re
from html.parser import HTMLParser
from pathlib import Path

from chummer5.web.catalogs import TEMPLATES_DIR

USER_FACING_ATTRIBUTES = frozenset({"title", "placeholder", "aria-label", "alt"})
BUTTON_INPUT_TYPES = frozenset({"submit", "button", "reset"})

_VALUE = "\x00"  # stands in for a `{{ ... }}` expression
_BREAK = "\x01"  # stands in for a `{% ... %}` tag


def _letters(text: str) -> bool:
    return any(ch.isalpha() for ch in text.replace(_VALUE, "").replace(_BREAK, ""))


def _prepare(source: str) -> str:
    """Blank everything that is not literal markup, keeping line numbers intact."""

    def keep_newlines(replacement: str):  # type: ignore[no-untyped-def]
        return lambda m: replacement + "\n" * m.group(0).count("\n")

    source = re.sub(r"\{#.*?#\}", keep_newlines(""), source, flags=re.S)
    source = re.sub(
        r"(<(script|style)\b[^>]*>).*?(</\2>)",
        lambda m: m.group(1) + "\n" * m.group(0).count("\n") + m.group(3),
        source,
        flags=re.S,
    )
    source = re.sub(r"\{\{.*?\}\}", keep_newlines(_VALUE), source, flags=re.S)
    return re.sub(r"\{%.*?%\}", keep_newlines(_BREAK), source, flags=re.S)


class _BareTextFinder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: list[tuple[int, str]] = []

    def handle_data(self, data: str) -> None:
        for chunk in data.split(_BREAK):
            if _letters(chunk):
                self.found.append((self.getpos()[0], " ".join(chunk.replace(_VALUE, "{}").split())))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        for name, value in attrs:
            if value is None:
                continue
            shown = name in USER_FACING_ATTRIBUTES or (
                tag == "input" and name == "value" and values.get("type") in BUTTON_INPUT_TYPES
            )
            if shown and _letters(value):
                self.found.append((self.getpos()[0], f'{name}="{value}"'))


def bare_text(path: Path) -> list[tuple[int, str]]:
    finder = _BareTextFinder()
    finder.feed(_prepare(path.read_text()))
    finder.close()
    return finder.found


def test_no_template_has_bare_user_facing_text() -> None:
    offenders = [
        f"{path.name}:{line}: {text}"
        for path in sorted(Path(TEMPLATES_DIR).glob("*.html"))
        for line, text in bare_text(path)
    ]
    assert offenders == [], "\n".join(offenders)


# --- Scripts: they may filter and toggle, but never write text a player reads. -------------------

_TEXT_WRITES = re.compile(r"\.(textContent|innerText|innerHTML|title|placeholder)\s*=|\balert\(")


def test_no_template_script_writes_user_visible_text() -> None:
    offenders = [
        f"{path.name}: {match.group(0)}"
        for path in sorted(Path(TEMPLATES_DIR).glob("*.html"))
        for script in re.findall(r"<script\b[^>]*>(.*?)</script>", path.read_text(), re.S)
        for match in _TEXT_WRITES.finditer(script)
    ]
    assert offenders == [], "\n".join(offenders)


# --- Python: the web layer builds no prose outside a catalog key. ---------------------------------

WEB_DIR = Path(TEMPLATES_DIR).parent

# Multi-word strings in web-layer Python that are identifiers, not prose shown to a player: data
# names matched against catalogs, a gear category, and an HTTP header value.
ALLOWED_PYTHON_STRINGS = frozenset(
    {
        "Essence Hole",
        "Essence Antihole",
        "Resonance Active",
        "Rigger Command Consoles",
        'attachment; filename="character.json"',
    }
)


def _looks_like_prose(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]{2,}.*\s.*[A-Za-z]", text)) and not text.endswith(".html")


def _prose_strings(path: Path) -> list[tuple[int, str]]:
    """Multi-word string literals and f-strings in `path`, skipping docstrings, dict keys, logging
    calls, `HTTPException(detail=...)` (a developer-facing 404/422 body, not page text), and
    `FontSuggestion(...)` (font family names)."""
    tree = ast.parse(path.read_text())
    skip: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr):
            skip.add(id(body[0].value))  # a docstring
        if isinstance(node, ast.Dict):
            skip.update(id(key) for key in node.keys if key is not None)
        if isinstance(node, ast.keyword) and node.arg == "detail":
            skip.update(id(sub) for sub in ast.walk(node.value))
        # A theme's font suggestions (chummer5.web.prefs): font family names are identifiers the
        # browser matches against installed fonts, never translated, and test_web_themes.py ties
        # each one to the theme's own --font-* stack. The role label is still a catalog key.
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "FontSuggestion":
            skip.update(id(sub) for sub in ast.walk(node))
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) in {
            "debug",
            "info",
            "warning",
            "error",
            "exception",
        }:
            skip.update(id(sub) for sub in ast.walk(node))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr) and id(node) not in skip:
            skip.update(id(value) for value in node.values)
            text = "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in node.values)
            if _looks_like_prose(text):
                found.append((node.lineno, f"f{text!r}"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in skip
            and _looks_like_prose(node.value)
            and node.value not in ALLOWED_PYTHON_STRINGS
        ):
            found.append((node.lineno, repr(node.value)))
    return found


def test_no_web_python_module_builds_bare_user_facing_text() -> None:
    modules = sorted(WEB_DIR.glob("*.py")) + sorted((WEB_DIR / "routes").glob("*.py"))
    offenders = [
        f"{path.relative_to(WEB_DIR)}:{line}: {text}"
        for path in modules
        for line, text in _prose_strings(path)
    ]
    assert offenders == [], "\n".join(offenders)


def test_the_python_scan_catches_what_it_is_for(tmp_path: Path) -> None:
    module = tmp_path / "bad.py"
    module.write_text(
        '"""A docstring is fine."""\n'
        'error = f"Could not load save: {exc}"\n'
        'info = "Character loaded."\n'
        'context = {"not prose either": 1}\n'
    )
    assert [text for _, text in _prose_strings(module)] == [
        "f'Could not load save: {}'",
        "'Character loaded.'",
    ]
