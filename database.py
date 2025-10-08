import sqlite3

def init_database():
    conn = sqlite3.connect('smart_door_lock.db')
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create access logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS access_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            access_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL,
            photo_url TEXT
        )
    ''')
    
    # Insert default data
    users = [
        ('admin', 'admin123', 'admin'),
        ('user1', 'user123', 'user'),
        ('user2', 'user123', 'user'),
        ('user3', 'user123', 'user'),
        ('user4', 'user123', 'user')
    ]
    
    cursor.executemany(
        'INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)',
        users
    )
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

if __name__ == '__main__':
    init_database()