#!/usr/bin/env python3
# TODO: inizializza il database
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.db.models import Base

def get_database_url():
    # Legge da variabile ENV o config file
    return os.getenv("DATABASE_URL", "sqlite:///./data.db")

def init_db():
    url = get_database_url()
    engine = create_engine(url, echo=True, future=True)
    Base.metadata.create_all(engine)
    print(f"Tabelle create correttamente su {url}")

if __name__ == "__main__":
    init_db()
