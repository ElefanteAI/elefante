"""Local content-addressed attachment storage for multi-modal memories.

Elefante remains model- and network-independent: this module stores user-chosen
local media bytes plus bounded descriptive metadata.  It never performs OCR,
transcription, captioning, or remote upload.  The text description is the
retrieval fallback for hosts that cannot render the media directly.
"""

from __future__ import annotations

import hashlib
import mimetypes
import os
import stat
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


MAX_ATTACHMENTS_PER_MEMORY = 8
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024
MAX_DESCRIPTION_LENGTH = 1_000

ALLOWED_MIME_TYPES = frozenset(
    {
        "image/gif",
        "image/jpeg",
        "image/png",
        "image/webp",
        "audio/flac",
        "audio/mpeg",
        "audio/mp4",
        "audio/ogg",
        "audio/wav",
        "video/mp4",
        "video/webm",
    }
)

_CANONICAL_EXTENSIONS = {
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "audio/flac": ".flac",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
}


class AttachmentValidationError(ValueError):
    """Raised before unsupported or unsafe media can enter the store."""


@dataclass(frozen=True)
class AttachmentDescriptor:
    """Portable metadata persisted with a memory; contains no absolute path."""

    sha256: str
    media_kind: str
    mime_type: str
    size_bytes: int
    original_name: str
    storage_path: str
    description: str
    width: int | None = None
    height: int | None = None
    duration_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


def _positive_optional_integer(spec: Mapping[str, Any], name: str) -> int | None:
    value = spec.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise AttachmentValidationError(f"{name} must be a positive integer")
    return value


def _mime_type(path: Path, declared: Any = None) -> str:
    guessed, _encoding = mimetypes.guess_type(path.name)
    mime_type = str(declared or guessed or "").strip().casefold()
    if mime_type not in ALLOWED_MIME_TYPES:
        raise AttachmentValidationError(
            f"Unsupported attachment MIME type: {mime_type or 'unknown'}"
        )
    if declared and guessed and str(declared).casefold() != guessed.casefold():
        raise AttachmentValidationError(
            f"Declared MIME type {declared!s} does not match file extension {guessed}"
        )
    return mime_type


def _safe_original_name(path: Path) -> str:
    name = path.name.strip()
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise AttachmentValidationError("Attachment filename is unsafe")
    return name[:255]


class AttachmentStore:
    """Content-addressed local media store rooted under Elefante data."""

    def __init__(self, root: Path, *, max_bytes: int = MAX_ATTACHMENT_BYTES):
        self.root = Path(root).expanduser().resolve()
        self.max_bytes = max_bytes

    def _open_source(self, source: Path):
        source = source.expanduser()
        if source.is_symlink():
            raise AttachmentValidationError("Symlink attachments are not accepted")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(source, flags)
        except OSError as error:
            raise AttachmentValidationError(f"Cannot open attachment: {error}") from error
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode):
            os.close(descriptor)
            raise AttachmentValidationError("Attachment must be a regular file")
        if details.st_size <= 0:
            os.close(descriptor)
            raise AttachmentValidationError("Attachment must not be empty")
        if details.st_size > self.max_bytes:
            os.close(descriptor)
            raise AttachmentValidationError(
                f"Attachment exceeds the {self.max_bytes}-byte limit"
            )
        return os.fdopen(descriptor, "rb"), details.st_size

    def ingest(self, spec: Mapping[str, Any]) -> AttachmentDescriptor:
        """Validate, atomically store, and describe one local attachment."""
        if not isinstance(spec, Mapping):
            raise AttachmentValidationError("Each attachment must be an object")
        raw_path = spec.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise AttachmentValidationError("Attachment path is required")
        source = Path(raw_path)
        description = str(spec.get("description") or "").strip()
        if not description:
            raise AttachmentValidationError(
                "Attachment description is required for text-only hosts"
            )
        if len(description) > MAX_DESCRIPTION_LENGTH:
            raise AttachmentValidationError(
                f"Attachment description exceeds {MAX_DESCRIPTION_LENGTH} characters"
            )
        mime_type = _mime_type(source, spec.get("mime_type"))
        width = _positive_optional_integer(spec, "width")
        height = _positive_optional_integer(spec, "height")
        duration_ms = _positive_optional_integer(spec, "duration_ms")

        self.root.mkdir(parents=True, exist_ok=True)
        source_file, expected_size = self._open_source(source)
        digest = hashlib.sha256()
        temporary_path: Path | None = None
        try:
            temporary_fd, temporary_name = tempfile.mkstemp(
                prefix=".attachment-", suffix=".tmp", dir=self.root
            )
            temporary_path = Path(temporary_name)
            with source_file, os.fdopen(temporary_fd, "wb") as target:
                while chunk := source_file.read(1024 * 1024):
                    digest.update(chunk)
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
            actual_size = temporary_path.stat().st_size
            if actual_size != expected_size:
                raise AttachmentValidationError("Attachment changed while it was read")

            sha256 = digest.hexdigest()
            relative = Path(sha256[:2]) / f"{sha256}{_CANONICAL_EXTENSIONS[mime_type]}"
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                existing_digest = hashlib.sha256()
                if destination.is_symlink() or not destination.is_file():
                    raise AttachmentValidationError(
                        "Existing content-addressed attachment failed integrity checks"
                    )
                with destination.open("rb") as existing:
                    while existing_chunk := existing.read(1024 * 1024):
                        existing_digest.update(existing_chunk)
                if (
                    destination.stat().st_size != actual_size
                    or existing_digest.hexdigest() != sha256
                ):
                    raise AttachmentValidationError(
                        "Existing content-addressed attachment failed integrity checks"
                    )
                temporary_path.unlink()
            else:
                os.chmod(temporary_path, 0o600)
                temporary_path.replace(destination)
            temporary_path = None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            if not source_file.closed:
                source_file.close()

        return AttachmentDescriptor(
            sha256=sha256,
            media_kind=mime_type.split("/", 1)[0],
            mime_type=mime_type,
            size_bytes=expected_size,
            original_name=_safe_original_name(source),
            storage_path=(Path("attachments") / relative).as_posix(),
            description=description,
            width=width,
            height=height,
            duration_ms=duration_ms,
        )

    def ingest_many(
        self, attachments: Iterable[Mapping[str, Any]]
    ) -> list[AttachmentDescriptor]:
        specs = list(attachments)
        if not specs:
            return []
        if len(specs) > MAX_ATTACHMENTS_PER_MEMORY:
            raise AttachmentValidationError(
                f"A memory may contain at most {MAX_ATTACHMENTS_PER_MEMORY} attachments"
            )
        return [self.ingest(spec) for spec in specs]

    def resolve(self, descriptor: AttachmentDescriptor | Mapping[str, Any]) -> Path:
        """Resolve one persisted descriptor without allowing path traversal."""
        storage_path = (
            descriptor.storage_path
            if isinstance(descriptor, AttachmentDescriptor)
            else str(descriptor.get("storage_path") or "")
        )
        relative = Path(storage_path)
        if not relative.parts or relative.parts[0] != "attachments":
            raise AttachmentValidationError("Attachment storage path is invalid")
        candidate = (self.root.parent / relative).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise AttachmentValidationError("Attachment storage path escapes its root")
        return candidate


__all__ = [
    "ALLOWED_MIME_TYPES",
    "AttachmentDescriptor",
    "AttachmentStore",
    "AttachmentValidationError",
    "MAX_ATTACHMENT_BYTES",
    "MAX_ATTACHMENTS_PER_MEMORY",
]
