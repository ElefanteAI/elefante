"""
M4 Silicon Compatibility Verification Script
--------------------------------------------
Verifies that critical libraries work correctly on macOS Apple Silicon (ARM64).
Specifically checks:
1. PyTorch / Sentence Transformers (MPS/CPU support)
2. ChromaDB (SQLite/HNSW compatibility)
3. Kuzu (Graph DB native binaries)
"""

import sys
import platform
import os
import time

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def verify_architecture():
    log("  Checking System Architecture...")
    system = platform.system()
    machine = platform.machine()
    processor = platform.processor()
    
    print(f"   System: {system}")
    print(f"   Machine: {machine}")
    print(f"   Processor: {processor}")
    
    if system == "Darwin" and machine == "arm64":
        log(" Detected macOS Apple Silicon (M-series).")
        return True
    else:
        log(f"  Detected {system} {machine}. Not strictly M-series, but proceeding.")
        return False

def verify_sentence_transformers():
    log("\n Verifying Sentence Transformers (PyTorch)...")
    try:
        from sentence_transformers import SentenceTransformer
        
        # Load model
        log("   Loading 'all-MiniLM-L6-v2'...")
        model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Test encoding
        log("   Testing embedding generation...")
        embeddings = model.encode(["This is a test sentence for M4 verification."])
        
        shape = embeddings.shape
        log(f"    Embedding generated. Shape: {shape}")
        return True
    except Exception as e:
        log(f"    Sentence Transformers failed: {e}")
        return False

def verify_chromadb():
    log("\n Verifying ChromaDB (Vector Store)...")
    try:
        import chromadb
        from chromadb.config import Settings
        
        # Create ephemeral client
        log("   Initializing ephemeral client...")
        client = chromadb.Client(Settings(
            is_persistent=False,
            anonymized_telemetry=False
        ))
        
        # Create collection
        collection = client.create_collection(name="test_m4_collection")
        
        # Add data
        log("   Adding data...")
        collection.add(
            documents=["This is a test document"],
            metadatas=[{"source": "test"}],
            ids=["id1"]
        )
        
        # Query
        log("   Querying data...")
        results = collection.query(
            query_texts=["test"],
            n_results=1
        )
        
        if results['ids'][0][0] == 'id1':
            log("    ChromaDB read/write successful.")
            return True
        else:
            log("    ChromaDB query returned unexpected results.")
            return False
            
    except Exception as e:
        log(f"    ChromaDB failed: {e}")
        # Common M1/M2/M3/M4 issue: SQLite version
        import sqlite3
        log(f"     SQLite version: {sqlite3.sqlite_version}")
        return False

def verify_kuzu():
    log("\n  Verifying Kuzu (Graph DB)...")
    try:
        import kuzu
        import shutil
        
        db_path = "./test_kuzu_m4_db"
        if os.path.exists(db_path):
            if os.path.isdir(db_path):
                shutil.rmtree(db_path)
            else:
                os.remove(db_path)
            
        # Initialize DB
        log("   Initializing Kuzu database...")
        db = kuzu.Database(db_path)
        conn = kuzu.Connection(db)
        
        # Create schema
        log("   Creating schema...")
        conn.execute("CREATE NODE TABLE User(name STRING, age INT64, PRIMARY KEY (name))")
        
        # Insert data
        log("   Inserting data...")
        conn.execute("CREATE (:User {name: 'Alice', age: 30})")
        
        # Query data
        log("   Querying data...")
        results = conn.execute("MATCH (u:User) RETURN u.name, u.age")
        
        row = results.get_next()
        if row[0] == 'Alice' and row[1] == 30:
            log("    Kuzu read/write successful.")
            # Cleanup
            conn = None
            db = None
            if os.path.isdir(db_path):
                shutil.rmtree(db_path)
            elif os.path.exists(db_path):
                os.remove(db_path)
            return True
        else:
            log("    Kuzu query returned unexpected results.")
            return False
            
    except Exception as e:
        log(f"    Kuzu failed: {e}")
        return False

def main():
    print("============================================================")
    print(" ELEFANTE M4 SILICON COMPATIBILITY CHECK")
    print("============================================================")
    
    verify_architecture()
    
    st_ok = verify_sentence_transformers()
    chroma_ok = verify_chromadb()
    kuzu_ok = verify_kuzu()
    
    print("\n============================================================")
    print(" SUMMARY")
    print("============================================================")
    print(f"Sentence Transformers: {' PASS' if st_ok else ' FAIL'}")
    print(f"ChromaDB:              {' PASS' if chroma_ok else ' FAIL'}")
    print(f"Kuzu Graph DB:         {' PASS' if kuzu_ok else ' FAIL'}")
    print("============================================================")
    
    if st_ok and chroma_ok and kuzu_ok:
        print("\n System is fully compatible with M4 Silicon.")
        sys.exit(0)
    else:
        print("\n Compatibility issues detected.")
        sys.exit(1)

if __name__ == "__main__":
    main()
