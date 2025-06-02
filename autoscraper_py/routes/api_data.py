from flask import Blueprint, request, jsonify, session
from urllib.parse import unquote
from ..AutoScraperUtil import (
    get_all_makes,
    get_models_for_make,
    get_trims_for_model,
    get_colors,
    clean_model_name # Import the new function
)
from ..auth_decorator import login_required # Import the updated decorator

# Create the blueprint
api_data_bp = Blueprint('api_data', __name__, url_prefix='/api') # Add prefix for API routes

# No placeholder decorator needed anymore

@api_data_bp.route('/makes')
@login_required # Apply actual decorator
def get_makes_api(): # Renamed function slightly to avoid conflict if imported directly
    popular = request.args.get('popular', 'true').lower() == 'true'
    makes = get_all_makes(popular=popular)
    return jsonify(makes)

@api_data_bp.route('/models/<make>')
@login_required # Apply actual decorator
def get_models_api(make): # Renamed function slightly
    # Decode make here if necessary, although Flask usually handles basic URL decoding
    decoded_make = unquote(make)
    models = get_models_for_make(decoded_make)
    return jsonify(models)

@api_data_bp.route('/trims/<make>/<model>')
@login_required # Apply actual decorator
def get_trims_api(make, model):
    """API endpoint to get trims for a specific make and model."""
    decoded_make = unquote(make)
    decoded_model = unquote(model)
    cleaned_model = clean_model_name(decoded_model) # Use the utility function
    trims = get_trims_for_model(decoded_make, cleaned_model)
    return jsonify(trims)

@api_data_bp.route('/colors/<make>/<model>')
@api_data_bp.route('/colors/<make>/<model>/<trim>') # Add route with optional trim
@login_required # Apply actual decorator
def get_colors_api(make, model, trim=None):
    """API endpoint to get colors for a specific make, model, and optional trim."""
    decoded_make = unquote(make)
    decoded_model = unquote(model)
    decoded_trim = unquote(trim) if trim else None
    cleaned_model = clean_model_name(decoded_model) # Use the utility function

    colors = get_colors(decoded_make, cleaned_model, decoded_trim)
    return jsonify(colors)
