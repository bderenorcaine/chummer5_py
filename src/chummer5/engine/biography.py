"""The character's biography (WP134): who they are, as opposed to what they can do.

Step Nine (p. 103) asks the player to flesh out the backstory: "What aliases are they known by?"
None of it feeds a rule. The fields mirror the legacy `.chum5` elements of the same meaning, so
legacy import fills them one to one. `street_name` is the legacy `<alias>`, and `notes` is
`<notes>`; `<gamenotes>` (the GM's) is not kept.

**No mugshot.** Legacy stores images as base64 in the save. That needs binary storage in this
project's JSON format and an upload path, and is deferred (see `spec/decisions-log.md`'s WP134
entry).
"""

from __future__ import annotations

from dataclasses import dataclass, fields

# field name -> the legacy `.chum5` element it maps to.
LEGACY_ELEMENTS: dict[str, str] = {
    "name": "name",
    "street_name": "alias",
    "player_name": "playername",
    "concept": "concept",
    "sex": "sex",
    "age": "age",
    "height": "height",
    "weight": "weight",
    "eyes": "eyes",
    "hair": "hair",
    "skin": "skin",
    "description": "description",
    "background": "background",
    "notes": "notes",
}

# Fields a form shows as multi-line text areas rather than one-line inputs.
LONG_FIELDS = frozenset({"description", "background", "notes"})

# The longest text a field keeps -- generous, but bounded, since it goes into every save. WP141:
# a one-line field is bounded tighter (legacy saves reach about 1000 characters, in a concept).
MAX_FIELD_LENGTH = 20000
MAX_SHORT_FIELD_LENGTH = 2000


def max_length(name: str) -> int:
    """The longest text field `name` keeps."""
    return MAX_FIELD_LENGTH if name in LONG_FIELDS else MAX_SHORT_FIELD_LENGTH


@dataclass(frozen=True)
class Biography:
    name: str = ""
    street_name: str = ""
    player_name: str = ""
    concept: str = ""
    sex: str = ""
    age: str = ""
    height: str = ""
    weight: str = ""
    eyes: str = ""
    hair: str = ""
    skin: str = ""
    description: str = ""
    background: str = ""
    notes: str = ""

    @property
    def display_name(self) -> str:
        """What the sheet heads with: the street name, falling back to the name."""
        return self.street_name or self.name

    def to_dict(self) -> dict[str, str]:
        """The non-empty fields, by name -- what a save stores."""
        return {f.name: getattr(self, f.name) for f in fields(self) if getattr(self, f.name)}


# The empty biography, for argument defaults.
NO_BIOGRAPHY = Biography()

BIOGRAPHY_FIELDS: tuple[str, ...] = tuple(f.name for f in fields(Biography))


def create_biography(values: dict[str, str]) -> Biography:
    """A `Biography` from `{field: text}`. Unknown fields are ignored; text is stripped, and
    rejected past the field's `max_length`."""
    kept: dict[str, str] = {}
    for name in BIOGRAPHY_FIELDS:
        text = str(values.get(name, "")).strip()
        if len(text) > max_length(name):
            raise ValueError(f"{name}: at most {max_length(name)} characters")
        kept[name] = text
    return Biography(**kept)
