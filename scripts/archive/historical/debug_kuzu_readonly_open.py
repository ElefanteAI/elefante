import kuzu

from src.utils.config import get_config


def test_real_db_readonly_open():
    config = get_config()
    db_path = config.elefante.graph_store.database_path
    print(f"Testing Real DB Path: {db_path}", flush=True)

    try:
        print("Attempting to open DB in READ_ONLY mode...", flush=True)
        db = kuzu.Database(db_path, read_only=True)
        conn = kuzu.Connection(db)
        results = conn.execute("MATCH (n) RETURN count(n)")
        if results.has_next():
            print(f"Success! Node count: {results.get_next()[0]}", flush=True)
        else:
            print("Success! (No nodes found)", flush=True)
    except Exception as e:
        print(f"Failed to open real DB: {e}", flush=True)


if __name__ == "__main__":
    test_real_db_readonly_open()
