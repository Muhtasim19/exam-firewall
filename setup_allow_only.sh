#!/bin/bash
# One-time setup for Allow-Only mode. Run once on EACH server:
#     cd ~/exam-firewall && sudo bash setup_allow_only.sh
set -e

if [ "$EUID" -ne 0 ]; then
    echo "Run with sudo:  sudo bash setup_allow_only.sh"
    exit 1
fi

cd "$(dirname "$0")"

if ss -lnuH 'sport = :5354' | grep -q . ; then
    if ! systemctl is-active --quiet dnsmasq-allowonly; then
        echo "Port 5354 is already used by something else. Stop and tell Claude what is using it:"
        ss -lnup 'sport = :5354'
        exit 1
    fi
fi

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

systemctl daemon-reload
systemctl enable dnsmasq-allowonly

# Writes /etc/dnsmasq-allowonly.conf from dns/allowed_sites.txt and starts the service
python3 allow_only.py

echo
systemctl --no-pager status dnsmasq-allowonly | head -5
echo
echo "Done. Restart the dashboard:  sudo systemctl restart exam-dashboard"
