# Linux Exam Firewall

## Overview
Linux Exam Firewall is a network-based firewall system that blocks access to AI tools,
gaming websites, and entertainment platforms during school exams and quizzes.

It works at the **network level**, so:
- No software is installed on student devices
- Works on Windows, macOS, and Linux
- Students cannot bypass it by changing their DNS settings
- Students cannot bypass it using IPv6
- Students cannot bypass it using DNS over HTTPS (DoH)
- Students cannot bypass it using QUIC/HTTP3
- Students cannot bypass it using VPN software
- Apple iCloud Private Relay is disabled on the network
- Blocked sites show a "BUSTED" warning page
- Controlled entirely from a **web dashboard**

---

## Why Use This System
During exams, students may try to access:
- AI tools (ChatGPT, OpenAI, Gemini, Claude, Perplexity, etc.)
- Online games (chess.com, lichess)
- Streaming sites (Netflix, YouTube)
- VPN services to bypass the firewall

Blocking at the device level is easy to bypass.
This firewall enforces rules **before traffic reaches the internet**.

---

## What This System Does
- Acts as a gateway between students and the internet
- Automatically assigns IP addresses to student devices (DHCP)
- Forces all DNS requests through the firewall (DNS hijacking)
- Blocks IPv6 DNS responses to prevent bypass
- Blocks DNS over HTTPS (DoH) bypass attempts
- Blocks QUIC/HTTP3 (UDP 443) to prevent proxy extensions
- Blocks common VPN ports (OpenVPN, WireGuard, IPSec, PPTP)
- Disables Apple iCloud Private Relay
- Allows school domain controller access for Windows login
- Blocks selected websites using dnsmasq DNS filtering
- **Custom website blocking from dashboard** — block any site instantly
- Shows "BUSTED" warning page when students visit blocked sites
- Auto-resolves AI service IPs dynamically on exam start
- Detects connected devices with IP, MAC, and hostname
- Allows individual device blocking/unblocking (drops ALL traffic)
- Kill switch to disconnect ALL students instantly
- Strict Mode — allows only Google Classroom and Docs
- Web dashboard with login, exam mode toggle, and device control
- Blocked domain list managed from GitHub
- Served via Nginx + Gunicorn (production ready)
- Server never sleeps (suspend/hibernate disabled)
- Server reboots daily at 4 AM for stability
- Live device logging to `/var/log/exam-firewall.log`
- Cron jobs for ARP refresh and device logging every minute
- Live analytics dashboard with DNS query monitoring

---

## Hardware Requirements
- 1 PC running Ubuntu 24.04.4 LTS
- 2 Ethernet ports:
  - **WAN** (`enp2s0`): connected to the internet router
  - **LAN** (`eno1`): connected to student devices via switch

> ⚠️ **NIC Quality Matters**: Cheap or old network cards may drop DHCP packets
> under load due to small hardware buffers. See Step 12 for the fix. If problems
> persist, replace the LAN network card with a quality Intel or Realtek card.

> ℹ️ **If you add a new NIC or move a card to a different PCI slot**, the interface
> name will change. Use a udev rule (Step 3b) to force a consistent name regardless
> of which slot the card is in.

---

## Network Layout

```
Internet
│
Router / Modem
│
Linux Firewall Server  (WAN: YOUR_WAN_IP / LAN: 192.168.50.1)
│
Ethernet Switch
│
Student Devices  (192.168.50.100 – 192.168.50.200)
```

> ⚠️ Replace `YOUR_WAN_IP` with the actual IP your server gets from the school router.
> Run `ip a show enp2s0` to find it after setup.

Teacher/Admin accesses dashboard via:
```
http://YOUR_WAN_IP
```

Analytics dashboard via:
```
http://YOUR_WAN_IP:8080
```

SSH access:
```
ssh admin_luniux@YOUR_WAN_IP
```

---

## Software Used
- Ubuntu 24.04.4 LTS
- `iptables` — firewall, routing, device blocking
- `ip6tables` — IPv6 blocking
- `isc-dhcp-server` — assigns IPs to student devices
- `dnsmasq` — DNS filtering (blocks websites)
- `netfilter-persistent` — saves firewall rules across reboots
- `ethtool` — NIC ring buffer optimization
- `udev` — network interface naming rules
- `Flask` — web dashboard backend
- `Gunicorn` — production WSGI server (3 workers)
- `Nginx` — reverse proxy (serves dashboard on port 80)
- `nmap` — network scanning for device refresh
- `SQLite` — analytics database
- `Python 3` — firewall logic

---

## Project Structure

```
exam-firewall/
│
├── dns/
│   └── blocked_domains.conf       ← Website block list (edit this on GitHub)
│
├── static/
│   ├── script.js
│   ├── style.css
│   └── busted.html                ← Busted page shown to students
│
├── templates/
│   ├── index.html                 ← Main dashboard
│   ├── login.html                 ← Admin login page
│   ├── analytics.html             ← Analytics dashboard
│   ├── analytics_login.html       ← Analytics login
│   ├── analytics_device.html      ← Device detail page
│   └── analytics_live.html        ← Live student monitor
│
├── app.py                         ← Flask web application
├── firewall.py                    ← Firewall & DNS logic
├── custom_block.py                ← Custom website block logic
├── analytics.py                   ← Analytics database logic
├── analytics_app.py               ← Analytics Flask app
├── dns_parser.py                  ← DNS blocked domain parser
├── live_monitor.py                ← Live DNS activity monitor
├── requirements.txt
└── README.md
```

---

## Complete From-Scratch Setup Guide

### Step 1: Install Ubuntu 24.04.4 LTS
1. Download Ubuntu 24.04.4 LTS from ubuntu.com
2. Flash it to a USB drive using Balena Etcher or Rufus
3. Boot the PC from the USB drive
4. Follow the installer — choose **Ubuntu Server** (no desktop needed)
5. During setup:
   - Create user: `admin_luniux`
   - Enable OpenSSH server when asked
6. After install, reboot and remove the USB drive

> ℹ️ The server has no GUI — it's just a terminal. You control everything via SSH
> or the web dashboard. This is normal and recommended for a firewall server.

---

### Step 2: Bring Up Network Interfaces
```bash
sudo ip link set eno1 up
sudo ip link set enp2s0 up
ip a
```

---

### Step 3: Configure Network with Netplan
```bash
cd /etc/netplan
sudo nano 01-netcfg.yaml
```

Paste:
```yaml
network:
  version: 2
  ethernets:
    enp2s0:
      dhcp4: false
      addresses:
        - YOUR_WAN_IP/24
      routes:
        - to: default
          via: YOUR_GATEWAY_IP
      nameservers:
        addresses: [8.8.8.8, 8.8.4.4]
    eno1:
      addresses:
        - 192.168.50.1/24
      dhcp4: false
```

> ℹ️ Replace `YOUR_WAN_IP` and `YOUR_GATEWAY_IP` with your school network values.
> Use `dhcp4: true` for `enp2s0` if you prefer DHCP instead of a static IP.

Save, then apply:
```bash
sudo chmod 600 /etc/netplan/01-netcfg.yaml
sudo netplan apply
```

Note your WAN IP:
```bash
ip a show enp2s0 | grep inet
```

---

### Step 3b: Force Consistent Interface Names (udev Rule)

> ℹ️ **Do this if you added a new NIC or moved a card to a different PCI slot.**

Find the MAC address of each card:
```bash
ip a | grep -E "^[0-9]|link/ether"
```

Create a udev rule:
```bash
sudo nano /etc/udev/rules.d/10-network.rules
```

Paste (replace MAC addresses with your actual ones):
```
SUBSYSTEM=="net", ACTION=="add", ATTR{address}=="YOUR_WAN_CARD_MAC", NAME="enp2s0"
```

Apply:
```bash
sudo udevadm control --reload-rules
sudo reboot
```

---

### Step 4: Fix Hostname Resolution
```bash
sudo nano /etc/hosts
```

Make sure the first line includes your hostname:
```
127.0.0.1 localhost node1
```

---

### Step 5: Disable systemd-resolved (Critical for dnsmasq)

> ⚠️ **This is the most important step!** Ubuntu 24.04 runs `systemd-resolved`
> which holds port 53 and **prevents dnsmasq from starting**.

```bash
sudo nano /etc/systemd/resolved.conf
```

Find `#DNSStubListener=yes` and change it to:
```
DNSStubListener=no
```

Save, then apply:
```bash
sudo systemctl restart systemd-resolved
sudo rm /etc/resolv.conf
sudo ln -s /run/systemd/resolve/resolv.conf /etc/resolv.conf
```

---

### Step 6: Update System
```bash
sudo apt update && sudo apt upgrade -y
```

---

### Step 7: Enable IP Forwarding
```bash
sudo nano /etc/sysctl.conf
```

Add or uncomment:
```
net.ipv4.ip_forward=1
net.ipv4.neigh.default.gc_stale_time=300
```

Apply:
```bash
sudo sysctl -p
```

---

### Step 8: Set Up NAT (Internet Sharing)
```bash
sudo iptables -t nat -A POSTROUTING -o enp2s0 -j MASQUERADE
```

---

### Step 9: Install isc-dhcp-server
```bash
sudo apt install isc-dhcp-server -y
sudo nano /etc/default/isc-dhcp-server
```

Set:
```
INTERFACESv4="eno1"
```

```bash
sudo nano /etc/dhcp/dhcpd.conf
```

Replace **entire file** with exactly this:
```
log-facility local7;

authoritative;

default-lease-time 86400;
max-lease-time 86400;
ddns-update-style none;

subnet 192.168.50.0 netmask 255.255.255.0 {
    range 192.168.50.100 192.168.50.200;
    option routers 192.168.50.1;
    option domain-name-servers 192.168.50.1;
    option subnet-mask 255.255.255.0;
    option broadcast-address 192.168.50.255;
}
```

Configure DHCP logging:
```bash
sudo nano /etc/rsyslog.d/dhcp.conf
```

Paste:
```
local7.*    /var/log/dhcp.log
```

```bash
sudo systemctl restart rsyslog
sudo systemctl enable isc-dhcp-server
sudo systemctl start isc-dhcp-server
```

Add DHCP override to wait for eno1:
```bash
sudo mkdir -p /etc/systemd/system/isc-dhcp-server.service.d/
sudo nano /etc/systemd/system/isc-dhcp-server.service.d/override.conf
```

Paste:
```ini
[Unit]
After=network-online.target sys-subsystem-net-devices-eno1.device
Wants=network-online.target sys-subsystem-net-devices-eno1.device
```

```bash
sudo systemctl daemon-reload
```

---

### Step 10: Install and Configure dnsmasq
```bash
sudo apt install dnsmasq -y
sudo nano /etc/dnsmasq.conf
```

Replace with:
```
bind-interfaces
interface=eno1
server=8.8.8.8
server=8.8.4.4
no-resolv
conf-dir=/etc/dnsmasq.d/,*.conf
filter-AAAA
log-queries
log-facility=/var/log/dnsmasq.log

# School domain controller — allows Windows domain login
# Ask school IT for your domain name and DC IP
server=/cpsd.us/172.25.205.59
server=/aspen.cpsd.us/8.8.8.8
```

> ⚠️ Replace `cpsd.us` and `172.25.205.59` with your school's domain and DC IP.
> The `aspen` line prevents the DC from hijacking the Aspen student portal.

Create dnsmasq override:
```bash
sudo mkdir -p /etc/systemd/system/dnsmasq.service.d/
sudo nano /etc/systemd/system/dnsmasq.service.d/override.conf
```

Paste:
```ini
[Unit]
After=network-online.target sys-subsystem-net-devices-eno1.device
Wants=network-online.target sys-subsystem-net-devices-eno1.device
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable dnsmasq
sudo systemctl restart dnsmasq
```

---

### Step 11: Build the Firewall Rules (Correct Order)

> ⚠️ **Order matters!** Rules must be added in this exact sequence.

Create EXAM_BLOCK chain:
```bash
sudo iptables -N EXAM_BLOCK
sudo iptables -A EXAM_BLOCK -j RETURN
```

DNS redirect:
```bash
sudo iptables -t nat -A PREROUTING -i eno1 -p udp --dport 53 -j REDIRECT --to-ports 53
sudo iptables -t nat -A PREROUTING -i eno1 -p tcp --dport 53 -j REDIRECT --to-ports 53
```

Allow domain controller traffic (Windows login):
```bash
sudo iptables -I FORWARD 1 -i eno1 -d 172.25.205.59 -j ACCEPT
sudo iptables -I FORWARD 1 -i eno1 -d 172.25.205.123 -j ACCEPT
sudo iptables -I FORWARD 1 -s 172.25.205.59 -o eno1 -j ACCEPT
sudo iptables -I FORWARD 1 -s 172.25.205.123 -o eno1 -j ACCEPT
```

Build FORWARD chain:
```bash
# Dashboard control chain
sudo iptables -A FORWARD -j EXAM_BLOCK

# Allow established connections
sudo iptables -A FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT

# Block external DNS servers
sudo iptables -A FORWARD -i eno1 -d 8.8.8.8 -j DROP
sudo iptables -A FORWARD -i eno1 -d 8.8.4.4 -j DROP
sudo iptables -A FORWARD -i eno1 -d 1.1.1.1 -j DROP
sudo iptables -A FORWARD -i eno1 -d 1.0.0.1 -j DROP
sudo iptables -A FORWARD -i eno1 -d 9.9.9.9 -j DROP
sudo iptables -A FORWARD -i eno1 -d 208.67.222.222 -j DROP
sudo iptables -A FORWARD -i eno1 -d 208.67.220.220 -j DROP

# Block QUIC/HTTP3
sudo iptables -A FORWARD -i eno1 -p udp --dport 443 -j DROP

# Block VPN ports
sudo iptables -A FORWARD -i eno1 -p udp --dport 1194 -j DROP
sudo iptables -A FORWARD -i eno1 -p tcp --dport 1194 -j DROP
sudo iptables -A FORWARD -i eno1 -p udp --dport 51820 -j DROP
sudo iptables -A FORWARD -i eno1 -p udp --dport 500 -j DROP
sudo iptables -A FORWARD -i eno1 -p udp --dport 4500 -j DROP
sudo iptables -A FORWARD -i eno1 -p tcp --dport 1723 -j DROP

# Allow normal internet traffic
sudo iptables -A FORWARD -i eno1 -o enp2s0 -j ACCEPT
sudo iptables -A FORWARD -i enp2s0 -o eno1 -m state --state RELATED,ESTABLISHED -j ACCEPT
```

Allow DHCP:
```bash
sudo iptables -I INPUT -i eno1 -p udp --dport 67 -j ACCEPT
sudo iptables -I INPUT -i eno1 -p udp --dport 68 -j ACCEPT
```

Block IPv6:
```bash
sudo ip6tables -A FORWARD -i eno1 -j DROP
```

---

### Step 12: Fix NIC Ring Buffer (Prevents DHCP Packet Loss)

```bash
sudo ethtool -g eno1
sudo ethtool -g enp2s0
sudo ethtool -G eno1 rx 4096
sudo ethtool -G enp2s0 rx 256
```

> ℹ️ Use the Pre-set maximum values shown for your specific cards.

Make permanent:
```bash
sudo nano /etc/systemd/system/optimize-eno1.service
```

Paste:
```ini
[Unit]
Description=Increase RX Ring Buffer on NICs
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c '/sbin/ethtool -G eno1 rx 4096; /sbin/ethtool -G enp2s0 rx 256'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable optimize-eno1.service
sudo systemctl start optimize-eno1.service
```

---

### Step 13: Disable Server Sleep
```bash
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
```

---

### Step 14: Save Firewall Rules
```bash
sudo apt install netfilter-persistent -y
sudo netfilter-persistent save
```

---

### Step 15: Install Required Tools
```bash
sudo apt install nmap git python3 python3-venv python3-pip -y
```

---

### Step 16: Clone the Project
```bash
cd ~
git clone https://github.com/Muhtasim19/exam-firewall.git
cd exam-firewall
```

---

### Step 17: Set Up Python Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
deactivate
```

---

### Step 18: Configure sudoers (Required for Dashboard)
```bash
sudo visudo
```

Add at the bottom:
```
admin_luniux ALL=(ALL) NOPASSWD: /sbin/iptables
admin_luniux ALL=(ALL) NOPASSWD: /usr/sbin/ip6tables
admin_luniux ALL=(ALL) NOPASSWD: /usr/bin/systemctl
admin_luniux ALL=(ALL) NOPASSWD: /bin/cp
admin_luniux ALL=(ALL) NOPASSWD: /bin/rm
admin_luniux ALL=(ALL) NOPASSWD: /usr/bin/nmap
admin_luniux ALL=(ALL) NOPASSWD: /usr/bin/conntrack
admin_luniux ALL=(ALL) NOPASSWD: /usr/sbin/arping
```

---

### Step 19: Set Up Nginx (Main Dashboard)
```bash
sudo apt install nginx -y
sudo nano /etc/nginx/sites-available/exam-dashboard
```

Paste (replace `YOUR_WAN_IP` with your actual WAN IP):
```nginx
server {
    listen 80;
    server_name YOUR_WAN_IP;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/exam-dashboard /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

---

### Step 19b: Set Up Busted Page (Shown to Students on Blocked Sites)

```bash
sudo mkdir -p /var/www/busted
sudo cp ~/exam-firewall/static/busted.html /var/www/busted/index.html
```

Create SSL certificate:
```bash
sudo mkdir -p /etc/nginx/ssl
sudo openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/busted.key \
  -out /etc/nginx/ssl/busted.crt \
  -subj "/CN=192.168.50.1"
```

Create Nginx config:
```bash
sudo nano /etc/nginx/sites-available/busted
```

Paste:
```nginx
server {
    listen 80;
    listen 443 ssl;
    server_name 192.168.50.1;
    ssl_certificate /etc/nginx/ssl/busted.crt;
    ssl_certificate_key /etc/nginx/ssl/busted.key;
    root /var/www/busted;
    index index.html;
    location / {
        try_files $uri $uri/ =404;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/busted /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

> ℹ️ Students visiting blocked sites will see a "BUSTED" warning page instead
> of a generic connection error. HSTS-enabled sites (ChatGPT etc.) will show
> a browser SSL warning instead — they are still blocked.

---

### Step 20: Set Up Nginx (Analytics Dashboard)
```bash
sudo nano /etc/nginx/sites-available/exam-analytics
```

Paste (replace `YOUR_WAN_IP` with your actual WAN IP):
```nginx
server {
    listen 8080;
    server_name YOUR_WAN_IP;
    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/exam-analytics /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
sudo iptables -I INPUT -i enp2s0 -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT -i enp2s0 -p tcp --dport 8080 -j ACCEPT
sudo netfilter-persistent save
```

---

### Step 21: Set Up Systemd Services

Main dashboard:
```bash
sudo nano /etc/systemd/system/exam-dashboard.service
```

Paste:
```ini
[Unit]
Description=Exam Firewall Dashboard
After=network.target

[Service]
User=root
WorkingDirectory=/home/admin_luniux/exam-firewall
ExecStart=/home/admin_luniux/exam-firewall/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:5000 app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Analytics dashboard:
```bash
sudo nano /etc/systemd/system/exam-analytics.service
```

Paste:
```ini
[Unit]
Description=Exam Firewall Analytics Dashboard
After=network.target

[Service]
User=root
WorkingDirectory=/home/admin_luniux/exam-firewall
ExecStart=/home/admin_luniux/exam-firewall/venv/bin/gunicorn --workers 1 --bind 127.0.0.1:5001 analytics_app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable exam-dashboard exam-analytics
sudo systemctl start exam-dashboard exam-analytics
```

---

### Step 22: Set Up Cron Jobs
```bash
sudo crontab -e
```

Add these lines:
```
* * * * * ip neigh flush dev eno1 nud failed; ip neigh flush dev eno1 nud incomplete
* * * * * for i in $(seq 100 200); do ping -c 1 -W 1 192.168.50.$i > /dev/null 2>&1 & done
* * * * * cd /home/admin_luniux/exam-firewall && /home/admin_luniux/exam-firewall/venv/bin/python3 -c "import firewall; firewall.connected_devices()"
0 4 * * * /sbin/reboot
```

> ℹ️ The last line reboots the server daily at 4 AM for stability.

---

### Step 23: Set Up Log Rotation
```bash
sudo nano /etc/logrotate.d/dnsmasq
```

Paste:
```
/var/log/dnsmasq.log {
    daily
    rotate 2
    compress
    missingok
    notifempty
    create 644 root root
    su root root
    postrotate
        systemctl restart dnsmasq
    endscript
}
```

---

### Step 24: Verify Everything is Running
```bash
sudo systemctl is-active exam-dashboard exam-analytics nginx dnsmasq isc-dhcp-server
sudo iptables -L FORWARD -n | head -10
ip -s link show eno1 | grep missed
```

All services should show `active` and missed packets should be `0`.

---

## Optional: Install a Desktop GUI

> ℹ️ Not recommended. Only install if you specifically need a desktop.

```bash
sudo apt install ubuntu-desktop -y
sudo reboot
```

> ⚠️ Uses 2-3 GB extra disk, 500 MB+ extra RAM, may slow down the firewall.
> On Ubuntu Desktop, NetworkManager may fight with Netplan — use nmcli or
> a systemd service to set the LAN IP instead.

---

## Domain Controller Setup (Windows Login)

> ℹ️ This allows students to login with school domain credentials while
> connected to the exam firewall network.

**Step 1 — Discover domain controller using nmap:**
```bash
sudo nmap -p 53,88,389,445 YOUR_DC_IP
```

**Step 2 — Allow DC traffic in iptables:**
```bash
sudo iptables -I FORWARD 1 -i eno1 -d YOUR_DC_IP -j ACCEPT
sudo iptables -I FORWARD 1 -s YOUR_DC_IP -o eno1 -j ACCEPT
sudo netfilter-persistent save
```

**Step 3 — Add DC DNS to dnsmasq:**
```bash
sudo nano /etc/dnsmasq.conf
```

Add:
```
server=/yourdomain.us/YOUR_DC_IP
server=/aspen.yourdomain.us/8.8.8.8
```

```bash
sudo systemctl restart dnsmasq
```

> ℹ️ The `aspen` line prevents the DC from hijacking the Aspen student portal.
> Add similar lines for any other web portals that use your school domain.

---

## Updating the System

After any code changes on GitHub:
```bash
cd ~/exam-firewall
git pull
sudo systemctl restart exam-dashboard exam-analytics
```

---

## Student Device Troubleshooting

If a student device has no internet after connecting:

**Windows — run as Administrator:**
```cmd
ipconfig /release
ipconfig /flushdns
ipconfig /renew
```

This releases the old school network IP and gets a fresh `192.168.50.x` from the firewall.

---

## Blocking Sites During Class

### Using Custom Block (instant, no restart needed):
1. Go to dashboard → **Custom Website Block** section
2. Type the domain (e.g. `nytimes.com`)
3. Click **🚫 Block Site**
4. Site is blocked within seconds — students see the BUSTED page

### To clear existing connections instantly:
1. Click **⛔ Kill All Internet**
2. Add the domain to custom block
3. Click **✅ Restore All Internet**
4. All students reconnect with fresh DNS — site is blocked

---

## Daily Use (After Setup)

### Access the Dashboards
```
Main dashboard:      http://YOUR_WAN_IP
Analytics dashboard: http://YOUR_WAN_IP:8080
```

### Monitor via SSH
```bash
ssh admin_luniux@YOUR_WAN_IP
sudo systemctl is-active exam-dashboard exam-analytics nginx dnsmasq isc-dhcp-server
ip -s link show eno1 | grep missed
```

---

## Blocked Domains (Current List)
Located in `dns/blocked_domains.conf`:

| Category | Sites |
|----------|-------|
| AI Tools | chatgpt.com, openai.com, claude.ai, gemini.google.com, perplexity.ai, grok.com, deepseek.com |
| AI Writing | grammarly.com, quillbot.com, wordtune.com |
| AI Image | midjourney.com, leonardo.ai, dreamstudio.ai |
| AI Video | runwayml.com, pika.art, synthesia.io |
| AI Audio | elevenlabs.io, suno.ai |
| AI Coding | copilot.github.com, githubcopilot.com |
| Homework | chegg.com, coursehero.com, brainly.com, quizlet.com |
| Games | chess.com, lichess.org |
| Streaming | netflix.com, youtube.com, twitch.tv |
| VPN Services | nordvpn.com, expressvpn.com, protonvpn.com, surfshark.com |
| Remote Access | teamviewer.com, anydesk.com |
| DoH Bypass | use-application-dns.net, dns.google, cloudflare-dns.com |
| Apple Relay | mask.icloud.com, mask-h2.icloud.com |

---

## Dashboard Features
- 🔐 Admin login with password protection and lockout after 5 failed attempts
- 📋 View all connected student devices (IP, MAC, Hostname, Status)
- 🔢 Sort devices by hostname number (click Hostname column)
- 🔄 Manual device refresh using nmap subnet scan
- 🚫 Block / Unblock individual devices (cuts ALL internet for that device)
- ⛔ Kill All Internet — disconnects every student instantly
- ✅ Restore All Internet — brings everyone back online
- 🔴 Enable / Disable Exam Mode (blocks AI sites, auto-resolves IPs)
- 🔒 Enable / Disable Strict Mode (Classroom & Docs only)
- 🌐 Custom Website Block — block any site instantly from dashboard
- 🗑️ Clear All Custom Blocks — removes all custom blocks at once
- 💀 Blocked sites show "BUSTED" warning page to students
- 🔄 Auto-refreshes every 10 seconds with countdown timer
- 📖 Quick Reference panel — explains each button
- 📊 Separate analytics dashboard at port 8080
- 🔍 Live student monitor — see what each device is browsing in real time

---

## Bypass Prevention Summary

| Bypass Method | How We Block It |
|---------------|----------------|
| Change DNS settings | Force all port 53 to our server |
| Use Google/Cloudflare DNS | Block 8.8.8.8, 1.1.1.1 etc. via iptables |
| DNS over HTTPS (DoH) | Block UDP 443 + null-route DoH domains |
| IPv6 DNS | `filter-AAAA` in dnsmasq + ip6tables DROP |
| Apple iCloud Private Relay | Null-route mask.icloud.com domains |
| QUIC/HTTP3 proxy extensions | Block UDP port 443 |
| OpenDNS | Block 208.67.222.222 and 208.67.220.220 |
| OpenVPN | Block UDP/TCP port 1194 |
| WireGuard | Block UDP port 51820 |
| IPSec/IKEv2 | Block UDP ports 500 and 4500 |
| PPTP VPN | Block TCP port 1723 |
| VPN websites | Blocked via DNS in blocked_domains.conf |

---

## Monitoring & Logs

| Log | Command |
|-----|---------|
| Live device log | `sudo tail -f /var/log/exam-firewall.log` |
| DHCP log | `sudo tail -f /var/log/dhcp.log` |
| DNS query log | `sudo tail -f /var/log/dnsmasq.log` |
| Dashboard logs | `sudo journalctl -u exam-dashboard -n 50 --no-pager` |
| Analytics logs | `sudo journalctl -u exam-analytics -n 50 --no-pager` |
| Nginx error log | `sudo tail -f /var/log/nginx/error.log` |
| NIC hardware stats | `ip -s link show eno1` |
| All live logs | `sudo journalctl -f` |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| dnsmasq fails to start | Run `sudo ss -tulpn \| grep :53` — disable `systemd-resolved` (Step 5) |
| dnsmasq fails after reboot | Check override.conf has `sys-subsystem-net-devices-eno1.device` (Step 10) |
| Interface name changed after NIC swap | Create udev rule (Step 3b) to force consistent name |
| No internet after NIC swap | Update Netplan and NAT rule to use new interface name |
| `sudo` hostname error | Add hostname to `/etc/hosts`: `127.0.0.1 localhost node1` |
| Dashboard asks for Linux password | Add sudoers entries (Step 18) |
| Websites not blocked | Check `/etc/dnsmasq.conf` has `conf-dir=/etc/dnsmasq.d/,*.conf` |
| Sites blocked but IPv6 still works | Check `filter-AAAA` is in `/etc/dnsmasq.conf` |
| Hostnames show as Unknown | Check `isc-dhcp-server`: `sudo systemctl status isc-dhcp-server` |
| Dashboard not starting | Check service: `sudo systemctl status exam-dashboard` |
| Teacher cannot access dashboard | Check Nginx: `sudo systemctl status nginx` |
| Kill switch won't restore | Run `sudo iptables -D FORWARD -i eno1 -o enp2s0 -j DROP` until bad rule |
| Devices disappear from dashboard | Click Refresh Devices or wait for auto-refresh |
| Server goes to sleep | Run `sudo systemctl mask sleep.target suspend.target` |
| Student device gets 169.254.x.x | Run `ipconfig /release` then `ipconfig /renew` on device |
| Student has no internet after connecting | Run `ipconfig /release && ipconfig /flushdns && ipconfig /renew` |
| DHCP crashes with extra lines | Clean dhcpd.conf — only keep the exact format from Step 9 |
| DHCP not giving IPs | Check `authoritative` is in `/etc/dhcp/dhcpd.conf` |
| DHCP fails after reboot | Add override.conf to isc-dhcp-server to wait for eno1 (Step 9) |
| Custom block not working | Check dnsmasq uses `restart` not `reload` in custom_block.py |
| Custom block slow to take effect | Kill All Internet → add block → Restore Internet |
| Busted page shows on teacher dashboard | Change `server_name` from `_` to `YOUR_WAN_IP` in exam-dashboard nginx config |
| Blocked sites show SSL error not busted page | Normal for HSTS sites — students are still blocked |
| Devices randomly lose internet | Check NIC: `ip -s link show eno1` — missed packets growing? |
| DHCP packets dropped by NIC | Run `sudo ethtool -g eno1` — is RX at maximum? |
| Missed packets keep climbing | NIC hardware is failing — replace the network card |
| FORWARD chain wrong order | Run `sudo iptables-save -c` and verify EXAM_BLOCK is correct |
| Windows domain login fails | Check DC rules in iptables and dnsmasq DC DNS entry (Step 11) |
| Aspen portal not loading | Add `server=/aspen.cpsd.us/8.8.8.8` to dnsmasq.conf |
| Server loses internet after days | Daily 4 AM reboot via cron handles this automatically |

---

## Project Status
✅ Firewall routing and NAT working  
✅ DHCP assigning IPs to students (24 hour leases)  
✅ DHCP logging to `/var/log/dhcp.log`  
✅ DHCP waits for eno1 before starting  
✅ DNS filtering working  
✅ DNS hijacking (students cannot bypass)  
✅ IPv6 bypass blocked  
✅ DNS over HTTPS (DoH) bypass blocked  
✅ QUIC/HTTP3 proxy bypass blocked  
✅ VPN ports blocked (OpenVPN, WireGuard, IPSec, PPTP)  
✅ VPN service websites blocked  
✅ Apple iCloud Private Relay disabled  
✅ OpenDNS blocked  
✅ Windows domain login working (DC whitelisted)  
✅ Aspen student portal working  
✅ systemd-resolved disabled (no port 53 conflict)  
✅ NIC ring buffer optimized  
✅ udev rule for consistent interface naming  
✅ dnsmasq waits for eno1 before starting  
✅ iptables FORWARD chain correct order  
✅ EXAM_BLOCK chain connected  
✅ Flask dashboard with login  
✅ Quick Reference panel on dashboard  
✅ Hostname sort (click column to sort 1→19)  
✅ Custom website block from dashboard (instant, no restart)  
✅ Busted page shown to students on blocked sites  
✅ Nginx + Gunicorn production setup  
✅ Teacher access via `http://YOUR_WAN_IP`  
✅ Analytics dashboard via `http://YOUR_WAN_IP:8080`  
✅ Live student monitor per device  
✅ DNS blocked domain logging  
✅ Device detection with hostname  
✅ Individual device blocking/unblocking  
✅ Kill switch / Restore all internet  
✅ Exam mode with auto IP detection  
✅ Strict mode (Classroom & Docs only)  
✅ Manual device refresh with nmap  
✅ Auto-refresh with countdown timer  
✅ Live device logging  
✅ SQLite analytics database  
✅ Cron jobs for ARP flush and device logging  
✅ Daily 4 AM reboot for stability  
✅ Log rotation (2 days compressed)  
✅ Auto-start on reboot  
✅ Server never sleeps  
✅ GitHub-managed block list  
✅ Static WAN IP configured  

---

## License
For educational and school use only.
