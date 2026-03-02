import os
import time
import psutil
import statistics
import asyncio
from chromadb.api import ClientAPI
from src.core.orchestrator import MemoryOrchestrator
from src.core.vector_store import get_vector_store
from src.core.graph_store import get_graph_store
from src.core.embeddings import get_embedding_service
from src.utils.config import get_config

def get_memory_mb():
    return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)

class BenchmarkStrategy:
    def setup(self): pass
    def ingest(self, d_id: str, content: str, expected_meta: dict): pass
    def retrieve(self, query: str) -> list: pass
    def evaluate(self, retrieved: list, expected_id: str) -> bool: pass

class ElefanteStrategy(BenchmarkStrategy):
    def setup(self):
        self.orchestrator = MemoryOrchestrator(
            get_vector_store(), get_graph_store(), get_embedding_service()
        )
        self.loop = asyncio.get_event_loop()
        
    def ingest(self, d_id: str, content: str, expected_meta: dict):
        self.loop.run_until_complete(
            self.orchestrator.add_memory(
                content=content,
                metadata={"title": d_id, **expected_meta},
                force_new=True
            )
        )

    def retrieve(self, query: str) -> list:
        results = self.loop.run_until_complete(
            self.orchestrator.search_memories(query=query, limit=5)
        )
        return [r.memory.content for r in results]

    def evaluate(self, retrieved: list, expected_id: str) -> bool:
        return any(expected_id in r for r in retrieved)

class BaselineStrategy(BenchmarkStrategy):
    def setup(self):
        config = get_config()
        # Initialize raw chromadb client ignoring kuzu logic
        import chromadb
        from chromadb.config import Settings
        path = config.elefante.vector_store.persist_directory
        self.chroma = chromadb.PersistentClient(path=path, settings=Settings(anonymized_telemetry=config.elefante.anonymized_telemetry, allow_reset=True))
        self.collection = self.chroma.get_or_create_collection("benchmark_baseline")
        
    def ingest(self, d_id: str, content: str, expected_meta: dict):
        self.collection.upsert(
            documents=[content],
            metadatas=[expected_meta],
            ids=[d_id]
        )

    def retrieve(self, query: str) -> list:
        res = self.collection.query(
            query_texts=[query],
            n_results=5
        )
        if res['documents'] and res['documents'][0]:
            return res['documents'][0]
        return []

    def evaluate(self, retrieved: list, expected_id: str) -> bool:
        return any(expected_id in str(r) for r in retrieved)

def extract_metrics(name: str, strategy: BenchmarkStrategy, dataset: list, queries: list):
    strategy.setup()
    
    # Measure Ingestion
    mem_before = get_memory_mb()
    t0 = time.perf_counter()
    for item in dataset:
        strategy.ingest(item['id'], item['content'], item['meta'])
    ingest_time_total = time.perf_counter() - t0
    memory_footprint = get_memory_mb() - mem_before
    
    ingest_latency_ms = (ingest_time_total / len(dataset)) * 1000
    
    # Measure Retrieval & Recall
    latencies = []
    hits = 0
    for q in queries:
        t0 = time.perf_counter()
        results = strategy.retrieve(q['query'])
        latencies.append((time.perf_counter() - t0) * 1000)
        if strategy.evaluate(results, q['expected_id']):
            hits += 1
            
    retrieve_latency_ms = statistics.mean(latencies)
    recall_accuracy = (hits / len(queries)) * 100
    
    return {
        "System": name,
        "Ingestion Latency (ms)": f"{ingest_latency_ms:.2f}",
        "Retrieval Latency (ms)": f"{retrieve_latency_ms:.2f}",
        "Memory Footprint (MB)": f"{memory_footprint:.2f}",
        "Context Recall Accuracy (%)": f"{recall_accuracy:.1f}",
    }

if __name__ == "__main__":
    test_dataset = [{"id": f"entity_target_{i}", "content": f"The relationship between Entity_{i} and Target_{i} is defined here. entity_target_{i}", "meta": {"test": "benchmark"}} for i in range(100)]
    test_queries = [{"query": f"What is the relationship for Entity_{i}?", "expected_id": f"entity_target_{i}"} for i in range(10)]
    
    baselines = [
        ("Standard Local ChromaDB (Baseline)", BaselineStrategy()),
        ("Elefante Hybrid (ChromaDB + Kuzu)", ElefanteStrategy())
    ]
    
    headers = ["System", "Ingestion Latency (ms)", "Retrieval Latency (ms)", "Memory Footprint (MB)", "Context Recall Accuracy (%)"]
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join(["---"] * len(headers)) + "|")
    
    for name, strat in baselines:
        res = extract_metrics(name, strat, test_dataset, test_queries)
        print("| " + " | ".join(str(res[k]) for k in headers) + " |")
