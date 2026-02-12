import subprocess

def run(cmd):
    subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

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

    try:
        with open("/var/lib/misc/dnsmasq.leases", "r") as f:
            for line in f.readlines():
                parts = line.split()
                if len(parts) >= 4:
                    mac = parts[1]
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
            mac = parts[4]
            state = parts[-1]

            
            if ip.startswith("192.168.50."):
                hostname = leases.get(ip, "Unknown")

                devices.append({
                    "ip": ip,
                    "mac": mac,
                    "hostname": hostname,
                    "state": state
                })

    return devices


def block_device(mac):
    run(f"iptables -I FORWARD -m mac --mac-source {mac} -j DROP")

def unblock_device(mac):
    run(f"iptables -D FORWARD -m mac --mac-source {mac} -j DROP")
