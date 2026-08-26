"""Test the DistillerEngine's JSON response parser in isolation (no LLM needed)."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.modules.distiller.engine import DistillerEngine

# Build engine without __init__ (skip prompt loading)
engine = DistillerEngine.__new__(DistillerEngine)
engine.backend = 'test'

# Simulate LLM response wrapped in code fences (common behavior)
fake_response = '''```json
[
  {
    "type": "decision",
    "content": "Use Astro with React islands for the landing page to minimize JS bundle size while keeping interactive components.",
    "tags": ["architecture", "frontend", "astro"],
    "source_turn": 3,
    "confidence": 0.9
  },
  {
    "type": "error_fix",
    "content": "When PDF streams fail on Windows, use wb (binary write) mode instead of w (text) mode to prevent encoding corruption.",
    "tags": ["python", "pdf", "windows"],
    "source_turn": 7,
    "confidence": 0.95
  },
  {
    "type": "preference",
    "content": "The user prefers maximum brevity in responses. No emojis unless requested.",
    "tags": ["communication"],
    "source_turn": null,
    "confidence": 0.85
  },
  {
    "type": "unknown_type_test",
    "content": "This has an unknown type and should default to fact.",
    "tags": [],
    "confidence": 0.5
  }
]
```'''

insights = engine._parse_response(fake_response, 'test-session-123')

print(f"Parsed {len(insights)} insights:")
for i in insights:
    print(f"  [{i.insight_type.value:20s}] conf={i.confidence} turn={i.source_turn} tags={i.suggested_tags}")
    print(f"    {i.content[:90]}")

assert len(insights) == 4, f"Expected 4 insights, got {len(insights)}"
assert insights[0].insight_type.value == "decision"
assert insights[2].source_turn is None
assert insights[3].insight_type.value == "fact"  # Unknown type → default

# Test empty response
empty = engine._parse_response("[]", "empty-session")
assert empty == [], f"Expected empty list, got {empty}"

# Test garbage response
garbage = engine._parse_response("This is not JSON at all.", "broken-session")
assert garbage == [], f"Expected empty for garbage input, got {garbage}"

print("\nAll engine parser tests PASSED")
