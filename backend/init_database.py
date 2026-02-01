#!/usr/bin/env python3
"""
(Re)create all database tables in plottery.db.
Run from the backend directory: python init_database.py

Use this if you see "no such table: documents" (e.g. after deleting plottery.db
or using an empty database file).
"""
import os
import sys

# Ensure we run from backend directory so plottery.db is created here
backend_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(backend_dir)
sys.path.insert(0, backend_dir)

from app.database import engine, init_db

if __name__ == "__main__":
    init_db()
    print("Database tables created successfully in plottery.db")
    print("Restart the backend if it is already running.")
