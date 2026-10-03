"""Reading an upload (WP140): the size-capped multipart parser, and turning one file into a
character.

**Limits, enforced while reading.** Starlette's own `request.form()` spools every file whole
before the route sees it. `read_upload` uses a subclass of its parser instead:

- each file is capped at `store.config.upload_max_bytes()` (default 10 MB). Past the cap nothing
  more of that file is kept (the rest of its bytes are read off the connection and dropped), and
  it comes back with `data=None`, so the other files of the request still get their own results;
- at most `MAX_FILES` files per request;
- the whole body is capped at what that many full-size files can take, checked against
  `Content-Length` before reading anything and counted while reading, so a body that keeps going
  is cut off rather than drained.

**One file, detected by content.** `import_file` reads a file starting with `<` as a legacy
`.chum5` and anything else as a native JSON save, except that a file *named* `.chum5`/`.xml`
that is neither is reported as a bad `.chum5`, the error its owner expects. A `.chum5` goes
through `defusedxml` (`chummer5.io.legacy_chum5`). Every failure is a translated message, never
a 500: the file is untrusted input.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

from defusedxml import DefusedXmlException
from fastapi import Request
from python_multipart.multipart import parse_options_header
from starlette.datastructures import Headers, UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from chummer5.engine.character import Character
from chummer5.io.legacy_import import UnsupportedLegacyCharacterError, import_chum5
from chummer5.io.save_format import CharacterSave, from_json
from chummer5.store import config
from chummer5.web.catalogs import (
    BIOWARE,
    CYBERWARE_ENTRIES,
    LIFESTYLES,
    METATYPES,
    POWERS,
    PRIORITIES,
    QUALITIES,
    SKILLS,
    SPELLS,
    TRADITIONS,
)
from chummer5.web.i18n import Message, MessageJoin
from chummer5.web.routes.character import build_from_save

logger = logging.getLogger(__name__)

MAX_FILES = 20
FILES_FIELD = "files"
# Room for the multipart framing (boundaries, part headers) and the form's small text fields.
_FRAMING_BYTES = 256 * 1024
_MAX_TEXT_FIELD_BYTES = 16 * 1024
_MAX_TEXT_FIELDS = 10
_XML_SUFFIXES = (".chum5", ".xml")


@dataclass(frozen=True)
class UploadedFile:
    filename: str
    data: bytes | None  # None: over the size cap


@dataclass
class ParsedUpload:
    files: list[UploadedFile] = field(default_factory=list)
    fields: dict[str, str] = field(default_factory=dict)


class UploadRejectedError(Exception):
    """The request as a whole is refused (too many files, too large, not a form)."""

    def __init__(self, message: Message) -> None:
        super().__init__(message.key)
        self.message = message


class _TooManyFilesError(MultiPartException):
    pass


class _BodyTooLargeError(MultiPartException):
    pass


class _CappedParser(MultiPartParser):
    """Starlette's parser, keeping at most `max_file_bytes` of each file."""

    def __init__(
        self, headers: Headers, stream: AsyncGenerator[bytes, None], max_file_bytes: int
    ) -> None:
        super().__init__(
            headers,
            stream,
            max_files=MAX_FILES + 1,  # ours refuses first, with its own exception
            max_fields=_MAX_TEXT_FIELDS,
            max_part_size=_MAX_TEXT_FIELD_BYTES,
        )
        self.max_file_bytes = max_file_bytes
        self.file_count = 0
        # Keyed by the UploadFile's id; `self.items` keeps every UploadFile alive meanwhile.
        self._kept: dict[int, int] = {}
        self.oversized: set[int] = set()

    def on_headers_finished(self) -> None:
        super().on_headers_finished()
        if self._current_part.file is not None:
            self.file_count += 1
            if self.file_count > MAX_FILES:
                raise _TooManyFilesError("too-many-files")

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        upload = self._current_part.file
        if upload is not None:
            key = id(upload)
            if key in self.oversized:
                return
            kept = self._kept.get(key, 0) + (end - start)
            if kept > self.max_file_bytes:
                self.oversized.add(key)
                return
            self._kept[key] = kept
        super().on_part_data(data, start, end)


async def _counted(request: Request, limit: int) -> AsyncGenerator[bytes, None]:
    seen = 0
    async for chunk in request.stream():
        seen += len(chunk)
        if seen > limit:
            raise _BodyTooLargeError("body-too-large")
        yield chunk


def _megabytes(size: int) -> str:
    return f"{size / (1024 * 1024):g}"


async def read_upload(request: Request) -> ParsedUpload:
    """The request's files (field `files`, in order; an empty file input is skipped) and its text
    fields. Raises `UploadRejectedError` for a request refused as a whole."""
    content_type, _ = parse_options_header(request.headers.get("Content-Type", ""))
    if content_type != b"multipart/form-data":
        return ParsedUpload()
    max_file = config.upload_max_bytes()
    max_body = MAX_FILES * max_file + _FRAMING_BYTES
    too_large = Message.of("Web_Upload_RequestTooLarge", count=MAX_FILES, size=_megabytes(max_file))
    declared = request.headers.get("Content-Length", "")
    if declared.isdigit() and int(declared) > max_body:
        raise UploadRejectedError(too_large)

    parser = _CappedParser(request.headers, _counted(request, max_body), max_file)
    try:
        form = await parser.parse()
    except _TooManyFilesError:
        raise UploadRejectedError(Message.of("Web_Upload_TooManyFiles", count=MAX_FILES)) from None
    except _BodyTooLargeError:
        raise UploadRejectedError(too_large) from None
    except MultiPartException as exc:
        logger.info("malformed upload: %s", exc.message)
        raise UploadRejectedError(Message.of("Web_Upload_Malformed")) from None

    parsed = ParsedUpload()
    try:
        for name, value in form.multi_items():
            if isinstance(value, str):
                parsed.fields.setdefault(name, value)
            elif name == FILES_FIELD and value.filename:
                data = None if id(value) in parser.oversized else await value.read()
                parsed.files.append(UploadedFile(value.filename, data))
    finally:
        for _, value in form.multi_items():
            if isinstance(value, UploadFile):
                await value.close()
    return parsed


# --- one file ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class FileImport:
    """One file's outcome: the character it holds and the notes to show (what was loaded, what
    an import dropped), or the error instead."""

    save: CharacterSave | None = None
    built: Character | None = None
    notes: tuple[Message, ...] = ()
    error: Message | None = None


def _is_xml(filename: str, data: bytes) -> bool:
    head = data.lstrip(b"\xef\xbb\xbf \t\r\n")[:1]
    if head == b"<":
        return True
    return head != b"{" and filename.lower().endswith(_XML_SUFFIXES)


def import_file(uploaded: UploadedFile, max_bytes: int) -> FileImport:
    if uploaded.data is None:
        return FileImport(error=Message.of("Web_Upload_FileTooLarge", size=_megabytes(max_bytes)))
    if _is_xml(uploaded.filename, uploaded.data):
        return _import_chum5(uploaded.data)
    return _load_json(uploaded.data)


def _load_json(data: bytes) -> FileImport:
    try:
        save = from_json(data.decode("utf-8-sig"))
        built = build_from_save(save)
    # A user-supplied file's shape is never trusted: malformed JSON (ValueError, via
    # json.JSONDecodeError/UnicodeDecodeError), a missing field (KeyError), a save shaped as
    # something other than a JSON object (AttributeError, from calling .get on a list/scalar), or
    # a shape that parses but fails one of build_character's own validations (ValueError) are all
    # just "not a loadable save".
    except (ValueError, KeyError, AttributeError, TypeError) as exc:
        return FileImport(error=Message.of("Web_Sheet_ErrorLoad", error=str(exc)))
    return FileImport(save=save, built=built, notes=(Message.of("Web_Sheet_Loaded"),))


def _import_chum5(data: bytes) -> FileImport:
    try:
        result = import_chum5(
            data,
            metatypes=METATYPES,
            priorities=PRIORITIES,
            skills=SKILLS,
            qualities=QUALITIES,
            lifestyles=LIFESTYLES,
            traditions=TRADITIONS,
            spells=SPELLS,
            powers=POWERS,
            cyberware=CYBERWARE_ENTRIES,
            bioware=BIOWARE,
        )
    except UnsupportedLegacyCharacterError as exc:
        # The importer's reasons are engine-side English, joined but not translated.
        return FileImport(
            error=Message.of(
                "Web_Sheet_ErrorCannotImport",
                reasons=MessageJoin(tuple(exc.reasons), "Web_List_Semicolon"),
            )
        )
    except DefusedXmlException:
        # Before ValueError, which it subclasses: an entity declaration or external reference.
        return FileImport(error=Message.of("Web_Upload_UnsafeXml"))
    except ET.ParseError as exc:
        return FileImport(error=Message.of("Web_Sheet_ErrorInvalidChum5", error=str(exc)))
    except (ValueError, KeyError, AttributeError, TypeError) as exc:
        # Well-formed XML the importer still can't take: a number field holding text, or a value
        # its engine checks refuse (two legacy test files carry adept powers at rating 0, see the
        # decisions log, 2026-10-03). Untrusted input: a message, not a 500.
        logger.info("unimportable .chum5 upload: %r", exc)
        return FileImport(error=Message.of("Web_Sheet_ErrorCannotImport", reasons=str(exc)))
    notes = [Message.of("Web_Sheet_Imported")]
    for key, names in (
        ("Web_Sheet_DroppedQualities", result.dropped_qualities),
        ("Web_Sheet_DroppedSkills", result.dropped_skills),
        ("Web_Sheet_DroppedSpells", result.dropped_spells),
        ("Web_Sheet_DroppedPowers", result.dropped_powers),
    ):
        if names:
            notes.append(Message.of(key, names=MessageJoin(tuple(names))))
    return FileImport(save=result.save, built=result.built, notes=tuple(notes))
