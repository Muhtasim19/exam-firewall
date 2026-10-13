import os
import re
from datetime import datetime, timedelta

DNS_LOG_PATH = "/var/log/dnsmasq.log"

def get_blocked_domains_set():
    """Get set of blocked domains from ALL dnsmasq conf files"""
    blocked = set()
    block_files = [
        "/etc/dnsmasq.d/exam-block.conf",
        "/etc/dnsmasq.d/custom-block.conf",
    ]
    for block_file in block_files:
        if os.path.exists(block_file):
            try:
                with open(block_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("address=/"):
                            parts = line.split("/")
                            if len(parts) >= 2:
                                blocked.add(parts[1])
            except:
                pass
    return blocked


def get_dhcp_hostnames():
    """Read DHCP leases file for IP -> hostname mapping"""
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


def get_blocked_attempts(minutes=60, limit=200):
    """
    Get recent blocked domain attempts across ALL devices.
    Returns list of {time, ip, hostname, domain} sorted newest first.
    """
    if not os.path.exists(DNS_LOG_PATH):
        return []
    blocked_domains = get_blocked_domains_set()
    if not blocked_domains:
        return []
    cutoff = datetime.now() - timedelta(minutes=minutes)
    results = []
    seen = set()
    hostnames = get_dhcp_hostnames()
    try:
        with open(DNS_LOG_PATH, "r") as f:
            f.seek(0, 2)
            file_size = f.tell()
            seek_pos = max(0, file_size - 3 * 1024 * 1024)
            f.seek(seek_pos)
            lines = f.readlines()
        for line in reversed(lines):
            if len(results) >= limit:
                break
            if "query[A]" not in line and "query[HTTPS]" not in line:
                continue
            match = re.search(
                r'(\w+\s+\d+\s+\d+:\d+:\d+).*query\[(?:A|HTTPS)\]\s+(\S+)\s+from\s+(192\.168\.50\.\d+)',
                line
            )
            if not match:
                continue
            time_str = match.group(1)
            domain = match.group(2).lower()
            ip = match.group(3)
            is_blocked = any(blocked in domain for blocked in blocked_domains)
            if not is_blocked:
                continue
            try:
                now = datetime.now()
                log_time = datetime.strptime(f"{now.year} {time_str}", "%Y %b %d %H:%M:%S")
                # Handle year rollover
                if log_time > now + timedelta(hours=1):
                    log_time = log_time.replace(year=now.year - 1)
            except:
                continue
            if log_time < cutoff:
                break
            key = f"{ip}_{domain}_{log_time.strftime('%H:%M')}"
            if key in seen:
                continue
            seen.add(key)
            results.append({
                "time": log_time.strftime("%H:%M:%S"),
                "ip": ip,
                "hostname": hostnames.get(ip, ip),
                "domain": domain,
            })
    except Exception as e:
        print(f"Blocked attempts error: {e}")
    return results


def get_live_stats(minutes=5):
    """Get DNS query stats for the last N minutes"""
    if not os.path.exists(DNS_LOG_PATH):
        return {"total": 0, "blocked": 0, "allowed": 0, "top_blocked": [], "top_allowed": []}

    blocked_domains = get_blocked_domains_set()
    cutoff = datetime.now() - timedelta(minutes=minutes)

    total = 0
    blocked_count = 0
    allowed_count = 0
    blocked_tally = {}
    allowed_tally = {}

    try:
        with open(DNS_LOG_PATH, "r") as f:
            f.seek(0, 2)
            file_size = f.tell()
            seek_pos = max(0, file_size - 2 * 1024 * 1024)
            f.seek(seek_pos)
            lines = f.readlines()

        for line in lines:
            if "query[A]" not in line and "query[HTTPS]" not in line:
                continue
            match = re.search(
                r'(\w+\s+\d+\s+\d+:\d+:\d+).*query\[(?:A|HTTPS)\]\s+(\S+)\s+from\s+192\.168\.50\.\d+',
                line
            )
            if not match:
                continue
            time_str = match.group(1)
            domain = match.group(2).lower()
            try:
                now = datetime.now()
                log_time = datetime.strptime(f"{now.year} {time_str}", "%Y %b %d %H:%M:%S")
                if log_time > now + timedelta(hours=1):
                    log_time = log_time.replace(year=now.year - 1)
            except:
                continue
            if log_time < cutoff:
                continue
            total += 1
            is_blocked = any(b in domain for b in blocked_domains)
            if is_blocked:
                blocked_count += 1
                blocked_tally[domain] = blocked_tally.get(domain, 0) + 1
            else:
                allowed_count += 1
                allowed_tally[domain] = allowed_tally.get(domain, 0) + 1

    except Exception as e:
        print(f"Live stats error: {e}")

    top_blocked = sorted(blocked_tally.items(), key=lambda x: x[1], reverse=True)[:5]
    top_allowed = sorted(allowed_tally.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "total": total,
        "blocked": blocked_count,
        "allowed": allowed_count,
        "top_blocked": [{"domain": d, "count": c} for d, c in top_blocked],
        "top_allowed": [{"domain": d, "count": c} for d, c in top_allowed],
    }


def get_device_queries(ip, minutes=60):
    """Get DNS queries for a specific device"""
    if not os.path.exists(DNS_LOG_PATH):
        return []
    blocked_domains = get_blocked_domains_set()
    cutoff = datetime.now() - timedelta(minutes=minutes)
    results = []
    try:
        with open(DNS_LOG_PATH, "r") as f:
            f.seek(0, 2)
            file_size = f.tell()
            seek_pos = max(0, file_size - 2 * 1024 * 1024)
            f.seek(seek_pos)
            lines = f.readlines()
        for line in reversed(lines):
            if len(results) >= 100:
                break
            if ip not in line:
                continue
            if "query[A]" not in line and "query[HTTPS]" not in line:
                continue
            match = re.search(
                r'(\w+\s+\d+\s+\d+:\d+:\d+).*query\[(?:A|HTTPS)\]\s+(\S+)\s+from\s+(' + re.escape(ip) + r')',
                line
            )
            if not match:
                continue
            time_str = match.group(1)
            domain = match.group(2).lower()
            try:
                now = datetime.now()
                log_time = datetime.strptime(f"{now.year} {time_str}", "%Y %b %d %H:%M:%S")
                if log_time > now + timedelta(hours=1):
                    log_time = log_time.replace(year=now.year - 1)
            except:
                continue
            if log_time < cutoff:
                break
            is_blocked = any(b in domain for b in blocked_domains)
            results.append({
                "time": log_time.strftime("%H:%M:%S"),
                "domain": domain,
                "blocked": is_blocked,
            })
    except Exception as e:
        print(f"Device queries error: {e}")
    return results


# ==========================
# System domains to filter out
# ==========================
SYSTEM_DOMAINS = [
    "pool.ntp.org", "windowsupdate.com", "microsoft.com", "msftconnecttest.com",
    "msftncsi.com", "cpsd.us", "msdcs", "googleapis.com", "gstatic.com",
    "clients6.google.com", "icloud.com", "apple.com", "akamai", "akadns",
    "cloudfront.net", "amazonaws.com", "digicert.com", "ocsp", "ctldl",
    "wpad", "local", "arpa", "in-addr", "msedge.net", "live.com",
    "office.com", "office365.com", "skype.com", "teams.microsoft.com",
    "avast.com", "norton.com", "sophos", "ivanti", "symcd.com",
    "symcb.com", "verisign.com", "entrust.net", "lencr.org",
]


def is_system_domain(domain):
    domain_lower = domain.lower()
    for system in SYSTEM_DOMAINS:
        if system in domain_lower:
            return True
    return False


def parse_live_activity(ip, minutes=10):
    """Get recent DNS activity for a specific device."""
    if not os.path.exists(DNS_LOG_PATH):
        return []
    blocked_domains = get_blocked_domains_set()
    cutoff = datetime.now() - timedelta(minutes=minutes)
    results = []
    seen_domains = set()
    try:
        with open(DNS_LOG_PATH, "r") as f:
            f.seek(0, 2)
            file_size = f.tell()
            seek_pos = max(0, file_size - 2 * 1024 * 1024)
            f.seek(seek_pos)
            lines = f.readlines()
        for line in reversed(lines):
            if len(results) >= 100:
                break
            if f"from {ip}" not in line:
                continue
            if "query[A]" not in line and "query[HTTPS]" not in line:
                continue
            match = re.search(
                r'(\w+\s+\d+\s+\d+:\d+:\d+).*query\[(?:A|HTTPS)\]\s+(\S+)\s+from',
                line
            )
            if not match:
                continue
            time_str = match.group(1)
            domain = match.group(2).lower()
            try:
                now = datetime.now()
                log_time = datetime.strptime(f"{now.year} {time_str}", "%Y %b %d %H:%M:%S")
                if log_time > now + timedelta(hours=1):
                    log_time = log_time.replace(year=now.year - 1)
            except:
                continue
            if log_time < cutoff:
                break
            if is_system_domain(domain):
                continue
            time_key = f"{domain}_{log_time.strftime('%H:%M')}"
            if time_key in seen_domains:
                continue
            seen_domains.add(time_key)
            is_blocked = any(b in domain for b in blocked_domains)
            results.append({
                "time": log_time.strftime("%H:%M:%S"),
                "domain": domain,
                "blocked": is_blocked,
                "timestamp": log_time
            })
    except Exception as e:
        print(f"Live monitor error: {e}")
    return results


def get_current_site(ip):
    """Get the most recent domain a device visited."""
    activity = parse_live_activity(ip, minutes=2)
    if activity:
        return activity[0]
    return None


def get_all_devices_activity():
    """Get latest activity for all devices — for overview column."""
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
                log_time = datetime.strptime(f"{now.year} {time_str}", "%Y %b %d %H:%M:%S")
                if log_time > now + timedelta(hours=1):
                    log_time = log_time.replace(year=now.year - 1)
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
