from flask import request, jsonify, redirect, url_for, session, flash
from functools import wraps
import time
from firebase_config import verify_id_token, get_user

def login_required_with_app(app, f):
    """
    Enhanced login_required decorator that ensures session persistence
    and proper authentication across requests.
    
    Args:
        app: The Flask application instance
        f: The function to decorate
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # First, check if the user is already in session
        if 'user_id' in session:
            user_id = session.get('user_id')
            
            # Re-validate the user if needed
            try:
                # Only re-validate occasionally for performance
                if 'last_validated' not in session or (time.time() - session.get('last_validated', 0) > 3600):
                    # Verify that the user still exists in Firebase
                    user = get_user(user_id)
                    if user:
                        # Update session with fresh data
                        session['last_validated'] = time.time()
                        session['email'] = user.email
                        session['display_name'] = user.display_name or user.email
                        session.modified = True  # Mark session as modified
                    else:
                        # User no longer exists, clear session
                        session.clear()
                        flash('Your session has expired. Please log in again.', 'warning')
                        return redirect(url_for('login'))
            except Exception as e:
                # Log the error but don't disrupt the user experience
                print(f"Error validating user: {e}")
                
            # User is authenticated, proceed
            return f(*args, **kwargs)
        
        # If not in session, check for Bearer token in Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split('Bearer ')[1]
            result = verify_id_token(token)
            
            if result['success']:
                user_info = result['user']
                # Store user information in session
                session['user_id'] = user_info.get('uid')
                session['email'] = user_info.get('email')
                session['display_name'] = user_info.get('name', user_info.get('email', 'User'))
                session['last_validated'] = time.time()
                session.modified = True  # Mark session as modified
                
                # If it's an API request, continue
                if request.path.startswith('/api/'):
                    return f(*args, **kwargs)
                    
                # For web pages, we might want to redirect to ensure a clean URL
                # But this causes problems with the auth flow, so we'll just proceed
                return f(*args, **kwargs)
            else:
                # For API endpoints, return JSON response
                if request.path.startswith('/api/'):
                    return jsonify({"success": False, "error": "Authentication failed"}), 401
                # For web pages, redirect to login
                flash('Authentication failed. Please log in again.', 'danger')
                return redirect(url_for('login'))
        
        # If no token is provided in a header for API requests
        if request.path.startswith('/api/'):
            return jsonify({"success": False, "error": "Authentication required"}), 401
        
        # For regular pages without authentication, redirect to login
        if request.path != '/login' and request.path != '/register':
            flash('Please log in to access this page', 'warning')
        return redirect(url_for('login'))
    
    return decorated_function