import sqlite3
import os
import re
from datetime import datetime, timedelta

DB_PATH = "/var/lib/exam-firewall/analytics.db"
DNS_LOG_PATH = "/var/log/dnsmasq.log"

# ==========================
# Database Setup
# ==========================

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_dns_table():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS dns_block_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            ip TEXT NOT NULL,
            hostname TEXT NOT NULL,
            domain TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


def cleanup_old_dns_data():
    """Delete entries older than 1 day"""
    conn = get_db()
    c = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    c.execute("DELETE FROM dns_block_log WHERE timestamp < ?", (cutoff,))
    conn.commit()
    conn.close()


def cleanup_per_device(max_entries=100):
    """Keep only last 100 blocked entries per device"""
    conn = get_db()
    c = conn.cursor()

    # Get all unique IPs
    c.execute("SELECT DISTINCT ip FROM dns_block_log")
    ips = [row['ip'] for row in c.fetchall()]

    for ip in ips:
        # Delete oldest entries keeping only last max_entries
        c.execute('''
            DELETE FROM dns_block_log
            WHERE ip = ? AND id NOT IN (
                SELECT id FROM dns_block_log
                WHERE ip = ?
                ORDER BY timestamp DESC
                LIMIT ?
            )
        ''', (ip, ip, max_entries))

    conn.commit()
    conn.close()


# ==========================
# DHCP Hostname Lookup
# ==========================

def get_hostnames():
    hostnames = {}
    try:
        with open("/var/lib/dhcp/dhcpd.leases", "r") as f:
            content = f.read()
        blocks = content.split("lease ")
        for block in blocks:
            if "hardware ethernet" not in block:
                continue
            lines = block.splitlines()
            ip = lines[0].strip().strip("{").strip()
            hostname = ""
            for line in lines:
                if "client-hostname" in line:
                    hostname = line.split()[-1].replace(";", "").replace('"', "")
            if ip and hostname:
                hostnames[ip] = hostname
    except:
        pass
    return hostnames


# ==========================
# DNS Log Parser
# ==========================

def parse_dns_log():
    """
    Parse dnsmasq log and extract blocked domain attempts.
    A blocked domain is one that resolves to 0.0.0.0.
    Keeps only last 100 blocked entries per device.
    """
    init_dns_table()
    cleanup_old_dns_data()
    cleanup_per_device(100)

    if not os.path.exists(DNS_LOG_PATH):
        return 0

    hostnames = get_hostnames()
    conn = get_db()
    c = conn.cursor()

    # Get last parsed position to avoid re-parsing
    c.execute('''
        CREATE TABLE IF NOT EXISTS dns_parser_state (
            id INTEGER PRIMARY KEY,
            last_position INTEGER DEFAULT 0
        )
    ''')

    c.execute("SELECT last_position FROM dns_parser_state WHERE id = 1")
    row = c.fetchone()
    last_position = row['last_position'] if row else 0

    blocked_count = 0
    pending_queries = {}  # domain -> (timestamp, ip)

    try:
        with open(DNS_LOG_PATH, 'r') as f:
            f.seek(last_position)

            for line in f:
                # Parse query lines: "query[A] domain from IP"
                query_match = re.search(
                    r'(\w+\s+\d+\s+\d+:\d+:\d+).*query\[A\]\s+(\S+)\s+from\s+(192\.168\.50\.\d+)',
                    line
                )
                if query_match:
                    time_str = query_match.group(1)
                    domain = query_match.group(2)
                    ip = query_match.group(3)
                    pending_queries[domain] = (time_str, ip)

                # Parse reply lines: "reply domain is 0.0.0.0"
                reply_match = re.search(
                    r'reply\s+(\S+)\s+is\s+0\.0\.0\.0',
                    line
                )
                if reply_match:
                    domain = reply_match.group(1)
                    if domain in pending_queries:
                        time_str, ip = pending_queries.pop(domain)
                        hostname = hostnames.get(ip, "Unknown")

                        # Convert log time to DB timestamp
                        try:
                            now = datetime.now()
                            log_time = datetime.strptime(
                                f"{now.year} {time_str}",
                                "%Y %b %d %H:%M:%S"
                            )
                            timestamp = log_time.strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                        # Save to database
                        c.execute('''
                            INSERT INTO dns_block_log (timestamp, ip, hostname, domain)
                            VALUES (?, ?, ?, ?)
                        ''', (timestamp, ip, hostname, domain))
                        blocked_count += 1

            # Save current file position
            new_position = f.tell()

        # Update parser state
        if row:
            c.execute(
                "UPDATE dns_parser_state SET last_position = ? WHERE id = 1",
                (new_position,)
            )
        else:
            c.execute(
                "INSERT INTO dns_parser_state (id, last_position) VALUES (1, ?)",
                (new_position,)
            )

    except Exception as e:
        print(f"DNS parser error: {e}")

    conn.commit()
    conn.close()
    return blocked_count


# ==========================
# Query Functions
# ==========================

def get_blocked_domains():
    """Get all blocked domain attempts today"""
    init_dns_table()
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT * FROM dns_block_log
        ORDER BY timestamp DESC
        LIMIT 200
    ''')
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_blocked_by_device():
    """Get blocked attempt count per device"""
    init_dns_table()
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT
            ip,
            hostname,
            COUNT(*) as attempt_count,
            MAX(timestamp) as last_attempt
        FROM dns_block_log
        GROUP BY ip
        ORDER BY attempt_count DESC
    ''')
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_top_blocked_domains():
    """Get most attempted blocked domains"""
    init_dns_table()
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT
            domain,
            COUNT(*) as attempt_count,
            COUNT(DISTINCT ip) as unique_devices
        FROM dns_block_log
        GROUP BY domain
        ORDER BY attempt_count DESC
        LIMIT 10
    ''')
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_total_blocked_today():
    """Get total blocked attempts today"""
    init_dns_table()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as total FROM dns_block_log")
    row = c.fetchone()
    conn.close()
    return row['total'] if row else 0
