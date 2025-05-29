from flask import Blueprint, render_template, redirect, url_for, session, current_app, send_from_directory, jsonify
from ..auth_decorator import login_required # Import the updated decorator
import os # Keep os import

# Create the blueprint
views_bp = Blueprint('views', __name__)

# No placeholder decorator needed anymore

@views_bp.route('/')
def landing():
    """Serves the public landing page."""
    if 'user_id' in session:
        return redirect(url_for('views.app_interface')) # Use blueprint name for url_for
    return render_template('landing.html')

@views_bp.route('/app')
@login_required # Apply the actual decorator
def app_interface():
    """Serves the main application interface for logged-in users."""
    # Print session info for debugging
    print(f"User session: {session.get('user_id')}, {session.get('email')}")
    return render_template('index.html', username=session.get('display_name', 'User'))

@views_bp.route('/pricing')
def pricing():
    """Serves the public pricing page."""
    return render_template('pricing.html')

@views_bp.route('/about')
def about():
    """Serves the public about page."""
    return render_template('about.html')

@views_bp.route('/terms')
def terms():
    """Serves the terms and conditions page."""
    return render_template('terms.html')

# Add favicon route here as well, as it's a static-like view
@views_bp.route('/favicon.ico')
def favicon():
    """
    Serves the favicon.ico file from the static folder.
    If the file doesn't exist, it returns a 404 Not Found response.
    """
    # No need for extra imports here
    try:
        # Use current_app.root_path to get the application root
        return send_from_directory(os.path.join(current_app.root_path, 'static'),
                                   'favicon.ico', mimetype='image/vnd.microsoft.icon')
    except FileNotFoundError:
        # Log that favicon wasn't found
        current_app.logger.warning("Favicon.ico not found in static directory")
        return '', 404

# Add route for index.js (assuming it's part of the main app view)
@views_bp.route('/static/index.js')
@login_required # Apply actual decorator
def serve_main_js():
    """Serves the main index.js file for the application."""
    # No need for extra imports here
    try:
        # Use current_app.static_folder which should be configured on the app
        return send_from_directory(current_app.static_folder, 'index.js', mimetype='application/javascript')
    except FileNotFoundError:
        current_app.logger.error("static/index.js not found when serving via blueprint")
        return jsonify({"success": False, "error": "Main script file not found."}), 404
