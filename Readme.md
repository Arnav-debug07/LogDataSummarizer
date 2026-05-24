# LogDataSummarizer - Offline Radar Telemetry Interpreter

## 📋 Project Overview

**LogDataSummarizer** is an intelligent offline radar telemetry analysis system that leverages **Retrieval-Augmented Generation (RAG)** to interpret military radar logs and provide expert diagnostics. The system combines local LLM inference, vector embeddings, and persistent memory to deliver human-level technical analysis of radar system failures and anomalies.

### Key Features
- 🔍 **Intelligent Log Retrieval** — Semantic search with fallback mechanisms
- 🧠 **Local LLM Analysis** — Runs entirely offline using Qwen model via Ollama
- 💾 **Persistent Memory** — Tracks fault history across sessions
- 🔄 **Multi-Step RAG Pipeline** — Evaluate → Refine → Synthesize workflow
- ⚡ **Production-Ready** — Comprehensive error handling and retry logic
- 📥 **Multiple Input Methods** — Interactive, JSON file, or direct API

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
python Rag_Models.ipynb
```

### Main Menu

When you run the program, you'll see:

```
========================================================================
🛰️  OFFLINE RADAR TELEMETRY ANALYZER
Retrieval-Augmented Generation (RAG) Pipeline
========================================================================

----------------------------------------------------------------------
📥 DATA INPUT OPTIONS
----------------------------------------------------------------------
1. Interactive Input (type records one by one)
2. Load from JSON File
3. View Input Format
4. Skip Input & Query Database
5. Display Database Stats
6. Exit
----------------------------------------------------------------------
Select option (1-6):
```

---

## 📥 Data Input Guide

### Option 1: Interactive Input

Select option **1** to enter telemetry records one by one:

```
--- Record #1 ---
Radar ID (e.g., AN-FPS-117_A) [or 'done']: AN-FPS-117_A
Timestamp (YYYY-MM-DD HH:MM:SS): 2026-05-22 14:00:00
Azimuth (0-360): 45.2
Elevation (-90 to +90): 12.1
Voltage (mV): 5000
Error Code (OK or ERR_XXX_DESCRIPTION): OK
Log Message: Normal sweep operations. Thermal gradients stable.
```

**Tips:**
- Type `done` when finished adding records
- Type `skip` to cancel current record
- Type `format` to display expected input format

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

## ❓ Query Examples

Once data is loaded, you can ask questions like:

```
[Query] Enter your inquiry: Why did the radar system go into safe mode?

[Query] Enter your inquiry: What voltage issues were detected?

[Query] Enter your inquiry: Show me all critical faults from today

[Query] Enter your inquiry: Explain the alignment failure on 2026-05-22
```

The system will:
1. **Retrieve** relevant logs
2. **Evaluate** if more data needed
3. **Refine** search if necessary
4. **Synthesize** a technical report
5. **Update** memory with new faults

---

## 📁 Project Structure

```
LogDataSummarizer/
├── Rag_Models.ipynb                  # Main RAG pipeline (Jupyter notebook)
├── README.md                         # This file (setup & usage)
├── ARCHITECTURE.md                   # Technical deep-dive
├── local_radar_db/                   # LanceDB vector database (auto-created)
│   ├── _latest.manifest
│   └── radar_telemetry.lance
├── radar_continuum_memory.json       # Persistent fault history (auto-created)
├── venv/                             # Python virtual environment
└── telemetry_data.json               # Sample data (create yourself)
```

---

## ⚙️ Configuration

Edit these constants in `Rag_Models.ipynb` to customize:

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
- Load telemetry data first (Option 1 or 2)
- Verify JSON format is correct (use Option 3)
- Check database stats (Option 5)

### Database Corruption or Reset

```bash
# Delete local database to start fresh
rm -rf local_radar_db
rm radar_continuum_memory.json

# Restart the system
python Rag_Models.ipynb
```

### Out of Memory (OOM) Errors

**Solution:** Reduce the retrieval limit in the code:
```python
# Change from 10 to 3
all_data.head(3)  # Instead of head(10)
```

---

## 📊 Key Components

### 1. **LanceDB Vector Database**
- Stores radar telemetry logs with 384-dim embeddings
- Auto-creates `local_radar_db/` directory
- Schema: `RadarLogSchema` (id, timestamp, radar_id, coordinates, error_code, log_message, vector)

### 2. **Ollama + Qwen LLM**
- Local language model running on port 11434
- Temperature: 0.0 (deterministic for factual output)
- Timeout: 120 seconds

### 3. **Embedding Model**
- **BAAI/bge-small-en-v1.5** (auto-downloaded, ~130MB)
- Generates 384-dimensional vectors for semantic search

### 4. **Continuum Memory**
- JSON file: `radar_continuum_memory.json`
- Persists: fault history, active anomalies, last processed timestamp
- Survives system restarts

---

## 📈 Performance Metrics

| Metric | Value |
|--------|-------|
| Embedding Generation | ~50ms per query |
| Database Query | ~10ms (pandas filtering) |
| LLM Response Time | ~5-10 seconds (7B model) |
| Total Pipeline Time | ~15-20 seconds |
| Database Size | ~100MB for 1K records |

---

## 🚀 Next Steps

1. **Add Custom Radar Data**
   - Use Interactive Input (Option 1)
   - Or prepare JSON file (Option 2)
   - View format with Option 3

2. **Deploy as API**
   - Wrap the pipeline in Flask/FastAPI
   - Expose endpoints for querying

3. **Scale Database**
   - Use production LanceDB setup
   - Add advanced indexing

4. **Integrate with Monitoring**
   - Connect to live radar systems
   - Stream telemetry data in real-time

---

## 📖 Documentation

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** — Technical deep-dive, system flow, tool explanations
- **Inline Code Comments** — Comprehensive comments throughout `Rag_Models.ipynb`

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

**Last Updated:** 24 May 2026
**Status:** ✅ Production Ready
**Version:** 2.0 (User Input Mode)