import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    conn = psycopg2.connect(
        os.environ.get('DATABASE_URL'),
        cursor_factory=RealDictCursor
    )
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Categories table (must be created before tasks)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            color TEXT DEFAULT '#6366f1'
        )
    ''')
    
    # Tasks table with category support
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            due_date TEXT,
            completed INTEGER DEFAULT 0,
            category_id INTEGER,
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Tags table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tags (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        )
    ''')
    
    # Task-Tag junction table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS task_tags (
            task_id INTEGER,
            tag_id INTEGER,
            PRIMARY KEY (task_id, tag_id),
            FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
        )
    ''')
    
    # Insert default categories if none exist
    cursor.execute('SELECT COUNT(*) as count FROM categories')
    if cursor.fetchone()['count'] == 0:
        default_categories = [
            ('Work', '#ef4444'),
            ('Personal', '#22c55e'),
            ('School', '#3b82f6'),
            ('Shopping', '#f59e0b'),
            ('Health', '#ec4899')
        ]
        cursor.executemany('INSERT INTO categories (name, color) VALUES (%s, %s)', default_categories)
    
    conn.commit()
    conn.close()

def dict_from_row(row):
    if row is None:
        return None
    return dict(row)
