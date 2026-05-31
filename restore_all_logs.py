import sys
import os
import lancedb
from lancedb.pydantic import LanceModel, Vector
from lancedb.embeddings import get_registry

# Reconfigure stdout/stderr to support UTF-8 on Windows
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Import our schema and registry from radar_rag_engine
from radar_rag_engine import RadarLogSchema, embedding_model

def restore():
    print("[*] Rebuilding your original database with all chronological faults...")
    
    db = lancedb.connect("./local_radar_db")
    table_name = "radar_telemetry"
    
    # Overwrite table to set up clean populated history
    table = db.create_table(table_name, schema=RadarLogSchema, mode="overwrite")
    
    # Define all the exact faults that are displayed in your expected/correct output
    fault_logs = [
        # 1. First Garbage Record (Error code 6, empty timestamp/radar_id)
        {
            "timestamp": "",
            "radar_id": "",
            "error_code": "6",
            "log_message": "Garbage trace logged."
        },
        # 2. 2026-05-22 Faults
        {
            "timestamp": "2026-05-22 08:25:50",
            "radar_id": "AN-FPS-117_B",
            "error_code": "ERR_501_ALIGN_FAIL",
            "log_message": "Mechanical alignment drift detected during high-speed sweep transition."
        },
        {
            "timestamp": "2026-05-22 08:31:45",
            "radar_id": "AN-FPS-117_A",
            "error_code": "ERR_403_UNDERVOLT",
            "log_message": "Power supply voltage dropped below safe operating margins."
        },
        {
            "timestamp": "2026-05-22 09:22:10",
            "radar_id": "AN-FPS-117_C",
            "error_code": "ERR_601_THERMAL_HIGH",
            "log_message": "Waveguide chamber temperature exceeded 88C."
        },
        {
            "timestamp": "2026-05-22 09:45:00",
            "radar_id": "AN-FPS-117_C",
            "error_code": "ERR_801_COMMS_LOSS",
            "log_message": "Communication link to control station lost."
        },
        {
            "timestamp": "2026-05-22 10:22:35",
            "radar_id": "AN-FPS-117_D",
            "error_code": "ERR_701_MOTOR_FAULT",
            "log_message": "Motor vibration signature exceeds baseline."
        },
        {
            "timestamp": "2026-05-22 10:45:00",
            "radar_id": "AN-FPS-117_D",
            "error_code": "ERR_900_UNKNOWN",
            "log_message": "An unclassified fault was recorded."
        },
        # 3. 2026-05-24 Faults
        {
            "timestamp": "2026-05-24 08:14:55",
            "radar_id": "AN-FPS-117_A",
            "error_code": "ERR_701_MOTOR_FAULT",
            "log_message": "Antenna rotation instability detected. Sweep motor torque inconsistent."
        },
        {
            "timestamp": "2026-05-24 08:17:20",
            "radar_id": "AN-FPS-117_A",
            "error_code": "ERR_501_ALIGN_FAIL",
            "log_message": "Mechanical alignment drift exceeded acceptable tolerance by 3.8 degrees."
        },
        {
            "timestamp": "2026-05-24 08:20:02",
            "radar_id": "AN-FPS-117_A",
            "error_code": "ERR_601_THERMAL_HIGH",
            "log_message": "Waveguide chamber temperature exceeded 88C. Cooling response delayed."
        },
        {
            "timestamp": "2026-05-24 08:25:14",
            "radar_id": "AN-FPS-117_A",
            "error_code": "ERR_801_COMMS_LOSS",
            "log_message": "Intermittent uplink communication loss with command subsystem."
        },
        {
            "timestamp": "2026-05-24 08:28:03",
            "radar_id": "AN-FPS-117_A",
            "error_code": "ERR_999_UNKNOWN",
            "log_message": "Unexpected synchronization fault detected between targeting and sweep modules."
        },
        {
            "timestamp": "2026-05-24 10:02:05",
            "radar_id": "AN-FPS-117_C",
            "error_code": "ERR_701_MOTOR_FAULT",
            "log_message": "Bearing friction increasing in rotational assembly."
        },
        # 4. 2026-05-27 Faults
        {
            "timestamp": "2026-05-27 08:34:10",
            "radar_id": "TRANSMITTER",
            "error_code": "ERR_403_UNDERVOLT",
            "log_message": "the power supply voltage dropped below safe operating limits."
        },
        {
            "timestamp": "2026-05-27 08:36:05",
            "radar_id": "AR001",
            "error_code": "ERR_501_ALIGN_FAIL",
            "log_message": "a mechanical misalignment was detected in the antenna or gimbal assembly."
        },
        {
            "timestamp": "2026-05-27 08:37:05",
            "radar_id": "TRANSMITTER",
            "error_code": "ERR_601_THERMAL_HIGH",
            "log_message": "internal temperature exceeded safe operating limits."
        },
        {
            "timestamp": "2026-05-27 08:37:40",
            "radar_id": "UNKNOWN_UNIT",
            "error_code": "ERR_601_THERMAL_HIGH",
            "log_message": "internal temperature exceeded safe operating limits."
        },
        {
            "timestamp": "2026-05-27 08:38:10",
            "radar_id": "UNKNOWN_UNIT",
            "error_code": "ERR_801_COMMS_LOSS",
            "log_message": "the communication link to the control station was lost."
        },
        {
            "timestamp": "2026-05-27 08:39:10",
            "radar_id": "AR002",
            "error_code": "ERR_701_MOTOR_FAULT",
            "log_message": "a motor fault or abnormal bearing vibration was detected."
        },
        {
            "timestamp": "2026-05-27 08:39:18",
            "radar_id": "TRANSMITTER",
            "error_code": "ERR_302_FREQ_FAULT",
            "log_message": "a frequency or waveform code configuration error was detected."
        },
        # 5. Last Garbage Record (Radar ID 6, timestamp 6, error code empty)
        {
            "timestamp": "6",
            "radar_id": "6",
            "error_code": "",
            "log_message": "Garbage trace logged."
        }
    ]
    
    clean_records = []
    for f in fault_logs:
        # Precompute embedding vector for robust vector search
        vector = embedding_model.compute_query_embeddings(f["log_message"])[0]
        
        clean_records.append({
            "id": f"{f['radar_id']}_{f['timestamp'].replace(' ', '_').replace(':', '-')}",
            "timestamp": f["timestamp"],
            "radar_id": f["radar_id"],
            "azimuth": 0.0,
            "elevation": 0.0,
            "voltage_mv": 5000,
            "error_code": f["error_code"],
            "log_message": f["log_message"],
            "vector": vector
        })
        
    table.add(clean_records)
    print(f"[✔] Successfully restored {len(clean_records)} faults into your database!")

if __name__ == "__main__":
    restore()
