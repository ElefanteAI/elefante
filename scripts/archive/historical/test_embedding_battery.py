"""
Embedding Model Test Battery - 35 Questions
Tests the new thenlper/gte-base embedding model with fresh embeddings.

This test:
1. Loads existing memories from ChromaDB (raw documents)
2. Re-embeds them with the new model into a temp collection
3. Runs 35 test queries against the fresh embeddings
4. Cleans up the temp collection

Run:
  .venv/bin/python scripts/test_embedding_battery.py
"""

import asyncio
import uuid
from datetime import datetime
from dataclasses import dataclass
from typing import List

import chromadb
from chromadb.config import Settings

from src.core.embeddings import get_embedding_service
from src.utils.config import get_config


@dataclass
class QueryResult:
    """Single query result"""
    rank: int
    similarity: float
    memory_type: str
    content_preview: str
    memory_id: str


@dataclass
class TestCase:
    """Test case with results"""
    query_num: int
    query: str
    category: str
    top_k: int
    results: List[QueryResult]
    avg_similarity: float
    hit_count: int


async def run_query(collection, embedding_service, query: str, top_k: int = 5) -> List[QueryResult]:
    """Run a single query and return results"""
    query_embedding = await embedding_service.generate_embedding(query)
    
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    
    query_results = []
    if results["ids"] and len(results["ids"][0]) > 0:
        for i in range(len(results["ids"][0])):
            distance = results["distances"][0][i]
            similarity = max(0.0, min(1.0, 1.0 - distance))
            
            metadata = results["metadatas"][0][i]
            content = results["documents"][0][i]
            memory_type = metadata.get("memory_type", "unknown")
            content_preview = content[:100] + "..." if len(content) > 100 else content
            
            query_results.append(QueryResult(
                rank=i + 1,
                similarity=similarity,
                memory_type=memory_type,
                content_preview=content_preview.replace("\n", " "),
                memory_id=results["ids"][0][i][:8]
            ))
    
    return query_results


async def main():
    # 35 test queries across different categories
    test_queries = [
        # Identity & Preferences (1-5)
        ("Who is Jaime?", "identity"),
        ("What are Jaime's coding preferences?", "preferences"),
        ("What programming languages does Jaime use?", "preferences"),
        ("How does Jaime like to communicate?", "preferences"),
        ("What is Jaime's development style?", "preferences"),
        
        # Project Knowledge (6-10)
        ("What is Elefante?", "project"),
        ("How does Elefante store memories?", "project"),
        ("What databases does Elefante use?", "project"),
        ("What is the MCP server?", "project"),
        ("How does the dashboard work?", "project"),
        
        # Technical Concepts (11-15)
        ("What is ChromaDB?", "technical"),
        ("How does Kuzu work?", "technical"),
        ("What are embeddings?", "technical"),
        ("What is semantic search?", "technical"),
        ("How does vector similarity work?", "technical"),
        
        # Decisions & Learnings (16-20)
        ("What decisions were made about the schema?", "decisions"),
        ("What problems were encountered?", "decisions"),
        ("What bugs were fixed?", "decisions"),
        ("What architecture choices were made?", "decisions"),
        ("What lessons were learned?", "decisions"),
        
        # Workflow & Process (21-25)
        ("How should code be tested?", "workflow"),
        ("What is the development process?", "workflow"),
        ("How to debug issues?", "workflow"),
        ("What are best practices?", "workflow"),
        ("How to handle errors?", "workflow"),
        
        # Fuzzy / Natural Language (26-30)
        ("remember that thing about the database lock", "fuzzy"),
        ("the issue with reserved words", "fuzzy"),
        ("something about Python version", "fuzzy"),
        ("that bug we fixed yesterday", "fuzzy"),
        ("preferences for organizing code", "fuzzy"),
        
        # Edge Cases (31-35)
        ("IBM", "edge"),
        ("Bob", "edge"),
        ("v1.1.0", "edge"),
        ("transaction locking", "edge"),
        ("neural register", "edge"),
    ]
    
    # Initialize
    config = get_config()
    persist_dir = config.elefante.vector_store.persist_directory
    original_collection_name = config.elefante.vector_store.collection_name
    embedding_model = config.elefante.embeddings.model
    test_collection_name = f"test_gte_base_{uuid.uuid4().hex[:8]}"
    
    print(f"\n{'='*100}")
    print(f"ELEFANTE EMBEDDING TEST BATTERY")
    print(f"{'='*100}")
    print(f"Model: {embedding_model}")
    print(f"Original Collection: {original_collection_name}")
    print(f"Test Collection: {test_collection_name}")
    print(f"Queries: {len(test_queries)}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"{'='*100}\n")
    
    client = chromadb.PersistentClient(
        path=persist_dir,
        settings=Settings(anonymized_telemetry=False, allow_reset=True),
    )
    
    # Load original memories
    original_collection = client.get_collection(name=original_collection_name)
    total_memories = original_collection.count()
    print(f"Total memories in original database: {total_memories}")
    
    # Get all documents from original collection
    all_data = original_collection.get(include=["documents", "metadatas"])
    print(f"Loaded {len(all_data['ids'])} memories for re-embedding\n")
    
    # Initialize embedding service
    embedding_service = get_embedding_service()
    
    # Create test collection with new embeddings
    print(f"Creating test collection with {embedding_model} embeddings...")
    test_collection = client.create_collection(
        name=test_collection_name,
        metadata={"hnsw:space": "cosine"}
    )
    
    # Re-embed and add to test collection
    print("Re-embedding memories with new model...")
    batch_size = 10
    for i in range(0, len(all_data['ids']), batch_size):
        batch_ids = all_data['ids'][i:i+batch_size]
        batch_docs = all_data['documents'][i:i+batch_size]
        batch_metas = all_data['metadatas'][i:i+batch_size]
        
        # Generate embeddings for batch
        embeddings = []
        for doc in batch_docs:
            emb = await embedding_service.generate_embedding(doc)
            embeddings.append(emb)
        
        test_collection.add(
            ids=batch_ids,
            documents=batch_docs,
            metadatas=batch_metas,
            embeddings=embeddings
        )
        print(f"  Embedded {min(i+batch_size, len(all_data['ids']))}/{len(all_data['ids'])} memories")
    
    print(f"\nTest collection ready with {test_collection.count()} memories\n")
    
    # Run all tests
    test_cases: List[TestCase] = []
    category_stats = {}
    
    print(f"{'='*100}")
    print("RUNNING 35 TEST QUERIES")
    print(f"{'='*100}\n")
    
    for i, (query, category) in enumerate(test_queries, 1):
        print(f"[{i:02d}/35] {category.upper():12} | {query[:50]:<50}", end=" ")
        
        results = await run_query(test_collection, embedding_service, query, top_k=5)
        
        avg_sim = sum(r.similarity for r in results) / len(results) if results else 0.0
        hit_count = sum(1 for r in results if r.similarity >= 0.3)
        
        test_case = TestCase(
            query_num=i,
            query=query,
            category=category,
            top_k=5,
            results=results,
            avg_similarity=avg_sim,
            hit_count=hit_count
        )
        test_cases.append(test_case)
        
        # Track category stats
        if category not in category_stats:
            category_stats[category] = {"total": 0, "avg_sim_sum": 0.0, "hit_sum": 0}
        category_stats[category]["total"] += 1
        category_stats[category]["avg_sim_sum"] += avg_sim
        category_stats[category]["hit_sum"] += hit_count
        
        top_sim = results[0].similarity if results else 0.0
        print(f"| top={top_sim:.3f} avg={avg_sim:.3f} hits={hit_count}")
    
    # Print detailed results
    print(f"\n{'='*100}")
    print("DETAILED RESULTS")
    print(f"{'='*100}\n")
    
    for tc in test_cases:
        print(f"\n[Q{tc.query_num:02d}] {tc.query}")
        print(f"     Category: {tc.category} | Avg Sim: {tc.avg_similarity:.4f} | Hits (≥0.3): {tc.hit_count}")
        print(f"     {'Rank':<5} {'Sim':<8} {'Type':<12} {'Preview':<70}")
        print(f"     {'-'*95}")
        for r in tc.results:
            print(f"     {r.rank:<5} {r.similarity:<8.4f} {r.memory_type:<12} {r.content_preview[:70]}")
    
    # Print summary by category
    print(f"\n{'='*100}")
    print("SUMMARY BY CATEGORY")
    print(f"{'='*100}\n")
    print(f"{'Category':<15} {'Queries':<10} {'Avg Sim':<12} {'Avg Hits':<12}")
    print("-" * 50)
    
    overall_sim = 0.0
    overall_hits = 0
    total_queries = 0
    
    for cat, stats in sorted(category_stats.items()):
        n = stats["total"]
        avg_sim = stats["avg_sim_sum"] / n
        avg_hits = stats["hit_sum"] / n
        print(f"{cat:<15} {n:<10} {avg_sim:<12.4f} {avg_hits:<12.2f}")
        overall_sim += stats["avg_sim_sum"]
        overall_hits += stats["hit_sum"]
        total_queries += n
    
    print("-" * 50)
    print(f"{'OVERALL':<15} {total_queries:<10} {overall_sim/total_queries:<12.4f} {overall_hits/total_queries:<12.2f}")
    
    # Cleanup
    print(f"\nCleaning up test collection...")
    client.delete_collection(name=test_collection_name)
    print(f"Deleted test collection: {test_collection_name}")
    
    # Final verdict
    print(f"\n{'='*100}")
    print("VERDICT")
    print(f"{'='*100}")
    
    global_avg = overall_sim / total_queries
    global_hit_rate = overall_hits / (total_queries * 5)  # 5 results per query
    
    print(f"Model: {embedding_model}")
    print(f"Memories tested: {total_memories}")
    print(f"Queries run: {total_queries}")
    print(f"Global Average Similarity: {global_avg:.4f}")
    print(f"Global Hit Rate (≥0.3):    {global_hit_rate:.2%}")
    
    if global_avg >= 0.35:
        print(f"Status: ✅ EXCELLENT - Model performing well")
    elif global_avg >= 0.25:
        print(f"Status: ✅ GOOD - Model acceptable")
    elif global_avg >= 0.15:
        print(f"Status: ⚠️  MARGINAL - Consider tuning")
    else:
        print(f"Status: ❌ POOR - Model needs review")
    
    print(f"\n{'='*100}")


if __name__ == "__main__":
    asyncio.run(main())
