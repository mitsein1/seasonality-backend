import os
from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue

# ── Load settings from environment ──────────────────────────────────────────────
DATABASE_URL   = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://seasonality_user:Silvio1989!@localhost:5432/seasonality"
)
BROKER_URL     = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
TIMEZONE       = os.getenv("TZ", "UTC")

# ── Create and configure Celery app ─────────────────────────────────────────────
# 'include' ensures tasks are registered even if modules are not auto-imported
app = Celery(
    "seasonality_tasks",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=[
        "backend.jobs.fetch_historical",
        "backend.jobs.compute_patterns",
        "backend.jobs.trading_tasks",
        "backend.jobs.update_pattern_aggregates",
    ],
)
# alias for decorators in task modules
tasks = app

# ── Define custom queues ─────────────────────────────────────────────────────────
app.conf.task_queues = (
    Queue('fetchers', Exchange('fetchers'), routing_key='fetchers'),
    Queue('computations', Exchange('computations'), routing_key='computations'),
)
app.conf.task_default_queue = 'fetchers'
app.conf.task_default_exchange = 'fetchers'
app.conf.task_default_routing_key = 'fetchers'

# ── Update core configuration ───────────────────────────────────────────────────
app.conf.update(
    database_url=DATABASE_URL,
    timezone=TIMEZONE,
    enable_utc=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)

# ── Auto-discover tasks in the jobs package ─────────────────────────────────────
app.autodiscover_tasks(["backend.jobs"])

# ── Periodic (beat) schedule ───────────────────────────────────────────────────
app.conf.beat_schedule = {
    # Live price updates every 10s
    "update-prices-every-10s": {
        "task": "backend.jobs.trading_tasks.update_prices",
        "schedule": 10.0,
        "options": {"queue": "fetchers"},
    },
    # Paper trading cycle every 10s
    "paper-trading-cycle-every-10s": {
        "task": "backend.jobs.trading_tasks.paper_trading_cycle",
        "schedule": 10.0,
        "options": {"queue": "computations"},
    },
    # Historical data fetch nightly at 02:00
    "fetch-historical-every-night": {
        "task": "backend.jobs.fetch_historical.fetch_and_save_task",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": "fetchers"},
    },
    # Weekly pattern computation
    "compute-patterns-weekly": {
        "task": "backend.jobs.compute_patterns.compute_patterns_task",
        "schedule": crontab(day_of_week="sun", hour=3, minute=0),
        "options": {"queue": "computations"},
    },
    # Aggregates for intraday, monthly, annual patterns
    "agg_intraday_every_night": {
        "task": "backend.jobs.update_pattern_aggregates.update_all_intraday",
        "schedule": crontab(hour=3, minute=0),
        "args": [
            ["EURUSD", "BTCUSD", "GOLD"],
            [1, 5, 10],
            "H1",
            [(0, 24)],
        ],
        "options": {"queue": "computations"},
    },
    "agg_monthly_every_night": {
        "task": "backend.jobs.update_pattern_aggregates.update_all_monthly",
        "schedule": crontab(hour=3, minute=30),
        "args": [
            ["EURUSD", "BTCUSD", "GOLD"],
            [1, 5, 10],
            [7, 14],
            [1, 5, 10],
        ],
        "options": {"queue": "computations"},
    },
    "agg_annual_every_night": {
        "task": "backend.jobs.update_pattern_aggregates.update_all_annual",
        "schedule": crontab(hour=4, minute=0),
        "args": [
            ["EURUSD", "BTCUSD", "GOLD"],
            [1, 5, 10, 20],
        ],
        "options": {"queue": "computations"},
    },
}

# ── Route specific tasks to appropriate queues ─────────────────────────────────
app.conf.task_routes = {
    "backend.jobs.fetch_historical.*": {"queue": "fetchers"},
    "backend.jobs.trading_tasks.update_prices": {"queue": "fetchers"},
    "backend.jobs.trading_tasks.paper_trading_cycle": {"queue": "computations"},
    "backend.jobs.compute_patterns.*": {"queue": "computations"},
    "backend.jobs.update_pattern_aggregates.*": {"queue": "computations"},
}

# ── Entrypoint: direct execution ────────────────────────────────────────────────
if __name__ == "__main__":
    app.start()
