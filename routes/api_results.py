import os
import csv
import time
import logging
from flask import Blueprint, request, jsonify, session, g, current_app
# Import transform_strings as well
from AutoScraperUtil import format_time_ymd_hms, showcarsmain, clean_model_name, transform_strings
# Import the new processing function and necessary constants from AutoScraper
from AutoScraper import fetch_autotrader_data, process_links_and_update_cache, CACHE_HEADERS
from firebase_config import (
    save_results,
    get_user_results,
    get_result,
    delete_result,
    update_user_settings, # Keep for potential other uses? Or remove if only for tokens? Check usage.
    deduct_search_tokens, # Import the new atomic function
    get_firestore_db      # Needed for direct listing deletion
)
from auth_decorator import login_required # Import the updated decorator

# Create the blueprint
api_results_bp = Blueprint('api_results', __name__, url_prefix='/api')
 
# No placeholder decorator needed anymore

@api_results_bp.route('/fetch_data', methods=['POST'])
@login_required # Apply actual decorator (it populates g)
def fetch_data_api():
    payload = request.json.get('payload')
    print(f"--- DEBUG: Received payload in /api/fetch_data: {payload}")
    user_id = g.user_id # Get from g, set by decorator

    if not payload:
        return jsonify({"success": False, "error": "No payload provided"}), 400

    try:
        # 1. Get user settings (including current tokens) from g
        user_settings = g.user_settings
        current_tokens = user_settings.get('search_tokens', 0)

        # 2. Perform initial fetch to get estimated count
        initial_scrape_data = fetch_autotrader_data(payload, initial_fetch_only=True)
        if not isinstance(initial_scrape_data, dict):
             logging.error(f"Initial fetch did not return expected dictionary. Got: {initial_scrape_data}")
             return jsonify({"success": False, "error": "Initial data fetch failed unexpectedly."}), 500

        estimated_count = initial_scrape_data.get('estimated_count', 0)
        initial_results_html = initial_scrape_data.get('initial_results_html', [])
        max_page = initial_scrape_data.get('max_page', 1)

        # 3. Calculate required tokens
        required_tokens = round(max(estimated_count / 100.0, 0.1), 1) if estimated_count > 0 else 0
        print(f"Estimated count: {estimated_count}, Required tokens: {required_tokens}")


        # 4. Check if user has enough tokens
        if current_tokens < required_tokens:
            logging.warning(f"User {user_id} insufficient tokens. Has: {current_tokens}, Needs: {required_tokens} for {estimated_count} listings.")
            return jsonify({
                "success": False,
                "error": f"Insufficient tokens. This search requires {required_tokens} tokens ({estimated_count} listings found), but you only have {current_tokens}."
            }), 402 # Payment Required

        # 5. If enough tokens, proceed with fetching remaining pages
        logging.info(f"User {user_id} has sufficient tokens ({current_tokens} >= {required_tokens}). Proceeding with full scrape.")
        if max_page > 1:
            all_results_html = fetch_autotrader_data(
                payload,
                start_page=1,
                initial_results_html=initial_results_html,
                max_page_override=max_page
            )
        else:
            all_results_html = initial_results_html

        if not all_results_html:
            logging.warning(f"Initial estimate was {estimated_count}, but full fetch returned no results.")
            required_tokens = 0 # Don't charge if no results
            return jsonify({
                "success": True,
                "file_path": None,
                "result_count": 0,
                "tokens_charged": 0,
                "tokens_remaining": current_tokens
            })

        # --- Processing and Saving Results ---
        make = payload.get('Make', 'Unknown')
        model = payload.get('Model', 'Unknown')
        model = clean_model_name(model) # Clean the model name here
        # Ensure Results directory exists (might be better in app startup)
        results_base_dir = "Results"
        if not os.path.exists(results_base_dir):
            os.makedirs(results_base_dir)
        folder_path = os.path.join(results_base_dir, f"{make}_{model}")
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        file_name = f"{payload.get('YearMin', '')}-{payload.get('YearMax', '')}_{payload.get('PriceMin', '')}-{payload.get('PriceMax', '')}_{format_time_ymd_hms()}.csv"
        full_path = os.path.join(folder_path, file_name).replace("\\", "/")

        # Get transformed exclusions for filtering within the processing function
        raw_exclusions = payload.get("Exclusions", [])
        transformed_exclusions = transform_strings(raw_exclusions) # Use imported transform_strings

        # Call the processing function, passing transformed exclusions for filtering
        processed_results_dicts = process_links_and_update_cache(
            data=all_results_html,
            transformed_exclusions=transformed_exclusions,
            max_workers=1000
        )
        logging.info(f"Processing and filtering complete via API. Got {len(processed_results_dicts)} results for this search (from cache or fetched).") # Updated log message

        # Save the results *for this specific search* to the timestamped file
        if processed_results_dicts:
            try:
                with open(full_path, mode="w", newline="", encoding="utf-8") as file:
                    # Use the headers defined in AutoScraper.py
                    writer = csv.DictWriter(file, fieldnames=CACHE_HEADERS)
                    writer.writeheader()
                    writer.writerows(processed_results_dicts)
                logging.info(f"Saved {len(processed_results_dicts)} results for this search to {full_path}")
                # No need to read the file back, we already have processed_results_dicts
            except Exception as e:
                 logging.error(f"Error writing timestamped CSV {full_path}: {e}", exc_info=True)
                 # Decide if this is fatal or if we can proceed with Firebase save
                 return jsonify({"success": False, "error": "Failed to save results file."}), 500
        else:
             logging.warning(f"No results obtained after processing links for file {full_path}")
             # Return success but indicate no results found after processing
             # Deduct tokens based on the initial estimate, even if processing yielded no results.
             deduct_result = deduct_search_tokens(user_id, required_tokens)
             if not deduct_result.get('success'):
                 # Log the error but proceed with the response, as the search itself was 'successful'
                 # in the sense that it ran, just token deduction failed.
                 logging.error(f"Failed to deduct tokens for user {user_id} after empty processing. Error: {deduct_result.get('error')}")
                 # Consider if a different response is needed here? For now, return as if deducted.

             # Calculate remaining tokens based on the initial count for the response
             tokens_remaining_after_deduction = current_tokens - required_tokens
             return jsonify({
                "success": True,
                "file_path": None,
                "result_count": 0,
                "tokens_charged": required_tokens,
                "tokens_remaining": tokens_remaining_after_deduction
             })

        # Use the directly obtained list of dicts for Firebase
        processed_results_for_firebase = processed_results_dicts

        # --- Save to Firebase ---
        metadata = {
            'make': make,
            'model': model, # Use the cleaned model name
            'yearMin': payload.get('YearMin', ''),
            'yearMax': payload.get('YearMax', ''),
            'priceMin': payload.get('PriceMin', ''),
            'priceMax': payload.get('PriceMax', ''),
            'file_name': file_name, # Keep the timestamped file name
            'timestamp': format_time_ymd_hms(), # Consider using a consistent timestamp
            'estimated_listings_scanned': estimated_count,
            'actual_results_found': len(processed_results_for_firebase), # Add actual count
            'tokens_charged': required_tokens,
            'custom_name': payload.get('custom_name') # Carry over custom name if payload had one
        }
        firebase_result = save_results(user_id, processed_results_for_firebase, metadata)

        # 6. Atomically deduct tokens (already calculated based on estimate)
        deduct_result = deduct_search_tokens(user_id, required_tokens)
        if not deduct_result.get('success'):
            # Log the error, but the search itself and saving succeeded.
            # The response will show the tokens *before* this failed deduction attempt.
            logging.error(f"Failed to deduct tokens for user {user_id} after successful search and save. Error: {deduct_result.get('error')}")
            # Potentially add a flag to the response? Or rely on logs for reconciliation.

        # Calculate remaining tokens based on the initial count for the response
        tokens_remaining_after_deduction = current_tokens - required_tokens

        # --- Prepare Response ---
        response_data = {
            "success": True,
            "file_path": full_path,
            "result_count": len(processed_results_for_firebase),
            "tokens_charged": required_tokens,
            "tokens_remaining": tokens_remaining_after_deduction # Show calculated remaining based on initial value
        }
        if firebase_result.get('success'):
            response_data["doc_id"] = firebase_result.get('doc_id')
        else:
             logging.error(f"Failed to save results to Firebase for user {user_id}. Error: {firebase_result.get('error')}")

        return jsonify(response_data)

    except Exception as e:
        logging.error(f"Error in fetch_data_api: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"An unexpected error occurred: {str(e)}"}), 500


@api_results_bp.route('/open_links', methods=['POST'])
@login_required # Apply actual decorator
def open_links_api():
    file_path = request.json.get('file_path')
    if not file_path:
        return jsonify({"success": False, "error": "No file path provided"}), 400

    try:
        # Basic path validation (more robust checks might be needed depending on security requirements)
        if not os.path.exists(file_path) or not file_path.startswith("Results/"):
             # Check if it exists and is within the expected 'Results' directory
             logging.warning(f"Attempt to open potentially invalid path: {file_path}")
             return jsonify({"success": False, "error": f"File not found or invalid path: {file_path}"}), 404

        showcarsmain(file_path)
        return jsonify({"success": True})
    except Exception as e:
        logging.error(f"Error opening links from {file_path}: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@api_results_bp.route('/list_results')
@login_required # Apply actual decorator
def list_results_api(): # Renamed function
    user_id = session.get('user_id') # Can get from session or g

    try:
        results = get_user_results(user_id)
        # The function already returns the desired format {id, metadata}
        return jsonify({"success": True, "results": results})
    except Exception as e:
        logging.error(f"Error listing results for user {user_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@api_results_bp.route('/get_result', methods=['POST'])
@login_required # Apply actual decorator
def get_result_api():
    result_id = request.json.get('result_id')
    user_id = session.get('user_id')

    if not result_id:
        return jsonify({"success": False, "error": "No result ID provided"}), 400

    try:
        result = get_result(user_id, result_id)
        if result is None:
            return jsonify({"success": False, "error": "Result not found"}), 404
        # Result includes 'metadata' and 'results' keys
        return jsonify({"success": True, "result": result})
    except Exception as e:
        logging.error(f"Error getting result {result_id} for user {user_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@api_results_bp.route('/delete_result', methods=['POST'])
@login_required # Apply actual decorator
def delete_result_api():
    result_id = request.json.get('result_id')
    user_id = session.get('user_id')

    if not result_id:
        return jsonify({"success": False, "error": "No result ID provided"}), 400

    try:
        result = delete_result(user_id, result_id)
        if not result.get('success'):
            error_msg = result.get('error', 'Failed to delete result')
            status_code = 404 if "not found" in error_msg.lower() else 500
            return jsonify({"success": False, "error": error_msg}), status_code
        return jsonify({"success": True})
    except Exception as e:
        logging.error(f"Error deleting result {result_id} for user {user_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@api_results_bp.route('/delete_listing_from_result', methods=['POST'])
@login_required # Apply actual decorator
def delete_listing_from_result_api():
    user_id = session.get('user_id')
    data = request.json
    result_id = data.get('result_id')
    listing_identifier = data.get('listing_identifier') # Expecting {'Link': '...'}

    if not result_id:
        return jsonify({"success": False, "error": "Result ID not provided"}), 400
    if not listing_identifier or 'Link' not in listing_identifier:
        return jsonify({"success": False, "error": "Listing identifier (Link) not provided"}), 400

    link_to_delete = listing_identifier['Link']

    try:
        db = get_firestore_db()
        if not db:
             logging.error("Firestore DB not initialized for delete_listing_from_result")
             return jsonify({"success": False, "error": "Database connection error"}), 500

        # Reference the 'listings' subcollection directly
        listings_coll_ref = db.collection('users').document(user_id).collection('results').document(result_id).collection('listings')

        # Query for the specific listing document by its 'Link' field
        query = listings_coll_ref.where('Link', '==', link_to_delete).limit(1)
        docs = query.stream()

        doc_to_delete = None
        for doc in docs:
            doc_to_delete = doc
            break # Should only be one match

        if doc_to_delete:
            # Delete the specific listing document
            doc_to_delete.reference.delete()
            logging.info(f"Deleted listing document {doc_to_delete.id} (Link: {link_to_delete}) from result '{result_id}' for user '{user_id}'.")
            # Optional: Decrement count in parent doc? For now, skip for performance.
            # parent_doc_ref = db.collection('users').document(user_id).collection('results').document(result_id)
            # parent_doc_ref.update({'result_count': firestore.Increment(-1)})
            return jsonify({"success": True})
        else:
            logging.warning(f"Listing with link '{link_to_delete}' not found in listings subcollection for result '{result_id}', user '{user_id}'. No changes made.")
            return jsonify({"success": True, "message": "Listing not found, no changes needed."}) # Still success, just didn't find it

    except Exception as e:
        logging.error(f"Error deleting listing (Link: {link_to_delete}) from result '{result_id}' for user '{user_id}': {e}", exc_info=True)
        return jsonify({"success": False, "error": f"An unexpected error occurred: {str(e)}"}), 500


@api_results_bp.route('/rename_result', methods=['POST'])
@login_required # Apply actual decorator
def rename_result_api():
    result_id = request.json.get('result_id')
    new_name = request.json.get('new_name')
    user_id = session.get('user_id')

    if not result_id or not new_name:
        return jsonify({"success": False, "error": "Missing result ID or new name"}), 400

    try:
        db = get_firestore_db()
        if not db:
             logging.error("Firestore DB not initialized for rename_result")
             return jsonify({"success": False, "error": "Database connection error"}), 500

        doc_ref = db.collection('users').document(user_id).collection('results').document(result_id)
        doc = doc_ref.get()

        if not doc.exists:
            return jsonify({"success": False, "error": "Result not found"}), 404

        # Update the custom_name within the metadata field
        doc_ref.update({'metadata.custom_name': new_name})
        logging.info(f"Renamed result '{result_id}' to '{new_name}' for user '{user_id}'.")
        return jsonify({"success": True})

    except Exception as e:
        logging.error(f"Error renaming result {result_id} for user {user_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
