import subprocess

LAN_PREFIX = "192.168.50."
YOUTUBE_CHAIN = "YOUTUBE_BLOCK"

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

def ensure_youtube_chain():
    # Check NAT table for chain (not filter table!)
    nat_chains = run("iptables -t nat -L")

    if YOUTUBE_CHAIN not in nat_chains:
        run_safe(f"iptables -t nat -N {YOUTUBE_CHAIN}")

    # Attach to PREROUTING if not already there
    prerouting = run("iptables -t nat -L PREROUTING -n")
    if YOUTUBE_CHAIN not in prerouting:
        run_safe(f"iptables -t nat -A PREROUTING -i eno1 -j {YOUTUBE_CHAIN}")

def block_youtube(ip):
    ensure_youtube_chain()

    # Redirect this student's DNS to port 5353 (YouTube-blocking dnsmasq)
    run_safe(
        f"iptables -t nat -C {YOUTUBE_CHAIN} -s {ip} -p udp --dport 53 -j REDIRECT --to-ports 5353 "
        f"|| iptables -t nat -I {YOUTUBE_CHAIN} 1 -s {ip} -p udp --dport 53 -j REDIRECT --to-ports 5353"
    )
    run_safe(
        f"iptables -t nat -C {YOUTUBE_CHAIN} -s {ip} -p tcp --dport 53 -j REDIRECT --to-ports 5353 "
        f"|| iptables -t nat -I {YOUTUBE_CHAIN} 1 -s {ip} -p tcp --dport 53 -j REDIRECT --to-ports 5353"
    )

def unblock_youtube(ip):
    run_safe(
        f"iptables -t nat -C {YOUTUBE_CHAIN} -s {ip} -p udp --dport 53 -j REDIRECT --to-ports 5353 "
        f"&& iptables -t nat -D {YOUTUBE_CHAIN} -s {ip} -p udp --dport 53 -j REDIRECT --to-ports 5353"
    )
    run_safe(
        f"iptables -t nat -C {YOUTUBE_CHAIN} -s {ip} -p tcp --dport 53 -j REDIRECT --to-ports 5353 "
        f"&& iptables -t nat -D {YOUTUBE_CHAIN} -s {ip} -p tcp --dport 53 -j REDIRECT --to-ports 5353"
    )

def get_youtube_blocked_ips():
    blocked = set()
    output = run(f"iptables -t nat -L {YOUTUBE_CHAIN} -n")
    for line in output.splitlines():
        if "5353" in line:
            parts = line.split()
            for part in parts:
                if part.startswith(LAN_PREFIX):
                    blocked.add(part)
    return blocked
