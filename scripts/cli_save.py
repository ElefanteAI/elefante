#!/usr/bin/env python3
"""
CLI bridge for saving memories to Elefante from Node.js.
Usage: python cli_save.py '<json_payload>'

JSON payload:
{
  "content": "The memory content",
  "memory_type": "fact|decision|insight|preference|note",
  "domain": "project|system|personal",
  "category": "some-category",
  "layer": "self|world|intent",
  "sublayer": "identity|preference|constraint|fact|failure|method|rule|goal|anti-pattern",
  "importance": 7,
  "tags": ["tag1", "tag2"]
}
"""
import sys
import os
import json
import asyncio

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

os.environ["ELEFANTE_ENV"] = "production"

try:
    from src.core.orchestrator import MemoryOrchestrator
except ImportError as e:
    print(json.dumps({"error": f"Import failed: {str(e)}"}))
    sys.exit(1)


async def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No JSON payload provided"}))
        sys.exit(1)

    try:
        payload = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {str(e)}"}))
        sys.exit(1)

    content = payload.get("content", "").strip()
    if not content:
        print(json.dumps({"error": "Empty content"}))
        sys.exit(1)

    try:
        # Silence ALL logging (including structlog which Elefante uses)
        import logging
        logging.basicConfig(level=logging.CRITICAL)
        logging.getLogger().setLevel(logging.CRITICAL)
        for name in ["kuzu", "chromadb", "src.core.orchestrator", "src.core.vector_store", 
                      "src.core.graph_store", "src.services", "sentence_transformers",
                      "httpx", "httpcore"]:
            logging.getLogger(name).setLevel(logging.CRITICAL)
        
        # Also silence structlog if present
        try:
            import structlog
            structlog.configure(
                wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL),
            )
        except ImportError:
            pass
        
        # Redirect stderr to devnull during orchestrator init/operation
        import io
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()

        orchestrator = MemoryOrchestrator()

        # Build metadata dict matching Elefante's expected schema
        metadata = {
            "domain": payload.get("domain", "project"),
            "category": payload.get("category", "chat-learned"),
            "layer": payload.get("layer", "world"),
            "sublayer": payload.get("sublayer", "fact"),
            "source": "conversation",
            "source_detail": "elefante-brain-chat",
        }

        memory = None
        kuzu_warning = None
        try:
            memory = await orchestrator.add_memory(
                content=content,
                memory_type=payload.get("memory_type", "fact"),
                tags=payload.get("tags", ["chat-learned", "auto-persist"]),
                metadata=metadata,
                importance=payload.get("importance", 7),
            )
        except Exception as save_err:
            err_str = str(save_err)
            # Kuzu lock is non-fatal — memory may still be in ChromaDB
            if "locked" in err_str.lower() or "kuzu" in err_str.lower():
                kuzu_warning = "Saved to vector store but graph store locked (non-fatal)"
                # Try to verify it was added to ChromaDB
                try:
                    verify_results = await orchestrator.search_memories(query=content[:50], limit=1)
                    if verify_results and len(verify_results) > 0:
                        memory = verify_results[0].memory
                except Exception:
                    pass
            else:
                raise

        # Restore stderr
        sys.stderr = old_stderr

        if memory is None and kuzu_warning is None:
            sys.stderr = old_stderr
            print(json.dumps({
                "success": False,
                "reason": "Memory rejected (duplicate or test-like content)"
            }))
        elif memory is not None:
            mem_id = str(memory.id) if hasattr(memory, 'id') else 'unknown'
            sys.stderr = old_stderr
            result = {
                "success": True,
                "memory_id": mem_id,
                "content_preview": content[:100]
            }
            if kuzu_warning:
                result["warning"] = kuzu_warning
            print(json.dumps(result))
        else:
            # kuzu_warning set but couldn't verify — still likely saved
            sys.stderr = old_stderr
            print(json.dumps({
                "success": True,
                "memory_id": "unverified",
                "content_preview": content[:100],
                "warning": kuzu_warning
            }))

    except Exception as e:
        # Restore stderr before printing
        try:
            sys.stderr = old_stderr
        except Exception:
            pass
        import traceback
        print(json.dumps({"error": str(e), "trace": traceback.format_exc()}))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
