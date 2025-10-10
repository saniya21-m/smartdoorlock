from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import datetime
import time
import socket
import requests

app = Flask(__name__)
CORS(app)

# Database configuration
DATABASE = 'smart_door_lock.db'
app.esp_commands = {}

def get_local_ip():
    """Get local IP address"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except:
        return "127.0.0.1"

def print_network_info():
    local_ip = get_local_ip()
    print("\n" + "="*50)
    print("🌐 NETWORK INFORMATION")
    print("="*50)
    print(f"   Local IP:    {local_ip}")
    print(f"   Server URL:  http://{local_ip}:5000")
    print("="*50)

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
        ('user3', 'user123', 'user'),
        ('user4', 'user123', 'user')
    ]
    
    for username, password, role in default_users:
        conn.execute(
            'INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)',
            (username, password, role)
        )
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully")

def log_access(username, status, action):
    try:
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO access_logs (username, status, action) VALUES (?, ?, ?)',
            (username, status, action)
        )
        conn.commit()
        conn.close()
        print(f"📝 Access logged: {username} - {status} - {action}")
    except Exception as e:
        print(f"❌ Error logging access: {e}")

def set_esp_command(command, relay_pin=None, duration=None):
    """Set command for ESP8266 with relay control details"""
    command_id = str(int(time.time()))
    
    if relay_pin is None:
        relay_pin = 1
    
    app.esp_commands[command_id] = {
        'command': command,
        'relay_pin': relay_pin,
        'duration': duration or 10000,
        'timestamp': time.time(),
        'executed': False
    }
    
    # Clean up old commands (older than 5 minutes)
    current_time = time.time()
    expired_commands = [cmd_id for cmd_id, cmd in app.esp_commands.items() 
                       if current_time - cmd['timestamp'] > 300]
    for cmd_id in expired_commands:
        del app.esp_commands[cmd_id]
    
    return command_id

# Test route
@app.route('/api/test', methods=['GET'])
def test():
    return jsonify({
        'success': True,
        'message': 'Backend is working!',
        'server_ip': get_local_ip(),
        'timestamp': datetime.datetime.now().isoformat()
    })

# Login route
@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data received'}), 400
            
        username = data.get('username')
        password = data.get('password')
        
        print(f"🔐 Login attempt: {username}")
        
        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ? AND password = ?',
            (username, password)
        ).fetchone()
        conn.close()
        
        if user:
            print(f"✅ Login successful: {username}")
            log_access(username, "success", "Login")
            return jsonify({
                'success': True,
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'role': user['role']
                }
            })
        else:
            print(f"❌ Login failed: {username}")
            log_access(username, "failed", "Login")
            return jsonify({
                'success': False,
                'error': 'Invalid username or password'
            }), 401
            
    except Exception as e:
        print(f"❌ Login error: {e}")
        return jsonify({'success': False, 'error': 'Server error'}), 500

# Unlock door route
@app.route('/api/unlock-door', methods=['POST'])
def unlock_door():
    try:
        data = request.get_json()
        username = data.get('username')
        is_admin = data.get('is_admin', False)
        
        print(f"🔓 Unlock door request from: {username} (admin: {is_admin})")
        
        # Set command for ESP8266 - activate relay for 10 seconds
        command_id = set_esp_command("activate", relay_pin=1, duration=10000)
        
        log_access(username, "success", "Unlocked")
        
        return jsonify({
            "success": True, 
            "message": "Unlock command sent to relay",
            "command_id": command_id,
            "relay_pin": 1,
            "duration": 10000
        })
        
    except Exception as e:
        print(f"❌ Unlock door error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# Lock door route
@app.route('/api/lock-door', methods=['POST'])
def lock_door():
    try:
        data = request.get_json()
        username = data.get('username')
        is_admin = data.get('is_admin', False)
        
        print(f"🔒 Lock door request from: {username} (admin: {is_admin})")
        
        # Set command for ESP8266 - deactivate relay
        command_id = set_esp_command("deactivate", relay_pin=1)
        
        log_access(username, "success", "Locked")
        
        return jsonify({
            "success": True, 
            "message": "Lock command sent to relay",
            "command_id": command_id,
            "relay_pin": 1
        })
        
    except Exception as e:
        print(f"❌ Lock door error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ESP8266 command polling endpoint
@app.route('/api/esp8266/command', methods=['GET'])
def get_esp_command():
    try:
        # Get the latest unexecuted command
        current_time = time.time()
        unexecuted_commands = [cmd_id for cmd_id, cmd in app.esp_commands.items() 
                             if not cmd['executed'] and current_time - cmd['timestamp'] < 60]
        
        if unexecuted_commands:
            command_id = unexecuted_commands[0]
            command_data = app.esp_commands[command_id]
            command_data['executed'] = True
            
            print(f"📡 Sending command to ESP8266: {command_data}")
            
            return jsonify({
                'has_command': True,
                'command_id': command_id,
                'command': command_data['command'],
                'relay_pin': command_data['relay_pin'],
                'duration': command_data.get('duration', 0)
            })
        
        return jsonify({'has_command': False, 'command': 'none'})
        
    except Exception as e:
        print(f"❌ ESP command error: {e}")
        return jsonify({'has_command': False, 'error': str(e)})

# ESP8266 status confirmation endpoint
@app.route('/api/esp8266/confirm', methods=['POST'])
def confirm_command():
    try:
        data = request.get_json()
        command_id = data.get('command_id')
        success = data.get('success', False)
        message = data.get('message', '')
        
        if command_id in app.esp_commands:
            if success:
                print(f"✅ ESP8266 executed command {command_id}: {message}")
                del app.esp_commands[command_id]
            else:
                print(f"❌ ESP8266 failed command {command_id}: {message}")
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"❌ ESP confirm error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ESP8266 debug endpoint
@app.route('/api/esp8266/debug', methods=['GET'])
def esp_debug():
    """Check ESP8266 connection status"""
    try:
        active_commands = []
        recent_commands = []
        
        current_time = time.time()
        for cmd_id, cmd in app.esp_commands.items():
            if not cmd['executed'] and current_time - cmd['timestamp'] < 60:
                active_commands.append(cmd_id)
            
            recent_commands.append({
                'command_id': cmd_id,
                'command': cmd['command'],
                'relay_pin': cmd['relay_pin'],
                'timestamp': cmd['timestamp'],
                'executed': cmd['executed']
            })
        
        recent_commands.sort(key=lambda x: x['timestamp'], reverse=True)
        recent_commands = recent_commands[:5]
        
        return jsonify({
            'success': True,
            'pending_commands': len(app.esp_commands),
            'active_commands': active_commands,
            'recent_commands': recent_commands,
            'total_commands_stored': len(app.esp_commands)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ESP8266 test command endpoint
@app.route('/api/esp8266/test-command', methods=['POST'])
def test_esp_command():
    """Send a test command to ESP8266"""
    try:
        command_id = set_esp_command("activate", relay_pin=1, duration=5000)
        
        return jsonify({
            'success': True,
            'message': 'Test command sent to ESP8266',
            'command_id': command_id,
            'command': 'activate relay for 5 seconds',
            'relay_pin': 1,
            'duration': 5000
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ESP8266 status endpoint
@app.route('/api/esp8266/status', methods=['POST'])
def esp_status():
    """Receive status updates from ESP8266"""
    try:
        data = request.get_json()
        status = data.get('status', 'unknown')
        message = data.get('message', '')
        ip_address = data.get('ip_address', '')
        
        print(f"📡 ESP8266 Status Update:")
        print(f"   Status: {status}")
        print(f"   Message: {message}")
        print(f"   IP Address: {ip_address}")
        
        return jsonify({'success': True, 'message': 'Status received'})
        
    except Exception as e:
        print(f"❌ ESP status error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Access logs route
@app.route('/api/access-logs', methods=['GET'])
def get_access_logs():
    try:
        conn = get_db_connection()
        logs = conn.execute('''
            SELECT * FROM access_logs 
            ORDER BY access_time DESC 
            LIMIT 20
        ''').fetchall()
        conn.close()
        
        logs_list = [{
            'id': log['id'],
            'username': log['username'],
            'access_time': log['access_time'],
            'status': log['status'],
            'action': log['action']
        } for log in logs]
        
        return jsonify({'success': True, 'logs': logs_list})
        
    except Exception as e:
        return jsonify({'success': False, 'error': 'Server error','exception':str(e)}), 500

if __name__ == '_main_':
    init_db()
    print_network_info()
    
    print("\n🚀 Starting Smart Door Lock Server on port 5000...")
    print("📡 Available endpoints:")
    print("   GET  /api/test")
    print("   GET  /api/esp8266/debug")
    print("   GET  /api/esp8266/command")
    print("   POST /api/esp8266/test-command")
    print("   POST /api/esp8266/confirm")
    print("   POST /api/esp8266/status")
    print("   POST /api/login")
    print("   POST /api/unlock-door")
    print("   POST /api/lock-door")
    print("   GET  /api/access-logs")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
import socket
import requests

app = Flask(__name__)
CORS(app)

# Database configuration
DATABASE = 'smart_door_lock.db'
app.esp_commands = {}

def get_local_ip():
    """Get local IP address"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except:
        return "127.0.0.1"

def print_network_info():
    local_ip = get_local_ip()
    print("\n" + "="*50)
    print("🌐 NETWORK INFORMATION")
    print("="*50)
    print(f"   Local IP:    {local_ip}")
    print(f"   Server URL:  http://{local_ip}:5000")
    print("="*50)

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
        ('user3', 'user123', 'user'),
        ('user4', 'user123', 'user')
    ]
    
    for username, password, role in default_users:
        conn.execute(
            'INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)',
            (username, password, role)
        )
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully")

def log_access(username, status, action):
    try:
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO access_logs (username, status, action) VALUES (?, ?, ?)',
            (username, status, action)
        )
        conn.commit()
        conn.close()
        print(f"📝 Access logged: {username} - {status} - {action}")
    except Exception as e:
        print(f"❌ Error logging access: {e}")

def set_esp_command(command, relay_pin=None, duration=None):
    """Set command for ESP8266 with relay control details"""
    command_id = str(int(time.time()))
    
    if relay_pin is None:
        relay_pin = 1
    
    app.esp_commands[command_id] = {
        'command': command,
        'relay_pin': relay_pin,
        'duration': duration or 10000,
        'timestamp': time.time(),
        'executed': False
    }
    
    # Clean up old commands (older than 5 minutes)
    current_time = time.time()
    expired_commands = [cmd_id for cmd_id, cmd in app.esp_commands.items() 
                       if current_time - cmd['timestamp'] > 300]
    for cmd_id in expired_commands:
        del app.esp_commands[cmd_id]
    
    return command_id

# Test route
@app.route('/api/test', methods=['GET'])
def test():
    return jsonify({
        'success': True,
        'message': 'Backend is working!',
        'server_ip': get_local_ip(),
        'timestamp': datetime.datetime.now().isoformat()
    })

# Login route
@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data received'}), 400
            
        username = data.get('username')
        password = data.get('password')
        
        print(f"🔐 Login attempt: {username}")
        
        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ? AND password = ?',
            (username, password)
        ).fetchone()
        conn.close()
        
        if user:
            print(f"✅ Login successful: {username}")
            log_access(username, "success", "Login")
            return jsonify({
                'success': True,
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'role': user['role']
                }
            })
        else:
            print(f"❌ Login failed: {username}")
            log_access(username, "failed", "Login")
            return jsonify({
                'success': False,
                'error': 'Invalid username or password'
            }), 401
            
    except Exception as e:
        print(f"❌ Login error: {e}")
        return jsonify({'success': False, 'error': 'Server error'}), 500

# Unlock door route
@app.route('/api/unlock-door', methods=['POST'])
def unlock_door():
    try:
        data = request.get_json()
        username = data.get('username')
        is_admin = data.get('is_admin', False)
        
        print(f"🔓 Unlock door request from: {username} (admin: {is_admin})")
        
        # Set command for ESP8266 - activate relay for 10 seconds
        command_id = set_esp_command("activate", relay_pin=1, duration=10000)
        
        log_access(username, "success", "Unlocked")
        
        return jsonify({
            "success": True, 
            "message": "Unlock command sent to relay",
            "command_id": command_id,
            "relay_pin": 1,
            "duration": 10000
        })
        
    except Exception as e:
        print(f"❌ Unlock door error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# Lock door route
@app.route('/api/lock-door', methods=['POST'])
def lock_door():
    try:
        data = request.get_json()
        username = data.get('username')
        is_admin = data.get('is_admin', False)
        
        print(f"🔒 Lock door request from: {username} (admin: {is_admin})")
        
        # Set command for ESP8266 - deactivate relay
        command_id = set_esp_command("deactivate", relay_pin=1)
        
        log_access(username, "success", "Locked")
        
        return jsonify({
            "success": True, 
            "message": "Lock command sent to relay",
            "command_id": command_id,
            "relay_pin": 1
        })
        
    except Exception as e:
        print(f"❌ Lock door error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ESP8266 command polling endpoint
@app.route('/api/esp8266/command', methods=['GET'])
def get_esp_command():
    try:
        # Get the latest unexecuted command
        current_time = time.time()
        unexecuted_commands = [cmd_id for cmd_id, cmd in app.esp_commands.items() 
                             if not cmd['executed'] and current_time - cmd['timestamp'] < 60]
        
        if unexecuted_commands:
            command_id = unexecuted_commands[0]
            command_data = app.esp_commands[command_id]
            command_data['executed'] = True
            
            print(f"📡 Sending command to ESP8266: {command_data}")
            
            return jsonify({
                'has_command': True,
                'command_id': command_id,
                'command': command_data['command'],
                'relay_pin': command_data['relay_pin'],
                'duration': command_data.get('duration', 0)
            })
        
        return jsonify({'has_command': False, 'command': 'none'})
        
    except Exception as e:
        print(f"❌ ESP command error: {e}")
        return jsonify({'has_command': False, 'error': str(e)})

# ESP8266 status confirmation endpoint
@app.route('/api/esp8266/confirm', methods=['POST'])
def confirm_command():
    try:
        data = request.get_json()
        command_id = data.get('command_id')
        success = data.get('success', False)
        message = data.get('message', '')
        
        if command_id in app.esp_commands:
            if success:
                print(f"✅ ESP8266 executed command {command_id}: {message}")
                del app.esp_commands[command_id]
            else:
                print(f"❌ ESP8266 failed command {command_id}: {message}")
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"❌ ESP confirm error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ESP8266 debug endpoint
@app.route('/api/esp8266/debug', methods=['GET'])
def esp_debug():
    """Check ESP8266 connection status"""
    try:
        active_commands = []
        recent_commands = []
        
        current_time = time.time()
        for cmd_id, cmd in app.esp_commands.items():
            if not cmd['executed'] and current_time - cmd['timestamp'] < 60:
                active_commands.append(cmd_id)
            
            recent_commands.append({
                'command_id': cmd_id,
                'command': cmd['command'],
                'relay_pin': cmd['relay_pin'],
                'timestamp': cmd['timestamp'],
                'executed': cmd['executed']
            })
        
        recent_commands.sort(key=lambda x: x['timestamp'], reverse=True)
        recent_commands = recent_commands[:5]
        
        return jsonify({
            'success': True,
            'pending_commands': len(app.esp_commands),
            'active_commands': active_commands,
            'recent_commands': recent_commands,
            'total_commands_stored': len(app.esp_commands)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ESP8266 test command endpoint
@app.route('/api/esp8266/test-command', methods=['POST'])
def test_esp_command():
    """Send a test command to ESP8266"""
    try:
        command_id = set_esp_command("activate", relay_pin=1, duration=5000)
        
        return jsonify({
            'success': True,
            'message': 'Test command sent to ESP8266',
            'command_id': command_id,
            'command': 'activate relay for 5 seconds',
            'relay_pin': 1,
            'duration': 5000
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ESP8266 status endpoint
@app.route('/api/esp8266/status', methods=['POST'])
def esp_status():
    """Receive status updates from ESP8266"""
    try:
        data = request.get_json()
        status = data.get('status', 'unknown')
        message = data.get('message', '')
        ip_address = data.get('ip_address', '')
        
        print(f"📡 ESP8266 Status Update:")
        print(f"   Status: {status}")
        print(f"   Message: {message}")
        print(f"   IP Address: {ip_address}")
        
        return jsonify({'success': True, 'message': 'Status received'})
        
    except Exception as e:
        print(f"❌ ESP status error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Access logs route
@app.route('/api/access-logs', methods=['GET'])
def get_access_logs():
    try:
        conn = get_db_connection()
        logs = conn.execute('''
            SELECT * FROM access_logs 
            ORDER BY access_time DESC 
            LIMIT 20
        ''').fetchall()
        conn.close()
        
        logs_list = [{
            'id': log['id'],
            'username': log['username'],
            'access_time': log['access_time'],
            'status': log['status'],
            'action': log['action']
        } for log in logs]
        
        return jsonify({'success': True, 'logs': logs_list})
        
    except Exception as e:
        return jsonify({'success': False, 'error': 'Server error','exception':str(e)}), 500

if __name__ == '_main_':
    init_db()
    print_network_info()
    
    print("\n🚀 Starting Smart Door Lock Server on port 5000...")
    print("📡 Available endpoints:")
    print("   GET  /api/test")
    print("   GET  /api/esp8266/debug")
    print("   GET  /api/esp8266/command")
    print("   POST /api/esp8266/test-command")
    print("   POST /api/esp8266/confirm")
    print("   POST /api/esp8266/status")
    print("   POST /api/login")
    print("   POST /api/unlock-door")
    print("   POST /api/lock-door")
    print("   GET  /api/access-logs")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
