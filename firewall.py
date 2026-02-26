import subprocess

def run(cmd):
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True
    )
    print("COMMAND:", cmd)
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)

def exam_on():
    run("systemctl start dnsmasq")

def exam_off():
    run("systemctl stop dnsmasq")

def exam_status():
    result = subprocess.run(
        ["systemctl", "is-active", "dnsmasq"],
        capture_output=True, text=True
    )
    return result.stdout.strip()


def connected_devices():
    devices = []
    leases = {}
    blocked_macs = get_blocked_macs()

    # Read dnsmasq leases
    try:
        with open("/var/lib/misc/dnsmasq.leases", "r") as f:
            for line in f.readlines():
                parts = line.split()
                if len(parts) >= 4:
                    ip = parts[2]
                    hostname = parts[3]
                    leases[ip] = hostname
    except:
        pass

    output = subprocess.check_output("ip neigh", shell=True, text=True)

    for line in output.splitlines():
        parts = line.split()

        if "lladdr" in parts:
            ip = parts[0]
            mac = parts[4].lower()
            state = parts[-1]

            if ip.startswith("192.168.50."):
                hostname = leases.get(ip, "Unknown")

                devices.append({
                    "ip": ip,
                    "mac": mac,
                    "hostname": hostname,
                    "state": state,
                    "blocked": mac in blocked_macs
                })

    return devices



def block_device(mac):
    run(f"iptables -I FORWARD 1 -m mac --mac-source {mac} -j DROP")

def unblock_device(mac):
    run(f"iptables -D FORWARD -m mac --mac-source {mac} -j DROP")

def get_blocked_macs():
    blocked = set()

    output = subprocess.check_output(
        "sudo iptables -L FORWARD -n --line-numbers",
        shell=True,
        text=True
    )

    for line in output.splitlines():
        if "MAC" in line:
            parts = line.split()
            for part in parts:
                if ":" in part and len(part) == 17:
                    blocked.add(part.lower())

    return blocked
