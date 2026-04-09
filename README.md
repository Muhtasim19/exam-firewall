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
- Apple iCloud Private Relay is disabled on the network
- Controlled entirely from a **web dashboard**

---

## Why Use This System
During exams, students may try to access:
- AI tools (ChatGPT, OpenAI, Gemini, Claude, Perplexity, etc.)
- Online games (chess.com, lichess)
- Streaming sites (Netflix, YouTube)

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
- Disables Apple iCloud Private Relay
- Blocks selected websites using dnsmasq DNS filtering
- Auto-resolves AI service IPs dynamically on exam start
- Detects connected devices with IP, MAC, and hostname
- Allows individual device blocking/unblocking (drops ALL traffic)
- Kill switch to disconnect ALL students instantly
- Strict Mode — allows only Google Classroom and Docs
- Web dashboard with login, exam mode toggle, and device control
- Blocked domain list managed from GitHub
- Served via Nginx + Gunicorn (production ready)
- Server never sleeps (suspend/hibernate disabled)
- Live device logging to `/var/log/exam-firewall.log`
- Cron jobs for ARP refresh and device logging every minute

---

## Hardware Requirements
- 1 PC running Ubuntu 24.04.4 LTS
- 2 Ethernet ports:
  - **WAN** (`enp2s0`): connected to the internet router
  - **LAN** (`eno1`): connected to student devices via switch

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
│   └── style.css
│
├── templates/
│   ├── index.html                 ← Main dashboard
│   ├── login.html                 ← Admin login page
│   ├── analytics.html             ← Analytics dashboard
│   ├── analytics_login.html       ← Analytics login page
│   └── analytics_device.html     ← Device detail page
│
├── app.py                         ← Flask web application
├── firewall.py                    ← Firewall & DNS logic
├── analytics.py                   ← Analytics database logic
├── analytics_app.py               ← Analytics Flask app
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
```

Check they are up:
```bash
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
      dhcp4: true
    eno1:
      addresses:
        - 192.168.50.1/24
      dhcp4: false
```

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

### Step 4: Update System
```bash
sudo apt update && sudo apt upgrade -y
```

---

### Step 5: Enable IP Forwarding
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

### Step 6: Set Up NAT (Internet Sharing)
```bash
sudo iptables -t nat -A POSTROUTING -o enp2s0 -j MASQUERADE
sudo iptables -A FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT
sudo iptables -A FORWARD -i eno1 -o enp2s0 -j ACCEPT
sudo iptables -A FORWARD -i enp2s0 -o eno1 -m state --state RELATED,ESTABLISHED -j ACCEPT
```

---

### Step 7: Install isc-dhcp-server
```bash
sudo apt install isc-dhcp-server -y
```

Configure the DHCP interface:
```bash
sudo nano /etc/default/isc-dhcp-server
```

Set:
```
INTERFACESv4="eno1"
```

Configure DHCP leases:
```bash
sudo nano /etc/dhcp/dhcpd.conf
```

Replace entire file with:
```
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

Start and enable:
```bash
sudo systemctl enable isc-dhcp-server
sudo systemctl start isc-dhcp-server
```

> ⚠️ `authoritative` is required so managed Windows devices accept the DHCP offer.
> ⚠️ 86400 second (24 hour) leases prevent frequent reconnection issues.

---

### Step 8: Install and Configure dnsmasq
```bash
sudo apt install dnsmasq -y
```

Edit config:
```bash
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
```

Create dnsmasq override to wait for network on boot:
```bash
sudo mkdir -p /etc/systemd/system/dnsmasq.service.d/
sudo nano /etc/systemd/system/dnsmasq.service.d/override.conf
```

Paste:
```ini
[Unit]
After=network-online.target
Wants=network-online.target
```

Restart dnsmasq:
```bash
sudo systemctl daemon-reload
sudo systemctl enable dnsmasq
sudo systemctl restart dnsmasq
```

> ⚠️ `filter-AAAA` blocks IPv6 DNS responses so students cannot bypass DNS blocking using IPv6.

---

### Step 9: Force All DNS Through Firewall and Block Bypasses

```bash
# Redirect all DNS to firewall
sudo iptables -t nat -A PREROUTING -i eno1 -p udp --dport 53 -j REDIRECT --to-ports 53
sudo iptables -t nat -A PREROUTING -i eno1 -p tcp --dport 53 -j REDIRECT --to-ports 53
```

Block external DNS servers (use `-I` to insert at top):
```bash
sudo iptables -I FORWARD 1 -i eno1 -d 8.8.8.8 -j DROP
sudo iptables -I FORWARD 1 -i eno1 -d 8.8.4.4 -j DROP
sudo iptables -I FORWARD 1 -i eno1 -d 1.1.1.1 -j DROP
sudo iptables -I FORWARD 1 -i eno1 -d 1.0.0.1 -j DROP
sudo iptables -I FORWARD 1 -i eno1 -d 9.9.9.9 -j DROP
sudo iptables -I FORWARD 1 -i eno1 -d 208.67.222.222 -j DROP
sudo iptables -I FORWARD 1 -i eno1 -d 208.67.220.220 -j DROP
```

Block QUIC/HTTP3 to prevent proxy extension bypass:
```bash
sudo iptables -I FORWARD 1 -i eno1 -p udp --dport 443 -j DROP
```

Allow DHCP traffic:
```bash
sudo iptables -I INPUT -i eno1 -p udp --dport 67 -j ACCEPT
sudo iptables -I INPUT -i eno1 -p udp --dport 68 -j ACCEPT
```

Block IPv6 forwarding:
```bash
sudo ip6tables -I FORWARD 1 -i eno1 -j DROP
```

---

### Step 10: Disable Server Sleep
```bash
sudo systemctl mask sleep.target
sudo systemctl mask suspend.target
sudo systemctl mask hibernate.target
sudo systemctl mask hybrid-sleep.target
```

---

### Step 11: Save Firewall Rules
```bash
sudo apt install netfilter-persistent -y
sudo netfilter-persistent save
```

---

### Step 12: Fix NIC Ring Buffer (Prevents DHCP Packet Loss)

> ⚠️ This is critical! Some network cards drop DHCP packets under load due to
> small hardware buffers. This fix prevents students from losing internet randomly.

Check your NIC's buffer capacity:
```bash
sudo ethtool -g eno1
```

Increase the receive buffer:
```bash
sudo ethtool -G eno1 rx 4096
```

Make it permanent with a systemd service:
```bash
sudo nano /etc/systemd/system/optimize-eno1.service
```

Paste:
```ini
[Unit]
Description=Increase RX Ring Buffer on eno1
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/sbin/ethtool -G eno1 rx 4096
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl daemon-reload
sudo systemctl enable optimize-eno1.service
sudo systemctl start optimize-eno1.service
```

---

### Step 13: Install Required Tools
```bash
sudo apt install nmap git python3 python3-venv python3-pip arping -y
```

---

### Step 14: Clone the Project
```bash
cd ~
git clone https://github.com/Muhtasim19/exam-firewall.git
cd exam-firewall/exam-firewall
```

---

### Step 15: Set Up Python Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

---

### Step 16: Configure sudoers (Required for Dashboard)
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

### Step 17: Set Up Nginx (Main Dashboard)
```bash
sudo apt install nginx -y
sudo nano /etc/nginx/sites-available/exam-dashboard
```

Paste:
```nginx
server {
    listen 80;
    server_name _;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Enable:
```bash
sudo ln -s /etc/nginx/sites-available/exam-dashboard /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

Open ports:
```bash
sudo iptables -I INPUT -i enp2s0 -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT -i enp2s0 -p tcp --dport 8080 -j ACCEPT
sudo netfilter-persistent save
```

---

### Step 18: Set Up Nginx (Analytics Dashboard)
```bash
sudo nano /etc/nginx/sites-available/exam-analytics
```

Paste:
```nginx
server {
    listen 8080;
    server_name _;
    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Enable:
```bash
sudo ln -s /etc/nginx/sites-available/exam-analytics /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

### Step 19: Set Up Systemd Services (Auto-start)

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
WorkingDirectory=/home/admin_luniux/exam-firewall/exam-firewall
ExecStart=/home/admin_luniux/exam-firewall/exam-firewall/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:5000 app:app
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
WorkingDirectory=/home/admin_luniux/exam-firewall/exam-firewall
ExecStart=/home/admin_luniux/exam-firewall/exam-firewall/venv/bin/gunicorn --workers 1 --bind 127.0.0.1:5001 analytics_app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable both:
```bash
sudo systemctl daemon-reload
sudo systemctl enable exam-dashboard exam-analytics
sudo systemctl start exam-dashboard exam-analytics
```

---

### Step 20: Set Up Cron Jobs
```bash
sudo crontab -e
```

Add these three lines:
```
* * * * * ip neigh flush dev eno1 nud failed; ip neigh flush dev eno1 nud incomplete
* * * * * for i in $(seq 100 200); do ping -c 1 -W 1 192.168.50.$i > /dev/null 2>&1 & done
* * * * * cd /home/admin_luniux/exam-firewall/exam-firewall && /home/admin_luniux/exam-firewall/exam-firewall/venv/bin/python3 -c "import firewall; firewall.connected_devices()"
```

---

### Step 21: Verify Everything is Running
```bash
sudo systemctl is-active exam-dashboard exam-analytics nginx dnsmasq isc-dhcp-server optimize-eno1
```

All should show `active`.

Verify FORWARD chain:
```bash
sudo iptables -L FORWARD -n
```

Should show `EXAM_BLOCK` as first rule and DROP rules before ACCEPT rules.

---

## Optional: Install a Desktop GUI

> ℹ️ Not recommended for a firewall server. Only install if you specifically need
> a desktop on the server machine.

```bash
sudo apt install ubuntu-desktop -y
sudo reboot
```

> ⚠️ Uses 2-3 GB extra disk, 500 MB+ extra RAM, may slow down the firewall.

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

# Watch live device log
sudo tail -f /var/log/exam-firewall.log

# Check all services
sudo systemctl is-active exam-dashboard exam-analytics nginx dnsmasq isc-dhcp-server
```

### Update Blocked Websites
Edit `dns/blocked_domains.conf` on GitHub, then on the server:
```bash
cd ~/exam-firewall/exam-firewall
git pull
sudo systemctl reload dnsmasq
```

### After Server Reboot
```bash
cd ~/exam-firewall/exam-firewall
git pull
sudo systemctl restart exam-dashboard exam-analytics
```

---

## Blocked Domains (Current List)
Located in `dns/blocked_domains.conf`:

| Category | Sites |
|----------|-------|
| AI Tools | chatgpt.com, openai.com, claude.ai, gemini.google.com, perplexity.ai, grok.com, deepseek.com |
| AI Image | midjourney.com, leonardo.ai, dreamstudio.ai |
| AI Video | runwayml.com, pika.art, synthesia.io |
| AI Audio | elevenlabs.io, suno.ai |
| AI Coding | copilot.github.com, githubcopilot.com |
| Games | chess.com |
| Streaming | netflix.com, youtube.com |
| DoH Bypass | use-application-dns.net |
| Apple Relay | mask.icloud.com, mask-h2.icloud.com |

---

## Dashboard Features
- 🔐 Admin login with password protection and lockout after 5 failed attempts
- 📋 View all connected student devices (IP, MAC, Hostname, Status)
- 🔄 Manual device refresh using nmap subnet scan
- 🚫 Block / Unblock individual devices (cuts ALL internet for that device)
- ⛔ Kill All Internet — disconnects every student instantly
- ✅ Restore All Internet — brings everyone back online
- 🔴 Enable / Disable Exam Mode (blocks AI sites, auto-resolves IPs)
- 🔒 Enable / Disable Strict Mode (Classroom & Docs only)
- 🔄 Auto-refreshes every 10 seconds with countdown timer
- 📊 Separate analytics dashboard showing device history and events

---

## Bypass Prevention Summary

| Bypass Method | How We Block It |
|---------------|----------------|
| Change DNS settings | Force all port 53 to our server |
| Use Google/Cloudflare DNS | Block 8.8.8.8, 1.1.1.1, etc. via iptables |
| DNS over HTTPS (DoH) | Block UDP 443 + null-route DoH domains |
| IPv6 DNS | `filter-AAAA` in dnsmasq + ip6tables DROP |
| Apple iCloud Private Relay | Null-route mask.icloud.com domains |
| QUIC/HTTP3 proxy extensions | Block UDP port 443 |
| OpenDNS | Block 208.67.222.222 and 208.67.220.220 |

---

## Monitoring & Logs

| Log | Command |
|-----|---------|
| Live device log | `sudo tail -f /var/log/exam-firewall.log` |
| Dashboard logs | `sudo journalctl -u exam-dashboard -n 50 --no-pager` |
| Analytics logs | `sudo journalctl -u exam-analytics -n 50 --no-pager` |
| Nginx error log | `sudo tail -f /var/log/nginx/error.log` |
| dnsmasq log | `sudo journalctl -u dnsmasq -n 50 --no-pager` |
| DHCP log | `sudo journalctl -u isc-dhcp-server -n 50 --no-pager` |
| NIC buffer stats | `ip -s link show eno1` |
| All live logs | `sudo journalctl -f` |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Dashboard asks for Linux password | Add sudoers entries (Step 16) |
| Websites not blocked | Check `/etc/dnsmasq.conf` has `conf-dir=/etc/dnsmasq.d/,*.conf` |
| Sites blocked but IPv6 still works | Check `filter-AAAA` is in `/etc/dnsmasq.conf` |
| Hostnames show as Unknown | Check `isc-dhcp-server`: `sudo systemctl status isc-dhcp-server` |
| Dashboard not starting | Check service: `sudo systemctl status exam-dashboard` |
| Teacher cannot access dashboard | Check Nginx: `sudo systemctl status nginx` |
| Kill switch won't restore | Run `sudo iptables -D FORWARD -i eno1 -o enp2s0 -j DROP` until bad rule |
| dnsmasq fails on boot | Check override: `sudo systemctl cat dnsmasq` |
| Devices disappear from dashboard | Click Refresh Devices or wait for auto-refresh |
| Server goes to sleep | Run `sudo systemctl mask sleep.target suspend.target` |
| Student device gets 169.254.x.x | Run `ipconfig /release` then `ipconfig /renew` on device |
| DHCP not giving IPs | Check `authoritative` is in `/etc/dhcp/dhcpd.conf` |
| Internet drops on exam mode | dnsmasq uses `reload` not `restart` — check firewall.py |
| Network interface not up | Run `sudo ip link set eno1 up` and `sudo ip link set enp2s0 up` |
| No IP on WAN interface | Check netplan config: `sudo cat /etc/netplan/01-netcfg.yaml` |
| Devices randomly lose internet | Check NIC buffer: `ip -s link show eno1` — missed packets growing? Run Step 12 |
| DHCP packets dropped | Run `sudo systemctl status optimize-eno1` — NIC buffer fix applied? |

---

## Project Status
✅ Firewall routing and NAT working  
✅ DHCP assigning IPs to students (24 hour leases)  
✅ DNS filtering working  
✅ DNS hijacking (students cannot bypass)  
✅ IPv6 bypass blocked  
✅ DNS over HTTPS (DoH) bypass blocked  
✅ QUIC/HTTP3 proxy bypass blocked  
✅ Apple iCloud Private Relay disabled  
✅ OpenDNS blocked  
✅ NIC ring buffer optimized (prevents DHCP packet loss)  
✅ Flask dashboard with login  
✅ Nginx + Gunicorn production setup  
✅ Teacher access via `http://YOUR_WAN_IP`  
✅ Analytics dashboard via `http://YOUR_WAN_IP:8080`  
✅ Device detection with hostname  
✅ Individual device blocking/unblocking  
✅ Kill switch / Restore all internet  
✅ Exam mode with auto IP detection  
✅ Strict mode (Classroom & Docs only)  
✅ Manual device refresh with nmap  
✅ Auto-refresh with countdown timer  
✅ Live device logging to `/var/log/exam-firewall.log`  
✅ SQLite analytics database  
✅ Cron jobs for ARP flush and device logging  
✅ Auto-start on reboot  
✅ Server never sleeps  
✅ dnsmasq waits for network on boot  
✅ GitHub-managed block list  

---

## License
For educational and school use only.
