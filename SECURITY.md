# Security Policy

## Overview

This project is a network firewall designed for school use. It controls student internet access and handles network-level traffic. Security issues should be taken seriously as vulnerabilities could allow students to bypass exam restrictions or compromise the school network.

---

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest (main branch) | ✅ Yes |
| Older commits | ❌ No — always use the latest version |

---

## Reporting a Vulnerability

If you discover a security vulnerability, **do not open a public GitHub Issue**.

Instead, please contact the project maintainer directly.

**What to include in your report:**
- Description of the vulnerability
- Steps to reproduce it
- Potential impact (e.g. students can bypass exam blocks, access admin dashboard)
- Any suggested fix if you have one

We will respond within a reasonable timeframe and coordinate a fix before any public disclosure.

---

## Known Security Considerations

### Dashboard Authentication
- The admin dashboard is protected by a password hash (scrypt)
- After 5 failed login attempts, the IP is locked out for 5 minutes
- Sessions expire after 10 minutes of inactivity
- **Recommendation:** Change the default password before deployment

### Network Security
- The dashboard should only be accessible from the school WAN network
- Student devices on the LAN (192.168.50.x) cannot access the dashboard
- All student DNS requests are forced through the firewall's dnsmasq

### Known Limitations
- HSTS-enabled sites (ChatGPT, Google) show a browser SSL error instead of the BUSTED page — this is expected behavior and they are still blocked
- Students with mobile data can bypass the firewall entirely — this is a hardware limitation
- VPN apps that use TCP port 443 (TLS-based VPNs) may bypass port-based VPN blocking

### Changing the Admin Password
To generate a new password hash:
```bash
cd ~/exam-firewall
source venv/bin/activate
python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('YOUR_NEW_PASSWORD'))"
```

Then update `ADMIN_PASSWORD_HASH` in `app.py`.

---

## Security Best Practices for Deployment

1. **Change the default admin password** before first use
2. **Keep Ubuntu updated**: `sudo apt update && sudo apt upgrade -y`
3. **Keep Python dependencies updated**: `pip install --upgrade -r requirements.txt`
4. **Restrict SSH access** to known admin IPs if possible
5. **Monitor logs** at `/var/log/exam-firewall.log` for unusual activity
6. **Reboot servers regularly** — daily 4 AM reboot is already configured
