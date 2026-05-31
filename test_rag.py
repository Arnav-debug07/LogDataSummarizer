import os
import json
import sys
import requests
import pandas as pd
import lancedb

# Reconfigure stdout/stderr to support UTF-8 on Windows
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Import all elements from our new script
from radar_rag_engine import (
    table,
    table_name,
    db,
    ContinuumMemory,
    generate_brief_event_summary,
    generate_human_readable_summary,
    process_radar_inquiry,
    bulk_add_telemetry
)

def run_test():
    print("=== STARTING RAG SYSTEM TEST ===")
    
    # 1. Check if the database already has records, if not, load them from telemetry_test_dataset.json
    try:
        df = table.to_pandas()
        record_count = len(df)
        print(f"[*] Current records in LanceDB: {record_count}")
    except Exception as e:
        print(f"[*] Database check failed, initializing: {e}")
        record_count = 0

    if record_count == 0:
        print("[*] Database is empty. Loading telemetry_test_dataset.json...")
        if os.path.exists("telemetry_test_dataset.json"):
            with open("telemetry_test_dataset.json", "r") as f:
                records = json.load(f)
            
            # Add records
            success = bulk_add_telemetry(records)
            if success:
                print(f"[✔] Successfully bulk-added {len(records)} records.")
            else:
                print("[ERROR] Failed to add records.")
                return
        else:
            print("[ERROR] telemetry_test_dataset.json not found in workspace!")
            return

    # 2. Initialize continuum memory
    print("\n[*] Initializing memory...")
    memory = ContinuumMemory()
    print(f"[✔] Current memory state: {memory.get_context_string()}")

    # 3a. Test generate_brief_event_summary
    print("\n[*] Generating brief event summary...")
    brief = generate_brief_event_summary(memory)
    print("\n--- BRIEF SUMMARY OUTPUT ---")
    print(brief)
    print("----------------------------")

    # 3b. Test generate_human_readable_summary (Detailed Report)
    print("\n[*] Generating detailed structured human-readable summary via local Qwen model...")
    summary = generate_human_readable_summary(memory)
    print("\n--- DETAILED SUMMARY OUTPUT ---")
    print(summary)
    print("-------------------------------")

    # 4. Test custom query (process_radar_inquiry)
    query = "Why did the radar unit AN-FPS-117_A go into protective safe mode? What were the events leading to it?"
    print(f"\n[*] Processing custom RAG query: '{query}'")
    report = process_radar_inquiry(query, memory)
    print("\n--- RAG QUERY REPORT ---")
    print(report)
    print("------------------------")

    # 5. Check updated memory state
    print(f"\n[✔] Updated memory state: {memory.get_context_string()}")

if __name__ == "__main__":
    run_test()
