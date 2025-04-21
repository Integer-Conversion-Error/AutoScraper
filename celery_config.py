from celery import Celery
import os

# Default Redis URL (adjust if your Redis server is different)
# Using environment variable for flexibility is good practice, but defaulting for now
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# Initialize Celery
# The first argument is the name of the current module, important for Celery internals.
# The 'broker' and 'backend' arguments specify where Celery sends/stores messages and results.
celery_app = Celery(
    'AutoScraperTasks', # Name of the Celery application (can be anything descriptive)
    broker=REDIS_URL,
    backend=REDIS_URL, # Using Redis as the result backend too
    include=['tasks'] # List of modules to import when the worker starts (points to tasks.py)
)

# Optional Celery configuration settings
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],  # Ensure tasks use JSON
    result_serializer='json',
    timezone='America/Toronto', # Match your application's timezone if needed
    enable_utc=True, # Recommended for timezone consistency
    # Add other configurations as needed, e.g., task time limits, rate limits
    # task_soft_time_limit=300, # Example: 5 minutes soft time limit
    # task_time_limit=360,      # Example: 6 minutes hard time limit
)

if __name__ == '__main__':
    # This allows running the worker directly using 'python celery_config.py worker ...'
    # although 'celery -A celery_config.celery_app worker ...' is more common.
    celery_app.start()
