import sys
import os
# Reconfigure stdout/stderr to support UTF-8 on Windows
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
from radar_rag_engine import parse_native_log_format
def validate():
    print("=== TESTING NATIVE LOG PARSING ===")
    if not os.path.exists("native_logs.txt"):
        print("[ERROR] native_logs.txt not found!")
        return
    with open("native_logs.txt", "r") as f:
        raw_lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    print(f"[*] Loaded {len(raw_lines)} lines from native_logs.txt")
    records, errors = parse_native_log_format(raw_lines, session_date="2026-05-24")
    print(f"[✔] Successfully parsed {len(records)} records")
    print(f"[*] Number of errors encountered: {len(errors)}")
    for err in errors[:5]:
        print(f"  - {err}")
    # Let's print out the first 5 parsed records
    print("\n--- FIRST 5 PARSED RECORDS ---")
    for i, rec in enumerate(records[:5], 1):
        print(f"Record #{i}:")
        print(f"  ID        : {rec['id']}")
        print(f"  Timestamp : {rec['timestamp']}")
        print(f"  Radar ID  : {rec['radar_id']}")
        print(f"  Azimuth   : {rec['azimuth']} (derived from lon)")
        print(f"  Elevation : {rec['elevation']} (derived from lat)")
        print(f"  Voltage   : {rec['voltage_mv']} mV")
        print(f"  Error Code: {rec['error_code']}")
        print(f"  Message   : {rec['log_message']}")
        print()
    # Let's look at unique radar units identified
    radar_units = set(rec['radar_id'] for rec in records)
    print(f"[*] Unique Radar IDs identified: {radar_units}")
    # Let's check for any error codes besides OK
    fault_records = [rec for rec in records if rec['error_code'] != 'OK']
    print(f"[*] Fault records found: {len(fault_records)}")
    for r in fault_records:
        print(f"  - {r['timestamp']} | {r['radar_id']} | {r['error_code']} | {r['log_message']}")
if __name__ == "__main__":
    validate()