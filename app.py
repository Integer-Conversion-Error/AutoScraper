from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import os
import json
import secrets
from AutoScraperUtil import (
    get_all_makes, 
    get_models_for_make, 
    transform_strings, 
    read_json_file, 
    save_json_to_file,
    format_time_ymd_hms,
    showcarsmain
)
from AutoScraper import fetch_autotrader_data, save_results_to_csv

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = secrets.token_hex(16)  # Generate a secure secret key for sessions

# Route guards
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@app.route('/')
@login_required
def index():
    return render_template('index.html', username=session.get('username', 'User'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # For now, accept any credentials
        session['username'] = username
        return redirect(url_for('index'))
    
    # If it's a GET request or login failed
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/api/makes')
@login_required
def get_makes():
    popular = request.args.get('popular', 'true').lower() == 'true'
    makes = get_all_makes(popular=popular)
    return jsonify(makes)

@app.route('/api/models/<make>')
@login_required
def get_models(make):
    models = get_models_for_make(make)
    return jsonify(models)

@app.route('/api/create_payload', methods=['POST'])
@login_required
def create_payload():
    payload = request.json
    return jsonify({"success": True, "payload": payload})

@app.route('/api/save_payload', methods=['POST'])
@login_required
def save_payload_api():
    payload = request.json.get('payload')
    if not payload:
        return jsonify({"success": False, "error": "No payload provided"})
    
    make = payload.get('Make', 'Unknown')
    model = payload.get('Model', 'Unknown')
    folder_path = f"Queries/{make}_{model}"
    
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    
    file_name = f"{payload.get('YearMin', '')}-{payload.get('YearMax', '')}_{payload.get('PriceMin', '')}-{payload.get('PriceMax', '')}_{format_time_ymd_hms()}.json"
    full_path = f"{folder_path}/{file_name}"
    
    save_json_to_file(payload, full_path)
    return jsonify({"success": True, "file_path": full_path})

@app.route('/api/load_payload', methods=['POST'])
@login_required
def load_payload_api():
    file_path = request.json.get('file_path')
    if not file_path:
        return jsonify({"success": False, "error": "No file path provided"})
    
    payload = read_json_file(file_path)
    if not payload:
        return jsonify({"success": False, "error": f"Failed to load payload from {file_path}"})
    
    return jsonify({"success": True, "payload": payload})

@app.route('/api/fetch_data', methods=['POST'])
@login_required
def fetch_data_api():
    payload = request.json.get('payload')
    if not payload:
        return jsonify({"success": False, "error": "No payload provided"})
    
    try:
        results = fetch_autotrader_data(payload)
        
        if not results:
            return jsonify({"success": False, "error": "No results found"})
        
        make = payload.get('Make', 'Unknown')
        model = payload.get('Model', 'Unknown')
        folder_path = f"Results/{make}_{model}"
        
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        
        file_name = f"{payload.get('YearMin', '')}-{payload.get('YearMax', '')}_{payload.get('PriceMin', '')}-{payload.get('PriceMax', '')}_{format_time_ymd_hms()}.csv"
        full_path = f"{folder_path}/{file_name}"
        
        save_results_to_csv(results, payload=payload, filename=full_path)
        
        return jsonify({
            "success": True, 
            "file_path": full_path,
            "result_count": len(results)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/open_links', methods=['POST'])
@login_required
def open_links_api():
    file_path = request.json.get('file_path')
    if not file_path:
        return jsonify({"success": False, "error": "No file path provided"})
    
    try:
        showcarsmain(file_path)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/list_payloads')
@login_required
def list_payloads():
    try:
        payloads = []
        for root, dirs, files in os.walk("Queries"):
            for file in files:
                if file.endswith(".json"):
                    payloads.append(os.path.join(root, file))
        return jsonify({"success": True, "payloads": payloads})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    # Create necessary directories
    if not os.path.exists("Queries"):
        os.makedirs("Queries")
    if not os.path.exists("Results"):
        os.makedirs("Results")
    
    print("Server running at http://localhost:5000")
    print("Go to the login page at http://localhost:5000/login")
    app.run(debug=True, port=5000)