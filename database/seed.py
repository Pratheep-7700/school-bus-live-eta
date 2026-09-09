"""
Database Seeding Script for School Bus Live ETA System.
Initializes SQLite schema and populates all tables with fictional demonstration data.
Can be executed standalone:
    python database/seed.py
"""
import os
import sys

# Ensure parent directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.database import init_db

if __name__ == '__main__':
    print("--------------------------------------------------")
    print("School Bus Live ETA: Seeding Database...")
    print("--------------------------------------------------")
    init_db(force=True)
    print("Database seeding completed successfully.")
