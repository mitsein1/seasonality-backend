import os
from celery import Celery
from celery.schedules import crontab

# Load settings
database_url = os.getenv('DATABASE_URL', 'sqlite:///./data.db')
broker_url     = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# Create Celery app
tasks = Celery('seasonality_tasks', broker=broker_url, backend=result_backend)

# Auto-discover tasks in backend/jobs
tasks.autodiscover_tasks(['backend.jobs'])

# Periodic schedule: nightly fetch, weekly compute
tasks.conf.beat_schedule = {
    'fetch-historical-every-night': {
        'task': 'backend.jobs.fetch_historical.fetch_and_save',
        'schedule': crontab(hour=2, minute=0),    # ogni notte alle 02:00 UTC
    },
    'compute-patterns-weekly': {
        'task': 'backend.jobs.compute_patterns.compute_patterns',
        'schedule': crontab(day_of_week='sun', hour=3, minute=0),  # ogni domenica alle 03:00 UTC
    },
}
tasks.conf.timezone = os.getenv('TZ', 'UTC')

if __name__ == '__main__':
    tasks.start()
