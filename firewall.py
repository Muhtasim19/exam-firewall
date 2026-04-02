import subprocess
import os

LAN_PREFIX = "192.168.50."
EXAM_CHAIN = "EXAM_BLOCK"

DNS_BLOCK_FILE = "/etc/dnsmasq.d/exam-block.conf"
DNS_SOURCE_FILE = "dns/blocked_domains.conf"

# Static IP blocks as fallback
IP_BLOCKS = [
    "104.18.32.0/24",
    "104.18.33.0/24",
    "172.64.154.0/24",
    "172.64.155.0/24",
    "172.253.112.0/21",
]

# Domains to auto-resolve IPs for
AI_DOMAINS = [
    "chatgpt.com",
    "openai.com",
    "gemini.google.com",
    "bard.google.com",
]

# Google services to whitelist in strict mode
WHITELIST_IPS = [
    "142.251.0.0/16",    # Google Classroom + Docs + Meet
    "172.253.0.0/16",    # Google accounts + services
    "216.239.32.0/19",   # Google services
    "64.233.160.0/19",   # Google services
    "74.125.0.0/16",     # Google broadly
    "172.217.0.0/16",    # Google broadly
]


# ==========================
# Utility
# ==========================

def run(cmd):
    result = subprocess.run(
        f"sudo {cmd}",
        shell=True,
        text=True,
        capture_output=True
    )
    return result.stdout.strip()


def run_safe(cmd):
    subprocess.run(f"sudo {cmd}", shell=True)


# ==========================
# Firewall Setup
# ==========================

def ensure_chain():
    chains = run("iptables -L")
    if EXAM_CHAIN not in chains:
        run_safe(f"iptables -N {EXAM_CHAIN}")

    chain_rules = run(f"iptables -L {EXAM_CHAIN}")
    if "RETURN" not in chain_rules:
        run_safe(f"iptables -A {EXAM_CHAIN} -j RETURN")

    forward_rules = run("iptables -L FORWARD")
    if EXAM_CHAIN not in forward_rules:
        run_safe(f"iptables -I FORWARD 1 -j {EXAM_CHAIN}")


# ==========================
# Auto IP Detection
# ==========================

def get_ai_ips():
    """Dynamically resolve current AI service IPs"""
    ip_ranges = set()

    for domain in AI_DOMAINS:
        result = subprocess.run(
            f"dig +short {domain}",
            shell=True,
            text=True,
            capture_output=True
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.endswith('.'):
                continue
            parts = line.split('.')
            if len(parts) == 4:
                try:
                    [int(p) for p in parts]
                    subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
                    ip_ranges.add(subnet)
                except ValueError:
                    continue

    return list(ip_ranges)


# ==========================
# Exam Mode
# ==========================

def exam_on():
    ensure_chain()

    if os.path.exists(DNS_SOURCE_FILE):
        run_safe(f"cp {DNS_SOURCE_FILE} {DNS_BLOCK_FILE}")

    run_safe("systemctl restart dnsmasq")

    # Block IP ranges - no conntrack flush needed
    dynamic_ips = get_ai_ips()
    all_blocks = list(set(IP_BLOCKS + dynamic_ips))

    for ip in all_blocks:
        result = run(f"iptables -C FORWARD -i eno1 -d {ip} -j DROP 2>/dev/null && echo found")
        if "found" not in result:
            run_safe(f"iptables -I FORWARD 1 -i eno1 -d {ip} -j DROP")


def exam_off():
    run_safe(f"iptables -F {EXAM_CHAIN}")
    run_safe(f"iptables -A {EXAM_CHAIN} -j RETURN")

    run_safe(f"rm -f {DNS_BLOCK_FILE}")
    run_safe("systemctl restart dnsmasq")

    # Remove ALL AI IP blocks from FORWARD
    output = run("iptables -L FORWARD -n")
    for line in output.splitlines():
        if "DROP" not in line:
            continue
        parts = line.split()
        for part in parts:
            if "/" in part and not any([
                part.startswith("1.1.1"),
                part.startswith("8.8"),
                part.startswith("9.9"),
                part == "0.0.0.0/0"
            ]):
                run_safe(f"iptables -D FORWARD -i eno1 -d {part} -j DROP")


def exam_status():
    if os.path.exists(DNS_BLOCK_FILE):
        return "active"
    return "inactive"


# ==========================
# Strict Mode
# ==========================

# Strict mode DROP rule uses a specific comment to identify it
STRICT_DROP_COMMENT = "strict-mode"

def strict_mode_on():
    ensure_chain()
    strict_mode_off()

    if os.path.exists(DNS_SOURCE_FILE):
        run_safe(f"cp {DNS_SOURCE_FILE} {DNS_BLOCK_FILE}")
    run_safe("systemctl restart dnsmasq")

    for i, ip in enumerate(WHITELIST_IPS):
        run_safe(f"iptables -I FORWARD {i + 2} -i eno1 -d {ip} -j ACCEPT")

    run_safe(f"iptables -I FORWARD {len(WHITELIST_IPS) + 2} -i eno1 -o enp2s0 -m comment --comment '{STRICT_DROP_COMMENT}' -j DROP")

def strict_mode_off():
    # Remove whitelist ACCEPT rules
    for ip in WHITELIST_IPS:
        while True:
            result = run(f"iptables -C FORWARD -i eno1 -d {ip} -j ACCEPT 2>/dev/null && echo found")
            if "found" not in result:
                break
            run_safe(f"iptables -D FORWARD -i eno1 -d {ip} -j ACCEPT")

    # Remove strict DROP rule
    while True:
        result = run(f"iptables -C FORWARD -i eno1 -o enp2s0 -m comment --comment '{STRICT_DROP_COMMENT}' -j DROP 2>/dev/null && echo found")
        if "found" not in result:
            break
        run_safe(f"iptables -D FORWARD -i eno1 -o enp2s0 -m comment --comment '{STRICT_DROP_COMMENT}' -j DROP")

    # Remove DNS blocking
    run_safe(f"rm -f {DNS_BLOCK_FILE}")
    run_safe("systemctl restart dnsmasq")

    # Flush connections so no cached sessions survive
    run_safe("conntrack -F")


def strict_status():
    output = run("iptables -L FORWARD -n -v")
    return "active" if STRICT_DROP_COMMENT in output else "inactive"


def network_status():
    output = run("iptables -L FORWARD -n -v")
    for line in output.splitlines():
        # Only match kill switch — no comment marker
        if "DROP" in line and "eno1" in line and "enp2s0" in line and STRICT_DROP_COMMENT not in line:
            return "killed"
    return "active"


# ==========================
# DHCP Hostname Detection
# ==========================

def get_dhcp_hostnames():
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
# Device Blocking
# ==========================

def block_device(ip):
    result = run(f"iptables -C {EXAM_CHAIN} -s {ip} -j DROP 2>/dev/null && echo found")
    if "found" not in result:
        run_safe(f"iptables -I {EXAM_CHAIN} 1 -s {ip} -j DROP")


def unblock_device(ip):
    while True:
        result = run(f"iptables -C {EXAM_CHAIN} -s {ip} -j DROP 2>/dev/null && echo found")
        if "found" not in result:
            break
        run_safe(f"iptables -D {EXAM_CHAIN} -s {ip} -j DROP")


def get_blocked_ips():
    blocked = set()
    output = run(f"iptables -L {EXAM_CHAIN} -n")

    for line in output.splitlines():
        parts = line.split()
        for part in parts:
            if part.startswith(LAN_PREFIX):
                blocked.add(part)

    return blocked


# ==========================
# Device Detection
# ==========================

def connected_devices():
    devices = {}
    blocked_ips = get_blocked_ips()
    hostnames = get_dhcp_hostnames()

    # Flush failed/incomplete ARP entries so waking devices are rediscovered
    run_safe("ip neigh flush dev eno1 nud failed")
    run_safe("ip neigh flush dev eno1 nud incomplete")

    output = subprocess.check_output("ip neigh", shell=True, text=True)

    for line in output.splitlines():
        parts = line.split()

        if "lladdr" in parts:
            ip = parts[0]
            mac = parts[4].lower()
            state = parts[-1]

            if ip.startswith(LAN_PREFIX):
                if ip not in devices or state == "REACHABLE":
                    devices[ip] = {
                        "ip": ip,
                        "mac": mac,
                        "hostname": hostnames.get(ip, "Unknown"),
                        "state": state,
                        "blocked": ip in blocked_ips
                    }

    return list(devices.values())


# ==========================
# Kill Switch
# ==========================

def kill_network():
    while True:
        result = run("iptables -C FORWARD -i eno1 -o enp2s0 -j DROP 2>/dev/null && echo found")
        if "found" not in result:
            break
        run_safe("iptables -D FORWARD -i eno1 -o enp2s0 -j DROP")
    run_safe("iptables -I FORWARD 1 -i eno1 -o enp2s0 -j DROP")


def restore_network():
    while True:
        result = run("iptables -C FORWARD -i eno1 -o enp2s0 -j DROP 2>/dev/null && echo found")
        if "found" not in result:
            break
        run_safe("iptables -D FORWARD -i eno1 -o enp2s0 -j DROP")


def network_status():
    output = run("iptables -L FORWARD -n -v")
    for line in output.splitlines():
        if "DROP" in line and "eno1" in line and "enp2s0" in line:
            return "killed"
    return "active"


# ==========================
# Run once at startup
# ==========================
ensure_chain()
