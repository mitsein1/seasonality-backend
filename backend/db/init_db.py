#!/usr/bin/env python3
import os
from sqlalchemy import create_engine
from backend.db.models import Base

def get_root_db_url():
    # Path assoluto alla root del progetto
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    DB_PATH = os.path.join(PROJECT_ROOT, 'data.db')
    return f"sqlite:///{DB_PATH}"

def init_db():
    url = get_root_db_url()
    engine = create_engine(url, echo=True, future=True)
    Base.metadata.create_all(engine)
    print(f"Tabelle create correttamente su {url}")

if __name__ == "__main__":
    init_db()
