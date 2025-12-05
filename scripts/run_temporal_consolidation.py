#!/usr/bin/env python3
"""
Script to run temporal memory consolidation.
Archives low-strength memories based on temporal decay.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.temporal_consolidation import get_temporal_consolidator
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def main():
    """Run temporal consolidation process."""
    print("\n=== Temporal Memory Consolidation ===\n")
    
    consolidator = get_temporal_consolidator()
    
    # Get current stats
    print("1. Analyzing current memory strength distribution...")
    stats = await consolidator.get_consolidation_stats()
    
    print(f"\nCurrent Statistics:")
    print(f"  Total memories analyzed: {stats['total_memories']}")
    print(f"  Average strength: {stats['avg_strength']:.2f}")
    print(f"  Min strength: {stats['min_strength']:.2f}")
    print(f"  Max strength: {stats['max_strength']:.2f}")
    print(f"  Weak memories (< {consolidator.weak_threshold}): {stats['weak_count']}")
    print(f"  Archive candidates (< {consolidator.archive_threshold}): {stats['archive_candidates']}")
    
    if stats['archive_candidates'] == 0:
        print("\n[OK] No memories need archiving at this time.")
        return
    
    # Run consolidation
    print(f"\n2. Running consolidation process...")
    result = await consolidator.consolidate_weak_memories()
    
    print(f"\nConsolidation Results:")
    print(f"  Memories scanned: {result['scanned']}")
    print(f"  Weak memories found: {result['weak_found']}")
    print(f"  Memories archived: {result['archived']}")
    print(f"  Errors: {result['errors']}")
    print(f"  Timestamp: {result['timestamp']}")
    
    if result['archived'] > 0:
        print(f"\n[OK] Successfully archived {result['archived']} low-strength memories")
    else:
        print("\n[OK] No memories were archived")
    
    print("\n=== Consolidation Complete ===\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nConsolidation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError during consolidation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

# Made with Bob
