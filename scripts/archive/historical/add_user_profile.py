"""
Add user profile memories to Elefante system.
This script stores the user's professional profile, preferences, and context.
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.orchestrator import MemoryOrchestrator

async def add_user_profile():
    """Add comprehensive user profile to memory system."""
    orchestrator = MemoryOrchestrator()
    
    print("\n" + "="*70)
    print("ADDING USER PROFILE TO ELEFANTE")
    print("="*70)
    
    memories = [
        {
            "content": "User Profile: Senior AI & Data Leader with ~20 years expert-level experience. Domain expertise: Applied AI Strategy, Data Science, IT Consulting, Prompt Engineering. Skill gaps: Infrastructure, Server Tooling, Packaging, DevOps. CRITICAL: Skip high-level AI explanations. Provide detailed, step-by-step instructions for infrastructure and CLI tasks.",
            "memory_type": "fact",
            "importance": 10,
            "tags": ["user-profile", "expertise", "communication-style"],
            "entities": [
                {"name": "User", "type": "person"},
                {"name": "AI Strategy", "type": "concept"},
                {"name": "DevOps", "type": "technology"}
            ]
        },
        {
            "content": "Communication Preferences: Direct, Technical, Clinical tone REQUIRED. FORBIDDEN: Apologizing, Small talk, Marketing fluff, Moralizing lectures. Preferred format: Lists, Tables, Code Blocks. Feedback loop: Implement corrections immediately without explaining 'why' unless asked.",
            "memory_type": "decision",
            "importance": 10,
            "tags": ["user-profile", "communication", "preferences"],
            "entities": [
                {"name": "User", "type": "person"}
            ]
        },
        {
            "content": "Workflow Enforcement: Methodology = Requirements -> Design -> Tasks. Philosophy = Local-First / Private AI. Privacy level = HIGH (Avoid PII leakage to cloud models). Always prioritize local solutions over cloud services.",
            "memory_type": "decision",
            "importance": 10,
            "tags": ["user-profile", "workflow", "privacy"],
            "entities": [
                {"name": "User", "type": "person"},
                {"name": "Local-First AI", "type": "concept"}
            ]
        },
        {
            "content": "Development Environment: OS platforms = macOS (Apple Silicon), Windows. Hybrid development environment. REQUIREMENT: Provide OS-agnostic solutions where possible, or specify commands for both Bash/Zsh AND PowerShell/WSL.",
            "memory_type": "fact",
            "importance": 9,
            "tags": ["user-profile", "environment", "cross-platform"],
            "entities": [
                {"name": "User", "type": "person"},
                {"name": "macOS", "type": "technology"},
                {"name": "Windows", "type": "technology"}
            ]
        },
        {
            "content": "Active Project Context: Project Elefante - Local AI memory system. Domain: elefante.ai. This is the user's current primary focus. All work should consider integration with and improvement of this system.",
            "memory_type": "fact",
            "importance": 10,
            "tags": ["user-profile", "current-project", "elefante"],
            "entities": [
                {"name": "User", "type": "person"},
                {"name": "Project Elefante", "type": "project"},
                {"name": "elefante.ai", "type": "project"}
            ]
        },
        {
            "content": "User's Skill Profile: EXPERT in AI/ML strategy, data science, prompt engineering. NOVICE in infrastructure, server tooling, packaging, DevOps. Implication: Provide detailed infrastructure instructions with explicit commands. Assume deep AI knowledge but explain infrastructure concepts step-by-step.",
            "memory_type": "insight",
            "importance": 9,
            "tags": ["user-profile", "skills", "learning-needs"],
            "entities": [
                {"name": "User", "type": "person"}
            ]
        },
        {
            "content": "Communication Anti-Patterns to AVOID with this user: (1) Apologizing for errors or limitations, (2) Engaging in small talk or pleasantries, (3) Using marketing language or hype, (4) Providing moral lectures or ethical warnings unless explicitly asked, (5) Explaining 'why' when user just wants 'how'.",
            "memory_type": "decision",
            "importance": 10,
            "tags": ["user-profile", "communication", "anti-patterns"],
            "entities": [
                {"name": "User", "type": "person"}
            ]
        },
        {
            "content": "User's Privacy Requirements: HIGH privacy level. Avoid PII leakage to cloud models. Prefer local-first solutions. When cloud services are necessary, explicitly flag privacy implications. User values data sovereignty and control.",
            "memory_type": "decision",
            "importance": 10,
            "tags": ["user-profile", "privacy", "security"],
            "entities": [
                {"name": "User", "type": "person"},
                {"name": "Privacy", "type": "concept"}
            ]
        }
    ]
    
    added_count = 0
    for i, memory_data in enumerate(memories, 1):
        try:
            result = await orchestrator.add_memory(**memory_data)
            print(f"\n[{i}/8] SUCCESS: {memory_data['content'][:80]}...")
            print(f"        ID: {result.id}")
            print(f"        Type: {memory_data['memory_type']}, Importance: {memory_data['importance']}")
            added_count += 1
        except Exception as e:
            print(f"\n[{i}/8] FAILED: {str(e)}")
    
    print("\n" + "="*70)
    print(f"USER PROFILE COMPLETE: {added_count}/8 memories added")
    print("="*70)
    
    # Verify
    stats = await orchestrator.get_stats()
    print(f"\nTotal memories in system: {stats['vector_store']['total_memories']}")
    print(f"Total entities in graph: {stats['graph_store']['total_entities']}")

if __name__ == "__main__":
    asyncio.run(add_user_profile())

