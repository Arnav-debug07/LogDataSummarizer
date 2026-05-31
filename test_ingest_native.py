import sys
import os
import shutil

# Reconfigure stdout/stderr to support UTF-8 on Windows
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# 1. Clean up local database directory FIRST before importing the module
# This guarantees that the imported 'table' will be a fresh, empty database
db_path = "./local_radar_db"
if os.path.exists(db_path):
    print(f"[*] Deleting existing database folder at {db_path} to ensure a fresh environment...")
    try:
        shutil.rmtree(db_path)
        print("[✔] Database folder deleted!")
    except Exception as e:
        print(f"[WARNING] Could not delete folder: {e}. Attempting standard table clearance instead.")

# Now import all elements from the RAG engine
from radar_rag_engine import (
    table,
    parse_native_log_format,
    bulk_add_telemetry,
    hybrid_retrieve,
    process_radar_inquiry,
    ContinuumMemory
)

def test_pipeline():
    print("=== STARTING NATIVE DATASET INGESTION & PIPELINE TEST ===")

    # 2. Load and parse native_logs.txt
    if not os.path.exists("native_logs.txt"):
        print("[ERROR] native_logs.txt not found!")
        return

    with open("native_logs.txt", "r") as f:
        raw_lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]

    print(f"[*] Parsing {len(raw_lines)} lines from native_logs.txt...")
    records, errors = parse_native_log_format(raw_lines, session_date="2026-05-24")
    
    # 3. Insert records
    print(f"[*] Ingesting {len(records)} records into LanceDB...")
    success = bulk_add_telemetry(records)
    if success:
        print("[✔] Ingestion complete!")
    else:
        print("[ERROR] Ingestion failed!")
        return

    # 4. Display Database Stats
    df = table.to_pandas()
    print(f"\n[*] Total records in database: {len(df)}")
    print(f"[*] Unique Radar Units: {df['radar_id'].unique().tolist()}")
    print(f"[*] Time Range: {df['timestamp'].min()} to {df['timestamp'].max()}")

    # 5. Perform semantic vector search on new native data
    query = "transmitter initialization"
    print(f"\n[*] Performing semantic search fallback test for: '{query}'")
    results = hybrid_retrieve(query, limit=3)
    print("--- SEARCH RESULTS ---")
    for r in results:
        print(f"[{r['timestamp']}] unit: {r['radar_id']} | code: {r['error_code']} | msg: {r['message']}")

    # 6. Run LLM RAG Query on new native data
    print("\n[*] Initializing memory engine...")
    memory = ContinuumMemory()
    
    query_inquiry = "At what frequency did the transmitter switch on and what tracking assignments were completed?"
    print(f"\n[*] Processing RAG inquiry: '{query_inquiry}'")
    report = process_radar_inquiry(query_inquiry, memory)
    print("\n--- RAG QUERY REPORT ON NEW DATASET ---")
    print(report)
    print("----------------------------------------")

if __name__ == "__main__":
    test_pipeline()
