# LogDataSummarizer - Offline Radar Telemetry Interpreter

## 📋 Project Overview

**LogDataSummarizer** is an intelligent offline radar telemetry analysis system that leverages **Retrieval-Augmented Generation (RAG)** to interpret military radar logs and provide expert diagnostics. The system combines local LLM inference, vector embeddings, and persistent memory to deliver human-level technical analysis of radar system performance.

### Key Features
- 🔍 **Brief Event Summary** — Instant paragraph-style timeline of all events with timestamps on demand
- 📊 **Detailed Analysis Summary** — In-depth system analysis available as an optional follow-up
- 🔴 **Error Code Analysis** — Technical severity ratings and recommended actions for all faults
- 🧠 **Intelligent Log Retrieval** — Semantic search with fallback mechanisms
- 🔄 **Custom Query Mode** — Ask specific questions about your radar data via RAG pipeline
- 💾 **Persistent Memory** — Tracks fault history across sessions
- ⚡ **Production-Ready** — Comprehensive error handling and retry logic
- 📥 **Multiple Input Methods** — Text file (pipe-separated), JSON file, or direct API

---

## 🛠️ System Requirements

### Hardware
- **CPU**: Intel/Apple Silicon (quad-core minimum)
- **RAM**: 16GB minimum (24GB recommended)
- **Storage**: 20GB free disk space (for models and database)
- **OS**: macOS, Linux, or Windows with WSL2

### Software Dependencies
- Python 3.10+
- Ollama (for local LLM inference)
- Qwen model (7B-instruct variant)

---

## 📦 Installation

### Step 1: Install Ollama

**macOS:**
```bash
# Download from https://ollama.ai
# Or use Homebrew
brew install ollama
```

**Linux:**
```bash
curl https://ollama.ai/install.sh | sh
```

**Windows (WSL2):**
```bash
# Install WSL2 first, then follow Linux instructions
wsl --install
```

Start Ollama service:
```bash
ollama serve
```

This will run on `http://localhost:11434`

### Step 2: Pull Qwen Model

In a new terminal:
```bash
ollama pull qwen2.5-coder:7b-instruct-q5_K_M
```

This downloads ~4.7GB. Grab a coffee ☕

### Step 3: Clone & Setup Project

```bash
# Navigate to your project directory
cd /Users/arnav/App_development/LogDataSummarizer

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install lancedb pandas requests sentence-transformers
```

### Step 4: Verify Setup

```bash
# Test Ollama connection
curl http://localhost:11434/api/tags

# Expected output: { "models": [ { "name": "qwen2.5-coder:7b-instruct-q5_K_M", ... } ] }
```

---

## 🚀 Quick Start

### Run the System

```bash
# Activate virtual environment
source venv/bin/activate

# Run the notebook (in Jupyter)
jupyter notebook Rag_Models.ipynb

# Or run as Python script
python radar_rag_engine.py
```

### Main Workflow

1. **Data Input** (Options 1-6)
   - Load telemetry data from a text file or JSON file
   - View expected data format
   - Check database statistics

2. **Brief Event Summary** (Option 4 — shown automatically)
   - Plain-English paragraph walking through every event in chronological order
   - Each event described with its timestamp in plain language

3. **Detailed Analysis Summary** (Optional — prompted after brief summary)
   - In-depth system-wide analysis
   - Key anomalies, performance metrics, and critical issues

4. **Post-Analysis Options** (Menu appears after summary)
   - View error code details with severity levels
   - Ask custom questions via RAG query mode
   - Export database stats
   - Regenerate summaries

---

## 📥 Data Input Guide

### Option 1: Text File Input

Create a plain text file with one record per line. Fields are separated by `|` (pipe):

```
radar_id|timestamp|azimuth|elevation|voltage_mv|error_code|log_message
```

**Example: `telemetry_data.txt`**

```
AN-FPS-117_A|2026-05-22 14:00:00|45.2|12.1|5000|OK|Normal sweep operations. Thermal gradients stable.
AN-FPS-117_A|2026-05-22 14:02:15|89.7|11.5|3100|ERR_403_UNDERVOLT|Critical: Voltage dropped below safe margins.
AN-FPS-117_B|2026-05-22 14:10:00|120.0|8.5|4800|OK|Routine scan complete. No anomalies detected.
```

**Notes:**
- Lines starting with `#` are treated as comments and ignored
- Blank lines are skipped
- If the log message itself contains `|`, it is handled correctly (only the first 6 pipes are used as delimiters)

Then select option **1** and provide the file path.

### Option 2: JSON File Input

Create a JSON file with telemetry records and load it:

**Example: `telemetry_data.json`**

```json
[
    {
        "id": "AN-FPS-117_A_2026-05-22_14-00-00",
        "timestamp": "2026-05-22 14:00:00",
        "radar_id": "AN-FPS-117_A",
        "azimuth": 45.2,
        "elevation": 12.1,
        "voltage_mv": 5000,
        "error_code": "OK",
        "log_message": "Normal sweep operations. Thermal gradients stable."
    },
    {
        "id": "AN-FPS-117_A_2026-05-22_14-02-15",
        "timestamp": "2026-05-22 14:02:15",
        "radar_id": "AN-FPS-117_A",
        "azimuth": 89.7,
        "elevation": 11.5,
        "voltage_mv": 3100,
        "error_code": "ERR_403_UNDERVOLT",
        "log_message": "Critical: Voltage dropped below safe margins."
    }
]
```

Then select option **2** and provide the file path.

### Option 3: View Input Format

Select option **3** to display comprehensive input format guide with field specifications and example error codes.

---

## 📋 Input Data Format Specification

### Field Requirements

| Field | Type | Valid Range | Required | Example |
|-------|------|-------------|----------|---------|
| `id` | String | Any unique value | No* | `AN-FPS-117_A_2026-05-22_14-00-00` |
| `timestamp` | String (ISO 8601) | YYYY-MM-DD HH:MM:SS | Yes | `2026-05-22 14:00:00` |
| `radar_id` | String | Any identifier | Yes | `AN-FPS-117_A` |
| `azimuth` | Float | 0.0 - 360.0 | Yes | `45.2` |
| `elevation` | Float | -90.0 - +90.0 | Yes | `12.1` |
| `voltage_mv` | Integer | 0 - 9999 | Yes | `5000` |
| `error_code` | String | "OK" or "ERR_XXX" | Yes | `ERR_403_UNDERVOLT` |
| `log_message` | String | Any text | Yes | `Voltage dropped...` |

*Auto-generated if not provided

### Common Error Codes

```
OK                      → Normal operation
ERR_403_UNDERVOLT       → Power supply voltage too low
ERR_501_ALIGN_FAIL      → Mechanical misalignment detected
ERR_601_THERMAL_HIGH    → Temperature exceeds safe limits
ERR_701_MOTOR_FAULT     → Motor malfunction
ERR_801_COMMS_LOSS      → Communication loss
ERR_999_UNKNOWN         → Unknown error
```

---

## 📊 Analysis Features

### 1. Brief Event Summary (Option 4 — Default View)

When you select "Brief Summary & Analyze Data", the system generates a concise plain-English paragraph that walks through every event in the log chronologically, calling out each timestamp in natural language. No headers, no jargon — just a clear narrative.

**Example Output:**
```
At 14:00:00 on 22 May 2026, radar unit AN-FPS-117_A began normal sweep
operations with all thermal gradients within acceptable limits. At 14:02:15,
a critical voltage drop was detected on the shifter power rail, falling below
safe operating margins. By 14:10:00, unit AN-FPS-117_B completed a routine
scan with no anomalies reported.
```

After the brief summary is printed, you are prompted:

```
[?] Would you like to view the detailed analysis summary? (y/n):
```

Entering `y` triggers the full in-depth analysis (see below).

### 2. Detailed Analysis Summary (Optional — Triggered from Option 4)

An in-depth analysis covering:
- Overall system status assessment
- Key events and anomalies
- Performance metrics (voltage ranges, error distributions)
- Critical issues highlighted

### 3. Error Code Details (Post-Analysis Option 1)

View comprehensive technical information about each error code:

```
[ERR_403_UNDERVOLT] (Occurrences: 3)
├─ Severity: 🔴 CRITICAL
├─ Description: Power supply voltage dropped below safe operating margins
└─ Recommended Action: Check power supply connections and voltage regulator.
                       May require immediate system shutdown.
```

### 4. Custom Query Mode (Post-Analysis Option 2)

Ask specific questions about your data using the RAG pipeline:

```
[Query] Enter your inquiry: Why did the system shutdown at 15:45?

📋 QUERY RESPONSE
═══════════════════════════════════════════════════════════════════════════
The system shutdown at 15:45:22 was triggered by a cascading sequence of
events. An initial voltage anomaly at 15:43:15 caused the shifter power rail
to drop below 3000mV...
═══════════════════════════════════════════════════════════════════════════
```

---

## 🔍 Post-Analysis Menu

After the summary flow, you have access to:

```
🔧 POST-ANALYSIS OPTIONS
─────────────────────────────────────────────────────────────
1. View Error Code Details & Severity
2. Ask Custom Query (RAG Mode)
3. Display Database Stats
4. Generate New Summary
5. Exit Program
─────────────────────────────────────────────────────────────
```

| Option | Purpose | Use Case |
|--------|---------|----------|
| 1 | Technical details for each error code | Understanding what went wrong |
| 2 | RAG-powered Q&A about your data | Deep investigation of specific events |
| 3 | Database statistics | Quick overview of data volume |
| 4 | Regenerate detailed summary | See new insights or verify previous analysis |
| 5 | Exit cleanly | End session and save memory state |

---

## 📁 Project Structure

```
LogDataSummarizer/
├── radar_rag_engine.py               # Main RAG pipeline
├── README.md                         # This file (setup & usage)
├── ARCHITECTURE.md                   # Technical deep-dive
├── local_radar_db/                   # LanceDB vector database (auto-created)
│   ├── _latest.manifest
│   └── radar_telemetry.lance
├── radar_continuum_memory.json       # Persistent fault history (auto-created)
├── venv/                             # Python virtual environment
├── telemetry_data.txt                # Sample text data (create yourself)
└── telemetry_data.json               # Sample JSON data (create yourself)
```

---

## ⚙️ Configuration

Edit these constants in `radar_rag_engine.py` to customize:

```python
# API Configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5-coder:7b-instruct-q5_K_M"

# Embedding Model (384-dimensional vectors)
embedding_model = registry.create(name="BAAI/bge-small-en-v1.5")

# Database
db_path = "./local_radar_db"
```

---

## 🔧 Troubleshooting

### Error: "Cannot connect to Ollama at http://localhost:11434"

**Solution:**
```bash
# Make sure Ollama is running
ollama serve

# In another terminal, verify it's responding
curl http://localhost:11434/api/tags
```

### Error: "Model not found: qwen2.5-coder:7b-instruct-q5_K_M"

**Solution:**
```bash
# Pull the model
ollama pull qwen2.5-coder:7b-instruct-q5_K_M

# Verify installation
ollama list
```

### Error: "No logs available in database"

**Solution:**
- Load telemetry data first (Option 1 or 2 in input menu)
- Verify file format is correct (use Option 3)
- Check database stats (Option 5)

### Text file not loading correctly

**Solution:**
- Ensure fields are separated by `|` (pipe character)
- Verify exactly 7 fields per line (radar_id, timestamp, azimuth, elevation, voltage_mv, error_code, log_message)
- Lines starting with `#` are skipped (use for comments)
- Check the warning output — skipped lines are reported with their line numbers

### Summary generation takes too long

**Solution:**
- Reduce dataset size (LLM processes all records)
- Increase Ollama timeout (currently 300s)
- Check if Ollama is running properly

### Database Corruption or Reset

```bash
# Delete local database to start fresh
rm -rf local_radar_db
rm radar_continuum_memory.json

# Restart the system
python radar_rag_engine.py
```

---

## 📈 Performance Metrics

| Metric | Value |
|--------|-------|
| Embedding Generation | ~50ms per query |
| Database Query | ~10ms (pandas filtering) |
| LLM Brief Summary | ~10-20 seconds (7B model) |
| LLM Detailed Summary | ~10-20 seconds (7B model) |
| LLM Query Response | ~5-10 seconds |
| Total Pipeline Time | ~15-30 seconds |
| Database Size | ~100MB for 1K records |

---

## 🚀 Next Steps

1. **Add Custom Radar Data**
   - Prepare a pipe-separated text file (Option 1)
   - Or prepare a JSON file (Option 2)
   - View format with Option 3

2. **Explore Your Data**
   - Generate brief event summary (Option 4)
   - Optionally view detailed analysis
   - View error code details
   - Ask custom questions

3. **Deploy as API** (Future)
   - Wrap the pipeline in Flask/FastAPI
   - Expose endpoints for querying

4. **Scale Database** (Future)
   - Use production LanceDB setup
   - Add advanced indexing

5. **Integrate with Monitoring** (Future)
   - Connect to live radar systems
   - Stream telemetry data in real-time

---

## 📖 Documentation

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** — Technical deep-dive, system flow, tool explanations
- **Inline Code Comments** — Comprehensive comments throughout `radar_rag_engine.py`

---

## 🤝 Support & Issues

If you encounter issues:

1. Check **Troubleshooting** section above
2. Verify Ollama is running: `curl http://localhost:11434/api/tags`
3. Check Python version: `python --version` (should be 3.10+)
4. Ensure dependencies: `pip list | grep -E "lancedb|pandas|requests"`
5. View input format: Select Option 3 in main menu

---

## 📝 License

This project is for educational and research purposes.

---

## 🙏 Acknowledgments

- **LanceDB** — Vector database for embeddings
- **Ollama** — Local LLM inference
- **Qwen** — Alibaba's open-source language model
- **Sentence Transformers** — BGE embedding model

---

**Last Updated:** 26 May 2026
**Status:** ✅ Production Ready
**Version:** 4.0 (Brief Event Summary + Optional Detailed Analysis)