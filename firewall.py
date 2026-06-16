import subprocess
import os
import logging

LAN_PREFIX = "192.168.50."
EXAM_CHAIN = "EXAM_BLOCK"

DNS_BLOCK_FILE = "/etc/dnsmasq.d/exam-block.conf"
DNS_SOURCE_FILE = "dns/blocked_domains.conf"

IP_BLOCKS = [
    "104.18.32.0/24",
    "104.18.33.0/24",
    "172.64.154.0/24",
    "172.64.155.0/24",
    "172.253.112.0/21",
]

AI_DOMAINS = [
    "chatgpt.com",
    "openai.com",
    "gemini.google.com",
    "bard.google.com",
]

WHITELIST_IPS = [
    "172.25.205.59/32",
    "172.25.205.123/32",
    "142.251.45.0/24",
    "142.251.211.0/24",
    "172.253.62.0/24",
    "216.239.32.0/19",
    "64.233.160.0/19",
    "74.125.0.0/16",
    "172.217.0.0/16",
]

STRICT_DROP_COMMENT = "strict-mode"

logging.basicConfig(
    filename='/var/log/exam-firewall.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

def log(msg):
    logging.info(msg)
    print(msg)


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


def get_ai_ips():
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


def exam_on():
    log("=== EXAM MODE ENABLED ===")
    try:
        import analytics
        analytics.log_mode_event("=== EXAM MODE ENABLED ===")
    except:
        pass

    ensure_chain()

    if os.path.exists(DNS_SOURCE_FILE):
        run_safe(f"cp {DNS_SOURCE_FILE} {DNS_BLOCK_FILE}")

    run_safe("systemctl restart dnsmasq")

    dynamic_ips = get_ai_ips()
    all_blocks = list(set(IP_BLOCKS + dynamic_ips))

    log(f"Blocking {len(all_blocks)} IP ranges")
    for ip in all_blocks:
        result = run(f"iptables -C FORWARD -i eno1 -d {ip} -j DROP 2>/dev/null && echo found")
        if "found" not in result:
            run_safe(f"iptables -I FORWARD 1 -i eno1 -d {ip} -j DROP")


def exam_off():
    log("=== EXAM MODE DISABLED ===")
    try:
        import analytics
        analytics.log_mode_event("=== EXAM MODE DISABLED ===")
    except:
        pass

    # Save individual device blocks before flushing
    device_blocks = get_blocked_ips()

    # Flush chain then restore individual device blocks
    run_safe(f"iptables -F {EXAM_CHAIN}")
    run_safe(f"iptables -A {EXAM_CHAIN} -j RETURN")

    # Restore individual device blocks
    for ip in device_blocks:
        run_safe(f"iptables -I {EXAM_CHAIN} 1 -s {ip} -j DROP")

    run_safe(f"rm -f {DNS_BLOCK_FILE}")
    run_safe("systemctl restart dnsmasq")

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


def reset_all_blocks():
    """Reset ALL individual device blocks and YouTube blocks"""
    log("=== RESET ALL BLOCKS ===")
    try:
        import analytics
        analytics.log_mode_event("=== RESET ALL BLOCKS ===")
    except:
        pass

    # Clear all device blocks from EXAM_BLOCK chain
    run_safe(f"iptables -F {EXAM_CHAIN}")
    run_safe(f"iptables -A {EXAM_CHAIN} -j RETURN")

    # Clear all YouTube blocks
    try:
        import youtube_block
        nat_output = run(f"iptables -t nat -L {youtube_block.YOUTUBE_CHAIN} -n")
        ips_to_unblock = set()
        for line in nat_output.splitlines():
            if "5353" in line:
                parts = line.split()
                for part in parts:
                    if part.startswith(LAN_PREFIX):
                        ips_to_unblock.add(part)
        for ip in ips_to_unblock:
            youtube_block.unblock_youtube(ip)
    except:
        pass


def block_all_crl(devices):
    """Block all devices with CRL- hostname"""
    log("=== BLOCK ALL CRL DEVICES ===")
    for device in devices:
        hostname = device.get("hostname", "")
        if hostname.lower().startswith("crl-"):
            block_device(device["ip"])


def unblock_all_crl(devices):
    """Unblock all devices with CRL- hostname"""
    log("=== UNBLOCK ALL CRL DEVICES ===")
    for device in devices:
        hostname = device.get("hostname", "")
        if hostname.lower().startswith("crl-"):
            unblock_device(device["ip"])


def strict_mode_on():
    log("=== STRICT MODE ENABLED ===")
    try:
        import analytics
        analytics.log_mode_event("=== STRICT MODE ENABLED ===")
    except:
        pass

    ensure_chain()
    strict_mode_off()

    if os.path.exists(DNS_SOURCE_FILE):
        run_safe(f"cp {DNS_SOURCE_FILE} {DNS_BLOCK_FILE}")
    run_safe("systemctl restart dnsmasq")

    for i, ip in enumerate(WHITELIST_IPS):
        run_safe(f"iptables -I FORWARD {i + 2} -i eno1 -d {ip} -j ACCEPT")

    run_safe(f"iptables -I FORWARD {len(WHITELIST_IPS) + 2} -i eno1 -o enp2s0 -m comment --comment '{STRICT_DROP_COMMENT}' -j DROP")


def strict_mode_off():
    log("=== STRICT MODE DISABLED ===")
    try:
        import analytics
        analytics.log_mode_event("=== STRICT MODE DISABLED ===")
    except:
        pass

    for ip in WHITELIST_IPS:
        while True:
            result = run(f"iptables -C FORWARD -i eno1 -d {ip} -j ACCEPT 2>/dev/null && echo found")
            if "found" not in result:
                break
            run_safe(f"iptables -D FORWARD -i eno1 -d {ip} -j ACCEPT")

    while True:
        result = run(f"iptables -C FORWARD -i eno1 -o enp2s0 -m comment --comment '{STRICT_DROP_COMMENT}' -j DROP 2>/dev/null && echo found")
        if "found" not in result:
            break
        run_safe(f"iptables -D FORWARD -i eno1 -o enp2s0 -m comment --comment '{STRICT_DROP_COMMENT}' -j DROP")

    run_safe(f"rm -f {DNS_BLOCK_FILE}")
    run_safe("systemctl restart dnsmasq")


def strict_status():
    output = run("iptables -L FORWARD -n -v")
    return "active" if STRICT_DROP_COMMENT in output else "inactive"


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


def block_device(ip):
    log(f"BLOCKING device: {ip}")
    try:
        import analytics
        hostname = get_dhcp_hostnames().get(ip, "Unknown")
        analytics.log_block_event(ip, hostname, "BLOCKING")
    except:
        pass

    result = run(f"iptables -C {EXAM_CHAIN} -s {ip} -j DROP 2>/dev/null && echo found")
    if "found" not in result:
        run_safe(f"iptables -I {EXAM_CHAIN} 1 -s {ip} -j DROP")


def unblock_device(ip):
    log(f"UNBLOCKING device: {ip}")
    try:
        import analytics
        hostname = get_dhcp_hostnames().get(ip, "Unknown")
        analytics.log_block_event(ip, hostname, "UNBLOCKING")
    except:
        pass

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


def connected_devices():
    devices = {}
    blocked_ips = get_blocked_ips()
    hostnames = get_dhcp_hostnames()

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

    log(f"--- Connected Devices ({len(devices)}) ---")
    for d in devices.values():
        status = "BLOCKED" if d["blocked"] else "ALLOWED"
        log(f"  {d['hostname']} | {d['ip']} | {d['state']} | {status}")

    try:
        import analytics
        analytics.log_devices(list(devices.values()))
    except:
        pass

    return list(devices.values())


def refresh_devices():
    log("=== MANUAL DEVICE REFRESH ===")
    run_safe("ip neigh flush dev eno1 nud failed")
    run_safe("ip neigh flush dev eno1 nud incomplete")
    run_safe("nmap -sn 192.168.50.0/24 --send-ip -T4")


def kill_network():
    log("=== KILL SWITCH ACTIVATED ===")
    try:
        import analytics
        analytics.log_mode_event("=== KILL SWITCH ACTIVATED ===")
    except:
        pass

    while True:
        result = run("iptables -C FORWARD -i eno1 -o enp2s0 -j DROP 2>/dev/null && echo found")
        if "found" not in result:
            break
        run_safe("iptables -D FORWARD -i eno1 -o enp2s0 -j DROP")
    run_safe("iptables -I FORWARD 1 -i eno1 -o enp2s0 -j DROP")


def restore_network():
    log("=== NETWORK RESTORED ===")
    try:
        import analytics
        analytics.log_mode_event("=== NETWORK RESTORED ===")
    except:
        pass

    while True:
        result = run("iptables -C FORWARD -i eno1 -o enp2s0 -j DROP 2>/dev/null && echo found")
        if "found" not in result:
            break
        run_safe("iptables -D FORWARD -i eno1 -o enp2s0 -j DROP")


def network_status():
    output = run("iptables -L FORWARD -n -v")
    for line in output.splitlines():
        if "DROP" in line and "eno1" in line and "enp2s0" in line and STRICT_DROP_COMMENT not in line:
            return "killed"
    return "active"


import sys
if 'gunicorn' in sys.argv[0] or 'app' in sys.modules:
    log("=== EXAM FIREWALL STARTED ===")
    ensure_chain()
