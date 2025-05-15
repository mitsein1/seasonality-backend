from backend.celery_worker import tasks
from backend.patterns.calc_patterns import compute_patterns

@tasks.task(name='backend.jobs.compute_patterns.compute_patterns')
def compute_patterns_task():
    """
    Celery task wrapper per il calcolo dei pattern e delle statistiche.
    """
    compute_patterns()
