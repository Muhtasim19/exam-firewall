# Linux Exam Firewall

## Overview
Linux Exam Firewall is a network-based system that blocks access to AI tools,
gaming websites, and entertainment platforms during quizzes or exams.

It works at the **network level**, so:
- No software is installed on student devices
- Works on Windows, macOS, and Linux
- Students cannot bypass it by changing DNS settings

This system is designed so a **Educator or school IT staff** can use it reliably.

---

## Why Use This System
During exams, students may try to access:
- AI tools (ChatGPT, OpenAI, Gemini, etc.)
- Online games (chess.com, lichess)
- Streaming sites (Netflix, YouTube)

Blocking at the device level is easy to bypass.
This firewall enforces rules **before traffic reaches the internet**.

---

## What This System Does
- Acts as a gateway between students and the internet
- Automatically gives IP addresses to student devices
- Forces all DNS requests through the firewall
- Blocks selected websites
- Allows normal educational websites

---

## Hardware Requirements
- 1 PC running Ubuntu Server (22.04 LTS recommended)
- 2 Ethernet ports:
  - **WAN**: connected to the internet
  - **LAN**: connected to student devices (direct cable or switch)

---

## Network Layout

Internet  
│  
Router / Modem  
│  
Linux Firewall Server  
│  
Ethernet / Switch  
│  
Student Devices  

---

## Software Used
- Ubuntu Server 22.04 LTS
- iptables (firewall & routing)
- dnsmasq (DNS filtering + DHCP)
- iptables-persistent (save firewall rules)

---

## Step-by-Step Setup Guide

### Step 1: Install Ubuntu Server
1. Download Ubuntu Server 22.04 LTS
2. Install it on the firewall PC
3. During setup:
   - Enable OpenSSH (optional but helpful)
   - No desktop environment needed

---

### Step 2: Identify Network Interfaces
Run:
```bash
ip a
```

You will see two Ethernet interfaces:
- One connected to the internet (example: `enp2s0`)
- One connected to students (example: `eno1`)

Write these down.

---

### Step 3: Enable Internet Forwarding
```bash
sudo sysctl -w net.ipv4.ip_forward=1
```

---

### Step 4: Set Up NAT (Internet Sharing)
Replace `enp2s0` with your **internet interface**:
```bash
sudo iptables -t nat -A POSTROUTING -o enp2s0 -j MASQUERADE
```

---

### Step 5: Allow Traffic Forwarding
Replace interface names if needed:
```bash
sudo iptables -A FORWARD -i eno1 -o enp2s0 -j ACCEPT
sudo iptables -A FORWARD -i enp2s0 -o eno1 -m state --state RELATED,ESTABLISHED -j ACCEPT
```

---

### Step 6: Install dnsmasq
```bash
sudo apt update
sudo apt install dnsmasq -y
```

---

### Step 7: Configure dnsmasq
Edit the config file:
```bash
sudo nano /etc/dnsmasq.conf
```

Add the following:

```
interface=eno1
bind-interfaces

# DHCP (automatic IPs for students)
dhcp-range=192.168.50.10,192.168.50.50,12h
dhcp-option=option:router,192.168.50.1
dhcp-option=option:dns-server,192.168.50.1

# Upstream DNS
server=8.8.8.8
server=1.1.1.1
```

Save:
- CTRL + O → ENTER
- CTRL + X

Restart:
```bash
sudo systemctl restart dnsmasq
```

---

### Step 8: Add Blocked Websites
Create a block list:
```bash
sudo nano /etc/dnsmasq.d/blocked.conf
```

Example blocked sites:

```
# AI tools
address=/chatgpt.com/0.0.0.0
address=/openai.com/0.0.0.0
address=/claude.ai/0.0.0.0
address=/perplexity.ai/0.0.0.0
address=/copilot.microsoft.com/0.0.0.0

# Streaming
address=/netflix.com/0.0.0.0
address=/youtube.com/0.0.0.0

# Games
address=/chess.com/0.0.0.0
address=/lichess.org/0.0.0.0
```

Restart dnsmasq:
```bash
sudo systemctl restart dnsmasq
```

---

### Step 9: Allow DNS Requests to Firewall
```bash
sudo iptables -I INPUT -i eno1 -p udp --dport 53 -j ACCEPT
sudo iptables -I INPUT -i eno1 -p tcp --dport 53 -j ACCEPT
```

---

### Step 10: Save Firewall Rules
```bash
sudo apt install iptables-persistent -y
sudo netfilter-persistent save
```

---

## How Educator Use It (Daily Use)

### Start Exam
- Plug student devices into the firewall network
- Devices automatically get internet access
- Blocked sites are unavailable

### End Exam
- Unplug student devices
- Or stop dnsmasq:
```bash
sudo systemctl stop dnsmasq
```

---

## Supported Devices
✔ Windows  
✔ macOS  
✔ Linux  

---

### Advance
---

## 🔘 Turning the Firewall ON and OFF (Exam Mode)


---


### 🔹 Exam Mode ON (Block AI, Games, Streaming)

This enables the firewall, DNS blocking, and automatic IP assignment.

On the **Linux server**, run:

```bash
sudo systemctl start dnsmasq
sudo netfilter-persistent reload
```

✅ Result:

* Students get internet automatically
* Blocked websites are inaccessible
* Works immediately

---

### 🔹 Exam Mode OFF (Normal Internet)

This disables DNS filtering and returns the network to normal.

On the **Linux server**, run:

```bash
sudo systemctl stop dnsmasq
```

✅ Result:

* DNS blocking stops
* Students will not have internet through this firewall
* Safe way to end an exam

---

### 🔹 Check Current Status

To see whether Exam Mode is ON or OFF:

```bash
systemctl status dnsmasq
```

* `active (running)` → **Exam Mode ON**
* `inactive (dead)` → **Exam Mode OFF**

---

## 🔁 Optional: One-Command Shortcuts

This makes it **very easy for you**.

### Create Exam ON command

```bash
sudo nano /usr/local/bin/exam-on
```

Paste:

```bash
#!/bin/bash
systemctl start dnsmasq
netfilter-persistent reload
echo "Exam Mode ENABLED"
```

Save, then:

```bash
sudo chmod +x /usr/local/bin/exam-on
```

---

### Create Exam OFF command

```bash
sudo nano /usr/local/bin/exam-off
```

Paste:

```bash
#!/bin/bash
systemctl stop dnsmasq
echo "Exam Mode DISABLED"
```

Save, then:

```bash
sudo chmod +x /usr/local/bin/exam-off
```

---

### How to Use 

```bash
sudo exam-on
```

➡️ Starts exam mode

```bash
sudo exam-off
```

➡️ Ends exam mode

This is **simple, safe, and professional**.

## Important Notes
- No Wi-Fi required
- No personal data is collected
- Students cannot bypass DNS
- Works immediately when plugged in



## Project Status
Tested and working.
Ready for classroom use.

---




