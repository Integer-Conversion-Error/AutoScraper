from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
import os
import json
import secrets
from datetime import timedelta
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('autoscraper')

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
from firebase_config import initialize_firebase, verify_id_token

# Initialize app with simple cookie-based sessions
app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))

# Make sessions permanent by default
app.permanent_session_lifetime = timedelta(days=30)

@app.before_request
def make_session_permanent():
    session.permanent = True
    # Log request info for debugging
    logger.debug(f"{request.method} {request.path} {session.get('user_id', 'No user')}")

def login_required(f):
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            logger.debug("Not authenticated, redirecting to login")
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    
    return decorated_function

@app.route('/')
@login_required
def index():
    """Main application page."""
    logger.debug(f"Rendering index for user: {session.get('user_id')}")
    return render_template('index.html', username=session.get('display_name', 'User'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    # If already logged in, go to index
    if 'user_id' in session:
        logger.debug("Already logged in, redirecting to index")
        return redirect(url_for('index'))
        
    if request.method == 'POST':
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
                
                logger.debug(f"Login successful for {session.get('email')}")
                flash('Login successful!', 'success')
                return redirect(url_for('index'))
            else:
                logger.error(f"Authentication failed: {result.get('error')}")
                flash('Authentication failed: ' + result.get('error', 'Unknown error'), 'danger')
        else:
            flash('No authentication token provided', 'danger')
            
    # If it's a GET request or login failed
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Handle user logout."""
    user_id = session.get('user_id')
    if user_id:
        logger.debug(f"Logging out user {user_id}")
    
    # Clear the user session
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

# Add a session debug endpoint
@app.route('/debug/session')
def debug_session():
    """Debug endpoint to see current session data."""
    if request.remote_addr == '127.0.0.1':  # Only allow local access
        return jsonify({
            "user_id": session.get('user_id'),
            "email": session.get('email'),
            "session_keys": list(session.keys())
        })
    return "Not authorized", 403

@app.route('/api/auth/check')
def auth_check():
    """Simple endpoint to check if user is authenticated."""
    is_auth = 'user_id' in session
    logger.debug(f"Auth check: {is_auth}")
    return jsonify({
        "authenticated": is_auth,
        "user": {
            "id": session.get('user_id'),
            "email": session.get('email'),
            "displayName": session.get('display_name')
        } if is_auth else None
    })


if __name__ == '__main__':
    # Initialize Firebase
    firebase_initialized = initialize_firebase()
    
    # Create necessary directories
    os.makedirs("Queries", exist_ok=True)
    os.makedirs("Results", exist_ok=True)
    
    logger.info("Firebase initialization: %s", "Successful" if firebase_initialized else "Failed")
    logger.info("Server running at http://localhost:5000")
    
    app.run(debug=True, port=5000)