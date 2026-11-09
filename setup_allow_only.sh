#!/bin/bash
# One-time setup for Allow-Only mode. Run once on EACH server
# (run it again after updates - it is safe to repeat):
#     cd ~/exam-firewall && sudo bash setup_allow_only.sh
set -e

if [ "$EUID" -ne 0 ]; then
    echo "Run with sudo:  sudo bash setup_allow_only.sh"
    exit 1
fi

cd "$(dirname "$0")"

check_port() {
    local port="$1" service="$2"
    if ss -lnuH "sport = :$port" | grep -q . ; then
        if ! systemctl is-active --quiet "$service"; then
            echo "Port $port is already used by something else. Stop and tell Claude what is using it:"
            ss -lnup "sport = :$port"
            exit 1
        fi
    fi
}

check_port 5354 dnsmasq-allowonly
check_port 5355 dnsmasq-allowonly-noyt

# Profile 1: Google + approved sites (YouTube allowed)
cat > /etc/systemd/system/dnsmasq-allowonly.service <<'EOF'
[Unit]
Description=dnsmasq for Allow-Only mode (port 5354)
After=network-online.target dnsmasq.service
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
ExecStart=/usr/sbin/dnsmasq --keep-in-foreground --conf-file=/etc/dnsmasq-allowonly.conf --pid-file=/run/dnsmasq-allowonly.pid
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Profile 2: same, but YouTube blocked (for students with the YouTube button on)
cat > /etc/systemd/system/dnsmasq-allowonly-noyt.service <<'EOF'
[Unit]
Description=dnsmasq for Allow-Only mode without YouTube (port 5355)
After=network-online.target dnsmasq.service
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
ExecStart=/usr/sbin/dnsmasq --keep-in-foreground --conf-file=/etc/dnsmasq-allowonly-noyt.conf --pid-file=/run/dnsmasq-allowonly-noyt.pid
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable dnsmasq-allowonly dnsmasq-allowonly-noyt

# Writes both config files from dns/allowed_sites.txt and starts the services
python3 allow_only.py || STATUS=$?

echo
systemctl --no-pager status dnsmasq-allowonly | head -5
echo
systemctl --no-pager status dnsmasq-allowonly-noyt | head -5
echo
if [ -n "$STATUS" ]; then
    echo "WARNING: setup finished with a problem (see the messages above)."
fi
echo "Done. Restart the dashboard:  sudo systemctl restart exam-dashboard"
