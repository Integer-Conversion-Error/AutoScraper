from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
import os
import json
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
    delete_payload
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
            make = payload.get('Make', 'Unknown')
            model = payload.get('Model', 'Unknown')
            year_min = payload.get('YearMin', '')
            year_max = payload.get('YearMax', '')
            price_min = payload.get('PriceMin', '')
            price_max = payload.get('PriceMax', '')
            
            formatted_name = f"Firebase/{make}_{model}/{year_min}-{year_max}_{price_min}-{price_max}"
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
        
        save_results_to_csv(results, payload=payload, filename=full_path,max_workers=1000)
        
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