"""
Elefante Session Distiller — CLI Entry Point
Usage: python -m src.modules.distiller [OPTIONS]

Commands:
  list      List recent chat sessions across all workspaces
  search    Search sessions by keyword
  distill   Parse + scrub + store a session
  stats     Show processing statistics
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime

from .scanner import SessionScanner
from .parser import ChatParser
from .privacy import PrivacyFilter
from .tracker import SessionTracker
from .models import InsightType


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(name)s | %(levelname)s | %(message)s",
    )

    if args.command == "list":
        return cmd_list(args)
    elif args.command == "search":
        return cmd_search(args)
    elif args.command == "distill":
        return cmd_distill(args)
    elif args.command == "stats":
        return cmd_stats(args)
    else:
        _build_parser().print_help()
        return 1


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_list(args) -> int:
    # ─── Silence Logs for Clean Output ───
    logging.getLogger("elefante.distiller.parser").setLevel(logging.ERROR)
    logging.getLogger("elefante.distiller.scanner").setLevel(logging.ERROR)
    
    scanner = SessionScanner()
    parser = ChatParser()
    
    sessions = scanner.list_sessions(limit=args.limit)

    if not sessions:
        print("No chat sessions found.")
        return 0

    print(f"{'Modified':<18} {'Size':>8}  {'Workspace':<20} {'Topic / First User Query'}")
    print("─" * 100)
    
    for s in sessions:
        mtime = s.modified_at.strftime("%Y-%m-%d %H:%M") if s.modified_at else "unknown"
        size_kb = f"{s.size_bytes / 1024:.0f}KB"
        ws = (s.workspace_name or s.workspace_id or "?")[:20]
        
        topic = "..."
        try:
            parsed = parser.parse(s.file_path)
            # Find first non-empty user message
            # ChatTurn uses 'user_text', not 'role'/'content'
            for turn in parsed.turns:
                if turn.user_text and turn.user_text.strip():
                    raw = turn.user_text.strip().split('\n')[0]
                    # Remove markdown bold/etc if simple
                    raw = raw.replace('**', '').replace('#', '').strip()
                    topic = (raw[:50] + '..') if len(raw) > 50 else raw
                    break
        except Exception as e:
            # Show the error details
            topic = f"[Err: {str(e)[:40]}]"

        print(f"{mtime:<18} {size_kb:>8}  {ws:<20} {topic}")

    return 0


def cmd_search(args) -> int:
    scanner = SessionScanner()
    results = scanner.search(args.keyword, limit=args.limit)

    if not results:
        print(f'No sessions contain "{args.keyword}".')
        return 0

    print(f'Found {len(results)} sessions containing "{args.keyword}":')
    for s in results:
        ws = s.workspace_name or s.workspace_id or "?"
        print(f"  [{ws}] {s.session_id} ({s.format}, {s.size_bytes / 1024:.0f}KB)")

    return 0


def cmd_distill(args) -> int:
    scanner = SessionScanner()
    parser = ChatParser()
    privacy = PrivacyFilter()
    tracker = SessionTracker()

    # Build distiller engine if not dry-run
    engine = None
    if not args.dry_run and args.engine:
        from .engine import DistillerEngine
        engine = DistillerEngine(
            backend=args.engine,
            model=args.model,
        )

    # Build ingester if --store is set
    ingester = None
    if args.store and not args.dry_run:
        try:
            from .ingester import MemoryIngester
            ingester = MemoryIngester()
        except Exception as e:
            print(f"WARNING: Cannot connect to Elefante memory: {e}")
            print("Insights will be printed but not stored.")

    # Determine target
    if args.target == "latest":
        sessions = scanner.list_sessions(limit=1)
        if not sessions:
            print("No sessions found.")
            return 1
        _distill_one(sessions[0].file_path, parser, privacy, tracker,
                      engine=engine, ingester=ingester, dry_run=args.dry_run, export=args.export)
    elif args.target == "all":
        sessions = scanner.list_sessions(limit=500)
        processed = 0
        skipped = 0
        errors = 0
        for s in sessions:
            result = _distill_one(s.file_path, parser, privacy, tracker,
                                  engine=engine, ingester=ingester, dry_run=args.dry_run, export=args.export)
            if result == "skipped":
                skipped += 1
            elif result == "ok":
                processed += 1
            else:
                errors += 1
        print(f"\nDone: {processed} processed, {skipped} already up-to-date, {errors} errors.")
    else:
        target_path = args.target
        if not target_path.endswith((".json", ".jsonl")):
            sessions = scanner.list_sessions(limit=500)
            match = [s for s in sessions if s.session_id == args.target]
            if not match:
                print(f"Session not found: {args.target}")
                return 1
            target_path = match[0].file_path
        _distill_one(target_path, parser, privacy, tracker,
                      engine=engine, ingester=ingester, dry_run=args.dry_run, export=args.export)

    return 0


def _distill_one(
    path: str,
    parser: ChatParser,
    privacy: PrivacyFilter,
    tracker: SessionTracker,
    engine=None,
    ingester=None,
    dry_run: bool = False,
    export: str | None = None,
) -> str:
    """Process a single session. Returns 'ok', 'skipped', or 'error'."""
    try:
        session = parser.parse(path)
    except Exception as e:
        print(f"  ERROR parsing {path}: {e}")
        return "error"

    if not session.turns:
        return "skipped"

    # Idempotency check
    if tracker.is_processed(session.session_id, session.content_hash):
        return "skipped"

    # Privacy scrub
    for turn in session.turns:
        turn.user_text, _ = privacy.scrub(turn.user_text)
        for chunk in turn.response_chunks:
            chunk.value, _ = privacy.scrub(chunk.value)

    ws = session.workspace_name or session.workspace_id or "unknown"

    if dry_run:
        print(f"\n[DRY RUN] Session: {session.session_id[:12]}...")
        print(f"  Workspace: {ws}")
        print(f"  Turns: {session.turn_count}")
        print(f"  Hash: {session.content_hash}")
        print(f"  Preview:")
        for i, turn in enumerate(session.turns[:3], 1):
            preview = turn.user_text[:80].replace("\n", " ")
            print(f"    Turn {i}: {preview}...")
        if session.turn_count > 3:
            print(f"    ... and {session.turn_count - 3} more turns")
        return "ok"

    # ── Export markdown if requested ──
    if export:
        import os
        os.makedirs(export, exist_ok=True)
        out_path = os.path.join(export, f"{session.session_id}.md")
        with open(out_path, "w") as f:
            f.write(session.to_markdown())
        print(f"  Exported: {out_path}")

    # ── LLM Distillation (the money maker) ──
    insights = []
    if engine:
        try:
            print(f"  Distilling {session.session_id[:12]}... ({session.turn_count} turns, {ws})")
            result = engine.distill(session)
            insights = result.insights

            if insights:
                print(f"  Signal: {len(insights)} insights extracted (ratio {result.signal_ratio})")
                for i, ins in enumerate(insights, 1):
                    icon = {"decision": "D", "root_cause": "R", "preference": "P",
                            "architecture_rule": "A", "fact": "F", "code_snippet": "C",
                            "error_fix": "E", "workflow": "W"}.get(ins.insight_type.value, "?")
                    print(f"    [{icon}] {ins.content[:90]}")
            else:
                print(f"  No insights (session was all noise)")

            # Store insights in Elefante memory
            if ingester and insights:
                stored = ingester.store_insights(session, insights)
                print(f"  Stored {len(stored)} insights in Elefante memory")
                # Also store raw reference
                ingester.store_raw_reference(session)

        except ConnectionError as e:
            print(f"  LLM unavailable: {e}")
            print(f"  Falling back to raw archive only.")
        except Exception as e:
            print(f"  Distillation error: {e}")
            import traceback
            traceback.print_exc()
    else:
        md = session.to_markdown()
        print(f"  Parsed: {session.session_id[:12]}... ({session.turn_count} turns, {len(md)} chars)")
        print(f"  (No LLM engine — use --engine ollama|openai|anthropic to distill)")

    # Mark as processed
    tracker.mark_processed(session.session_id, session.content_hash, insights_count=len(insights))
    return "ok"


def cmd_stats(args) -> int:
    tracker = SessionTracker()
    stats = tracker.get_stats()
    scanner = SessionScanner()
    all_sessions = scanner.list_sessions(limit=500)

    print(f"Sessions discovered:  {len(all_sessions)}")
    print(f"Sessions processed:   {stats['total_processed']}")
    print(f"Sessions remaining:   {len(all_sessions) - stats['total_processed']}")
    print(f"Total insights:       {stats['total_insights']}")
    return 0


# ─── Argument Parser ─────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="elefante-distiller",
        description="Extract knowledge from VS Code chat sessions into Elefante memory.",
    )
    p.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    sub = p.add_subparsers(dest="command")

    # list
    ls = sub.add_parser("list", help="List recent chat sessions")
    ls.add_argument("-n", "--limit", type=int, default=20, help="Max sessions to show")

    # search
    sr = sub.add_parser("search", help="Search sessions by keyword")
    sr.add_argument("keyword", help="Text to search for")
    sr.add_argument("-n", "--limit", type=int, default=20)

    # distill
    di = sub.add_parser("distill", help="Parse, scrub, and distill a session")
    di.add_argument("target", nargs="?", default="latest", help="Session UUID, file path, 'latest', or 'all'")
    di.add_argument("--engine", "-e", choices=["ollama", "openai", "anthropic", "lmstudio"],
                    help="LLM backend for distillation")
    di.add_argument("--model", "-m", help="Model name (defaults per engine)")
    di.add_argument("--store", "-s", action="store_true",
                    help="Store insights into Elefante memory")
    di.add_argument("--export", help="Export parsed sessions as markdown to this directory")
    di.add_argument("--dry-run", action="store_true", help="Show what would be processed without storing")

    # stats
    sub.add_parser("stats", help="Show processing statistics")

    return p


if __name__ == "__main__":
    sys.exit(main())
