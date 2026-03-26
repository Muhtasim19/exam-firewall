import subprocess
import os

LAN_PREFIX = "192.168.50."
EXAM_CHAIN = "EXAM_BLOCK"

DNS_BLOCK_FILE = "/etc/dnsmasq.d/exam-block.conf"
DNS_SOURCE_FILE = "dns/blocked_domains.conf"

IP_BLOCKS = [
    "104.18.32.0/24",
    "104.18.33.0/24",
    "172.64.154.0/24",
    "172.64.155.0/24",
    "172.253.112.0/21",  # All Gemini subnets
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
    # Create EXAM_BLOCK chain if missing
    chains = run("iptables -L")
    if EXAM_CHAIN not in chains:
        run_safe(f"iptables -N {EXAM_CHAIN}")

    # Ensure RETURN rule exists at end of chain
    chain_rules = run(f"iptables -L {EXAM_CHAIN}")
    if "RETURN" not in chain_rules:
        run_safe(f"iptables -A {EXAM_CHAIN} -j RETURN")

    # Attach EXAM_BLOCK as FIRST rule in FORWARD
    forward_rules = run("iptables -L FORWARD")
    if EXAM_CHAIN not in forward_rules:
        run_safe(f"iptables -I FORWARD 1 -j {EXAM_CHAIN}")

# ==========================
# Exam Mode
# ==========================

def exam_on():
    ensure_chain()

    # Enable DNS blocking
    if os.path.exists(DNS_SOURCE_FILE):
        run_safe(f"cp {DNS_SOURCE_FILE} {DNS_BLOCK_FILE}")

    run_safe("systemctl restart dnsmasq")

    # Flush only TCP connections (leaves DHCP/UDP alone)
    run_safe("conntrack -F -p tcp")

    # Block IP ranges - check first to avoid duplicates
    for ip in IP_BLOCKS:
        result = run(f"iptables -C FORWARD -i eno1 -d {ip} -j DROP 2>/dev/null && echo found")
        if "found" not in result:
            run_safe(f"iptables -I FORWARD 1 -i eno1 -d {ip} -j DROP")


def exam_off():
    # Flush EXAM_BLOCK chain (removes individual device blocks too)
    run_safe(f"iptables -F {EXAM_CHAIN}")
    run_safe(f"iptables -A {EXAM_CHAIN} -j RETURN")

    # Remove DNS block file
    run_safe(f"rm -f {DNS_BLOCK_FILE}")
    run_safe("systemctl restart dnsmasq")

    # Remove IP blocks
    for ip in IP_BLOCKS:
        while True:
            result = run(f"iptables -C FORWARD -i eno1 -d {ip} -j DROP 2>/dev/null && echo found")
            if "found" not in result:
                break
            run_safe(f"iptables -D FORWARD -i eno1 -d {ip} -j DROP")


def exam_status():
    # Check DNS block file
    if os.path.exists(DNS_BLOCK_FILE):
        return "active"
    return "inactive"


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
    ensure_chain()
    # Add to EXAM_BLOCK chain
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
    ensure_chain()

    devices = {}
    blocked_ips = get_blocked_ips()
    hostnames = get_dhcp_hostnames()

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
