import logging
import os
import time # Potentially needed if adding delays or timing info

from celery_config import celery_app
from AutoScraper import (
    fetch_autotrader_data,
    process_links_and_update_cache,
    CACHE_HEADERS # Needed? Maybe not if not writing local CSV
)
from AutoScraperUtil import transform_strings, format_time_ymd_hms, clean_model_name
from firebase_config import save_results, deduct_search_tokens

# Configure logger for tasks
logger = logging.getLogger("CeleryTasks")
# Basic configuration if running standalone, adjust as needed
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60) # bind=True gives access to self
def run_scrape_task(self, payload, user_id, required_tokens, initial_results_html, max_page):
    """
    Celery task to perform the full scrape, processing, and saving.
    """
    task_id = self.request.id
    logger.info(f"[Task ID: {task_id}] Starting scrape task for user '{user_id}'. Payload keys: {list(payload.keys())}")

    try:
        # 1. Perform full data fetch using initial data
        logger.info(f"[Task ID: {task_id}] Performing full fetch (max_page={max_page})...")
        if max_page > 1:
            all_results_html = fetch_autotrader_data(
                payload,
                start_page=1, # Start from page 1 since page 0 is initial_results_html
                initial_results_html=initial_results_html,
                max_page_override=max_page
            )
        else:
            # If max_page was 1 or less, the initial fetch got everything
            all_results_html = initial_results_html
            logger.info(f"[Task ID: {task_id}] Max page was {max_page}, using initial results directly.")

        if not all_results_html:
            # This case should ideally be caught by the API route if estimate was 0,
            # but handle defensively.
            logger.warning(f"[Task ID: {task_id}] Full fetch returned no results, though initial estimate suggested otherwise or max_page=1.")
            # Optionally update Firebase status here if you add a status field
            return {"status": "Complete", "message": "No results found after full fetch."}

        # 2. Get transformed exclusions
        raw_exclusions = payload.get("Exclusions", [])
        transformed_exclusions = transform_strings(raw_exclusions)

        # 3. Process links/cache (includes filtering)
        logger.info(f"[Task ID: {task_id}] Processing {len(all_results_html)} raw results (fetching details, caching, filtering)...")
        processed_results_dicts = process_links_and_update_cache(
            data=all_results_html,
            transformed_exclusions=transformed_exclusions
            # max_workers defaults to 100 in the function now
        )
        actual_results_count = len(processed_results_dicts)
        logger.info(f"[Task ID: {task_id}] Processing complete. Found {actual_results_count} results after filtering.")

        # 4. Prepare metadata (even if no results after filtering, we might still charge)
        make = payload.get('Make', 'Unknown')
        model = payload.get('Model', 'Unknown')
        model = clean_model_name(model) # Clean model name
        timestamp_str = format_time_ymd_hms() # Generate timestamp once

        metadata = {
            'make': make,
            'model': model,
            'yearMin': payload.get('YearMin', ''),
            'yearMax': payload.get('YearMax', ''),
            'priceMin': payload.get('PriceMin', ''),
            'priceMax': payload.get('PriceMax', ''),
            'file_name': f"{payload.get('YearMin', '')}-{payload.get('YearMax', '')}_{payload.get('PriceMin', '')}-{payload.get('PriceMax', '')}_{timestamp_str}.csv", # Keep consistent naming convention
            'timestamp': timestamp_str,
            # 'estimated_listings_scanned': estimated_count, # estimated_count not passed, maybe add later if needed
            'actual_results_found': actual_results_count,
            'tokens_charged': required_tokens, # Charge based on initial estimate
            'custom_name': payload.get('custom_name'), # Carry over custom name
            'status': 'Completed' # Add a status field
        }

        # 5. Attempt token deduction (based on initial estimate)
        # Do this *before* saving results, so we don't save if deduction fails? Or log and continue?
        # Let's log and continue for now, as the work was done.
        logger.info(f"[Task ID: {task_id}] Attempting to deduct {required_tokens} tokens for user '{user_id}'.")
        deduct_result = deduct_search_tokens(user_id, required_tokens)
        if not deduct_result.get('success'):
            logger.error(f"[Task ID: {task_id}] Failed to deduct tokens for user '{user_id}'. Error: {deduct_result.get('error')}. Proceeding with result save.")
            metadata['token_deduction_status'] = f"Failed: {deduct_result.get('error')}" # Add status to metadata
        else:
            logger.info(f"[Task ID: {task_id}] Successfully deducted {required_tokens} tokens for user '{user_id}'.")
            metadata['token_deduction_status'] = "Success"

        # 6. Save results to Firebase
        if actual_results_count > 0:
            logger.info(f"[Task ID: {task_id}] Saving {actual_results_count} results to Firebase for user '{user_id}'.")
            firebase_result = save_results(user_id, processed_results_dicts, metadata)
            if not firebase_result.get('success'):
                logger.error(f"[Task ID: {task_id}] Failed to save results to Firebase for user '{user_id}'. Error: {firebase_result.get('error')}")
                # If Firebase save fails, we might want the task to retry
                raise Exception(f"Firebase save failed: {firebase_result.get('error')}") # Celery will retry based on task settings
            else:
                doc_id = firebase_result.get('doc_id')
                logger.info(f"[Task ID: {task_id}] Successfully saved results to Firebase. Doc ID: {doc_id}")
                return {"status": "Complete", "doc_id": doc_id, "results_count": actual_results_count}
        else:
            # If no results after filtering, still save metadata document to indicate the search ran
            logger.info(f"[Task ID: {task_id}] No results after filtering, saving metadata-only document to Firebase for user '{user_id}'.")
            metadata['status'] = 'Completed - No Results After Filtering'
            firebase_result = save_results(user_id, [], metadata) # Save empty results list with metadata
            if not firebase_result.get('success'):
                 logger.error(f"[Task ID: {task_id}] Failed to save metadata-only results to Firebase for user '{user_id}'. Error: {firebase_result.get('error')}")
                 raise Exception(f"Firebase metadata-only save failed: {firebase_result.get('error')}")
            else:
                doc_id = firebase_result.get('doc_id')
                logger.info(f"[Task ID: {task_id}] Successfully saved metadata-only results to Firebase. Doc ID: {doc_id}")
                return {"status": "Complete", "doc_id": doc_id, "results_count": 0}

    except Exception as exc:
        logger.error(f"[Task ID: {task_id}] Error during scrape task for user '{user_id}': {exc}", exc_info=True)
        # Optionally update Firebase status to 'Failed' here
        # Re-raise the exception to trigger Celery retry mechanism
        raise self.retry(exc=exc)
