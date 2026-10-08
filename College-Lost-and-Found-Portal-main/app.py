from flask import Flask, request, jsonify, send_from_directory
import sqlite3
import os
from datetime import datetime

app = Flask(__name__, static_folder='.', static_url_path='')

# Database setup
DATABASE = 'lost_found.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # First, check if the table exists and what columns it has
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='items'")
    table_exists = cursor.fetchone()
    
    if table_exists:
        # Get existing columns
        cursor.execute("PRAGMA table_info(items)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Check if we need to migrate from old schema to new schema
        if 'name' in columns and 'item_name' not in columns:
            print("Migrating database schema...")
            # Add new columns
            cursor.execute("ALTER TABLE items ADD COLUMN item_name TEXT")
            cursor.execute("ALTER TABLE items ADD COLUMN student_name TEXT")
            cursor.execute("ALTER TABLE items ADD COLUMN registration_number TEXT")
            cursor.execute("ALTER TABLE items ADD COLUMN contact_number TEXT")
            cursor.execute("ALTER TABLE items ADD COLUMN department TEXT")
            cursor.execute("ALTER TABLE items ADD COLUMN year_of_study TEXT")
            
            # Copy data from old columns to new columns
            cursor.execute("UPDATE items SET item_name = name WHERE item_name IS NULL")
            cursor.execute("UPDATE items SET student_name = 'Unknown Student' WHERE student_name IS NULL")
            cursor.execute("UPDATE items SET registration_number = 'Not Provided' WHERE registration_number IS NULL")
            cursor.execute("UPDATE items SET contact_number = 'Not Provided' WHERE contact_number IS NULL")
            cursor.execute("UPDATE items SET department = 'Not Specified' WHERE department IS NULL")
            cursor.execute("UPDATE items SET year_of_study = 'Not Specified' WHERE year_of_study IS NULL")
            
            print("Database migration completed!")
    else:
        # Create new table with all columns
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

# Initialize the database when the app starts
with app.app_context():
    init_db()

# Serve static files (HTML, CSS, JS)
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)

# API to get all items
@app.route('/api/items', methods=['GET'])
def get_items():
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM items ORDER BY reported_at DESC').fetchall()
    conn.close()
    return jsonify([dict(item) for item in items])

# API to report a new item
@app.route('/api/items', methods=['POST'])
def add_item():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Invalid JSON'}), 400

    item_type = data.get('type')
    item_name = data.get('item_name')
    description = data.get('description')
    location = data.get('location')
    student_name = data.get('student_name')
    registration_number = data.get('registration_number')
    contact_number = data.get('contact_number')
    contact_email = data.get('contact_email')
    department = data.get('department')
    year_of_study = data.get('year_of_study')

    if not all([item_type, item_name, student_name, registration_number, contact_number, contact_email]):
        return jsonify({'message': 'Missing required fields: type, item_name, student_name, registration_number, contact_number, contact_email'}), 400

    reported_at = datetime.now().isoformat()

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO items (type, item_name, description, location, student_name, registration_number, contact_number, contact_email, department, year_of_study, reported_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (item_type, item_name, description, location, student_name, registration_number, contact_number, contact_email, department, year_of_study, reported_at)
        )
        conn.commit()
        return jsonify({'message': 'Item added successfully', 'id': cursor.lastrowid}), 201
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({'message': f'Database error: {e}'}), 500
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(debug=True) # debug=True enables auto-reloading and better error messages