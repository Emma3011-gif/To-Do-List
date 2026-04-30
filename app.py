from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from database import get_db_connection, init_db, dict_from_row
from datetime import datetime
import os
import hashlib

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Lazy database initialization
_db_initialized = False

def ensure_db_initialized():
    global _db_initialized
    if not _db_initialized:
        try:
            init_db()
            _db_initialized = True
        except Exception as e:
            print(f"Database initialization failed: {e}")

@app.before_request
def initialize_db_on_first_request():
    ensure_db_initialized()

def task_to_dict(task_row):
    return {
        'id': task_row['id'],
        'title': task_row['title'],
        'description': task_row['description'],
        'due_date': task_row['due_date'],
        'completed': bool(task_row['completed']),
        'created_at': task_row['created_at'],
        'updated_at': task_row['updated_at']
    }

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@app.route('/health')
def health():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        conn.close()
        return jsonify({'status': 'healthy', 'database': 'connected'}), 200
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

@app.route('/')
def index():
    if 'user_id' not in session:
        return render_template('login.html')
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.form
        email = data.get('email', '').strip()
        password = data.get('password', '')
        confirm_password = data.get('confirm_password', '')
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        
        if not email or not password:
            return render_template('login.html', error='Email and password required')
        
        if password != confirm_password:
            return render_template('login.html', error='Passwords do not match')
        
        if len(password) < 6:
            return render_template('login.html', error='Password must be at least 6 characters')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO users (email, password, first_name, last_name) VALUES (%s, %s, %s, %s) RETURNING id',
                (email, hash_password(password), first_name, last_name)
            )
            result = cursor.fetchone()
            conn.commit()
            user_id = result['id']
            session['user_id'] = user_id
            session['email'] = email
            session['first_name'] = first_name
            return redirect(url_for('index'))
        except Exception as e:
            conn.close()
            if 'unique' in str(e).lower():
                return render_template('login.html', error='Email already registered')
            return render_template('login.html', error=str(e))
    
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.form
    email = data.get('email', '').strip()
    password = data.get('password', '')
    
    if not email or not password:
        return render_template('login.html', error='Email and password required')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE email=%s', (email,))
    row = cursor.fetchone()
    conn.close()
    
    if not row or row['password'] != hash_password(password):
        return render_template('login.html', error='Invalid email or password')
    
    session['user_id'] = row['id']
    session['email'] = row['email']
    session['first_name'] = row['first_name'] or ''
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('register'))

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tasks WHERE user_id=%s ORDER BY created_at DESC', (session['user_id'],))
    tasks = [task_to_dict(dict_from_row(row)) for row in cursor.fetchall()]
    conn.close()
    return jsonify(tasks)

@app.route('/api/tasks', methods=['POST'])
def create_task():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    title = data.get('title', '').strip()
    
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO tasks (title, description, due_date, category_id, user_id) VALUES (%s, %s, %s, %s, %s) RETURNING id',
        (title, data.get('description'), data.get('due_date'), data.get('category_id'), session['user_id'])
    )
    result = cursor.fetchone()
    task_id = result['id']
    conn.commit()
    conn.close()
    
    task = get_task_by_id(task_id)
    return jsonify(task), 201

@app.route('/api/tasks/<int:task_id>', methods=['GET'])
def get_task(task_id):
    task = get_task_by_id(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify(task)

@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE tasks SET title=%s, description=%s, due_date=%s, category_id=%s, completed=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s',
        (data.get('title'), data.get('description'), data.get('due_date'), 
         data.get('category_id'), data.get('completed', 0), task_id)
    )
    
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({'error': 'Task not found'}), 404
    
    conn.commit()
    conn.close()
    
    task = get_task_by_id(task_id)
    return jsonify(task)

@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM tasks WHERE id=%s', (task_id,))
    
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({'error': 'Task not found'}), 404
    
    conn.commit()
    conn.close()
    return jsonify({'message': 'Task deleted'})

@app.route('/api/tasks/<int:task_id>/toggle', methods=['PATCH'])
def toggle_task(task_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE tasks SET completed = 1 - completed, updated_at=CURRENT_TIMESTAMP WHERE id=%s', (task_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/categories', methods=['GET'])
def get_categories():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM categories ORDER BY name')
    categories = [dict_from_row(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(categories)

@app.route('/api/stats', methods=['GET'])
def get_stats():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) as total FROM tasks WHERE user_id=%s', (session['user_id'],))
    total = cursor.fetchone()['total']
    cursor.execute('SELECT COUNT(*) as completed FROM tasks WHERE completed=1 AND user_id=%s', (session['user_id'],))
    completed = cursor.fetchone()['completed']
    conn.close()
    return jsonify({
        'total': total,
        'completed': completed,
        'active': total - completed
    })

@app.route('/api/profile', methods=['GET'])
def get_profile():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, first_name, last_name, email FROM users WHERE id=%s', (session['user_id'],))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({
        'id': row['id'],
        'first_name': row['first_name'],
        'last_name': row['last_name'],
        'email': row['email']
    })

def get_task_by_id(task_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tasks WHERE id=%s', (task_id,))
    row = cursor.fetchone()
    conn.close()
    return task_to_dict(dict_from_row(row)) if row else None

if __name__ == '__main__':
    app.secret_key = 'dev-secret-key-change-in-production'
    app.run(host='0.0.0.0', port=5000, debug=False)
