import subprocess

LAN_PREFIX = "192.168.50."
EXAM_CHAIN = "EXAM_BLOCK"

# ==========================
# Utility
# ==========================

def run(cmd):
    result = subprocess.run(
        cmd,
        shell=True,
        text=True,
        capture_output=True
    )
    return result.stdout.strip()

def run_safe(cmd):
    subprocess.run(cmd, shell=True)

# ==========================
# Ensure EXAM_BLOCK Chain Exists
# ==========================

def ensure_chain():
    # Create chain if not exists
    chains = run("iptables -L")
    if EXAM_CHAIN not in chains:
        run_safe(f"iptables -N {EXAM_CHAIN}")

    # Make sure RELATED,ESTABLISHED is allowed FIRST
    run_safe("iptables -C FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT || iptables -I FORWARD 1 -m state --state RELATED,ESTABLISHED -j ACCEPT")

    # Attach EXAM_BLOCK safely (only once)
    forward_rules = run("iptables -L FORWARD")
    if EXAM_CHAIN not in forward_rules:
        run_safe(f"iptables -A FORWARD -j {EXAM_CHAIN}")

# ==========================
# Exam Mode Control (dnsmasq)
# ==========================

def exam_on():
    run_safe("systemctl start dnsmasq")

def exam_off():
    run_safe("systemctl stop dnsmasq")

def exam_status():
    result = subprocess.run(
        ["systemctl", "is-active", "dnsmasq"],
        capture_output=True,
        text=True
    )
    return result.stdout.strip()

# ==========================
# Device Detection
# ==========================

def connected_devices():
    ensure_chain()

    devices = []
    leases = {}
    blocked_ips = get_blocked_ips()

    # Read DHCP leases
    try:
        with open("/var/lib/misc/dnsmasq.leases") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 4:
                    leases[parts[2]] = parts[3]
    except:
        pass

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
                    "hostname": leases.get(ip, "Unknown"),
                    "state": state,
                    "blocked": ip in blocked_ips
                })

    return devices

# ==========================
# Blocking Logic (Safe)
# ==========================

def block_device(ip):
    ensure_chain()

    blocked_ips = get_blocked_ips()
    if ip not in blocked_ips:
        run_safe(f"iptables -A {EXAM_CHAIN} -s {ip} -j DROP")

def unblock_device(ip):
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
