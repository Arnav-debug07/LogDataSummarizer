from flask import Flask, render_template, request, jsonify
import os
import json
import datetime
from werkzeug.utils import secure_filename
from radar_rag_engine_web import (
    ContinuumMemory, 
    generate_brief_event_summary, 
    generate_human_readable_summary, 
    process_radar_inquiry, 
    display_graphical_representation,
    display_error_code_details,
    parse_native_log_format,
    bulk_add_telemetry
)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

radar_memory = ContinuumMemory()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    filename = secure_filename(file.filename)
    if not (filename.lower().endswith('.txt') or filename.lower().endswith('.json')):
        return jsonify({'error': 'Invalid file format. Only .txt or .json are supported. Please re-enter.'}), 400
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    try:
        if filename.lower().endswith('.json'):
            with open(filepath, 'r') as f:
                data = json.load(f)
            if isinstance(data, dict):
                records = [data]
            elif isinstance(data, list):
                records = data
            else:
                return jsonify({'error': 'JSON must be a list or dict.'}), 400
            
            if bulk_add_telemetry(records):
                return jsonify({'message': f'Successfully loaded {len(records)} records from JSON.'})
            else:
                return jsonify({'error': 'Failed to add records.'}), 500
        
        elif filename.lower().endswith('.txt'):
            with open(filepath, 'r') as f:
                raw_lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            
            if not raw_lines:
                return jsonify({'error': 'File is empty.'}), 400
            
            import re
            native_count = sum(1 for l in raw_lines if re.match(r'^time:\s*\d{2}:\d{2}:\d{2}', l, re.IGNORECASE))
            is_native = native_count > len(raw_lines) / 2
            
            if is_native:
                session_date = str(datetime.date.today())
                records, errors = parse_native_log_format(raw_lines, session_date)
            else:
                records = []
                errors = []
                for line_num, line in enumerate(raw_lines, start=1):
                    parts = line.split('|')
                    if len(parts) >= 7:
                        records.append({
                            "id": f"{parts[0].strip()}_{parts[1].strip().replace(' ','_').replace(':','-')}",
                            "timestamp": parts[1].strip(),
                            "radar_id": parts[0].strip(),
                            "azimuth": float(parts[2].strip()),
                            "elevation": float(parts[3].strip()),
                            "voltage_mv": int(parts[4].strip()),
                            "error_code": parts[5].strip(),
                            "log_message": '|'.join(parts[6:]).strip()
                        })
            
            if not records:
                return jsonify({'error': 'No valid records parsed.'}), 400
                
            if bulk_add_telemetry(records):
                return jsonify({'message': f'Successfully loaded {len(records)} records. Warnings/Errors: {len(errors)}'})
            else:
                return jsonify({'error': 'Failed to add records.'}), 500
                
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/action', methods=['POST'])
def handle_action():
    data = request.json
    action = data.get('action')
    query = data.get('query', '')
    
    if action == 'brief_summary':
        res = generate_brief_event_summary(radar_memory)
        return jsonify({'type': 'text', 'content': res})
    elif action == 'deep_analysis':
        res = generate_human_readable_summary(radar_memory)
        return jsonify({'type': 'text', 'content': res})
    elif action == 'interactive_summary':
        if not query:
            return jsonify({'error': 'Query is required.'}), 400
        res = process_radar_inquiry(query, radar_memory)
        return jsonify({'type': 'text', 'content': res})
    elif action == 'graphical_summary':
        res = display_graphical_representation()
        if res.startswith('[ERROR]') or res.startswith('[⚠️'):
            return jsonify({'type': 'text', 'content': res})
        return jsonify({'type': 'image', 'url': f'/{res}?t={datetime.datetime.now().timestamp()}'}) # Cache buster
    elif action == 'error_codes':
        res = display_error_code_details()
        return jsonify({'type': 'text', 'content': res})
    else:
        return jsonify({'error': 'Invalid action.'}), 400

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, port=5000)
