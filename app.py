# Update the imports in app.py to include csv
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
import os
import json
import csv  # Add this import
import secrets
from datetime import timedelta
from functools import wraps
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

# Import Firebase config
from firebase_config import (
    initialize_firebase, 
    get_firestore_db,
    create_user, 
    verify_id_token, 
    get_user,
    save_payload,
    get_user_payloads,
    get_payload,
    update_payload,
    delete_payload,
    save_results,           # Add these new imports
    get_user_results,       # Add these new imports
    get_result,             # Add these new imports
    delete_result           # Add these new imports
)
# Initialize Firebase
firebase_initialized = initialize_firebase()

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = secrets.token_hex(32)  # Use a stronger secret key

# Configure session
app.config['SESSION_TYPE'] = 'filesystem'  # Store sessions on filesystem
app.config['SESSION_PERMANENT'] = True     # Make sessions permanent
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)  # Increase session lifetime
app.config['SESSION_USE_SIGNER'] = True    # Add a signer for security

# Import the login_required decorator after app is created
from auth_decorator import login_required_with_app
login_required = lambda f: login_required_with_app(app, f)  # Pass app to the decorator

@app.route('/')
@login_required
def index():
    # Print session info for debugging
    print(f"User session: {session.get('user_id')}, {session.get('email')}")
    return render_template('index.html', username=session.get('display_name', 'User'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # If user is already logged in, redirect to index
    if 'user_id' in session:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        # This route now only receives the Firebase ID token after client-side auth
        id_token = request.form.get('idToken')
        if id_token:
            # Verify the token with Firebase
            result = verify_id_token(id_token)
            if result['success']:
                user_info = result['user']
                # Store user information in session
                session['user_id'] = user_info.get('uid')
                session['email'] = user_info.get('email')
                session['display_name'] = user_info.get('name', user_info.get('email', 'User'))
                session.modified = True  # Mark session as modified
                
                print(f"Login successful for user: {session.get('email')}")
                flash('Login successful!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Authentication failed: ' + result.get('error', 'Unknown error'), 'danger')
        else:
            flash('No authentication token provided', 'danger')
            
    # If it's a GET request or login failed
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    # This page will handle user registration
    return render_template('register.html')

@app.route('/logout')
def logout():
    """
    Handle user logout with proper session cleanup and Firebase sign out.
    Renders a logout page that handles Firebase client-side logout before redirecting.
    """
    # Clear the user session on the server side
    user_email = session.get('email', 'Unknown user')
    session.clear()
    
    # Log the logout
    print(f"Logged out user: {user_email}")
    
    # Render the logout page which will handle Firebase client-side logout
    return render_template('logout.html')

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
    user_id = session.get('user_id')
    
    if not payload:
        return jsonify({"success": False, "error": "No payload provided"})
    
    if not user_id:
        return jsonify({"success": False, "error": "User not authenticated"})
    
    # Save payload to Firebase
    result = save_payload(user_id, payload)
    
    if result['success']:
        return jsonify({
            "success": True, 
            "file_path": f"Firebase/{result['doc_id']}",
            "doc_id": result['doc_id']
        })
    else:
        return jsonify({"success": False, "error": result.get('error', 'Failed to save payload')})

@app.route('/api/list_payloads')
@login_required
def list_payloads():
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({"success": False, "error": "User not authenticated"})
    
    try:
        # Get payloads from Firebase
        payloads = get_user_payloads(user_id)
        
        # Format for the frontend
        formatted_payloads = []
        for payload_data in payloads:
            payload = payload_data['payload']
            
            # Use custom_name if available, otherwise create a formatted name
            if 'custom_name' in payload:
                formatted_name = payload['custom_name']
            else:
                make = payload.get('Make', 'Unknown')
                model = payload.get('Model', 'Unknown')
                year_min = payload.get('YearMin', '')
                year_max = payload.get('YearMax', '')
                price_min = payload.get('PriceMin', '')
                price_max = payload.get('PriceMax', '')
                
                formatted_name = f"{make} {model} ({year_min}-{year_max}, ${price_min}-${price_max})"
            
            formatted_payloads.append({
                "name": formatted_name,
                "id": payload_data['id']
            })
        
        return jsonify({"success": True, "payloads": formatted_payloads})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# In your load_payload_api function in app.py
@app.route('/api/load_payload', methods=['POST'])
@login_required
def load_payload_api():
    file_path = request.json.get('file_path')
    doc_id = request.json.get('doc_id')  # Get the document ID directly
    user_id = session.get('user_id')
    
    if not file_path:
        return jsonify({"success": False, "error": "No file path provided"})
    
    if not user_id:
        return jsonify({"success": False, "error": "User not authenticated"})
    
    # Check if it's a Firebase path
    if file_path.startswith("Firebase/"):
        # Use the doc_id directly
        if not doc_id:
            return jsonify({"success": False, "error": "No document ID provided"})
        
        # Get the payload from Firebase
        payload = get_payload(user_id, doc_id)
        
        if not payload:
            return jsonify({"success": False, "error": f"Failed to load payload from Firebase"})
        
        return jsonify({"success": True, "payload": payload})
    else:
        # Legacy file-based loading (for backward compatibility)
        payload = read_json_file(file_path)
        if not payload:
            return jsonify({"success": False, "error": f"Failed to load payload from {file_path}"})
        
        return jsonify({"success": True, "payload": payload})

@app.route('/api/fetch_data', methods=['POST'])
@login_required
def fetch_data_api():
    payload = request.json.get('payload')
    user_id = session.get('user_id')
    
    if not payload:
        return jsonify({"success": False, "error": "No payload provided"})
    
    if not user_id:
        return jsonify({"success": False, "error": "User not authenticated"})
    
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
        
        # Save results to CSV
        save_results_to_csv(results, payload=payload, filename=full_path, max_workers=1000)
        
        # Read the CSV to get the processed results
        processed_results = []
        with open(full_path, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                processed_results.append(dict(row))
        
        # Save to Firebase
        metadata = {
            'make': make,
            'model': model,
            'yearMin': payload.get('YearMin', ''),
            'yearMax': payload.get('YearMax', ''),
            'priceMin': payload.get('PriceMin', ''),
            'priceMax': payload.get('PriceMax', ''),
            'file_name': file_name,
            'timestamp': format_time_ymd_hms()
        }
        
        # Save to Firebase
        firebase_result = save_results(user_id, processed_results, metadata)
        
        response_data = {
            "success": True, 
            "file_path": full_path,
            "result_count": len(processed_results)
        }
        
        if firebase_result.get('success'):
            response_data["doc_id"] = firebase_result.get('doc_id')
        
        return jsonify(response_data)
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
    
    
# Add these API endpoints to app.py

@app.route('/api/list_results')
@login_required
def list_results():
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({"success": False, "error": "User not authenticated"})
    
    try:
        # Get results from Firebase
        results = get_user_results(user_id)
        
        return jsonify({"success": True, "results": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/get_result', methods=['POST'])
@login_required
def get_result_api():
    result_id = request.json.get('result_id')
    user_id = session.get('user_id')
    
    if not result_id:
        return jsonify({"success": False, "error": "No result ID provided"})
    
    if not user_id:
        return jsonify({"success": False, "error": "User not authenticated"})
    
    try:
        # Get the result from Firebase
        result = get_result(user_id, result_id)
        
        if not result:
            return jsonify({"success": False, "error": "Result not found"})
        
        return jsonify({"success": True, "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/delete_result', methods=['POST'])
@login_required
def delete_result_api():
    result_id = request.json.get('result_id')
    user_id = session.get('user_id')
    
    if not result_id:
        return jsonify({"success": False, "error": "No result ID provided"})
    
    if not user_id:
        return jsonify({"success": False, "error": "User not authenticated"})
    
    try:
        # Delete the result from Firebase
        result = delete_result(user_id, result_id)
        
        if not result.get('success'):
            return jsonify({"success": False, "error": result.get('error', 'Failed to delete result')})
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
    
    
@app.route('/favicon.ico')
def favicon():
    """
    Serves the favicon.ico file from the static folder.
    If the file doesn't exist, it returns a 404 Not Found response.
    """
    from flask import send_from_directory
    
    try:
        return send_from_directory(os.path.join(app.root_path, 'static'),
                                   'favicon.ico', mimetype='image/vnd.microsoft.icon')
    except FileNotFoundError:
        # Log that favicon wasn't found
        print("Favicon.ico not found in static directory")
        return '', 404  # Return empty response with 404 status code

# Add these API endpoints to app.py

@app.route('/api/rename_payload', methods=['POST'])
@login_required
def rename_payload_api():
    payload_id = request.json.get('payload_id')
    new_name = request.json.get('new_name')
    user_id = session.get('user_id')
    
    if not payload_id or not new_name:
        return jsonify({"success": False, "error": "Missing payload ID or new name"})
    
    if not user_id:
        return jsonify({"success": False, "error": "User not authenticated"})
    
    try:
        # Get the current payload
        payload = get_payload(user_id, payload_id)
        if not payload:
            return jsonify({"success": False, "error": "Payload not found"})
        
        # Add a custom_name field instead of overwriting existing data
        payload_data = payload.copy()
        payload_data['custom_name'] = new_name
        
        # Save the updated payload
        result = update_payload(user_id, payload_id, payload_data)
        
        if result.get('success'):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": result.get('error', 'Failed to rename payload')})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/delete_payload', methods=['POST'])
@login_required
def delete_payload_api():
    payload_id = request.json.get('payload_id')
    user_id = session.get('user_id')
    
    if not payload_id:
        return jsonify({"success": False, "error": "No payload ID provided"})
    
    if not user_id:
        return jsonify({"success": False, "error": "User not authenticated"})
    
    try:
        # Delete the payload from Firebase
        result = delete_payload(user_id, payload_id)
        
        if result.get('success'):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": result.get('error', 'Failed to delete payload')})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/rename_result', methods=['POST'])
@login_required
def rename_result_api():
    result_id = request.json.get('result_id')
    new_name = request.json.get('new_name')
    user_id = session.get('user_id')
    
    if not result_id or not new_name:
        return jsonify({"success": False, "error": "Missing result ID or new name"})
    
    if not user_id:
        return jsonify({"success": False, "error": "User not authenticated"})
    
    try:
        # Get the current result
        result_data = get_result(user_id, result_id)
        
        if not result_data:
            return jsonify({"success": False, "error": "Result not found"})
        
        # Create a copy of the original document to preserve all fields
        new_result_data = result_data.copy()
        
        # Update the metadata with the custom name
        if 'metadata' not in new_result_data:
            new_result_data['metadata'] = {}
        new_result_data['metadata']['custom_name'] = new_name
        
        # Get the results array
        results = new_result_data.get('results', [])
        
        # Get the updated metadata
        metadata = new_result_data.get('metadata', {})
        
        # First delete the existing result
        delete_result_response = delete_result(user_id, result_id)
        if not delete_result_response.get('success'):
            return jsonify({"success": False, "error": delete_result_response.get('error', 'Failed to delete existing result')})
        
        # Then create a new result with the updated metadata
        create_result = save_results(user_id, results, metadata)
        
        if create_result.get('success'):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": create_result.get('error', 'Failed to rename result')})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    # Create necessary directories for legacy support
    if not os.path.exists("Queries"):
        os.makedirs("Queries")
    if not os.path.exists("Results"):
        os.makedirs("Results")
    
    print("Firebase initialization:", "Successful" if firebase_initialized else "Failed")
    print("Server running at http://localhost:5000")
    print("Go to the login page at http://localhost:5000/login")
    app.run(debug=True, port=5000)
