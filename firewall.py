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
    output = subprocess.check_output("ip neigh", shell=True).decode()

    for line in output.splitlines():
        parts = line.split()
        if "lladdr" in parts:
            devices.append({
                "ip": parts[0],
                "mac": parts[4],
                "state": parts[-1]
            })
    return devices

def block_device(mac):
    run(f"iptables -I FORWARD -m mac --mac-source {mac} -j DROP")

def unblock_device(mac):
    run(f"iptables -D FORWARD -m mac --mac-source {mac} -j DROP")
