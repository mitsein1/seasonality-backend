from backend.celery_worker import tasks
from backend.data_fetch.download_all_mt5 import fetch_and_save

@tasks.task(name='backend.jobs.fetch_historical.fetch_and_save')
def fetch_and_save_task():
    """
    Celery task wrapper per scaricare dati storici da MT5.
    """
    fetch_and_save()
