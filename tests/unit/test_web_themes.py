"""WP100: theme tokens and the theme selector.

The contract being pinned: `static/app.css` is structure only (it defines no token), and each
`static/themes/<slug>.css` is a complete token set and nothing else -- custom-property declarations
under `:root`, plus one `prefers-color-scheme: dark` block of the same. Those two halves together
are what make a theme unable to drift into structural CSS, and unable to leave app.css reading an
undefined token (which would silently fall back to the property's initial value).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chummer5.web.app import create_app
from chummer5.web.catalogs import STATIC_DIR
from chummer5.web.prefs import DEFAULT_THEME, THEMES

APP_CSS = Path(STATIC_DIR) / "app.css"
THEMES_DIR = Path(STATIC_DIR) / "themes"
DARK_QUERY = "@media (prefers-color-scheme: dark)"


def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _declarations(block: str, where: str) -> set[str]:
    """The custom-property names declared in a `{...}` body -- asserting every declaration in it
    *is* a custom property."""
    names = set()
    for declaration in (d.strip() for d in block.split(";")):
        if not declaration:
            continue
        name, sep, value = declaration.partition(":")
        assert sep and value.strip(), f"{where}: malformed declaration {declaration!r}"
        assert name.strip().startswith("--"), f"{where}: not a custom property: {declaration!r}"
        names.add(name.strip())
    return names


def _parse_theme(path: Path) -> tuple[set[str], set[str]]:
    """`(light tokens, dark tokens)` of a theme file, failing on anything that isn't exactly
    `:root {...}` followed by `@media (prefers-color-scheme: dark) { :root {...} }`."""
    css = " ".join(_strip_comments(path.read_text()).split())
    match = re.fullmatch(
        r":root \{(?P<light>[^{}]*)\} "
        + re.escape(DARK_QUERY)
        + r" \{ :root \{(?P<dark>[^{}]*)\} \}",
        css,
    )
    assert match is not None, (
        f"{path.name}: a theme must be one `:root` block plus one dark `:root` block, nothing else"
    )
    return (
        _declarations(match["light"], f"{path.name} :root"),
        _declarations(match["dark"], f"{path.name} dark :root"),
    )


def _tokens_used_by_app_css() -> set[str]:
    return set(re.findall(r"var\((--[a-z0-9-]+)\)", APP_CSS.read_text()))


def test_every_listed_theme_has_a_stylesheet_and_every_stylesheet_is_listed() -> None:
    assert {theme.slug for theme in THEMES} == {path.stem for path in THEMES_DIR.glob("*.css")}
    assert DEFAULT_THEME in {theme.slug for theme in THEMES}
    assert len(THEMES) >= 2  # the mechanism has to actually be exercised


def test_app_css_is_structure_only() -> None:
    css = _strip_comments(APP_CSS.read_text())
    assert not re.search(r"(^|[;{\s])--[a-z0-9-]+\s*:", css), "app.css must not define tokens"
    assert "color-scheme: light dark" in css  # the scheme *mechanism* stays here


@pytest.mark.parametrize("theme", [t.slug for t in THEMES])
def test_a_theme_contains_only_custom_property_declarations(theme: str) -> None:
    light, dark = _parse_theme(THEMES_DIR / f"{theme}.css")
    assert light and dark  # both schemes handled, not just one


@pytest.mark.parametrize("theme", [t.slug for t in THEMES])
def test_a_theme_defines_every_token_app_css_reads(theme: str) -> None:
    light, dark = _parse_theme(THEMES_DIR / f"{theme}.css")
    assert _tokens_used_by_app_css() - light == set()
    # The dark block only *re*defines: a token that exists only in dark mode is a typo.
    assert dark - light == set()


def test_the_parser_rejects_a_theme_that_smuggles_in_a_selector(tmp_path: Path) -> None:
    bad = tmp_path / "bad.css"
    bad.write_text(":root { --a: 1; } .step-nav__item { color: red; }")
    with pytest.raises(AssertionError):
        _parse_theme(bad)
    bad.write_text(f":root {{ --a: 1; color: red; }} {DARK_QUERY} {{ :root {{ --a: 2; }} }}")
    with pytest.raises(AssertionError):
        _parse_theme(bad)


def _stylesheets(html: str) -> list[str]:
    return re.findall(r'<link\s[^>]*rel="stylesheet"[^>]*href="([^"]+)"', html, re.S)


def test_the_shell_links_the_default_theme_ahead_of_app_css() -> None:
    client = TestClient(create_app())

    sheets = _stylesheets(client.get("/").text)

    assert [Path(s).name for s in sheets] == [f"{DEFAULT_THEME}.css", "app.css"]
    assert sheets[0].endswith(f"/static/themes/{DEFAULT_THEME}.css")


def test_selecting_a_theme_links_it_in_every_later_render_and_marks_the_picker() -> None:
    client = TestClient(create_app())
    client.get("/")

    response = client.post("/ui/prefs/theme", data={"theme": "sketch"})

    assert response.status_code == 200
    # The page restyles in place: the new link comes back out of band, and nothing else.
    assert 'id="theme-stylesheet"' in response.text
    assert 'hx-swap-oob="true"' in response.text
    assert "/static/themes/sketch.css" in response.text
    # A preference is not a chargen change, so the nav/panel/tabs are not told to re-fetch.
    assert "HX-Trigger" not in response.headers
    for url in ("/", "/ui/page/skills", "/character/sheet"):
        html = client.get(url).text
        assert Path(_stylesheets(html)[0]).name == "sketch.css", url
        assert re.search(r'<option value="sketch"\s+selected>', html), url
    # Another session is unaffected.
    other = TestClient(create_app())
    assert Path(_stylesheets(other.get("/").text)[0]).name == f"{DEFAULT_THEME}.css"


def test_an_unknown_theme_is_rejected_and_changes_nothing() -> None:
    client = TestClient(create_app())
    client.get("/")

    assert client.post("/ui/prefs/theme", data={"theme": "../app"}).status_code == 422

    assert Path(_stylesheets(client.get("/").text)[0]).name == f"{DEFAULT_THEME}.css"


def test_the_picker_offers_every_theme_and_posts_on_change() -> None:
    html = TestClient(create_app()).get("/").text

    form = re.search(r'<form class="app-shell__prefs"[^>]*>', html)
    assert form is not None
    assert 'hx-post="/ui/prefs/theme"' in form.group(0)
    assert 'hx-trigger="change"' in form.group(0)
    for theme in THEMES:
        assert f'<option value="{theme.slug}"' in html
