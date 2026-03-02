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
# Firewall Chain Setup
# ==========================

def ensure_chain():
    """
    Ensures:
    - EXAM_BLOCK chain exists
    - ESTABLISHED traffic allowed
    - EXAM_BLOCK attached safely to FORWARD
    """

    # Create custom chain if not exists
    chains = run("iptables -L")
    if EXAM_CHAIN not in chains:
        run_safe(f"iptables -N {EXAM_CHAIN}")

    # Allow established connections FIRST (critical)
    run_safe(
        "iptables -C FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT "
        "|| iptables -I FORWARD 1 -m state --state RELATED,ESTABLISHED -j ACCEPT"
    )

    # Attach EXAM_BLOCK only once
    forward_rules = run("iptables -L FORWARD")
    if EXAM_CHAIN not in forward_rules:
        run_safe(f"iptables -A FORWARD -j {EXAM_CHAIN}")


# ==========================
# Exam Mode Control
# ==========================

def exam_on():
    """
    Exam mode ON:
    - Ensure firewall chain is active
    - Keep network routing normal
    """
    ensure_chain()


def exam_off():
    """
    Exam mode OFF:
    - Flush EXAM_BLOCK rules (unblock everyone)
    """
    run_safe(f"iptables -F {EXAM_CHAIN}")


def exam_status():
    """
    Exam is active if EXAM_BLOCK chain has rules
    """
    output = run(f"iptables -L {EXAM_CHAIN} -n")
    lines = output.splitlines()

    # If more than header lines exist → rules present
    if len(lines) > 2:
        return "active"
    else:
        return "inactive"


# ==========================
# Device Detection
# ==========================

def connected_devices():
    ensure_chain()

    devices = []
    leases = {}
    blocked_ips = get_blocked_ips()

    # Read DHCP leases (if using dnsmasq)
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

    # Prevent duplicate rules
    run_safe(
        f"iptables -C {EXAM_CHAIN} -s {ip} -j DROP "
        f"|| iptables -A {EXAM_CHAIN} -s {ip} -j DROP"
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
# Emergency Reset (Optional)
# ==========================

def reset_firewall():
    """
    Completely removes EXAM_BLOCK chain
    """
    run_safe(f"iptables -F {EXAM_CHAIN}")
    run_safe(f"iptables -D FORWARD -j {EXAM_CHAIN}")
    run_safe(f"iptables -X {EXAM_CHAIN}")
