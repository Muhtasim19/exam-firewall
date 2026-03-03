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
# Firewall Setup
# ==========================

def ensure_chain():
    # Create chain if missing
    chains = run("iptables -L")
    if EXAM_CHAIN not in chains:
        run_safe(f"iptables -N {EXAM_CHAIN}")

    # Always allow established connections FIRST
    run_safe(
        "iptables -C FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT "
        "|| iptables -I FORWARD 1 -m state --state RELATED,ESTABLISHED -j ACCEPT"
    )

    # Attach chain once
    forward_rules = run("iptables -L FORWARD")
    if EXAM_CHAIN not in forward_rules:
        run_safe(f"iptables -I FORWARD 2 -j {EXAM_CHAIN}")

    # IMPORTANT: Ensure chain ends with RETURN
    chain_rules = run(f"iptables -L {EXAM_CHAIN}")
    if "RETURN" not in chain_rules:
        run_safe(f"iptables -A {EXAM_CHAIN} -j RETURN")


# ==========================
# Exam Mode
# ==========================

def exam_on():
    ensure_chain()


def exam_off():
    # Flush only DROP rules (not RETURN)
    run_safe(f"iptables -F {EXAM_CHAIN}")
    run_safe(f"iptables -A {EXAM_CHAIN} -j RETURN")


def exam_status():
    output = run(f"iptables -L {EXAM_CHAIN} -n")
    lines = output.splitlines()

    # Count DROP rules
    drops = [line for line in lines if "DROP" in line]

    if drops:
        return "active"
    return "inactive"


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
                    "hostname": "Unknown",
                    "state": state,
                    "blocked": ip in blocked_ips
                })

    return devices
