import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = "/var/lib/exam-firewall/analytics.db"

# ==========================
# Database Setup
# ==========================

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    # Device connection log
    c.execute('''
        CREATE TABLE IF NOT EXISTS device_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            ip TEXT NOT NULL,
            mac TEXT NOT NULL,
            hostname TEXT NOT NULL,
            state TEXT NOT NULL,
            blocked INTEGER NOT NULL DEFAULT 0
        )
    ''')

    # Exam/strict mode events
    c.execute('''
        CREATE TABLE IF NOT EXISTS mode_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event TEXT NOT NULL
        )
    ''')

    # Block events (individual device blocks)
    c.execute('''
        CREATE TABLE IF NOT EXISTS block_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            ip TEXT NOT NULL,
            hostname TEXT NOT NULL,
            action TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()


# ==========================
# Data Cleanup (keep 1 day)
# ==========================

def cleanup_old_data():
    conn = get_db()
    c = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    c.execute("DELETE FROM device_log WHERE timestamp < ?", (cutoff,))
    c.execute("DELETE FROM mode_events WHERE timestamp < ?", (cutoff,))
    c.execute("DELETE FROM block_events WHERE timestamp < ?", (cutoff,))
    conn.commit()
    conn.close()


# ==========================
# Log Functions
# ==========================

def log_devices(devices):
    """Log current connected devices - called every minute by cron"""
    init_db()
    cleanup_old_data()
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for d in devices:
        c.execute('''
            INSERT INTO device_log (timestamp, ip, mac, hostname, state, blocked)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (now, d['ip'], d['mac'], d['hostname'], d['state'], 1 if d['blocked'] else 0))

    conn.commit()
    conn.close()


def log_mode_event(event):
    """Log exam/strict mode changes"""
    init_db()
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute("INSERT INTO mode_events (timestamp, event) VALUES (?, ?)", (now, event))
    conn.commit()
    conn.close()


def log_block_event(ip, hostname, action):
    """Log individual device block/unblock"""
    init_db()
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('''
        INSERT INTO block_events (timestamp, ip, hostname, action)
        VALUES (?, ?, ?, ?)
    ''', (now, ip, hostname, action))
    conn.commit()
    conn.close()


# ==========================
# Query Functions
# ==========================

def get_device_summary():
    """Get unique devices seen today with first/last seen times"""
    init_db()
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT
            ip,
            mac,
            hostname,
            MIN(timestamp) as first_seen,
            MAX(timestamp) as last_seen,
            COUNT(*) as log_count,
            MAX(blocked) as was_blocked
        FROM device_log
        GROUP BY ip, mac
        ORDER BY first_seen DESC
    ''')
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_device_timeline(ip):
    """Get timeline for a specific device"""
    init_db()
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT timestamp, state, blocked
        FROM device_log
        WHERE ip = ?
        ORDER BY timestamp DESC
        LIMIT 100
    ''', (ip,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_mode_events():
    """Get all exam/strict mode events today"""
    init_db()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM mode_events ORDER BY timestamp DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_block_events():
    """Get all block/unblock events today"""
    init_db()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM block_events ORDER BY timestamp DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_peak_devices():
    """Get peak number of devices connected at any point today"""
    init_db()
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT timestamp, COUNT(*) as count
        FROM device_log
        GROUP BY timestamp
        ORDER BY count DESC
        LIMIT 1
    ''')
    row = c.fetchone()
    conn.close()
    return dict(row) if row else {'timestamp': 'N/A', 'count': 0}


def get_hourly_counts():
    """Get device counts per hour for chart"""
    init_db()
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT
            strftime('%H:00', timestamp) as hour,
            COUNT(DISTINCT ip) as unique_devices
        FROM device_log
        GROUP BY hour
        ORDER BY hour
    ''')
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]
