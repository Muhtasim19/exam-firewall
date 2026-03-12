import subprocess
import os

LAN_PREFIX = "192.168.50."
EXAM_CHAIN = "EXAM_BLOCK"

# DNS blocking
# WRONG - dnsmasq won't find this
DNS_BLOCK_FILE = "/etc/dnsmasq.d/exam-block.conf"
DNS_SOURCE_FILE = "dns/blocked_domains.conf"


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

    # Allow established connections
    run_safe(
        "iptables -C FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT "
        "|| iptables -I FORWARD 1 -m state --state RELATED,ESTABLISHED -j ACCEPT"
    )

    # Attach exam chain
    forward_rules = run("iptables -L FORWARD")

    if EXAM_CHAIN not in forward_rules:
        run_safe(f"iptables -I FORWARD 2 -j {EXAM_CHAIN}")

    # Ensure RETURN rule exists
    chain_rules = run(f"iptables -L {EXAM_CHAIN}")

    if "RETURN" not in chain_rules:
        run_safe(f"iptables -A {EXAM_CHAIN} -j RETURN")


# ==========================
# Exam Mode
# ==========================

def exam_on():
    ensure_chain()

    # Enable DNS blocking
    if os.path.exists(DNS_SOURCE_FILE):
        run_safe(f"cp {DNS_SOURCE_FILE} {DNS_BLOCK_FILE}")

    run_safe("systemctl restart dnsmasq")


def exam_off():
    # Remove IP blocks
    run_safe(f"iptables -F {EXAM_CHAIN}")
    run_safe(f"iptables -A {EXAM_CHAIN} -j RETURN")

    # Remove DNS block file
    run_safe(f"rm -f {DNS_BLOCK_FILE}")

    run_safe("systemctl restart dnsmasq")


def exam_status():

    # Check iptables
    output = run(f"iptables -L {EXAM_CHAIN} -n")

    for line in output.splitlines():
        if "DROP" in line:
            return "active"

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

            # Only update if hostname exists (keeps most recent)
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

    run_safe(
        f"iptables -C {EXAM_CHAIN} -s {ip} -j DROP "
        f"|| iptables -I {EXAM_CHAIN} 1 -s {ip} -j DROP"
    )


def unblock_device(ip):

    run_safe(
        f"iptables -C {EXAM_CHAIN} -s {ip} -j DROP "
        f"&& iptables -D {EXAM_CHAIN} -s {ip} -j DROP"
    )


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

    devices = []
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

                devices.append({
                    "ip": ip,
                    "mac": mac,
                    "hostname": hostnames.get(ip, "Unknown"),
                    "state": state,
                    "blocked": ip in blocked_ips
                })

    return devices


# ==========================
# Kill Switch
# ==========================

def kill_network():
    ensure_chain()
    # Block ALL student traffic
    run_safe("iptables -I FORWARD -i eno1 -o enp2s0 -j DROP")

def restore_network():
    # Remove the kill switch rule
    run_safe("iptables -D FORWARD -i eno1 -o enp2s0 -j DROP")
    
def network_status():
    output = run("iptables -L FORWARD -n -v")
    for line in output.splitlines():
        if "DROP" in line and "eno1" in line:
            return "killed"
    return "active"
