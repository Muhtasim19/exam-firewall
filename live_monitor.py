import re
import os
from datetime import datetime, timedelta

DNS_LOG_PATH = "/var/log/dnsmasq.log"

# ==========================
# System domains to filter out
# ==========================
SYSTEM_DOMAINS = [
    "pool.ntp.org",
    "windowsupdate.com",
    "microsoft.com",
    "msftconnecttest.com",
    "msftncsi.com",
    "cpsd.us",
    "msdcs",
    "googleapis.com",
    "gstatic.com",
    "clients6.google.com",
    "icloud.com",
    "apple.com",
    "akamai",
    "akadns",
    "cloudfront.net",
    "amazonaws.com",
    "digicert.com",
    "ocsp",
    "ctldl",
    "wpad",
    "local",
    "arpa",
    "in-addr",
    "msedge.net",
    "bing.com",
    "live.com",
    "office.com",
    "office365.com",
    "skype.com",
    "teams.microsoft.com",
    "avast.com",
    "norton.com",
    "sophos",
]

def is_system_domain(domain):
    """Check if domain is system/background traffic"""
    domain_lower = domain.lower()
    for system in SYSTEM_DOMAINS:
        if system in domain_lower:
            return True
    return False


def get_blocked_domains_set():
    """Get set of blocked domains from dnsmasq conf"""
    blocked = set()
    block_file = "/etc/dnsmasq.d/exam-block.conf"
    if os.path.exists(block_file):
        with open(block_file, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("address=/"):
                    # address=/chatgpt.com/0.0.0.0 → chatgpt.com
                    parts = line.split("/")
                    if len(parts) >= 2:
                        blocked.add(parts[1])
    return blocked


def parse_live_activity(ip, minutes=10):
    """
    Get recent DNS activity for a specific device
    Returns list of {time, domain, blocked, query_type}
    """
    if not os.path.exists(DNS_LOG_PATH):
        return []

    blocked_domains = get_blocked_domains_set()
    cutoff = datetime.now() - timedelta(minutes=minutes)
    results = []
    seen_domains = set()

    try:
        # Read last portion of log file for speed
        with open(DNS_LOG_PATH, "r") as f:
            # Seek to last 2MB for performance
            f.seek(0, 2)
            file_size = f.tell()
            seek_pos = max(0, file_size - 2 * 1024 * 1024)
            f.seek(seek_pos)
            lines = f.readlines()

        for line in reversed(lines):
            # Only process query lines for this IP
            if f"from {ip}" not in line:
                continue

            # Only process A record queries (actual browsing)
            if "query[A]" not in line and "query[HTTPS]" not in line:
                continue

            # Parse the line
            match = re.search(
                r'(\w+\s+\d+\s+\d+:\d+:\d+).*query\[(?:A|HTTPS)\]\s+(\S+)\s+from',
                line
            )
            if not match:
                continue

            time_str = match.group(1)
            domain = match.group(2).lower()

            # Parse time
            try:
                now = datetime.now()
                log_time = datetime.strptime(
                    f"{now.year} {time_str}",
                    "%Y %b %d %H:%M:%S"
                )
            except:
                continue

            # Only show recent activity
            if log_time < cutoff:
                break

            # Filter system domains
            if is_system_domain(domain):
                continue

            # Deduplicate within 30 second windows
            time_key = f"{domain}_{log_time.strftime('%H:%M')}"
            if time_key in seen_domains:
                continue
            seen_domains.add(time_key)

            # Check if blocked
            is_blocked = any(
                blocked in domain
                for blocked in blocked_domains
            )

            results.append({
                "time": log_time.strftime("%H:%M:%S"),
                "domain": domain,
                "blocked": is_blocked,
                "timestamp": log_time
            })

    except Exception as e:
        print(f"Live monitor error: {e}")

    return results[:50]  # Return last 50 entries


def get_current_site(ip):
    """Get the most recent domain a device visited"""
    activity = parse_live_activity(ip, minutes=2)
    if activity:
        return activity[0]
    return None


def get_all_devices_activity():
    """Get latest activity for all devices - for overview page"""
    if not os.path.exists(DNS_LOG_PATH):
        return {}

    cutoff = datetime.now() - timedelta(minutes=5)
    devices = {}

    try:
        with open(DNS_LOG_PATH, "r") as f:
            f.seek(0, 2)
            file_size = f.tell()
            seek_pos = max(0, file_size - 1 * 1024 * 1024)
            f.seek(seek_pos)
            lines = f.readlines()

        for line in reversed(lines):
            if "query[A]" not in line:
                continue

            match = re.search(
                r'(\w+\s+\d+\s+\d+:\d+:\d+).*query\[A\]\s+(\S+)\s+from\s+(192\.168\.50\.\d+)',
                line
            )
            if not match:
                continue

            time_str = match.group(1)
            domain = match.group(2).lower()
            ip = match.group(3)

            if is_system_domain(domain):
                continue

            if ip in devices:
                continue

            try:
                now = datetime.now()
                log_time = datetime.strptime(
                    f"{now.year} {time_str}",
                    "%Y %b %d %H:%M:%S"
                )
                if log_time < cutoff:
                    continue
            except:
                continue

            devices[ip] = {
                "domain": domain,
                "time": log_time.strftime("%H:%M:%S")
            }

    except Exception as e:
        print(f"Activity overview error: {e}")

    return devices
