"""WP147 (Phase Z): the redesigned Qualities page -- two budget boxes, Positive and Negative tables
of their own, no submit button, messages after the last control, and stable ids on every control
so htmx can restore focus after an autosave swap. See spec/plan/phase-z-page-redesigns.md,
"Redesign 3"."""

from __future__ import annotations

import re
from collections import Counter

from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.data.traditions import load_traditions
from chummer5.engine.character import create_character, metatype_choices
from chummer5.engine.qualities import QUALITY_KARMA_LIMIT, offerable_quality_catalog
from chummer5.web.app import MVP_QUALITIES, create_app
from chummer5.web.catalogs import QUALITIES

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
HERMETIC = next(t for t in load_traditions() if t.name == "Hermetic")
SPELLCASTING = next(s for s in SKILLS if s.name == "Spellcasting")
COUNTERSPELLING = next(s for s in SKILLS if s.name == "Counterspelling")


def _quality(name: str):
    return next(q for q in MVP_QUALITIES if q.name == name)


_CATLIKE = _quality("Catlike")
_LUCKY = _quality("Lucky")
_GEARHEAD = _quality("Gearhead")
_UNCOUTH = _quality("Uncouth")
_INSOMNIA_FULL = _quality("Insomnia (Full)")
_CODEBLOCK = _quality("Codeblock")


def _human(heritage_letter: str = "A"):
    heritage = PRIORITIES.heritage[heritage_letter]
    return next(c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human")


def _confirm(client: TestClient) -> None:
    """A mundane Human: Heritage A, Attributes B, Skills C, Resources D, Talent E."""
    client.get("/")
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "attributes_letter": "B",
            "skills_letter": "C",
            "resources_letter": "D",
            "talent_letter": "E",
            "metatype_id": _human().metatype.id,
        },
    )
    assert "Confirmed: Human" in response.text


def _confirm_magician(client: TestClient) -> None:
    """A Hermetic Human Magician (Talent B), so the Mentor Spirit fieldset shows."""
    client.get("/")
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "E",
            "talent_letter": "B",
            "attributes_letter": "C",
            "skills_letter": "D",
            "resources_letter": "A",
            "metatype_id": _human("E").metatype.id,
        },
    )
    assert "Confirmed: Human" in response.text
    response = client.post(
        "/ui/talent",
        data={
            "talent_letter": "B",
            "talent_codename": "Magician",
            "tradition_id": HERMETIC.id,
            "granted_skill_id": [SPELLCASTING.id, COUNTERSPELLING.id],
        },
    )
    assert "Confirmed: Magician (Hermetic)" in response.text


def _boxes(html: str) -> list[tuple[bool, str]]:
    """Each budget box as (overspent?, `remaining/limit`), in page order."""
    return [
        (bool(over), value)
        for over, value in re.findall(
            r'<div class="budget-box( budget-box--over)?">.*?budget-box__value">([^<]*)<',
            html,
            re.S,
        )
    ]


def _sections(html: str) -> tuple[str, str]:
    """The Positive and Negative sections' markup."""
    positive_start = html.index("quality-section--positive")
    negative_start = html.index("quality-section--negative")
    return html[positive_start:negative_start], html[negative_start : html.index("</form>")]


def _box(remaining: int) -> str:
    return f"{remaining}/{QUALITY_KARMA_LIMIT}"


def test_two_boxes_start_full() -> None:
    client = TestClient(create_app())
    _confirm(client)

    page = client.get("/ui/page/qualities").text

    assert _boxes(page) == [(False, _box(QUALITY_KARMA_LIMIT))] * 2
    assert "Positive Qualities" in page and "Negative Qualities" in page


def test_each_box_counts_down_its_own_pool() -> None:
    client = TestClient(create_app())
    _confirm(client)

    response = client.post("/ui/qualities", data={"quality_id": [_CATLIKE.id, _UNCOUTH.id]})

    assert _boxes(response.text) == [
        (False, _box(QUALITY_KARMA_LIMIT - _CATLIKE.karma)),
        (False, _box(QUALITY_KARMA_LIMIT + _UNCOUTH.karma)),  # Negative karma is stored < 0
    ]


def test_an_overspent_positive_pool_highlights_only_its_own_box() -> None:
    client = TestClient(create_app())
    _confirm(client)
    picks = [_CATLIKE, _LUCKY, _GEARHEAD]
    spent = sum(q.karma for q in picks)
    assert spent > QUALITY_KARMA_LIMIT

    response = client.post("/ui/qualities", data={"quality_id": [q.id for q in picks]})

    assert 'class="error"' in response.text
    assert _boxes(response.text) == [
        (True, _box(QUALITY_KARMA_LIMIT - spent)),
        (False, _box(QUALITY_KARMA_LIMIT)),
    ]


def test_an_overspent_negative_pool_highlights_only_its_own_box() -> None:
    client = TestClient(create_app())
    _confirm(client)
    picks = [_UNCOUTH, _INSOMNIA_FULL]
    spent = -sum(q.karma for q in picks)
    assert spent > QUALITY_KARMA_LIMIT

    response = client.post("/ui/qualities", data={"quality_id": [q.id for q in picks]})

    assert _boxes(response.text) == [
        (False, _box(QUALITY_KARMA_LIMIT)),
        (True, _box(QUALITY_KARMA_LIMIT - spent)),
    ]


def test_each_quality_appears_only_in_its_own_section() -> None:
    client = TestClient(create_app())
    _confirm(client)

    positive, negative = _sections(client.get("/ui/page/qualities").text)

    offered = offerable_quality_catalog(
        create_character(_human(), "A", "B", PRIORITIES, {}), QUALITIES
    )
    for quality in offered:
        mine, other = (
            (positive, negative) if quality.category == "Positive" else (negative, positive)
        )
        assert f'value="{quality.id}"' in mine, quality.name
        assert f'value="{quality.id}"' not in other, quality.name
    assert "Category" not in positive + negative  # the section says it


def test_a_repeatable_negative_quality_s_another_row_stays_in_the_negative_section() -> None:
    client = TestClient(create_app())
    _confirm(client)

    response = client.post(
        "/ui/qualities",
        data={"quality_id": _CODEBLOCK.id, f"quality_text_{_CODEBLOCK.id}": "Matrix Perception"},
    )

    positive, negative = _sections(response.text)
    assert f'value="{_CODEBLOCK.id}:1"' in negative
    assert _CODEBLOCK.id not in positive


def test_no_submit_button_and_no_collapsible_wrapper() -> None:
    client = TestClient(create_app())
    _confirm(client)

    page = client.get("/ui/page/qualities").text
    fragment = page[page.index('id="quality-selection"') :]

    assert 'type="submit"' not in fragment[: fragment.index("</form>")]
    assert "<details" not in fragment[: fragment.index("</form>")]
    assert '<h1 class="page__heading">Qualities</h1>' in page


def test_messages_come_after_the_last_control() -> None:
    client = TestClient(create_app())
    _confirm_magician(client)

    response = client.post("/ui/qualities", data={"quality_id": "not-a-quality"})

    html = response.text
    assert "<fieldset" in html
    assert html.index("</fieldset>") < html.index("</form>") < html.index('class="error"')


def test_every_control_has_a_unique_stable_id_including_repeat_instances() -> None:
    client = TestClient(create_app())
    _confirm(client)
    data = {
        "quality_id": [_CODEBLOCK.id, f"{_CODEBLOCK.id}:1"],
        f"quality_text_{_CODEBLOCK.id}": "Matrix Perception",
        f"quality_text_{_CODEBLOCK.id}:1": "Hack on the Fly",
    }

    first = client.post("/ui/qualities", data=data).text
    second = client.post("/ui/qualities", data=data).text

    form = first[first.index("<form") : first.index("</form>")]
    controls = re.findall(r"<(?:input|select)\b[^>]*>", form)
    assert controls
    ids = [re.search(r'\bid="([^"]+)"', c) for c in controls]
    assert all(ids), [c for c, i in zip(controls, ids, strict=True) if not i]
    counts = Counter(i.group(1) for i in ids if i)
    assert [k for k, n in counts.items() if n > 1] == []
    for suffix in (_CODEBLOCK.id, f"{_CODEBLOCK.id}_1", f"{_CODEBLOCK.id}_2"):
        assert f'id="quality-{suffix}"' in form
        assert f'id="quality-text-{suffix}"' in form
    # Stable: the same state renders the same ids.
    assert re.findall(r'\bid="([^"]+)"', form) == re.findall(
        r'\bid="([^"]+)"', second[second.index("<form") : second.index("</form>")]
    )


def test_mentor_spirit_controls_have_ids() -> None:
    client = TestClient(create_app())
    _confirm_magician(client)

    page = client.get("/ui/page/qualities").text

    assert 'id="mentor-archetype" name="mentor_spirit_archetype_id"' in page


def _shown(html: str) -> dict[str, bool]:
    """Which category sections are visible (not `hidden`)."""
    return {
        view: re.search(
            rf'<section class="quality-section quality-section--{view}"( hidden)?>', html
        ).group(1)
        is None
        for view in ("positive", "negative")
    }


def _selected_view(html: str) -> str:
    start = html.index('id="quality-view"')
    select = html[start : html.index("</select>", start)]
    return re.search(r'<option value="(\w+)" selected', select).group(1)


def test_the_page_opens_on_positive_qualities() -> None:
    client = TestClient(create_app())
    _confirm_magician(client)

    page = client.get("/ui/page/qualities").text

    assert _selected_view(page) == "Positive"
    assert _shown(page) == {"positive": True, "negative": False}
    assert '<fieldset class="quality-mentor">' in page
    # The dropdown is a form control, before the tables: switching it is an autosave.
    form = page[page.index("<form") : page.index("</form>")]
    assert form.index('name="quality_view"') < form.index("quality-section--positive")


def test_switching_to_negative_shows_only_negative_and_hides_the_mentor_fieldset() -> None:
    client = TestClient(create_app())
    _confirm_magician(client)

    response = client.post("/ui/qualities", data={"quality_view": "Negative"})

    assert _selected_view(response.text) == "Negative"
    assert _shown(response.text) == {"positive": False, "negative": True}
    assert '<fieldset class="quality-mentor" hidden>' in response.text


def test_the_hidden_category_s_picks_still_post_and_stay_committed() -> None:
    client = TestClient(create_app())
    _confirm(client)
    client.post("/ui/qualities", data={"quality_id": [_CATLIKE.id, _UNCOUTH.id]})

    # The browser posts every checkbox in the form, hidden section included.
    response = client.post(
        "/ui/qualities", data={"quality_id": [_CATLIKE.id, _UNCOUTH.id], "quality_view": "Negative"}
    )

    positive, _ = _sections(response.text)
    assert re.search(rf'value="{_CATLIKE.id}"\s+checked', positive)
    sheet = client.get("/character/sheet").text
    assert "Catlike" in sheet and "Uncouth" in sheet


def test_an_error_echo_keeps_the_chosen_view() -> None:
    client = TestClient(create_app())
    _confirm(client)
    picks = [_UNCOUTH, _INSOMNIA_FULL]  # over the Negative limit

    response = client.post(
        "/ui/qualities", data={"quality_id": [q.id for q in picks], "quality_view": "Negative"}
    )

    assert 'class="error"' in response.text
    assert _shown(response.text) == {"positive": False, "negative": True}


def test_an_unknown_view_falls_back_to_positive() -> None:
    client = TestClient(create_app())
    _confirm(client)

    response = client.post("/ui/qualities", data={"quality_view": "Sideways"})

    assert _selected_view(response.text) == "Positive"
    assert _shown(response.text) == {"positive": True, "negative": False}
