"""
Store user preferences in Elefante
This demonstrates how to store important working style preferences
that the AI assistant should remember
"""

import asyncio
import sys
import io
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.orchestrator import get_orchestrator
from src.models.memory import MemoryType

async def store_preferences():
    """Store example user preferences"""
    
    orchestrator = get_orchestrator()
    
    print("\n" + "="*70)
    print("🐘 STORING USER PREFERENCES IN ELEFANTE")
    print("="*70 + "\n")
    
    # Preference 1: Communication style
    print("📝 Storing preference: Communication style...")
    memory1 = await orchestrator.add_memory(
        content=(
            "The user prefers clear, concise communication with technical details. "
            "They appreciate step-by-step explanations and want to understand the "
            "reasoning behind decisions. Avoid unnecessary verbosity but provide "
            "sufficient context for complex topics."
        ),
        memory_type=MemoryType.NOTE,
        importance=9,
        tags=["preference", "communication", "style"],
        entities=[
            {"name": "User", "type": "person"},
            {"name": "communication style", "type": "concept"}
        ]
    )
    print(f"✅ Stored: {memory1.id}\n")
    
    # Preference 2: Code organization
    print("📝 Storing preference: Code organization...")
    memory2 = await orchestrator.add_memory(
        content=(
            "The user values clean, well-organized code with proper documentation. "
            "They prefer modular design patterns and appreciate when code follows "
            "established best practices. Comments should explain 'why' not 'what'."
        ),
        memory_type=MemoryType.NOTE,
        importance=8,
        tags=["preference", "code", "organization", "best-practices"],
        entities=[
            {"name": "User", "type": "person"},
            {"name": "code quality", "type": "concept"}
        ]
    )
    print(f"✅ Stored: {memory2.id}\n")
    
    # Preference 3: Working hours
    print("📝 Storing preference: Working schedule...")
    memory3 = await orchestrator.add_memory(
        content=(
            "The user typically works during standard business hours in their timezone. "
            "They prefer to batch similar tasks together and appreciate reminders "
            "about pending items at the start of work sessions."
        ),
        memory_type=MemoryType.FACT,
        importance=7,
        tags=["preference", "schedule", "workflow"],
        entities=[
            {"name": "User", "type": "person"},
            {"name": "work schedule", "type": "concept"}
        ]
    )
    print(f"✅ Stored: {memory3.id}\n")
    
    # Preference 4: Learning style
    print("📝 Storing preference: Learning approach...")
    memory4 = await orchestrator.add_memory(
        content=(
            "The user learns best through practical examples and hands-on experimentation. "
            "They appreciate when new concepts are demonstrated with working code samples "
            "and real-world use cases rather than abstract theory."
        ),
        memory_type=MemoryType.NOTE,
        importance=8,
        tags=["preference", "learning", "education"],
        entities=[
            {"name": "User", "type": "person"},
            {"name": "learning style", "type": "concept"}
        ]
    )
    print(f"✅ Stored: {memory4.id}\n")
    
    print("="*70)
    print("✅ ALL PREFERENCES STORED SUCCESSFULLY")
    print("="*70)
    print("\nThese preferences will now be automatically retrieved")
    print("whenever the AI assistant works with you!")
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(store_preferences())

# Made with Bob
