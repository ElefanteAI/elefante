"""
End-to-end smoke test for the Session Distiller v2.
Exercises: Scanner → Parser → Privacy → Tracker → CLI
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from modules.distiller.scanner import SessionScanner
from modules.distiller.parser import ChatParser
from modules.distiller.privacy import PrivacyFilter
from modules.distiller.tracker import SessionTracker
from modules.distiller.models import ResponseKind

PASS = "✓"
FAIL = "✗"
results = []

def test(name, fn):
    try:
        fn()
        results.append((name, True, ""))
        print(f"  {PASS} {name}")
    except Exception as e:
        results.append((name, False, str(e)))
        print(f"  {FAIL} {name}: {e}")


# ─── 1. Scanner ───────────────────────────────────────────────────────────────

def test_scanner_init():
    scanner = SessionScanner()
    assert scanner.root.exists(), f"Root not found: {scanner.root}"

def test_scanner_list():
    scanner = SessionScanner()
    sessions = scanner.list_sessions(limit=5)
    assert len(sessions) > 0, "No sessions found"
    s = sessions[0]
    assert s.session_id, "Missing session_id"
    assert s.workspace_id, "Missing workspace_id"
    assert s.size_bytes > 0, "Zero-byte file"
    assert s.modified_at is not None, "Missing mtime"

def test_scanner_workspace_name():
    scanner = SessionScanner()
    sessions = scanner.list_sessions(limit=5)
    named = [s for s in sessions if s.workspace_name]
    assert len(named) > 0, f"No workspace names resolved out of {len(sessions)} sessions"


# ─── 2. Parser ────────────────────────────────────────────────────────────────

def test_parser_returns_typed():
    scanner = SessionScanner()
    parser = ChatParser()
    sessions = scanner.list_sessions(limit=5)
    session = parser.parse(sessions[0].file_path)
    # CRITICAL: Must return ChatSession, not dict
    assert type(session).__name__ == "ChatSession", f"Got {type(session)} instead of ChatSession"
    assert session.session_id, "Missing session_id"
    assert session.source_format in ("json", "jsonl"), f"Bad format: {session.source_format}"

def test_parser_turns_are_typed():
    scanner = SessionScanner()
    parser = ChatParser()
    sessions = scanner.list_sessions(limit=10)
    # Find a session with actual content
    for s in sessions:
        session = parser.parse(s.file_path)
        if session.turns:
            turn = session.turns[0]
            assert type(turn).__name__ == "ChatTurn", f"Got {type(turn)} instead of ChatTurn"
            assert isinstance(turn.user_text, str), "user_text is not str"
            assert isinstance(turn.response_chunks, list), "response_chunks is not list"
            if turn.response_chunks:
                chunk = turn.response_chunks[0]
                assert type(chunk).__name__ == "ResponseChunk", f"Got {type(chunk)} instead of ResponseChunk"
                assert isinstance(chunk.kind, ResponseKind), f"kind is {type(chunk.kind)}"
            return
    raise AssertionError("No sessions with turns found")

def test_parser_content_hash():
    scanner = SessionScanner()
    parser = ChatParser()
    sessions = scanner.list_sessions(limit=5)
    session = parser.parse(sessions[0].file_path)
    h1 = session.content_hash
    h2 = session.content_hash  # Same input → same hash
    assert h1 == h2, "Hash is not deterministic"
    assert len(h1) == 16, f"Hash length wrong: {len(h1)}"


# ─── 3. Privacy ──────────────────────────────────────────────────────────────

def test_privacy_scrubs_keys():
    pf = PrivacyFilter()
    dirty = 'My key is sk-abc123456789012345678901234567890123456789 and password=hunter2'
    clean, result = pf.scrub(dirty)
    assert "sk-abc" not in clean, f"OpenAI key not scrubbed: {clean}"
    assert "hunter2" not in clean, f"Password not scrubbed: {clean}"
    assert result.redactions >= 2, f"Expected 2+ redactions, got {result.redactions}"

def test_privacy_preserves_clean():
    pf = PrivacyFilter()
    clean_text = "Just a normal conversation about Python lists and dict comprehensions."
    scrubbed, result = pf.scrub(clean_text)
    assert scrubbed == clean_text, "Clean text was modified"
    assert result.redactions == 0

def test_privacy_github_token():
    pf = PrivacyFilter()
    dirty = "Use ghp_1234567890abcdefghijABCDEFGHIJ123456 to authenticate"
    clean, result = pf.scrub(dirty)
    assert "ghp_" not in clean, f"GitHub token not scrubbed: {clean}"


# ─── 4. Tracker ──────────────────────────────────────────────────────────────

def test_tracker_idempotent():
    import tempfile, os
    tmp = os.path.join(tempfile.gettempdir(), "elefante_test_tracker.json")
    try:
        tracker = SessionTracker(tracker_path=tmp)
        assert not tracker.is_processed("test-uuid", "hash123")
        tracker.mark_processed("test-uuid", "hash123", insights_count=5)
        assert tracker.is_processed("test-uuid", "hash123")
        # Changed content → should NOT be marked as processed
        assert not tracker.is_processed("test-uuid", "hash-CHANGED")
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

def test_tracker_stats():
    import tempfile, os
    tmp = os.path.join(tempfile.gettempdir(), "elefante_test_tracker2.json")
    try:
        tracker = SessionTracker(tracker_path=tmp)
        tracker.mark_processed("a", "h1", 3)
        tracker.mark_processed("b", "h2", 7)
        stats = tracker.get_stats()
        assert stats["total_processed"] == 2
        assert stats["total_insights"] == 10
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# ─── 5. Integration: Full Pipeline ───────────────────────────────────────────

def test_full_pipeline():
    import tempfile, os
    scanner = SessionScanner()
    parser = ChatParser()
    privacy = PrivacyFilter()
    tmp = os.path.join(tempfile.gettempdir(), "elefante_test_pipeline.json")
    tracker = SessionTracker(tracker_path=tmp)

    try:
        sessions = scanner.list_sessions(limit=5)
        assert sessions, "No sessions to test"

        # Parse
        session = parser.parse(sessions[0].file_path)

        # Check idempotency (first time = not processed)
        assert not tracker.is_processed(session.session_id, session.content_hash)

        # Privacy scrub
        for turn in session.turns:
            turn.user_text, _ = privacy.scrub(turn.user_text)
            for chunk in turn.response_chunks:
                chunk.value, _ = privacy.scrub(chunk.value)

        # Generate output
        md = session.to_markdown()
        flat = session.to_flat_text()
        assert len(md) > 0, "Empty markdown output"
        assert len(flat) > 0, "Empty flat text output"

        # Mark processed
        tracker.mark_processed(session.session_id, session.content_hash)

        # Idempotency check (second time = skip)
        assert tracker.is_processed(session.session_id, session.content_hash)

    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# ─── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== Elefante Session Distiller v2 — Smoke Test ===\n")

    print("[Scanner]")
    test("Scanner init", test_scanner_init)
    test("Scanner list sessions", test_scanner_list)
    test("Scanner workspace name resolution", test_scanner_workspace_name)

    print("\n[Parser]")
    test("Parser returns ChatSession", test_parser_returns_typed)
    test("Parser turns are typed", test_parser_turns_are_typed)
    test("Parser content hash deterministic", test_parser_content_hash)

    print("\n[Privacy]")
    test("Privacy scrubs API keys", test_privacy_scrubs_keys)
    test("Privacy preserves clean text", test_privacy_preserves_clean)
    test("Privacy catches GitHub tokens", test_privacy_github_token)

    print("\n[Tracker]")
    test("Tracker idempotency", test_tracker_idempotent)
    test("Tracker stats", test_tracker_stats)

    print("\n[Integration]")
    test("Full pipeline: scan→parse→scrub→track", test_full_pipeline)

    # Summary
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n{'=' * 50}")
    print(f"Results: {passed}/{total} passed")
    if passed < total:
        print("\nFailures:")
        for name, ok, err in results:
            if not ok:
                print(f"  {FAIL} {name}: {err}")
        sys.exit(1)
    else:
        print("All tests passed.")
        sys.exit(0)
