import subprocess

LAN_PREFIX = "192.168.50."

def run(cmd):
    result = subprocess.run(
        cmd,
        shell=True,
        text=True,
        capture_output=True
    )
    return result.stdout.strip()


# ==========================
# Exam Mode Control
# ==========================

def exam_on():
    run("systemctl start dnsmasq")

def exam_off():
    run("systemctl stop dnsmasq")

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
# Blocking Logic (Clean)
# ==========================

def block_device(ip):
    run(f"iptables -A EXAM_BLOCK -s {ip} -j DROP")

def unblock_device(ip):
    run(f"iptables -D EXAM_BLOCK -s {ip} -j DROP")

def get_blocked_ips():
    blocked = set()

    output = run("iptables -L EXAM_BLOCK -n")

    for line in output.splitlines():
        parts = line.split()
        for part in parts:
            if part.startswith(LAN_PREFIX):
                blocked.add(part)

    return blocked
