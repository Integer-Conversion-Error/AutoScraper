from tasks import celery_app, scrape_and_process_task
import logging

# Configure basic logging for this script
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the arguments as a Python dictionary
task_kwargs = {
    "payload": {
        "Make": "Ford",
        "Model": "Bronco",
        "Address": "Kanata, ON",
        "Proximity": -1,
        "YearMin": None,
        "YearMax": None,
        "PriceMin": None,
        "PriceMax": None,
        "OdometerMin": None,
        "OdometerMax": None,
        "IsNew": True,
        "IsUsed": True,
        "WithPhotos": True,
        "Exclusions": [],
        "Inclusion": "",
        "Trim": None,
        "Color": None,
        "Drivetrain": None,
        "Transmission": None,
        "BodyType": None,
        "NumberOfDoors": None,
        "SeatingCapacity": None,
        "IsDamaged": False
    },
    "user_id": "vppslmbF9zZXLS5SAHLZu2HAj4c2",
    "required_tokens": 15.9,
    "initial_scrape_data": {
        "initial_results_html": [],
        "max_page": 106,
        "estimated_count": 1590
    }
}

if __name__ == "__main__":
    logger.info("Attempting to send task to Celery worker...")
    try:
        # Send the task using .delay() or .apply_async()
        # .delay() is a shortcut for .apply_async()
        async_result = scrape_and_process_task.delay(**task_kwargs)
        logger.info(f"Task sent successfully. Task ID: {async_result.id}")
    except Exception as e:
        logger.error(f"Failed to send task: {e}", exc_info=True)
