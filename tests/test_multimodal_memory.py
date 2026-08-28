"""Regression tests for local, content-addressed multi-modal memory media."""

import pytest

from src.core.multimodal import (
    AttachmentStore,
    AttachmentValidationError,
    MAX_ATTACHMENTS_PER_MEMORY,
)


PNG = b"\x89PNG\r\n\x1a\n" + b"local-image-bytes"


def test_ingest_is_content_addressed_private_and_portable(tmp_path):
    source = tmp_path / "diagram.png"
    source.write_bytes(PNG)
    store = AttachmentStore(tmp_path / "data" / "attachments")

    first = store.ingest(
        {
            "path": str(source),
            "description": "Architecture diagram showing the daemon boundary.",
            "width": 640,
            "height": 480,
        }
    )
    second = store.ingest(
        {"path": str(source), "description": "Same content, second reference."}
    )

    assert first.sha256 == second.sha256
    assert first.storage_path.startswith("attachments/")
    assert str(tmp_path) not in first.storage_path
    assert first.original_name == "diagram.png"
    assert first.media_kind == "image"
    stored = store.resolve(first)
    assert stored.read_bytes() == PNG
    assert stored.stat().st_mode & 0o777 == 0o600
    assert len(list((tmp_path / "data" / "attachments").rglob("*.png"))) == 1


def test_existing_same_size_corruption_fails_content_address_integrity(tmp_path):
    source = tmp_path / "diagram.png"
    source.write_bytes(PNG)
    store = AttachmentStore(tmp_path / "data" / "attachments")
    descriptor = store.ingest(
        {"path": str(source), "description": "Architecture diagram."}
    )
    stored = store.resolve(descriptor)
    stored.write_bytes(b"x" * len(PNG))

    with pytest.raises(AttachmentValidationError, match="integrity"):
        store.ingest(
            {"path": str(source), "description": "Architecture diagram."}
        )


def test_description_is_required_for_text_only_hosts(tmp_path):
    source = tmp_path / "diagram.png"
    source.write_bytes(PNG)

    with pytest.raises(AttachmentValidationError, match="description is required"):
        AttachmentStore(tmp_path / "attachments").ingest({"path": str(source)})


def test_unsupported_empty_oversize_and_symlink_media_are_rejected(tmp_path):
    store = AttachmentStore(tmp_path / "attachments", max_bytes=8)
    unsupported = tmp_path / "payload.exe"
    unsupported.write_bytes(b"payload")
    with pytest.raises(AttachmentValidationError, match="Unsupported"):
        store.ingest({"path": str(unsupported), "description": "no"})

    empty = tmp_path / "empty.png"
    empty.write_bytes(b"")
    with pytest.raises(AttachmentValidationError, match="must not be empty"):
        store.ingest({"path": str(empty), "description": "empty"})

    large = tmp_path / "large.png"
    large.write_bytes(PNG)
    with pytest.raises(AttachmentValidationError, match="exceeds"):
        store.ingest({"path": str(large), "description": "large"})

    link = tmp_path / "link.png"
    link.symlink_to(large)
    with pytest.raises(AttachmentValidationError, match="Symlink"):
        store.ingest({"path": str(link), "description": "link"})


def test_declared_mime_dimensions_and_count_are_validated(tmp_path):
    source = tmp_path / "diagram.png"
    source.write_bytes(PNG)
    store = AttachmentStore(tmp_path / "attachments")
    with pytest.raises(AttachmentValidationError, match="does not match"):
        store.ingest(
            {
                "path": str(source),
                "description": "diagram",
                "mime_type": "image/jpeg",
            }
        )
    with pytest.raises(AttachmentValidationError, match="positive integer"):
        store.ingest(
            {"path": str(source), "description": "diagram", "width": 0}
        )
    with pytest.raises(AttachmentValidationError, match="at most"):
        store.ingest_many(
            [
                {"path": str(source), "description": f"diagram {index}"}
                for index in range(MAX_ATTACHMENTS_PER_MEMORY + 1)
            ]
        )


def test_resolver_rejects_traversal_metadata(tmp_path):
    store = AttachmentStore(tmp_path / "data" / "attachments")
    with pytest.raises(AttachmentValidationError, match="invalid|escapes"):
        store.resolve({"storage_path": "attachments/../../secret"})
