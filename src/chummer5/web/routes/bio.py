"""The Bio page (WP134): `POST /ui/bio`, the character's name, alias, concept and background.

Phase W left a disabled "Bio" nav entry for this. Nothing here feeds a rule: the page edits
`Character.biography` (`chummer5.engine.biography`) and nothing else, so unlike every other step
it can never make a selection stale.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from chummer5.engine.biography import (
    BIOGRAPHY_FIELDS,
    LONG_FIELDS,
    Biography,
    create_biography,
    max_length,
)
from chummer5.engine.character import Character
from chummer5.web.catalogs import templates
from chummer5.web.session import resolve_session, set_session_cookie

router = APIRouter()

# field -> label key. Legacy's own "Label_*" keys wherever its text is the label (WP102 rule 1),
# which is why the street name is labelled "Alias:".
_LABEL_KEYS: dict[str, str] = {
    "name": "Label_CharacterName",
    "street_name": "Label_Alias",
    "player_name": "Label_Player",
    "concept": "Label_Concept",
    "sex": "Label_Sex",
    "age": "Label_Age",
    "height": "Label_Height",
    "weight": "Label_Weight",
    "eyes": "Label_Eyes",
    "hair": "Label_Hair",
    "skin": "Label_Skin",
    "description": "Label_Description",
    "background": "Label_Background",
    "notes": "Label_Notes",
}


def _bio_context(
    character: Character | None, biography: Biography | None = None, *, error: str | None = None
) -> dict[str, Any]:
    """Context for `_bio.html`: one row per field, showing `biography` (a rejected submission,
    echoed back) or the character's own."""
    if character is None:
        return {"character": None, "bio_error": error}
    shown = biography if biography is not None else character.biography
    return {
        "character": character,
        "bio_rows": [
            {
                "field": field,
                "label_key": _LABEL_KEYS[field],
                "value": getattr(shown, field),
                "long": field in LONG_FIELDS,
                "max_length": max_length(field),  # WP141
            }
            for field in BIOGRAPHY_FIELDS
        ],
        "bio_error": error,
    }


@router.post("/ui/bio", response_class=HTMLResponse)
async def submit_bio(request: Request) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    session.current_page = "bio"
    if session.character is None:
        context = _bio_context(None)
    else:
        form = await request.form()
        values = {field: str(form.get(field) or "") for field in BIOGRAPHY_FIELDS}
        try:
            biography = create_biography(values)
        except ValueError as exc:
            echoed = Biography(**{f: v[:200] for f, v in values.items()})
            context = _bio_context(session.character, echoed, error=str(exc))
        else:
            session.character = replace(session.character, biography=biography)
            context = _bio_context(session.character)
    response = templates.TemplateResponse(request, "_bio.html", context)
    set_session_cookie(request, response, new_cookie)
    return response
