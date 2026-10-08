
"""
Database Reset Script for College Lost & Found Portal
This script will reset the database to start fresh with the new schema.
"""

import sqlite3
import os

DATABASE = 'lost_found.db'

def reset_database():
    """Reset the database by deleting the old one and creating a new one."""
    print("🔄 Resetting database...")
    
    # Delete existing database if it exists
    if os.path.exists(DATABASE):
        os.remove(DATABASE)
        print(f"✅ Deleted existing database: {DATABASE}")
    
    # Create new database with updated schema
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL, -- 'lost' or 'found'
            item_name TEXT NOT NULL,
            description TEXT,
            location TEXT,
            student_name TEXT NOT NULL,
            registration_number TEXT NOT NULL,
            contact_number TEXT NOT NULL,
            contact_email TEXT NOT NULL,
            department TEXT,
            year_of_study TEXT,
            reported_at TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()
    
    print("✅ New database created with updated schema!")
    print("🎉 Database reset completed successfully!")

if __name__ == "__main__":
    reset_database()
