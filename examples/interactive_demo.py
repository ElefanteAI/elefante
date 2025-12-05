import asyncio
import sys
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from src.core.orchestrator import MemoryOrchestrator

async def chat_loop():
    print("\n🐘 Elefante Memory System - Interactive Demo")
    print("---------------------------------------------")
    print("Type a message to store it. Type 'exit' to quit.")
    print("Try: 'I live in Seattle' or 'My favorite color is blue'")
    print("---------------------------------------------\n")

    try:
        print("Initializing Brain...", end="", flush=True)
        orch = MemoryOrchestrator()
        print(" Done! 🧠\n")
    except Exception as e:
        print(f"\nError initializing: {e}")
        return

    # Session ID for this chat
    session_id = "demo-session-001"

    while True:
        try:
            user_input = input("\n👤 You: ")
            if user_input.lower() in ['exit', 'quit']:
                break
            
            if not user_input.strip():
                continue

            # 1. Add Memory
            print("   🐘 Elefante is thinking...", end="", flush=True)
            await orch.add_memory(
                content=user_input,
                metadata={"source": "demo", "session_id": session_id}
            )
            print(" [Memory Stored]")

            # 2. Retrieve Context (to show what it learned)
            context = await orch.get_context(session_id=session_id)
            
            # Extract User Profile facts
            user_facts = []
            for entity in context.get('entities', []):
                # Check for User Profile facts (linked to EnterpriseUser)
                if entity.get('is_user_fact'):
                    user_facts.append(entity['name']) # name contains the truncated content/fact
                elif entity.get('name') == 'EnterpriseUser':
                    pass # The user node itself

            if user_facts:
                print(f"   💡 I know this about you:")
                for fact in user_facts[-3:]: # Show last 3 facts
                    print(f"      - {fact}")
            else:
                print("   (No user facts detected yet)")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")

    print("\nGoodbye! 👋")

if __name__ == "__main__":
    asyncio.run(chat_loop())
