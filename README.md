# Linux Exam Firewall

## Overview
Linux Exam Firewall is a network-based firewall system that blocks access to AI tools,
gaming websites, and entertainment platforms during school exams and quizzes.

It works at the **network level**, so:
- No software is installed on student devices
- Works on Windows, macOS, and Linux
- Students cannot bypass it by changing their DNS settings
- Students cannot bypass it using IPv6
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
- Blocks selected websites using dnsmasq DNS filtering
- Detects connected devices with IP, MAC, and hostname
- Allows individual device blocking/unblocking (drops ALL traffic)
- Kill switch to disconnect ALL students instantly
- Web dashboard with login, exam mode toggle, and device control
- Blocked domain list managed from GitHub
- Served via Nginx + Gunicorn (production ready)

---

## Hardware Requirements
- 1 PC running Ubuntu Server 22.04 LTS
- 2 Ethernet ports:
  - **WAN** (`enp2s0`): connected to the internet router
  - **LAN** (`eno1`): connected to student devices via switch

---

## Network Layout

```
Internet
│
Router / Modem  (10.10.32.1)
│
Linux Firewall Server  (WAN: 10.10.32.70 / LAN: 192.168.50.1)
│
Ethernet Switch
│
Student Devices  (192.168.50.100 – 192.168.50.254)
```

Teacher accesses dashboard via:
```
http://10.10.32.70
```

---

## Software Used
- Ubuntu Server 22.04 LTS
- `iptables` — firewall, routing, device blocking
- `ip6tables` — IPv6 blocking
- `isc-dhcp-server` — assigns IPs to student devices
- `dnsmasq` — DNS filtering (blocks websites)
- `netfilter-persistent` — saves firewall rules across reboots
- `Flask` — web dashboard backend
- `Gunicorn` — production WSGI server
- `Nginx` — reverse proxy (serves dashboard on port 80)
- `Python 3` — firewall logic
- `conntrack` — flushes existing connections on exam start

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
│   └── login.html                 ← Admin login page
│
├── app.py                         ← Flask web application
├── firewall.py                    ← Firewall & DNS logic
├── requirements.txt
└── README.md
```

---

## Step-by-Step Setup Guide

### Step 1: Install Ubuntu Server
1. Download Ubuntu Server 22.04 LTS
2. Install it on the firewall PC
3. Enable OpenSSH during setup (recommended)

---

### Step 2: Identify Network Interfaces
```bash
ip a
```
Note your two interfaces:
- Internet-facing (example: `enp2s0`)
- Student-facing (example: `eno1`)

---

### Step 3: Enable IP Forwarding
```bash
sudo sysctl -w net.ipv4.ip_forward=1
```

To make it permanent:
```bash
sudo nano /etc/sysctl.conf
# Uncomment or add:
net.ipv4.ip_forward=1
```

---

### Step 4: Set Up NAT (Internet Sharing)
```bash
sudo iptables -t nat -A POSTROUTING -o enp2s0 -j MASQUERADE
sudo iptables -A FORWARD -i eno1 -o enp2s0 -j ACCEPT
sudo iptables -A FORWARD -i enp2s0 -o eno1 -m state --state RELATED,ESTABLISHED -j ACCEPT
```

---

### Step 5: Install isc-dhcp-server
```bash
sudo apt update
sudo apt install isc-dhcp-server -y
```

Configure `/etc/dhcp/dhcpd.conf`:
```
subnet 192.168.50.0 netmask 255.255.255.0 {
  range 192.168.50.100 192.168.50.200;
  option routers 192.168.50.1;
  option domain-name-servers 192.168.50.1;
  default-lease-time 600;
  max-lease-time 600;
}
```

---

### Step 6: Install and Configure dnsmasq
```bash
sudo apt install dnsmasq -y
```

Edit `/etc/dnsmasq.conf`:
```
bind-interfaces
interface=eno1
server=8.8.8.8
server=8.8.4.4
no-resolv
conf-dir=/etc/dnsmasq.d/,*.conf
filter-AAAA
```

> ⚠️ `filter-AAAA` blocks IPv6 DNS responses so students cannot bypass DNS blocking using IPv6.

> ⚠️ Make sure `conf-dir=/etc/dnsmasq.d/,*.conf` is **uncommented** (no `#` at the start).

---

### Step 7: Force All DNS Through Firewall
```bash
sudo iptables -t nat -A PREROUTING -i eno1 -p udp --dport 53 -j REDIRECT --to-ports 53
sudo iptables -t nat -A PREROUTING -i eno1 -p tcp --dport 53 -j REDIRECT --to-ports 53
```

Block external DNS servers:
```bash
sudo iptables -A FORWARD -i eno1 -d 8.8.8.8 -j DROP
sudo iptables -A FORWARD -i eno1 -d 1.1.1.1 -j DROP
sudo iptables -A FORWARD -i eno1 -d 8.8.4.4 -j DROP
sudo iptables -A FORWARD -i eno1 -d 9.9.9.9 -j DROP
```

Block IPv6 forwarding:
```bash
sudo ip6tables -A FORWARD -i eno1 -j DROP
```

---

### Step 8: Save Firewall Rules
```bash
sudo apt install netfilter-persistent -y
sudo netfilter-persistent save
```

---

### Step 9: Clone the Project
```bash
cd ~
git clone https://github.com/Muhtasim19/exam-firewall.git
cd exam-firewall/exam-firewall
```

---

### Step 10: Set Up Python Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

---

### Step 11: Install conntrack
```bash
sudo apt install conntrack -y
```

---

### Step 12: Configure sudoers (Required for Dashboard)
The dashboard needs to run iptables and systemctl without password prompts.

```bash
sudo visudo
```

Add at the bottom (replace `admin_luniux` with your username):
```
admin_luniux ALL=(ALL) NOPASSWD: /sbin/iptables
admin_luniux ALL=(ALL) NOPASSWD: /usr/bin/systemctl
admin_luniux ALL=(ALL) NOPASSWD: /bin/cp
admin_luniux ALL=(ALL) NOPASSWD: /bin/rm
```

---

### Step 13: Set Up Nginx
```bash
sudo apt install nginx -y
sudo nano /etc/nginx/sites-available/exam-dashboard
```

Paste:
```nginx
server {
    listen 80;
    server_name 10.10.32.70;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/exam-dashboard /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

Open port 80:
```bash
sudo iptables -I INPUT -i enp2s0 -p tcp --dport 80 -j ACCEPT
sudo netfilter-persistent save
```

---

### Step 14: Set Up Systemd Service (Auto-start)
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

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable exam-dashboard
sudo systemctl start exam-dashboard
```

---

## Daily Use (After Setup)

### Access the Dashboard
Teacher opens a browser and goes to:
```
http://10.10.32.70
```

Login with your admin password.

---

### Update Blocked Websites
Edit `dns/blocked_domains.conf` on GitHub, then on the server:
```bash
cd ~/exam-firewall/exam-firewall
git pull
sudo systemctl restart dnsmasq
```

Then toggle Exam Mode off and on from the dashboard to reload the new list.

---

### After Server Reboot
```bash
cd ~/exam-firewall/exam-firewall
git pull
sudo systemctl restart exam-dashboard
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

To add more sites, edit `dns/blocked_domains.conf` on GitHub and pull on the server.

---

## Dashboard Features
- 🔐 Admin login with password protection and lockout after 5 failed attempts
- 📋 View all connected student devices (IP, MAC, Hostname, Status)
- 🚫 Block / Unblock individual devices (cuts ALL internet for that device)
- ⛔ Kill All Internet — disconnects every student instantly
- ✅ Restore All Internet — brings everyone back online
- 🔴 Enable / Disable Exam Mode
- 🔄 Auto-refreshes every 10 seconds

---

## How Device Blocking Works
- Uses `iptables` to drop ALL traffic from a student's IP
- Works through a custom chain called `EXAM_BLOCK`
- Block/unblock is instant from the dashboard
- Does not require exam mode to be active

---

## How DNS Blocking Works
1. Dashboard copies `dns/blocked_domains.conf` → `/etc/dnsmasq.d/exam-block.conf`
2. dnsmasq resolves blocked domains to `0.0.0.0` (unreachable)
3. All student DNS requests are forced through the firewall
4. `filter-AAAA` blocks IPv6 DNS responses — students cannot bypass using IPv6
5. Students cannot bypass by using Google DNS or Cloudflare DNS
6. `conntrack -F` flushes all existing connections when exam mode starts

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Dashboard asks for Linux password | Add sudoers entries (Step 12) |
| Websites not blocked | Check `/etc/dnsmasq.conf` has `conf-dir=/etc/dnsmasq.d/,*.conf` uncommented |
| Sites blocked but IPv6 still works | Check `filter-AAAA` is in `/etc/dnsmasq.conf` |
| Hostnames show as Unknown | Check `isc-dhcp-server` is running: `sudo systemctl status isc-dhcp-server` |
| Dashboard not starting | Check service: `sudo systemctl status exam-dashboard` |
| Teacher cannot access dashboard | Check Nginx: `sudo systemctl status nginx` |
| Kill switch won't restore | Run `sudo iptables -D FORWARD -i eno1 -o enp2s0 -j DROP` until it says bad rule |

---

## Project Status
✅ Firewall routing and NAT working  
✅ DHCP assigning IPs to students  
✅ DNS filtering working  
✅ DNS hijacking (students cannot bypass)  
✅ IPv6 bypass blocked  
✅ Flask dashboard with login  
✅ Nginx + Gunicorn production setup  
✅ Teacher access via `http://10.10.32.70`  
✅ Device detection with hostname  
✅ Individual device blocking/unblocking  
✅ Kill switch / Restore all internet  
✅ Exam mode flushes existing connections  
✅ Auto-start on reboot  
✅ GitHub-managed block list  


---

## License
For educational and school use only.
