import firebase_admin
from firebase_admin import credentials, firestore, auth
import json
import os

# Initialize Firebase Admin SDK
def initialize_firebase():
    """
    Initialize the Firebase Admin SDK with credentials from the firebase_credentials.json file.
    If running in production, the credentials may be stored as environment variables.
    """
    try:
        # First try to load from a credentials file
        if os.path.exists('firebase_credentials.json'):
            cred = credentials.Certificate('firebase_credentials.json')
            firebase_admin.initialize_app(cred)
        # If no file exists, try to load from environment variables
        else:
            # This assumes the credentials are stored as a JSON string in the FIREBASE_CREDENTIALS env var
            firebase_creds = json.loads(os.environ.get('FIREBASE_CREDENTIALS', '{}'))
            if firebase_creds:
                cred = credentials.Certificate(firebase_creds)
                firebase_admin.initialize_app(cred)
            else:
                print("WARNING: No Firebase credentials found.")
                return False

        # Initialize Firestore
        db = firestore.client()
        return True
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
        return False

def get_firestore_db():
    """
    Get the Firestore database instance.

    Returns:
        firestore.Client: The Firestore database client
    """
    try:
        return firestore.client()
    except Exception as e:
        print(f"Error getting Firestore client: {e}")
        return None

# Firebase Authentication functions
def create_user(email, password, display_name=None):
    """
    Create a new user in Firebase Authentication.

    Args:
        email (str): The user's email
        password (str): The user's password
        display_name (str, optional): The user's display name

    Returns:
        dict: User information including UID
    """
    try:
        user = auth.create_user(
            email=email,
            password=password,
            display_name=display_name or email.split('@')[0]
        )
        return {'success': True, 'uid': user.uid}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def verify_id_token(id_token):
    """
    Verify a Firebase authentication token.

    Args:
        id_token (str): The ID token to verify

    Returns:
        dict: The decoded token information
    """
    try:
        decoded_token = auth.verify_id_token(id_token,clock_skew_seconds=3)
        return {'success': True, 'user': decoded_token}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_user(uid):
    """
    Retrieve a user by their UID.

    Args:
        uid (str): The user's UID

    Returns:
        UserRecord: The user record
    """
    try:
        return auth.get_user(uid)
    except Exception as e:
        print(f"Error retrieving user: {e}")
        return None

# Firestore operations for payloads
def save_payload(user_id, payload):
    """
    Save a search payload to Firestore.

    Args:
        user_id (str): The ID of the user who created the payload
        payload (dict): The search payload to save

    Returns:
        dict: Success status and document ID
    """
    try:
        db = get_firestore_db()
        if not db:
            return {'success': False, 'error': 'Database connection failed'}

        # Create a reference to the payloads collection for this user
        payloads_ref = db.collection('users').document(user_id).collection('payloads')

        # Add necessary metadata
        payload_with_metadata = {
            **payload,
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP
        }

        # Save the payload
        doc_ref = payloads_ref.add(payload_with_metadata)
        return {'success': True, 'doc_id': doc_ref[1].id}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_user_payloads(user_id):
    """
    Get all payloads for a specific user.

    Args:
        user_id (str): The user's ID

    Returns:
        list: List of payload documents
    """
    try:
        db = get_firestore_db()
        if not db:
            return []

        payloads_ref = db.collection('users').document(user_id).collection('payloads')
        payloads = payloads_ref.order_by('created_at', direction=firestore.Query.DESCENDING).get()

        result = []
        for payload_doc in payloads:
            data = payload_doc.to_dict()
            result.append({
                'id': payload_doc.id,
                'payload': data,
                'created_at': data.get('created_at')
            })

        return result
    except Exception as e:
        print(f"Error retrieving payloads: {e}")
        return []

def get_payload(user_id, payload_id):
    """
    Get a specific payload by ID.

    Args:
        user_id (str): The user's ID
        payload_id (str): The payload document ID

    Returns:
        dict: The payload data
    """
    try:
        db = get_firestore_db()
        if not db:
            print(f"Debug - get_payload: Database connection failed")
            return None

        print(f"Debug - get_payload: Fetching document for User: {user_id}, Payload ID: {payload_id}")
        payload_ref = db.collection('users').document(user_id).collection('payloads').document(payload_id)
        payload = payload_ref.get()

        if not payload.exists:
            print(f"Debug - get_payload: Document does not exist")
            return None

        print(f"Debug - get_payload: Document found, contains keys: {list(payload.to_dict().keys())}")
        return payload.to_dict()
    except Exception as e:
        print(f"Error retrieving payload: {e}")
        return None

def update_payload(user_id, payload_id, payload_data):
    """
    Update an existing payload.

    Args:
        user_id (str): The user's ID
        payload_id (str): The payload document ID
        payload_data (dict): The updated payload data

    Returns:
        dict: Success status
    """
    try:
        db = get_firestore_db()
        if not db:
            return {'success': False, 'error': 'Database connection failed'}

        # Add updated timestamp
        payload_data['updated_at'] = firestore.SERVER_TIMESTAMP

        payload_ref = db.collection('users').document(user_id).collection('payloads').document(payload_id)
        payload_ref.update(payload_data)

        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def delete_payload(user_id, payload_id):
    """
    Delete a payload.

    Args:
        user_id (str): The user's ID
        payload_id (str): The payload document ID

    Returns:
        dict: Success status
    """
    try:
        db = get_firestore_db()
        if not db:
            return {'success': False, 'error': 'Database connection failed'}

        payload_ref = db.collection('users').document(user_id).collection('payloads').document(payload_id)
        payload_ref.delete()

        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# --- User Settings Functions ---

def get_user_settings(user_id):
    """
    Get user-specific settings like search tokens and AI access.

    Args:
        user_id (str): The user's ID

    Returns:
        dict: User settings with defaults if not found.
    """
    try:
        db = get_firestore_db()
        if not db:
            print("Error getting user settings: Database connection failed")
            # Return defaults on DB error to avoid blocking functionality
            return {'search_tokens': 0, 'can_use_ai': False}

        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        if user_doc.exists:
            user_data = user_doc.to_dict()
            # Return existing settings, applying defaults if fields are missing
            search_tokens = user_data.get('search_tokens', 0)
            settings = {
                'search_tokens': round(float(search_tokens), 1), # Round to one decimal place
                'can_use_ai': user_data.get('can_use_ai', False),
                'isPayingUser': user_data.get('isPayingUser', False) # Add isPayingUser field
            }
            return settings
        else:
            # User document doesn't exist, return defaults including isPayingUser
            print(f"User document {user_id} not found, returning default settings.")
            # Ensure default is also float for consistency if it were non-zero, though 0.0 is fine.
            return {'search_tokens': 0.0, 'can_use_ai': False, 'isPayingUser': False}
    except Exception as e:
        print(f"Error retrieving user settings for {user_id}: {e}")
        # Return defaults on error, including isPayingUser
        # Ensure default is also float for consistency.
        return {'search_tokens': 0.0, 'can_use_ai': False, 'isPayingUser': False}

def update_user_settings(user_id, settings_update):
    """
    Update user-specific settings. Creates the user document if it doesn't exist.

    Args:
        user_id (str): The user's ID
        settings_update (dict): Dictionary containing settings to update (e.g., {'search_tokens': 10, 'can_use_ai': True})

    Returns:
        dict: Success status
    """
    try:
        db = get_firestore_db()
        if not db:
            return {'success': False, 'error': 'Database connection failed'}

        user_ref = db.collection('users').document(user_id)

        # Use set with merge=True to create or update the document/fields
        user_ref.set(settings_update, merge=True)

        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def deduct_search_tokens(user_id, tokens_to_deduct):
    """
    Atomically deduct search tokens from a user's account.

    Args:
        user_id (str): The user's ID.
        tokens_to_deduct (float or int): The number of tokens to deduct.

    Returns:
        dict: Success status.
    """
    if tokens_to_deduct <= 0:
        # No need to update if deduction amount is zero or negative
        return {'success': True, 'message': 'No tokens deducted.'}

    try:
        db = get_firestore_db()
        if not db:
            return {'success': False, 'error': 'Database connection failed'}

        user_ref = db.collection('users').document(user_id)

        # Use firestore.Increment to atomically decrease the token count
        # Note: We negate the value because Increment adds, so we add a negative value.
        update_result = user_ref.update({
            'search_tokens': firestore.Increment(-float(tokens_to_deduct)) # Ensure float for consistency
        })

        # The update method doesn't directly confirm the operation succeeded in the way
        # 'set' or 'add' might return references, but it will raise an exception on failure.
        # We assume success if no exception is raised.

        # After successful deduction, fetch the updated user document to get the new token count
        updated_user_doc = user_ref.get()
        if updated_user_doc.exists:
            updated_settings = updated_user_doc.to_dict()
            tokens_after_deduction = updated_settings.get('search_tokens', 0) # Default to 0 if somehow missing
            # Round the remaining tokens to one decimal place
            rounded_tokens_remaining = round(float(tokens_after_deduction), 1)
            return {'success': True, 'tokens_remaining': rounded_tokens_remaining}
        else:
            # This case should ideally not happen if deduction was successful on an existing user
            # logger.error(f"User document not found for {user_id} after token deduction.") # logger is not defined here
            print(f"User document not found for {user_id} after token deduction.")
            return {'success': False, 'error': 'User not found after deduction.', 'tokens_remaining': 0}

    except Exception as e:
        # Specific error handling could be added here (e.g., user not found?)
        print(f"Error deducting tokens for user {user_id}: {e}")
        # Attempt to fetch current tokens even on error, to provide some value if possible
        current_tokens_on_error = 0
        try:
            user_doc_on_error = db.collection('users').document(user_id).get()
            if user_doc_on_error.exists:
                current_tokens_on_error = user_doc_on_error.to_dict().get('search_tokens', 0)
        except Exception as fetch_err:
            print(f"Could not fetch tokens during error handling for user {user_id}: {fetch_err}")
        # Round the remaining tokens in the error case as well
        rounded_tokens_on_error = round(float(current_tokens_on_error), 1)
        return {'success': False, 'error': str(e), 'tokens_remaining': rounded_tokens_on_error}

# --- End User Settings Functions ---


# --- Helper function for deleting subcollections ---
def _delete_collection(coll_ref, batch_size):
    """Recursively delete a collection in batches."""
    docs = coll_ref.limit(batch_size).stream()
    deleted = 0

    for doc in docs:
        print(f'Deleting doc {doc.id} => {doc.to_dict()}') # Careful logging potentially sensitive data
        doc.reference.delete()
        deleted = deleted + 1

    if deleted >= batch_size:
        return _delete_collection(coll_ref, batch_size)
# --- End Helper ---


# --- Firestore Results Functions (Using Subcollections) ---

def save_results(user_id, results_list, metadata):
    """
    Save search results to Firestore, storing listings in a subcollection.

    Args:
        user_id (str): The ID of the user who owns the results
        results_list (list): The list of result dictionaries (each is a listing)
        metadata (dict): Metadata about the search (make, model, etc.)

    Returns:
        dict: Success status and document ID
    """
    try:
        db = get_firestore_db()
        if not db:
            return {'success': False, 'error': 'Database connection failed'}

        # 1. Create the main result document with metadata only
        main_results_coll_ref = db.collection('users').document(user_id).collection('results')
        metadata_doc = {
            'metadata': metadata,
            'created_at': firestore.SERVER_TIMESTAMP,
            'result_count': len(results_list) # Store the count here
        }
        # Add the metadata document first to get its ID
        update_time, main_doc_ref = main_results_coll_ref.add(metadata_doc)
        main_doc_id = main_doc_ref.id
        print(f"Created metadata document: {main_doc_id}")

        # 2. Create a reference to the 'listings' subcollection under the new main doc
        listings_coll_ref = main_doc_ref.collection('listings')

        # 3. Use batch writes to add each listing as a document in the subcollection
        batch = db.batch()
        batch_count = 0
        commit_count = 0
        max_batch_size = 499 # Firestore batch limit is 500 operations

        for listing_data in results_list:
            # Create a new document reference in the 'listings' subcollection (auto-ID)
            listing_doc_ref = listings_coll_ref.document()
            batch.set(listing_doc_ref, listing_data)
            batch_count += 1

            # Commit the batch when it reaches the size limit
            if batch_count >= max_batch_size:
                print(f"Committing batch {commit_count + 1} with {batch_count} listings...")
                batch.commit()
                print("Batch committed.")
                commit_count += 1
                # Start a new batch
                batch = db.batch()
                batch_count = 0

        # Commit any remaining listings in the last batch
        if batch_count > 0:
            print(f"Committing final batch {commit_count + 1} with {batch_count} listings...")
            batch.commit()
            print("Final batch committed.")

        return {'success': True, 'doc_id': main_doc_id}

    except Exception as e:
        # Consider cleanup if metadata doc was created but listings failed
        print(f"Error saving results: {e}")
        return {'success': False, 'error': str(e)}


def get_user_results(user_id):
    """
    Get metadata for all results for a specific user. Does NOT fetch listings.

    Args:
        user_id (str): The user's ID

    Returns:
        list: List of result documents containing only metadata.
    """
    try:
        db = get_firestore_db()
        if not db:
            return []

        results_ref = db.collection('users').document(user_id).collection('results')
        # Fetch only metadata documents, ordered by creation time
        results_query = results_ref.order_by('created_at', direction=firestore.Query.DESCENDING)
        results_stream = results_query.stream() # Use stream for potentially large number of results

        result_list = []
        for result_doc in results_stream:
            data = result_doc.to_dict()
            metadata = data.get('metadata', {})
            result_list.append({
                'id': result_doc.id,
                'metadata': metadata,
                'created_at': data.get('created_at'),
                'result_count': data.get('result_count', 0) # Get count from metadata doc
            })

        return result_list
    except Exception as e:
        print(f"Error retrieving results metadata: {e}")
        return []

def get_result(user_id, result_id):
    """
    Get a specific result by ID, including its listings from the subcollection.

    Args:
        user_id (str): The user's ID
        result_id (str): The result document ID

    Returns:
        dict: The result data including metadata and the list of listings, or None if not found.
    """
    try:
        db = get_firestore_db()
        if not db:
            return None

        # 1. Get the main metadata document
        main_doc_ref = db.collection('users').document(user_id).collection('results').document(result_id)
        main_doc = main_doc_ref.get()

        if not main_doc.exists:
            print(f"Result metadata document {result_id} not found for user {user_id}")
            return None

        result_data = main_doc.to_dict() # Contains 'metadata', 'created_at', 'result_count'

        # 2. Get all documents from the 'listings' subcollection
        listings_coll_ref = main_doc_ref.collection('listings')
        listings_stream = listings_coll_ref.stream() # Use stream for efficiency

        listings = []
        for listing_doc in listings_stream:
            listings.append(listing_doc.to_dict())

        # 3. Combine metadata and listings
        result_data['results'] = listings # Add the listings array back for frontend compatibility

        # Optional: Verify count if needed
        if len(listings) != result_data.get('result_count', -1):
             print(f"Warning: Mismatch between stored result_count ({result_data.get('result_count')}) and actual listings found ({len(listings)}) for result {result_id}")
             # Update the count?
             # main_doc_ref.update({'result_count': len(listings)})

        return result_data
    except Exception as e:
        print(f"Error retrieving result {result_id}: {e}")
        return None

def delete_result(user_id, result_id):
    """
    Delete a result document and its 'listings' subcollection.

    Args:
        user_id (str): The user's ID
        result_id (str): The result document ID

    Returns:
        dict: Success status
    """
    try:
        db = get_firestore_db()
        if not db:
            return {'success': False, 'error': 'Database connection failed'}

        main_doc_ref = db.collection('users').document(user_id).collection('results').document(result_id)

        # Check if document exists before attempting deletion
        if not main_doc_ref.get().exists:
             print(f"Result document {result_id} not found for user {user_id}. Nothing to delete.")
             return {'success': True, 'message': 'Result not found.'} # Or return error?

        # 1. Delete the 'listings' subcollection first
        listings_coll_ref = main_doc_ref.collection('listings')
        print(f"Deleting listings subcollection for result {result_id}...")
        _delete_collection(listings_coll_ref, batch_size=100) # Adjust batch size as needed
        print(f"Finished deleting listings subcollection.")

        # 2. Delete the main metadata document
        print(f"Deleting main result document {result_id}...")
        main_doc_ref.delete()
        print(f"Main result document {result_id} deleted.")

        return {'success': True}
    except Exception as e:
        print(f"Error deleting result {result_id}: {e}")
        return {'success': False, 'error': str(e)}

# --- End Firestore Results Functions ---


# --- AI Analysis Cache Functions ---

def _make_link_firestore_safe(link_string):
    """Converts a URL string into a Firestore-safe document ID."""
    if not link_string:
        return None
    # Replace common problematic characters for Firestore document IDs
    # Firestore IDs cannot contain '/', '.', '..', or be '__.*__'.
    # We'll replace '/', ':', '?', '&', '#', '.' with '_'
    # and ensure it doesn't start/end with '.' or contain '..'
    safe_link = link_string.replace('/', '_').replace(':', '_').replace('?', '_') \
                           .replace('&', '_').replace('#', '_').replace('.', '_')
    # Basic check for leading/trailing problematic chars (though our replacements handle most)
    if safe_link.startswith('_'):
        safe_link = 'link' + safe_link
    if safe_link.endswith('_'):
        safe_link = safe_link + 'end'
    # Ensure it's not excessively long (Firestore ID limit is 1500 bytes)
    return safe_link[:1400] # Truncate if very long, allowing some buffer

def get_ai_analysis(user_id, listing_link_original):
    """
    Retrieves a stored AI analysis for a specific listing link.

    Args:
        user_id (str): The user's ID.
        listing_link_original (str): The original URL of the listing.

    Returns:
        dict: The stored analysis data (including 'analysis_text', 'created_at') 
              or None if not found.
    """
    db = get_firestore_db()
    if not db or not listing_link_original:
        return None
    
    safe_listing_link = _make_link_firestore_safe(listing_link_original)
    if not safe_listing_link:
        return None

    try:
        analysis_ref = db.collection('users').document(user_id) \
                         .collection('ai_analyses').document(safe_listing_link)
        analysis_doc = analysis_ref.get()

        if analysis_doc.exists:
            return analysis_doc.to_dict()
        return None
    except Exception as e:
        print(f"Error retrieving AI analysis for user {user_id}, link {listing_link_original}: {e}")
        return None

def save_ai_analysis(user_id, listing_link_original, analysis_text):
    """
    Saves a new AI analysis result to Firestore.

    Args:
        user_id (str): The user's ID.
        listing_link_original (str): The original URL of the listing.
        analysis_text (str): The AI-generated analysis text.

    Returns:
        bool: True if successful, False otherwise.
    """
    db = get_firestore_db()
    if not db or not listing_link_original:
        return False

    safe_listing_link = _make_link_firestore_safe(listing_link_original)
    if not safe_listing_link:
        return False
        
    try:
        analysis_ref = db.collection('users').document(user_id) \
                         .collection('ai_analyses').document(safe_listing_link)
        
        analysis_data = {
            'analysis_text': analysis_text,
            'original_link': listing_link_original,
            'created_at': firestore.SERVER_TIMESTAMP
        }
        analysis_ref.set(analysis_data)
        return True
    except Exception as e:
        print(f"Error saving AI analysis for user {user_id}, link {listing_link_original}: {e}")
        return False

# --- End AI Analysis Cache Functions ---
