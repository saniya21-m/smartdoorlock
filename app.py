from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3, datetime, time, socket, os

app = Flask(__name__)
CORS(app)

# =============================
# DATABASE CONFIGURATION
# =============================
DATABASE = 'smart_door_lock.db'
app.esp_commands = {}

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS access_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            access_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL,
            action TEXT NOT NULL
        )
    ''')
    default_users = [
        ('admin', 'admin123', 'admin'),
        ('Himani', 'Himani123', 'user'),
        ('user2', 'user123', 'user'),
        ('user3', 'user123', 'user')
    ]
    for username, password, role in default_users:
        conn.execute('INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)',
                     (username, password, role))
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully")

def log_access(username, status, action):
    conn = get_db_connection()
    conn.execute('INSERT INTO access_logs (username, status, action) VALUES (?, ?, ?)',
                 (username, status, action))
    conn.commit()
    conn.close()

# =============================
# ROUTES
# =============================

@app.route('/')
def home():
    return "✅ Smart Door Lock API is running on Render!"

# 🔹 Test API
@app.route('/api/test', methods=['GET'])
def test():
    return jsonify({
        "success": True,
        "message": "Smart Door Lock backend running on Render!",
        "timestamp": datetime.datetime.now().isoformat()
    })

# 🔹 Login API
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                        (username, password)).fetchone()
    conn.close()

    if user:
        log_access(username, "success", "Login")
        return jsonify({
            "success": True,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "role": user["role"]
            }
        })
    else:
        log_access(username, "failed", "Login")
        return jsonify({"success": False, "error": "Invalid username or password"}), 401

# 🔹 Unlock Door
@app.route('/api/unlock-door', methods=['POST'])
def unlock_door():
    data = request.get_json()
    username = data.get('username')
    log_access(username, "success", "Unlocked")
    app.esp_commands['last'] = {"command": "activate", "timestamp": time.time()}
    return jsonify({"success": True, "message": "Door unlocked"})

# 🔹 Lock Door
@app.route('/api/lock-door', methods=['POST'])
def lock_door():
    data = request.get_json()
    username = data.get('username')
    log_access(username, "success", "Locked")
    app.esp_commands['last'] = {"command": "deactivate", "timestamp": time.time()}
    return jsonify({"success": True, "message": "Door locked"})

# 🔹 ESP Command Polling
@app.route('/api/esp8266/command', methods=['GET'])
def esp_command():
    cmd = app.esp_commands.get('last', None)
    if cmd and (time.time() - cmd['timestamp'] < 10):
        return jsonify({"has_command": True, "command": cmd["command"]})
    return jsonify({"has_command": False, "command": "none"})

# 🔹 Access Logs
@app.route('/api/access-logs', methods=['GET'])
def access_logs():
    conn = get_db_connection()
    logs = conn.execute('SELECT * FROM access_logs ORDER BY access_time DESC LIMIT 20').fetchall()
    conn.close()
    return jsonify({
        "success": True,
        "logs": [
            {
                "id": log["id"],
                "username": log["username"],
                "access_time": log["access_time"],
                "status": log["status"],
                "action": log["action"]
            } for log in logs
        ]
    })

# =============================
# MAIN APP RUNNER
# =============================
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 10000))  # Render assigns dynamic port
    app.run(host='0.0.0.0', port=port)
