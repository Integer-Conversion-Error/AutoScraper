import os
import csv
import logging
from celery import Celery, Task
from celery.utils.log import get_task_logger

# Import necessary functions from other modules
from AutoScraper import fetch_autotrader_data, process_links_and_update_cache, CACHE_HEADERS
from AutoScraperUtil import format_time_ymd_hms, clean_model_name, transform_strings
from firebase_config import initialize_firebase, save_results, deduct_search_tokens, get_firestore_db # Add initialize_firebase

# Configure Celery
# Replace 'redis://localhost:6379/0' with your actual Redis broker URL if different
# You might need to install redis: pip install redis
celery_app = Celery('tasks', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')

# Optional: Configure Celery further (e.g., timezone)
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],  # Ensure JSON serialization
    result_serializer='json',
    timezone='America/Toronto', # Match your app's timezone
    enable_utc=True,
)

# Get a logger for tasks
logger = get_task_logger(__name__)

# Firebase is initialized in app.py, which should be sufficient for the worker process as well.
# Removing the redundant initialization here.

class ProgressTask(Task):
    """Custom Task class to easily update state."""
    def update_progress(self, current, total, step="Processing"):
        self.update_state(
            state='PROGRESS',
            meta={'current': current, 'total': total, 'step': step}
        )

@celery_app.task(bind=True, base=ProgressTask, name='tasks.scrape_and_process_task')
def scrape_and_process_task(self, payload, user_id, required_tokens, initial_scrape_data):
    """
    Celery task to perform the full scrape, process results, save, and deduct tokens.
    """
    logger.info(f"[Task ID: {self.request.id}] Starting scrape for user {user_id}. Payload: {payload}")
    self.update_progress(0, 100, "Initializing scrape...")

    try:
        # --- 1. Full Data Fetch ---
        logger.info(f"[Task ID: {self.request.id}] Performing full data fetch.")
        # Extract data needed from initial_scrape_data passed from the route
        initial_results_html = initial_scrape_data.get('initial_results_html', [])
        max_page = initial_scrape_data.get('max_page', 1)

        if max_page > 1:
            # Pass the task instance (self) to the fetch function for progress updates
            all_results_html = fetch_autotrader_data(
                payload,
                start_page=1,
                initial_results_html=initial_results_html,
                max_page_override=max_page,
                task_instance=self # Pass task instance here
            )
        else:
            all_results_html = initial_results_html
            self.update_progress(100, 100, "Fetching complete (1 page).") # Update progress if only one page

        if not all_results_html:
            logger.warning(f"[Task ID: {self.request.id}] Full fetch returned no results.")
            # Deduct tokens anyway based on initial estimate, as the attempt was made
            deduct_result = deduct_search_tokens(user_id, required_tokens)
            if not deduct_result.get('success'):
                logger.error(f"[Task ID: {self.request.id}] Failed to deduct tokens for user {user_id} after empty fetch. Error: {deduct_result.get('error')}")
            # Return success but indicate no results found
            return {
                "status": "Complete",
                "file_path": None,
                "result_count": 0,
                "doc_id": None,
                "tokens_charged": required_tokens,
                "tokens_remaining": deduct_result.get('tokens_remaining', 'N/A') # Get remaining from deduct func
            }

        # --- 2. Processing and Saving Results ---
        logger.info(f"[Task ID: {self.request.id}] Processing {len(all_results_html)} fetched items.")
        self.update_progress(0, 100, "Processing results...") # Reset progress for processing step

        make = payload.get('Make', 'Unknown')
        model = payload.get('Model', 'Unknown')
        model = clean_model_name(model)
        results_base_dir = "Results"
        folder_path = os.path.join(results_base_dir, f"{make}_{model}")
        os.makedirs(folder_path, exist_ok=True) # Ensure directory exists

        timestamp = format_time_ymd_hms()
        file_name = f"{payload.get('YearMin', '')}-{payload.get('YearMax', '')}_{payload.get('PriceMin', '')}-{payload.get('PriceMax', '')}_{timestamp}.csv"
        full_path = os.path.join(folder_path, file_name).replace("\\", "/")

        raw_exclusions = payload.get("Exclusions", [])
        transformed_exclusions = transform_strings(raw_exclusions)

        # Pass the task instance (self) to the processing function
        processed_results_dicts = process_links_and_update_cache(
            data=all_results_html,
            transformed_exclusions=transformed_exclusions,
            max_workers=1000, # Consider making this configurable
            task_instance=self # Pass task instance here
        )
        logger.info(f"[Task ID: {self.request.id}] Processing complete. Got {len(processed_results_dicts)} results.")
        self.update_progress(100, 100, "Processing complete.")

        # --- 3. Save to Local File ---
        if processed_results_dicts:
            logger.info(f"[Task ID: {self.request.id}] Saving {len(processed_results_dicts)} results to {full_path}")
            self.update_progress(0, 100, "Saving local file...")
            try:
                with open(full_path, mode="w", newline="", encoding="utf-8") as file:
                    writer = csv.DictWriter(file, fieldnames=CACHE_HEADERS)
                    writer.writeheader()
                    writer.writerows(processed_results_dicts)
                self.update_progress(100, 100, "Local file saved.")
            except Exception as e:
                 logger.error(f"[Task ID: {self.request.id}] Error writing timestamped CSV {full_path}: {e}", exc_info=True)
                 # Don't deduct tokens if saving failed critically
                 raise Exception(f"Failed to save results file: {e}") # Raise exception to mark task as failed
        else:
             logger.warning(f"[Task ID: {self.request.id}] No results obtained after processing links for file {full_path}")
             full_path = None # No file path if no results

        # --- 4. Save to Firebase ---
        doc_id = None
        if processed_results_dicts:
            logger.info(f"[Task ID: {self.request.id}] Saving results to Firebase for user {user_id}")
            self.update_progress(0, 100, "Saving to Firebase...")
            metadata = {
                'make': make,
                'model': model,
                'yearMin': payload.get('YearMin', ''),
                'yearMax': payload.get('YearMax', ''),
                'priceMin': payload.get('PriceMin', ''),
                'priceMax': payload.get('PriceMax', ''),
                'file_name': file_name,
                'timestamp': timestamp,
                'estimated_listings_scanned': initial_scrape_data.get('estimated_count', 0), # Use estimate from initial fetch
                'actual_results_found': len(processed_results_dicts),
                'tokens_charged': required_tokens, # Tokens charged based on estimate
                'custom_name': payload.get('custom_name')
            }
            firebase_result = save_results(user_id, processed_results_dicts, metadata)
            if firebase_result.get('success'):
                doc_id = firebase_result.get('doc_id')
                logger.info(f"[Task ID: {self.request.id}] Successfully saved results to Firebase (Doc ID: {doc_id})")
                self.update_progress(100, 100, "Saved to Firebase.")
            else:
                 logger.error(f"[Task ID: {self.request.id}] Failed to save results to Firebase for user {user_id}. Error: {firebase_result.get('error')}")
                 # Decide if this is fatal. For now, log error but continue to token deduction.
                 self.update_progress(100, 100, "Firebase save failed.") # Mark progress done, but log indicates error
        else:
            logger.info(f"[Task ID: {self.request.id}] Skipping Firebase save as there were no processed results.")


        # --- 5. Deduct Tokens ---
        logger.info(f"[Task ID: {self.request.id}] Deducting {required_tokens} tokens for user {user_id}")
        self.update_progress(0, 100, "Finalizing...")
        deduct_result = deduct_search_tokens(user_id, required_tokens)
        if not deduct_result.get('success'):
            # Log the error, but the task itself succeeded in scraping/saving.
            logger.error(f"[Task ID: {self.request.id}] Failed to deduct tokens for user {user_id} after successful task completion. Error: {deduct_result.get('error')}")
            # The 'tokens_remaining' will reflect the state *before* this failed deduction attempt in the final result.

        tokens_remaining_final = deduct_result.get('tokens_remaining', 'N/A') # Get remaining tokens from the result of the deduction function

        logger.info(f"[Task ID: {self.request.id}] Task completed successfully.")
        self.update_progress(100, 100, "Complete.")

        # --- 6. Return Final Result ---
        return {
            "status": "Complete",
            "file_path": full_path,
            "result_count": len(processed_results_dicts),
            "doc_id": doc_id,
            "tokens_charged": required_tokens,
            "tokens_remaining": tokens_remaining_final
        }

    except Exception as e:
        logger.error(f"[Task ID: {self.request.id}] Task failed: {e}", exc_info=True)
        self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': str(e)})
        # Do NOT deduct tokens if the task failed before the deduction step
        raise # Re-raise the exception so Celery marks the task as failed

# --- Optional: Add a route within tasks.py for status checking ---
# Alternatively, this route can be in api_results.py or app.py

from flask import Blueprint, jsonify as flask_jsonify
from celery.result import AsyncResult

tasks_bp = Blueprint('tasks_api', __name__, url_prefix='/api/tasks') # Separate prefix for task routes

@tasks_bp.route('/status/<task_id>')
def task_status(task_id):
    """Endpoint to check the status of a Celery task."""
    task_result = AsyncResult(task_id, app=celery_app)

    response_data = {
        'task_id': task_id,
        'state': task_result.state,
    }

    if task_result.state == 'PENDING':
        response_data['status'] = 'Task is pending or not found.'
    elif task_result.state == 'PROGRESS':
        response_data['progress'] = task_result.info.get('current', 0)
        response_data['total'] = task_result.info.get('total', 100)
        response_data['step'] = task_result.info.get('step', 'Processing...')
    elif task_result.state == 'SUCCESS':
        response_data['result'] = task_result.result # Contains the dict returned by the task
    elif task_result.state == 'FAILURE':
        response_data['error'] = str(task_result.info) # Celery stores exception info here
        # Optionally include traceback: response_data['traceback'] = task_result.traceback

    return flask_jsonify(response_data)
