# New RAG Model
# radar_rag_engine.py
# ---------------------------------------------------------------
# Offline Radar Telemetry Interpreter
# Requires: Ollama running locally with Qwen model downloaded
# ---------------------------------------------------------------

import json
import time
import sys
from typing import List, Dict, Any, Optional
import lancedb
from lancedb.pydantic import LanceModel, Vector
from lancedb.embeddings import get_registry
import requests
import pandas as pd

# Reconfigure stdout/stderr to support UTF-8 on Windows to avoid UnicodeEncodeErrors
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# ---------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5-coder:7b-instruct-q5_K_M"

registry = get_registry().get("sentence-transformers")
embedding_model = registry.create(name="BAAI/bge-small-en-v1.5")


def call_local_qwen(prompt: str, json_mode: bool = False) -> str:
    """
    Call the local Qwen LLM via Ollama API
    
    Args:
        prompt: The input prompt for the LLM
        json_mode: If True, request JSON-formatted response
        
    Returns:
        LLM response text or error message
    """
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0}
    }
    if json_mode:
        payload["format"] = "json"

    try:
        print("[*] Waiting for LLM response (this may take 10-30 seconds)...")
        response = requests.post(OLLAMA_URL, json=payload, timeout=300)
        if response.status_code == 200:
            return response.json().get("response", "").strip()
        else:
            return f"Error: Ollama returned status {response.status_code}"
    except requests.exceptions.Timeout:
        return "Error: Ollama request timed out (300s). Try again or check if Ollama is running."
    except requests.exceptions.ConnectionError:
        return "Error: Cannot connect to Ollama at http://localhost:11434. Make sure Ollama is running."
    except Exception as e:
        return f"Error connecting to local LLM: {str(e)}"


class RadarLogSchema(LanceModel):
    """
    Schema for radar telemetry logs stored in LanceDB
    
    Attributes:
        id: Unique identifier for the log entry
        timestamp: ISO format timestamp (YYYY-MM-DD HH:MM:SS)
        radar_id: Identifier for the radar unit (e.g., "AN-FPS-117_A")
        azimuth: Horizontal angle in degrees (0-360)
        elevation: Vertical angle in degrees (-90 to +90)
        voltage_mv: Power supply voltage in millivolts
        error_code: Status code ("OK" or "ERR_XXX_DESCRIPTION")
        log_message: Full text description of the event
        vector: 384-dimensional embedding of log_message
    """
    id: str
    timestamp: str
    radar_id: str
    azimuth: float
    elevation: float
    voltage_mv: int
    error_code: str
    log_message: str
    vector: Vector(384) = embedding_model.VectorField() # type: ignore


try:
    db = lancedb.connect("./local_radar_db")
    table_name = "radar_telemetry"

    # Auto-repair and rebuild database if corrupted or missing vectors
    if table_name in db.list_tables().tables:
        table = db.open_table(table_name)
        df = table.to_pandas()
        if not df.empty and df['vector'].isna().any():
            print("[*] Rebuilding or repairing local database index (computing missing vector embeddings)...")
            clean_records = []
            for _, row in df.iterrows():
                log_message = str(row.get('log_message', ''))
                # Recompute embedding if missing
                if row.get('vector') is None or len(row.get('vector', [])) == 0:
                    vector = embedding_model.compute_query_embeddings(log_message)[0]
                else:
                    vector = row['vector']
                
                clean_records.append({
                    "id": row.get('id', ''),
                    "timestamp": row.get('timestamp', ''),
                    "radar_id": row.get('radar_id', ''),
                    "azimuth": float(row.get('azimuth', 0.0)),
                    "elevation": float(row.get('elevation', 0.0)),
                    "voltage_mv": int(row.get('voltage_mv', 5000)),
                    "error_code": row.get('error_code', 'OK'),
                    "log_message": log_message,
                    "vector": vector
                })
            
            # Recreate table with clean, embedded records
            table = db.create_table(table_name, schema=RadarLogSchema, mode="overwrite")
            if clean_records:
                table.add(clean_records)
            print("[✔] Database successfully repaired!")
    else:
        table = db.create_table(table_name, schema=RadarLogSchema)
except Exception as e:
    print(f"[ERROR] Failed to connect to LanceDB: {str(e)}")
    raise


class ContinuumMemory:
    """
    Persistent memory system for tracking radar faults and anomalies across sessions
    
    Stores:
        - Last processed timestamp
        - Known critical faults
        - Active anomalies per radar unit
    """
    def __init__(self):
        self.state_file = "radar_continuum_memory.json"
        self.initialize_memory()

    def initialize_memory(self):
        """Load memory from disk or create new state"""
        try:
            with open(self.state_file, 'r') as f:
                self.memory = json.load(f)
        except FileNotFoundError:
            self.memory = {
                "last_processed_timestamp": "1970-01-01 00:00:00",
                "known_critical_faults": [],
                "active_anomalies": {}
            }
            self.save()
        except json.JSONDecodeError:
            print(f"[WARNING] Memory file corrupted, starting fresh")
            self.memory = {
                "last_processed_timestamp": "1970-01-01 00:00:00",
                "known_critical_faults": [],
                "active_anomalies": {}
            }
            self.save()

    def save(self):
        """Persist memory state to JSON file"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.memory, f, indent=2)
        except Exception as e:
            print(f"[WARNING] Failed to save memory: {str(e)}")

    def update_state(self, new_fault: str, radar_id: str):
        """
        Add new fault to history and update anomaly tracking
        
        Args:
            new_fault: Error code to track
            radar_id: Radar unit identifier
        """
        if new_fault not in self.memory["known_critical_faults"]:
            self.memory["known_critical_faults"].append(new_fault)
        self.memory["active_anomalies"][radar_id] = f"Last fault tracked: {new_fault}"
        self.save()

    def get_context_string(self) -> str:
        """Export memory as JSON string for LLM context"""
        return json.dumps(self.memory)


# ---------------------------------------------------------------
# ERROR CODE REFERENCE
# ---------------------------------------------------------------

ERROR_CODE_REFERENCE = {
    "OK": {
        "description": "Normal operation",
        "severity": "🟢 NORMAL",
        "action": "No action required"
    },
    "ERR_403_UNDERVOLT": {
        "description": "Power supply voltage dropped below safe operating margins",
        "severity": "🔴 CRITICAL",
        "action": "Check power supply connections and voltage regulator. May require immediate system shutdown."
    },
    "ERR_501_ALIGN_FAIL": {
        "description": "Mechanical misalignment detected in antenna or gimbal system",
        "severity": "🟠 HIGH",
        "action": "Perform mechanical alignment check. Contact maintenance for calibration."
    },
    "ERR_601_THERMAL_HIGH": {
        "description": "Internal temperature exceeds safe operating limits",
        "severity": "🟠 HIGH",
        "action": "Check cooling system and ventilation. Reduce operational load if necessary."
    },
    "ERR_701_MOTOR_FAULT": {
        "description": "Motor malfunction or bearing failure detected",
        "severity": "🟠 HIGH",
        "action": "Inspect motor assembly. Schedule motor replacement."
    },
    "ERR_801_COMMS_LOSS": {
        "description": "Communication link to control station lost",
        "severity": "🟠 HIGH",
        "action": "Verify network connectivity and signal strength. Restart communication module."
    },
    "ERR_900_UNKNOWN": {
        "description": "Unknown or undefined error",
        "severity": "🟡 MEDIUM",
        "action": "Enable debug logging and contact support."
    },
    "ERR_101_TX_FAIL": {
        "description": "Transmitter failed to switch on or initialise",
        "severity": "🔴 CRITICAL",
        "action": "Check transmitter power supply and initialisation sequence. Restart transmitter subsystem."
    },
    "ERR_102_TX_PWR_LOW": {
        "description": "Transmitter operating at low power when high power expected",
        "severity": "🟠 HIGH",
        "action": "Verify power mode command was accepted. Check RF amplifier chain."
    },
    "ERR_201_TRACK_FAIL": {
        "description": "Track initialisation or weapon track mode assignment failed",
        "severity": "🟠 HIGH",
        "action": "Re-assign track mode. Check track processor and antenna handoff."
    },
    "ERR_301_TARGET_LOST": {
        "description": "Continuous track lost — target no longer updating",
        "severity": "🟠 HIGH",
        "action": "Verify target is within radar coverage. Check receiver gain and clutter filters."
    },
    "ERR_302_FREQ_FAULT": {
        "description": "Transmitter frequency or code configuration error",
        "severity": "🟡 MEDIUM",
        "action": "Verify frequency and waveform code settings match mission parameters."
    }
}


def print_input_format():
    """Display expected input data format for telemetry records."""
    print("\n" + "="*70)
    print("\U0001f4cb EXPECTED INPUT DATA FORMAT")
    print("="*70)
    print("""
--- NATIVE LOG FORMAT (auto-detected) ---

Lines follow the pattern:
    time: HH:MM:SS <free-text message>

The parser infers all fields automatically from the message text.
Radar ID is extracted from track/CTN identifiers (e.g. AR001, AR002).
Error code is inferred from keywords — see documentation for full mapping.
Azimuth and elevation are derived from lon/lat on CTN lines where present.

Example:
    time: 08:30:30 transmitter switched on
    time: 08:30:38 transmitter put to low power and initialization success
    time: 08:31:20 CTN-AR001, Target id 17,lat 11.18,lon 77.22
    time: 08:39:20 transmitter put to low power
    time: 08:39:48 transmitter power off

--- PIPE-SEPARATED FORMAT (legacy, also supported) ---

radar_id|timestamp|azimuth|elevation|voltage_mv|error_code|log_message

Example:
AN-FPS-117_A|2026-05-22 14:00:00|45.2|12.1|5000|OK|Normal operations.
AN-FPS-117_A|2026-05-22 14:02:15|89.7|11.5|3100|ERR_403_UNDERVOLT|Voltage drop.

--- COMMON ERROR CODES ---

OK                  Normal operation
ERR_101_TX_FAIL     Transmitter failed to initialise
ERR_102_TX_PWR_LOW  Transmitter at low power unexpectedly
ERR_201_TRACK_FAIL  Track initialisation failed
ERR_301_TARGET_LOST Continuous track lost
ERR_302_FREQ_FAULT  Frequency/code configuration error
ERR_403_UNDERVOLT   Power supply voltage low
ERR_501_ALIGN_FAIL  Mechanical misalignment
ERR_601_THERMAL_HIGH Temperature exceeds safe limits
ERR_701_MOTOR_FAULT Motor malfunction
ERR_801_COMMS_LOSS  Communication loss
    """)
    print("="*70 + "\n")


def add_telemetry_record(radar_id: str, timestamp: str, azimuth: float, elevation: float,
                         voltage_mv: int, error_code: str, log_message: str) -> bool:
    """
    Add a single telemetry record to the database
    
    Args:
        radar_id: Unit identifier
        timestamp: ISO format (YYYY-MM-DD HH:MM:SS)
        azimuth: Horizontal angle (0-360)
        elevation: Vertical angle (-90 to +90)
        voltage_mv: Power voltage
        error_code: Status code
        log_message: Event description
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Manually compute the embedding vector for robust vector search
        vector = embedding_model.compute_query_embeddings(log_message)[0]
        
        record = {
            "id": f"{radar_id}_{timestamp.replace(' ', '_').replace(':', '-')}",
            "timestamp": timestamp,
            "radar_id": radar_id,
            "azimuth": azimuth,
            "elevation": elevation,
            "voltage_mv": voltage_mv,
            "error_code": error_code,
            "log_message": log_message,
            "vector": vector
        }
        table.add([record])
        print(f"[✔] Record added: {radar_id} @ {timestamp}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to add record: {str(e)}")
        return False


def bulk_add_telemetry(telemetry_list: List[Dict]) -> bool:
    """
    Add multiple telemetry records to the database
    
    Args:
        telemetry_list: List of telemetry dictionaries
        
    Returns:
        True if successful, False otherwise
    """
    try:
        clean_list = []
        for record in telemetry_list:
            # Precompute embedding if missing
            if "vector" not in record or record["vector"] is None:
                record["vector"] = embedding_model.compute_query_embeddings(record.get("log_message", ""))[0]
                
            clean_list.append(record)
            
        if clean_list:
            table.add(clean_list)
            print(f"[✔] {len(clean_list)} records added to database")
            return True
        else:
            print("[WARNING] No valid records found in telemetry bulk list.")
            return False
    except Exception as e:
        print(f"[ERROR] Bulk add failed: {str(e)}")
        return False


def hybrid_retrieve(query_text: str, time_filter: Optional[str] = None, limit: int = 3, retry: int = 0) -> List[Dict]:
    """
    Retrieve relevant telemetry records from database using semantic vector search
    with substring matching fallback.
    
    Args:
        query_text: Search query text
        time_filter: Optional timestamp prefix filter (YYYY-MM-DD)
        limit: Maximum records to return
        retry: Current retry attempt
        
    Returns:
        List of matching telemetry records
    """
    try:
        # Get all data from LanceDB to verify contents
        all_data = table.to_pandas()
        
        if all_data.empty:
            print("[*] Database is empty")
            return []
        
        print(f"[DEBUG] Database has {len(all_data)} records")
        print(f"[DEBUG] Performing semantic vector search for: '{query_text}'")
        
        # 1. Compute query vector
        query_vector = embedding_model.compute_query_embeddings(query_text)[0]
        
        # 2. Query LanceDB using cosine similarity
        query_builder = table.search(query_vector).metric("cosine")
        
        if time_filter:
            # SQL-like filtering on timestamp prefix
            query_builder = query_builder.where(f"timestamp LIKE '{time_filter}%'")
            
        results_df = query_builder.limit(limit).to_pandas()
        
        # If vector search returned nothing or has empty values, fallback to substring matching
        if results_df.empty or results_df['vector'].isna().all():
            print("[*] Vector search returned no matches or unindexed data. Falling back to pandas substring search...")
            query_lower = query_text.lower()
            mask = (
                all_data['log_message'].str.lower().str.contains(query_lower, na=False) |
                all_data['error_code'].str.lower().str.contains(query_lower, na=False) |
                all_data['radar_id'].str.lower().str.contains(query_lower, na=False)
            )
            if time_filter:
                mask = mask & all_data['timestamp'].str.startswith(time_filter)
            
            filtered_results = all_data[mask].head(limit)
            if filtered_results.empty:
                print("[*] Substring search returned no matches, returning top fallback logs for analysis.")
                # Return the critical event window logs if possible, else just head
                critical_events = all_data[all_data['error_code'] != "OK"]
                if not critical_events.empty:
                    filtered_results = critical_events.head(limit)
                else:
                    filtered_results = all_data.head(limit)
            results_df = filtered_results

        print(f"[DEBUG] Found {len(results_df)} semantically similar matches")
        
        records = []
        for _, r in results_df.iterrows():
            records.append({
                "timestamp": r.get("timestamp", ""),
                "radar_id": r.get("radar_id", ""),
                "azimuth": float(r.get("azimuth", 0)),
                "elevation": float(r.get("elevation", 0)),
                "voltage": int(r.get("voltage_mv", 0)),
                "error_code": r.get("error_code", ""),
                "message": r.get("log_message", "")
            })
        return records
    except Exception as e:
        print(f"[ERROR] hybrid_retrieve failed: {str(e)}")
        # Fallback: return first critical records or first records
        try:
            all_data = table.to_pandas()
            results = all_data[all_data['error_code'] != "OK"].head(limit)
            if results.empty:
                results = all_data.head(limit)
            return [
                {
                    "timestamp": r.get("timestamp", ""),
                    "radar_id": r.get("radar_id", ""),
                    "azimuth": float(r.get("azimuth", 0)),
                    "elevation": float(r.get("elevation", 0)),
                    "voltage": int(r.get("voltage_mv", 0)),
                    "error_code": r.get("error_code", ""),
                    "message": r.get("log_message", "")
                } for _, r in results.iterrows()
            ]
        except:
            return []


def generate_brief_event_summary(memory_engine: ContinuumMemory) -> str:
    """
    Generate a brief fault-only summary — one line per unique fault type per unit.
    Deduplicates so repeated rows from multiple loads don't bloat the output.
    Shows the FIRST occurrence timestamp for each unique (radar_id, error_code) pair.
    """
    try:
        all_data = table.to_pandas()

        if all_data.empty:
            return "[*] No telemetry data available in database."

        fault_data = all_data[all_data['error_code'] != 'OK'].sort_values('timestamp')

        if fault_data.empty:
            return "[\u2714] No faults detected. All records show normal (OK) status."

        FAULT_PHRASES = {
            "ERR_101_TX_FAIL":      "the transmitter failed to initialise",
            "ERR_102_TX_PWR_LOW":   "the transmitter dropped to unexpectedly low power",
            "ERR_201_TRACK_FAIL":   "track initialisation failed",
            "ERR_301_TARGET_LOST":  "continuous track was lost with no target update",
            "ERR_302_FREQ_FAULT":   "a frequency or waveform code configuration error was detected",
            "ERR_403_UNDERVOLT":    "the power supply voltage dropped below safe operating limits",
            "ERR_501_ALIGN_FAIL":   "a mechanical misalignment was detected in the antenna or gimbal assembly",
            "ERR_601_THERMAL_HIGH": "internal temperature exceeded safe operating limits",
            "ERR_701_MOTOR_FAULT":  "a motor fault or abnormal bearing vibration was detected",
            "ERR_801_COMMS_LOSS":   "the communication link to the control station was lost",
            "ERR_900_UNKNOWN":      "an unclassified fault was recorded",
        }

        # Deduplicate: keep only the first occurrence of each (radar_id, error_code) pair
        seen = set()
        unique_faults = []
        for _, row in fault_data.iterrows():
            key = (row.get("radar_id", ""), row.get("error_code", ""))
            if key not in seen:
                seen.add(key)
                unique_faults.append(row)

        lines_out = ["### 📊 Brief Fault Summary\n"]
        for row in unique_faults:
            timestamp  = row.get("timestamp",  "unknown time")
            radar_id   = row.get("radar_id",   "unknown unit")
            error_code = row.get("error_code", "ERR_900_UNKNOWN")
            phrase     = FAULT_PHRASES.get(
                            error_code,
                            ERROR_CODE_REFERENCE.get(
                                error_code,
                                ERROR_CODE_REFERENCE["ERR_900_UNKNOWN"]
                            )["description"].lower()
                         )
            lines_out.append(
                f"- **{timestamp}**: Unit **{radar_id}** reported *{phrase}* (`{error_code}`).\n"
            )

        return "\n".join(lines_out)

    except Exception as e:
        return f"[ERROR] Brief summary generation failed: {str(e)}"


def generate_human_readable_summary(memory_engine: ContinuumMemory) -> str:
    """
    Generate a structured detailed report for every fault event.
    For each fault: timestamp, radar unit, error code, component name,
    fault type, description, impact, and recommended action.
    Shown only when the user opts in after the brief summary.

    Args:
        memory_engine: ContinuumMemory instance for context

    Returns:
        Structured per-fault detailed report text
    """
    try:
        all_data = table.to_pandas()

        if all_data.empty:
            return "[*] No telemetry data available in database."

        fault_data = all_data[all_data['error_code'] != 'OK'].sort_values('timestamp')

        if fault_data.empty:
            return "[✔] No faults detected. All records show normal (OK) status across the entire dataset."

        faults = []
        for _, row in fault_data.iterrows():
            faults.append({
                "timestamp":   row.get("timestamp",   ""),
                "radar_id":    row.get("radar_id",    ""),
                "error_code":  row.get("error_code",  ""),
                "azimuth":     row.get("azimuth",     0),
                "elevation":   row.get("elevation",   0),
                "voltage_mv":  row.get("voltage_mv",  0),
                "log_message": row.get("log_message", "")
            })

        summary_prompt = (
            "You are a radar telemetry analyst writing a detailed fault report.\n\n"
            "For EACH fault event listed below, produce a structured block in EXACTLY this format — "
            "no deviations, no extra sections, no introductory or closing text:\n\n"
            "FAULT #<number>\n"
            "  Timestamp          : <exact timestamp from record>\n"
            "  Radar Unit         : <radar_id>\n"
            "  Error Code         : <error_code>\n"
            "  Component          : <exact sensor/instrument/component name extracted verbatim from log_message>\n"
            "  Fault Type         : <one-word or short category: Power / Mechanical / Thermal / Communication / Motor / Unknown>\n"
            "  Description        : <one sentence — what this error means technically>\n"
            "  Impact             : <one sentence — what effect this fault has on system operation>\n"
            "  Recommended Action : <one sentence — what should be done to fix or investigate it>\n"
            "\n"
            "Separate each fault block with: ------------------------------------------------\n\n"
            "Rules:\n"
            "- Use the EXACT timestamp string from the record — do not reformat it.\n"
            "- Extract the component name verbatim from log_message.\n"
            "- Keep every field to one line.\n"
            "- Do not add any text before FAULT #1 or after the last fault block.\n\n"
            f"[Fault Events]:\n{json.dumps(faults, indent=2)}\n\nReport:"
        )

        response = call_local_qwen(summary_prompt)

        if response.startswith("Error"):
            # Fallback: build structured blocks manually using ERROR_CODE_REFERENCE
            out = []
            for i, f in enumerate(faults, start=1):
                ref = ERROR_CODE_REFERENCE.get(f["error_code"], ERROR_CODE_REFERENCE["ERR_900_UNKNOWN"])
                out.append(f"FAULT #{i}")
                out.append(f"  Timestamp          : {f['timestamp']}")
                out.append(f"  Radar Unit         : {f['radar_id']}")
                out.append(f"  Error Code         : {f['error_code']}")
                out.append(f"  Component          : (see log) {f['log_message'][:80]}")
                out.append(f"  Fault Type         : {ref['severity']}")
                out.append(f"  Description        : {ref['description']}")
                out.append(f"  Impact             : N/A (LLM unavailable)")
                out.append(f"  Recommended Action : {ref['action']}")
                out.append("-" * 48)
            return "\n".join(out)

        return response

    except Exception as e:
        return f"[ERROR] Summary generation failed: {str(e)}"


def display_error_code_details() -> str:
    """
    Return detailed information about all error codes found in database as a string.
    """
    try:
        all_data = table.to_pandas()
        
        if all_data.empty:
            return "[*] No data in database"
        
        error_codes = all_data['error_code'].unique()
        error_counts = all_data['error_code'].value_counts().to_dict()
        
        out = []
        out.append("="*80)
        out.append("🔍 ERROR CODE TECHNICAL REFERENCE")
        out.append("="*80)
        
        for error_code in sorted(error_codes):
            count = error_counts.get(error_code, 0)
            ref = ERROR_CODE_REFERENCE.get(error_code, ERROR_CODE_REFERENCE["ERR_900_UNKNOWN"])
            
            out.append(f"\n[{error_code}] (Occurrences: {count})")
            out.append(f"├─ Severity: {ref['severity']}")
            out.append(f"├─ Description: {ref['description']}")
            out.append(f"└─ Recommended Action: {ref['action']}")
        
        out.append("\n" + "="*80 + "\n")
        return "\n".join(out)
        
    except Exception as e:
        return f"[ERROR] Failed to display error codes: {str(e)}"


def display_database_stats():
    """Display current database statistics"""
    try:
        all_data = table.to_pandas()
        print("\n" + "="*60)
        print("📊 DATABASE STATISTICS")
        print("="*60)
        print(f"Total Records: {len(all_data)}")
        if not all_data.empty:
            print(f"Radar Units: {all_data['radar_id'].unique().tolist()}")
            print(f"Error Codes Found: {all_data['error_code'].unique().tolist()}")
            print(f"Time Range: {all_data['timestamp'].min()} to {all_data['timestamp'].max()}")
        print("="*60 + "\n")
    except Exception as e:
        print(f"[ERROR] Failed to display stats: {str(e)}")


def interactive_input_mode():
    """
    Interactive mode for users to input telemetry records one by one
    """
    print("\n" + "="*60)
    print("🔧 INTERACTIVE TELEMETRY INPUT MODE")
    print("="*60)
    print("Enter telemetry data record by record.")
    print("Type 'done' when finished, 'skip' to cancel current record.")
    print("Type 'format' to display expected input format.\n")
    
    records = []
    record_count = 1
    
    while True:
        print(f"\n--- Record #{record_count} ---")
        
        try:
            radar_id = input("Radar ID (e.g., AN-FPS-117_A) [or 'done']: ").strip()
            if radar_id.lower() == "done":
                break
            if radar_id.lower() == "skip":
                print("[*] Record skipped")
                continue
            if radar_id.lower() == "format":
                print_input_format()
                continue
            
            timestamp = input("Timestamp (YYYY-MM-DD HH:MM:SS): ").strip()
            azimuth = float(input("Azimuth (0-360): ").strip())
            elevation = float(input("Elevation (-90 to +90): ").strip())
            voltage_mv = int(input("Voltage (mV): ").strip())
            error_code = input("Error Code (OK or ERR_XXX_DESCRIPTION): ").strip()
            log_message = input("Log Message: ").strip()
            
            record = {
                "id": f"{radar_id}_{timestamp.replace(' ', '_').replace(':', '-')}",
                "timestamp": timestamp,
                "radar_id": radar_id,
                "azimuth": azimuth,
                "elevation": elevation,
                "voltage_mv": voltage_mv,
                "error_code": error_code,
                "log_message": log_message
            }
            records.append(record)
            print(f"[✔] Record added")
            record_count += 1
            
        except ValueError as e:
            print(f"[ERROR] Invalid input: {str(e)}. Please try again.")
            continue
        except KeyboardInterrupt:
            print("\n[*] Input cancelled")
            break
    
    if records:
        if bulk_add_telemetry(records):
            print(f"\n[✔] Successfully added {len(records)} records")
            time.sleep(1)
    
    return len(records) > 0


def parse_native_log_format(raw_lines, session_date=None):
    """
    Parse lines in  'time: HH:MM:SS <message>'  format into schema records.

    All fields not directly present are inferred from message content:
      radar_id   - track/CTN identifier extracted via regex
      error_code - keyword-based mapping
      azimuth    - lon value from CTN lines (proxy)
      elevation  - lat value from CTN lines (proxy)
      voltage_mv - 3000 on undervolt errors, 5000 otherwise

    Args:
        raw_lines    : list of stripped, non-blank, non-comment strings
        session_date : "YYYY-MM-DD" prefix (defaults to today)

    Returns:
        (records list, errors list)
    """
    import re
    from datetime import date as _date

    if session_date is None:
        session_date = str(_date.today())

    records = []
    errors  = []
    prev_ctn_secs = None

    def to_secs(t):
        h, m, s = t.split(':')
        return int(h)*3600 + int(m)*60 + int(s)

    existing_ids = set()

    for line_num, line in enumerate(raw_lines, start=1):
        m = re.match(r'^time:\s*(\d{2}:\d{2}:\d{2})\s+(.*)', line, re.IGNORECASE)
        if not m:
            errors.append(f"Line {line_num}: not a native-format line — skipping")
            continue

        time_str  = m.group(1)
        message   = m.group(2).strip()
        timestamp = f"{session_date} {time_str}"
        msg_lower = message.lower()

        # ── radar_id ──────────────────────────────────────────────────────
        ar_m = re.search(r'\b(AR\d+)\b', message, re.IGNORECASE)
        if ar_m:
            radar_id = ar_m.group(1).upper()
        elif re.search(r'transmitter|freq|power', msg_lower):
            radar_id = "TRANSMITTER"
        else:
            radar_id = "UNKNOWN_UNIT"

        # ── azimuth / elevation from lat/lon ──────────────────────────────
        azimuth, elevation = 0.0, 0.0
        lat_m = re.search(r'lat\s*([\d.]+)', msg_lower)
        lon_m = re.search(r'lon\s*([\d.]+)', msg_lower)
        if lat_m:
            elevation = float(lat_m.group(1))
        if lon_m:
            azimuth   = float(lon_m.group(1))

        # ── error_code ────────────────────────────────────────────────────
        error_code = "OK"
        voltage_mv = 5000

        if re.search(r'transmitter switched on|power on|transmitter on', msg_lower):
            error_code = "OK"
        elif re.search(r'transmitter power off|power off|switched off', msg_lower):
            error_code = "OK"
        elif re.search(r'initialization success|init success|initialisation success', msg_lower):
            error_code = "OK"
        elif re.search(r'high power', msg_lower):
            error_code = "OK"
        elif re.search(r'low power', msg_lower):
            if re.search(r'unexpected|fault|fail|error', msg_lower):
                error_code = "ERR_102_TX_PWR_LOW"
            else:
                error_code = "OK"
        elif re.search(r'wtm|weapon track|put to wtm', msg_lower):
            if re.search(r'fail|fault|error|lost', msg_lower):
                error_code = "ERR_201_TRACK_FAIL"
            else:
                error_code = "OK"
        elif re.search(r'ctn-|target id|lat.*lon', msg_lower):
            cur_secs = to_secs(time_str)
            if prev_ctn_secs is not None and (cur_secs - prev_ctn_secs) > 60:
                error_code = "ERR_301_TARGET_LOST"
            else:
                error_code = "OK"
            prev_ctn_secs = cur_secs
        elif re.search(r'freq.*fault|frequency error|code.*fault|waveform.*error', msg_lower):
            error_code = "ERR_302_FREQ_FAULT"
        elif re.search(r'undervolt|low voltage|voltage drop|power supply low', msg_lower):
            error_code = "ERR_403_UNDERVOLT"
            voltage_mv = 3000
        elif re.search(r'misalign|align.*fail|alignment fault|gimbal.*fault', msg_lower):
            error_code = "ERR_501_ALIGN_FAIL"
        elif re.search(r'thermal|temperature.*high|overheat|cooling.*fail', msg_lower):
            error_code = "ERR_601_THERMAL_HIGH"
        elif re.search(r'motor fault|bearing.*fail|drive.*fault', msg_lower):
            error_code = "ERR_701_MOTOR_FAULT"
        elif re.search(r'comms loss|link lost|communication.*fail|comms.*fault', msg_lower):
            error_code = "ERR_801_COMMS_LOSS"
        elif re.search(r'fail|fault|error|lost|critical|alarm', msg_lower):
            error_code = "ERR_900_UNKNOWN"

        # ── unique id ─────────────────────────────────────────────────────
        base_id   = f"{radar_id}_{timestamp.replace(' ', '_').replace(':', '-')}"
        record_id = base_id
        suffix    = 0
        while record_id in existing_ids:
            suffix   += 1
            record_id = f"{base_id}_{suffix}"
        existing_ids.add(record_id)

        records.append({
            "id":          record_id,
            "timestamp":   timestamp,
            "radar_id":    radar_id,
            "azimuth":     azimuth,
            "elevation":   elevation,
            "voltage_mv":  voltage_mv,
            "error_code":  error_code,
            "log_message": message
        })

    return records, errors


def text_file_input_mode():
    """
    Load telemetry data from a text file.
    Auto-detects between native  'time: HH:MM:SS …'  and pipe-separated formats.
    """
    print("\n" + "="*60)
    print("\U0001f4c4 TEXT FILE INPUT MODE")
    print("="*60)
    print("Supported formats:")
    print("  \u2022 Native log  — 'time: HH:MM:SS <message>'")
    print("  \u2022 Pipe-separated — radar_id|timestamp|azimuth|…")
    print("Type 'format' to display the full format guide.\n")

    file_input = input("Enter text file path [or 'format']: ").strip()

    if file_input.lower() == "format":
        print_input_format()
        return False

    file_path = file_input

    try:
        with open(file_path, 'r') as f:
            raw_lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]

        if not raw_lines:
            print("[ERROR] File is empty or contains only comments")
            return False

        import re
        native_count = sum(1 for l in raw_lines
                           if re.match(r'^time:\s*\d{2}:\d{2}:\d{2}', l, re.IGNORECASE))
        is_native = native_count > len(raw_lines) / 2

        if is_native:
            print(f"[*] Detected: NATIVE log format ({native_count}/{len(raw_lines)} lines matched)")

            date_input = input("Session date [YYYY-MM-DD, or Enter for today]: ").strip()
            if date_input and re.match(r'\d{4}-\d{2}-\d{2}', date_input):
                session_date = date_input
            else:
                from datetime import date as _date
                session_date = str(_date.today())
                if date_input:
                    print(f"[\u26a0\ufe0f] Invalid date — using today: {session_date}")
                else:
                    print(f"[*] Using today\u2019s date: {session_date}")

            records, errors = parse_native_log_format(raw_lines, session_date)

        else:
            print("[*] Detected: PIPE-SEPARATED format")
            records, errors = [], []

            for line_num, line in enumerate(raw_lines, start=1):
                parts = line.split('|')
                if len(parts) < 7:
                    errors.append(f"Line {line_num}: Expected 7 fields, got {len(parts)} — skipping")
                    continue
                try:
                    records.append({
                        "id":          f"{parts[0].strip()}_{parts[1].strip().replace(' ','_').replace(':','-')}",
                        "timestamp":   parts[1].strip(),
                        "radar_id":    parts[0].strip(),
                        "azimuth":     float(parts[2].strip()),
                        "elevation":   float(parts[3].strip()),
                        "voltage_mv":  int(parts[4].strip()),
                        "error_code":  parts[5].strip(),
                        "log_message": '|'.join(parts[6:]).strip()
                    })
                except ValueError as e:
                    errors.append(f"Line {line_num}: Parse error — {str(e)} — skipping")

        if errors:
            print(f"\n[\u26a0\ufe0f WARNINGS] {len(errors)} line(s) had issues:")
            for err in errors:
                print(f"  \u2022 {err}")

        if not records:
            print("[ERROR] No valid records parsed from file")
            return False

        if bulk_add_telemetry(records):
            print(f"\n[\u2714] Successfully loaded {len(records)} records from {file_path}")
            return True
        return False

    except FileNotFoundError:
        print(f"[ERROR] File not found: {file_path}")
        return False
    except Exception as e:
        print(f"[ERROR] Failed to load file: {str(e)}")
        return False


def json_file_input_mode():
    """
    Load telemetry data from a JSON file
    """
    print("\n" + "="*60)
    print("📄 JSON FILE INPUT MODE")
    print("="*60)
    print("Expected format: Array of telemetry records")
    print("Type 'format' to display expected format.\n")
    
    file_input = input("Enter JSON file path [or 'format']: ").strip()
    
    if file_input.lower() == "format":
        print_input_format()
        return False
    
    file_path = file_input
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Handle both single dict and list of dicts
        if isinstance(data, dict):
            records = [data]
        elif isinstance(data, list):
            records = data
        else:
            print("[ERROR] JSON must be dict or list of dicts")
            return False
        
        if bulk_add_telemetry(records):
            print(f"\n[✔] Successfully loaded {len(records)} records from {file_path}")
            return True
        else:
            return False
            
    except FileNotFoundError:
        print(f"[ERROR] File not found: {file_path}")
        return False
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON: {str(e)}")
        return False
    except Exception as e:
        print(f"[ERROR] Failed to load file: {str(e)}")
        return False


def process_radar_inquiry(user_question: str, memory_engine: ContinuumMemory) -> str:
    """
    Process a user inquiry through the full RAG pipeline
    
    Pipeline stages:
    1. Retrieval: Fetch relevant logs from database
    2. Evaluation: LLM decides if more data needed
    3. Refinement: Optional second search with refined query
    4. Synthesis: LLM generates technical report
    5. Memory Update: Persist new faults to state
    
    Args:
        user_question: User's inquiry about radar system
        memory_engine: ContinuumMemory instance for state persistence
        
    Returns:
        Technical report or error message
    """
    try:
        print(f"\n[User Inquiry]: {user_question}")

        retrieved_logs = hybrid_retrieve(user_question)
        
        if not retrieved_logs:
            print("[*] Using fallback: returning all logs for analysis")
            # Fallback: get all logs if search fails
            try:
                all_data = table.to_pandas()
                if not all_data.empty:
                    all_results = all_data.head(10).to_dict('records')
                    retrieved_logs = [
                        {
                            "timestamp": r.get("timestamp", ""),
                            "radar_id": r.get("radar_id", ""),
                            "azimuth": r.get("azimuth", 0),
                            "elevation": r.get("elevation", 0),
                            "voltage": r.get("voltage_mv", 0),
                            "error_code": r.get("error_code", ""),
                            "message": r.get("log_message", "")
                        } for r in all_results
                    ]
                else:
                    return "[ERROR] No logs available in database."
            except Exception as e:
                return f"[ERROR] Fallback retrieval failed: {str(e)}"

        # Stage 1: LLM Evaluation - Determine if more data needed
        evaluation_prompt = f"""You are an automated Radar Telemetry Critic. Analyze the user inquiry and the initial retrieved data.

User Query: {user_question}
Initial Results: {json.dumps(retrieved_logs)}

Respond in JSON format:
{{"needs_more_data": true/false, "refined_search_query": ""}}"""

        eval_output = call_local_qwen(evaluation_prompt, json_mode=True)
        
        try:
            eval_json = json.loads(eval_output)
        except json.JSONDecodeError:
            eval_json = {"needs_more_data": False, "refined_search_query": ""}

        # Stage 2: Conditional Refinement
        if eval_json.get("needs_more_data") and eval_json.get("refined_search_query"):
            refined_query = eval_json['refined_search_query']
            print(f"[*] Refined Query: '{refined_query}'")
            secondary_logs = hybrid_retrieve(refined_query, limit=2)
            retrieved_logs.extend([log for log in secondary_logs if log not in retrieved_logs])

        # Stage 3: LLM Synthesis - Generate final report
        final_synthesis_prompt = f"""You are an expert military radar diagnostics model. Synthesize a technical report.

[Memory]: {memory_engine.get_context_string()}
[Logs]: {json.dumps(retrieved_logs, indent=2)}
[Request]: {user_question}

Provide a clear technical summary."""

        response = call_local_qwen(final_synthesis_prompt)
        
        if response.startswith("Error"):
            return f"[ERROR] LLM failed: {response}"

        # Stage 4: Update Memory - Track new faults
        for log in retrieved_logs:
            error_code = log.get("error_code", "")
            radar_id = log.get("radar_id", "")
            if error_code and error_code != "OK" and radar_id:
                memory_engine.update_state(error_code, radar_id)

        return response
        
    except Exception as e:
        return f"[ERROR] process_radar_inquiry failed: {str(e)}"


def display_graphical_representation() -> str:
    """
    Generate and display high-end graphical visualizations of loaded telemetry data.
    Saves a high-resolution copy to 'static/radar_telemetry_visualization.png' in the workspace.
    Returns the path to the saved image or an error message.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')  # Required for headless environments
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        
        all_data = table.to_pandas()
        if all_data.empty:
            return "[⚠️ WARNING] No telemetry data in database to visualize!"
            
        # Programmatic Tactical/Console Theme
        plt.style.use('dark_background')
        fig = plt.figure(figsize=(12, 18), facecolor='#0f172a')
        
        # 1. Subplot 1: Voltage Telemetry Time-Series
        ax1 = fig.add_subplot(311)
        ax1.set_facecolor('#1e293b')
        
        # Parse and sort timestamps
        df_time = all_data.copy()
        df_time['timestamp_dt'] = pd.to_datetime(df_time['timestamp'], errors='coerce')
        df_time = df_time.dropna(subset=['timestamp_dt']).sort_values('timestamp_dt')
        
        if not df_time.empty:
            for radar_id in df_time['radar_id'].unique():
                unit_df = df_time[df_time['radar_id'] == radar_id]
                ax1.plot(unit_df['timestamp_dt'], unit_df['voltage_mv'], marker='o', markersize=4, linestyle='-', linewidth=1.5, label=str(radar_id))
            
            # Undervoltage safety margin threshold
            ax1.axhline(y=3300, color='#ef4444', linestyle='--', linewidth=1.5, label='Failsafe Limit (3300mV)')
            
            # Formatting
            ax1.set_title("⚡ VOLTAGE MONITORING & FLUCTUATIONS", color='#38bdf8', fontsize=11, fontweight='bold', pad=10)
            ax1.set_xlabel("Operational Time", color='#94a3b8', fontsize=9)
            ax1.set_ylabel("Power Level (mV)", color='#94a3b8', fontsize=9)
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            plt.setp(ax1.get_xticklabels(), rotation=30, ha='right', fontsize=8, color='#94a3b8')
            plt.setp(ax1.get_yticklabels(), fontsize=8, color='#94a3b8')
            ax1.grid(True, color='#334155', linestyle=':', alpha=0.6)
            ax1.legend(loc='lower left', fontsize=8, facecolor='#0f172a', edgecolor='#334155')
        else:
            ax1.text(0.5, 0.5, "No temporal data found", color='#94a3b8', ha='center', va='center')
            ax1.set_title("⚡ VOLTAGE MONITORING & FLUCTUATIONS", color='#38bdf8', fontsize=11, fontweight='bold')
            
        # 2. Subplot 2: Anomaly Severity & Frequency
        ax2 = fig.add_subplot(312)
        ax2.set_facecolor('#1e293b')
        
        error_counts = all_data['error_code'].value_counts()
        if not error_counts.empty:
            # Color bars according to severity
            colors = []
            for err_code in error_counts.index:
                ref = ERROR_CODE_REFERENCE.get(err_code, ERROR_CODE_REFERENCE.get("ERR_900_UNKNOWN", {}))
                sev = ref.get('severity', '')
                if '🟢' in sev:
                    colors.append('#10b981') # Emerald
                elif '🔴' in sev:
                    colors.append('#ef4444') # Rose
                elif '🟠' in sev:
                    colors.append('#f97316') # Orange
                elif '🟡' in sev:
                    colors.append('#eab308') # Amber
                else:
                    colors.append('#06b6d4') # Cyan
            
            bars = ax2.bar(error_counts.index, error_counts.values, color=colors, edgecolor='#334155', width=0.5)
            
            # Value labels on top of bars
            for bar in bars:
                height = bar.get_height()
                ax2.annotate(f'{int(height)}',
                            xy=(bar.get_x() + bar.get_width() / 2, height),
                            xytext=(0, 3),  # 3 points vertical offset
                            textcoords="offset points",
                            ha='center', va='bottom', fontsize=8, color='#f1f5f9')
            
            ax2.set_title("📊 FAULT SEVERITY & FREQUENCY DISTRIBUTION", color='#38bdf8', fontsize=11, fontweight='bold', pad=10)
            ax2.set_xlabel("Diagnostic Code", color='#94a3b8', fontsize=9)
            ax2.set_ylabel("Occurrences", color='#94a3b8', fontsize=9)
            plt.setp(ax2.get_xticklabels(), rotation=30, ha='right', fontsize=8, color='#94a3b8')
            plt.setp(ax2.get_yticklabels(), fontsize=8, color='#94a3b8')
            ax2.grid(True, axis='y', color='#334155', linestyle=':', alpha=0.6)
        else:
            ax2.set_title("📊 FAULT SEVERITY & FREQUENCY DISTRIBUTION", color='#38bdf8', fontsize=11, fontweight='bold')
            
        # 3. Subplot 3: Spatial Tracking Path (Azimuth vs Elevation)
        ax3 = fig.add_subplot(313)
        ax3.set_facecolor('#1e293b')
        
        # Filter records with tracking coordinates (either non-zero or specific keywords)
        tracking_df = all_data[(all_data['azimuth'] != 0.0) | (all_data['elevation'] != 0.0)].copy()
        
        if not tracking_df.empty:
            tracking_df['timestamp_dt'] = pd.to_datetime(tracking_df['timestamp'], errors='coerce')
            tracking_df = tracking_df.dropna(subset=['timestamp_dt']).sort_values('timestamp_dt')
            
            for radar_id in tracking_df['radar_id'].unique():
                unit_df = tracking_df[tracking_df['radar_id'] == radar_id]
                # Plot path connections
                ax3.plot(unit_df['azimuth'], unit_df['elevation'], color='#38bdf8', linestyle='--', linewidth=1, alpha=0.5)
                # Scatter nodes
                scatter = ax3.scatter(unit_df['azimuth'], unit_df['elevation'], s=15, alpha=0.8, label=str(radar_id))
            
            ax3.set_title("📡 SPATIAL TRACK SWEEP TRAJECTORY MAP", color='#38bdf8', fontsize=11, fontweight='bold', pad=10)
            ax3.set_xlabel("Horizontal Angle - Azimuth (deg)", color='#94a3b8', fontsize=9)
            ax3.set_ylabel("Vertical Angle - Elevation (deg)", color='#94a3b8', fontsize=9)
            plt.setp(ax3.get_xticklabels(), fontsize=8, color='#94a3b8')
            plt.setp(ax3.get_yticklabels(), fontsize=8, color='#94a3b8')
            ax3.grid(True, color='#334155', linestyle=':', alpha=0.6)
            ax3.legend(loc='upper right', fontsize=8, facecolor='#0f172a', edgecolor='#334155')
        else:
            ax3.text(0.5, 0.5, "No spatial coordinate targets tracked", color='#94a3b8', ha='center', va='center')
            ax3.set_title("📡 SPATIAL TRACK SWEEP TRAJECTORY MAP", color='#38bdf8', fontsize=11, fontweight='bold')
            
        fig.tight_layout()
        
        # Save a high-resolution version
        import os
        if not os.path.exists("static"):
            os.makedirs("static")
        save_path = "static/radar_telemetry_visualization.png"
        fig.savefig(save_path, dpi=300, facecolor='#0f172a', edgecolor='none')
        plt.close(fig)
        return save_path
        
    except ImportError:
        return "[ERROR] matplotlib is not installed. Please install it using: pip install matplotlib"
    except Exception as e:
        return f"[ERROR] Failed to display graphical representation: {str(e)}"


if __name__ == "__main__":
    print("\n" + "="*70)
    print("🛰️  OFFLINE RADAR TELEMETRY ANALYZER")
    print("Retrieval-Augmented Generation (RAG) Pipeline")
    print("="*70)
    
    # Initialize memory
    radar_memory = ContinuumMemory()
    print("[✔] Continuum Memory initialized")
    
    # Data Input Menu
    data_loaded = False
    while True:
        print("\n" + "-"*70)
        print("📥 DATA INPUT OPTIONS")
        print("-"*70)
        print("1. Load from Text File (.txt, pipe-separated)")
        print("2. Load from JSON File")
        print("3. View Input Format")
        print("4. Brief Summary & Analyze Data")
        print("5. Display Database Stats")
        print("6. Exit Program")
        print("-"*70)
        
        choice = input("Select option (1-6): ").strip()
        
        if choice == "1":
            text_file_input_mode()
            display_database_stats()
            data_loaded = True
        
        elif choice == "2":
            json_file_input_mode()
            display_database_stats()
            data_loaded = True
        
        elif choice == "3":
            print_input_format()
        
        elif choice == "4":
            print("\n[*] Checking database for records...")
            
            # Check if database has data
            try:
                check_data = table.to_pandas()
                if check_data.empty:
                    print("[⚠️ WARNING] Database is empty!")
                    print("[*] Please load telemetry data first (Option 1 or 2).\n")
                    continue
                data_loaded = True
            except:
                print("[⚠️ WARNING] Could not check database.\n")
                continue
            
            # Generate brief event-timeline paragraph
            print("\n[*] Generating brief event summary...")
            print("[*] This may take 10-30 seconds...\n")
            brief = generate_brief_event_summary(radar_memory)
            
            print("\n" + "="*70)
            print("📋 EVENT SUMMARY")
            print("="*70)
            print(brief)
            print("="*70)
            
            # Offer the detailed summary as an optional step
            print("\n[?] Would you like to view the detailed analysis summary? (y/n): ", end="")
            detail_choice = input().strip().lower()
            if detail_choice == 'y':
                print("\n[*] Generating detailed analysis summary...")
                print("[*] This may take 10-30 seconds...\n")
                detailed = generate_human_readable_summary(radar_memory)
                print("\n" + "="*70)
                print("📋 DETAILED ANALYSIS SUMMARY")
                print("="*70)
                print(detailed)
                print("="*70)
            
            break
        
        elif choice == "5":
            display_database_stats()
        
        elif choice == "6":
            print("\n[✔] Thank you for using Radar Telemetry Analyzer!")
            print("[✔] Exiting program...")
            sys.exit(0)
        
        else:
            print("[ERROR] Invalid option. Please select 1-6.")
    
    # Analysis Mode - MAIN FEATURE (only if data exists)
    if not data_loaded:
        print("[ERROR] No data loaded. Exiting.")
        sys.exit(1)
    
    # Update memory with discovered faults
    try:
        all_data = table.to_pandas()
        if not all_data.empty:
            for error_code in all_data['error_code'].unique():
                if error_code and error_code != "OK":
                    # Get a representative radar_id
                    radar_id = all_data[all_data['error_code'] == error_code]['radar_id'].iloc[0]
                    radar_memory.update_state(error_code, radar_id)
    except:
        pass
    
    # Menu for additional options
    while True:
        print("\n" + "-"*70)
        print("🔧 POST-ANALYSIS OPTIONS")
        print("-"*70)
        print("1. View Error Code Details & Severity")
        print("2. Ask Custom Query (RAG Mode)")
        print("3. Display Database Stats")
        print("4. Generate New Summary")
        print("5. Display Graphical Representation")
        print("6. Exit Program")
        print("-"*70)
        
        choice = input("Select option (1-6): ").strip()
        
        if choice == "1":
            display_error_code_details()
        
        elif choice == "2":
            print("\n" + "="*70)
            print("❓ CUSTOM QUERY MODE")
            print("="*70)
            print("Ask questions about your radar telemetry data.")
            print("Type 'back' to return to analysis menu.\n")
            
            while True:
                inquiry = input("\n[Query] Enter your inquiry: ").strip()
                
                if inquiry.lower() == "back":
                    print("\n[*] Returning to analysis menu...")
                    break
                
                if not inquiry:
                    print("[ERROR] Please enter a valid inquiry")
                    continue
                
                print("\n[*] Processing inquiry...")
                print("[*] This may take 10-30 seconds...\n")
                report = process_radar_inquiry(inquiry, radar_memory)
                print("\n" + "="*70)
                print("📋 QUERY RESPONSE")
                print("="*70)
                print(report)
                print("="*70)
        
        elif choice == "3":
            display_database_stats()
        
        elif choice == "4":
            print("\n[*] Generating new summary...")
            print("[*] This may take 10-30 seconds...\n")
            summary = generate_human_readable_summary(radar_memory)
            print("\n" + "="*70)
            print("📋 TELEMETRY SUMMARY (UPDATED)")
            print("="*70)
            print(summary)
            print("="*70)
        
        elif choice == "5":
            display_graphical_representation()
        
        elif choice == "6":
            print("\n[✔] Thank you for using Radar Telemetry Analyzer!")
            print("[✔] Memory state saved to radar_continuum_memory.json")
            sys.exit(0)
        
        else:
            print("[ERROR] Invalid option. Please select 1-6.")
