from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3, datetime, time, socket, os

app = Flask(__name__)
CORS(app)

# Database config
DATABASE = 'smart_door_lock.db'
app.esp_commands = {}

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def home():
    return "✅ Smart Door Lock Flask API is running successfully on Render!"

@app.route('/api/test', methods=['GET'])
def test():
    return jsonify({
        "success": True,
        "message": "Backend is working on Render!",
        "timestamp": datetime.datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))  # Render sets PORT dynamically
    app.run(host='0.0.0.0', port=port)
