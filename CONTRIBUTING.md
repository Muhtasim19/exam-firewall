# Contributing to Linux Exam Firewall

Thank you for your interest in improving this project! This guide is written for future CS students or teachers who want to update or extend the system.

---

## Understanding the Project

Before making changes, read the [README](README.md) fully. The system runs on Ubuntu Server and controls student internet access via iptables, dnsmasq, and a Flask web dashboard.

**Key files to understand:**
- `firewall.py` — all iptables logic (blocking, exam mode, strict mode)
- `app.py` — Flask routes (what URLs do what)
- `custom_block.py` — per-session custom website blocking
- `youtube_block.py` — per-device YouTube blocking via secondary dnsmasq
- `templates/index.html` — the teacher dashboard UI

---

## Setting Up a Dev Environment

> ⚠️ Do NOT test on a live school server with students connected.
> Use a spare PC or VM.

**Requirements:**
- Ubuntu 24.04 LTS
- 2 network interfaces (WAN + LAN)
- Python 3.10+

**Steps:**
```bash
git clone https://github.com/Muhtasim19/exam-firewall.git
cd exam-firewall
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

Follow the full setup guide in [README.md](README.md) to configure iptables, dnsmasq, and DHCP.

---

## Making Changes

### Dashboard UI (HTML/CSS/JS)
- Edit `templates/index.html` for layout and buttons
- Edit `static/style.css` for styling
- Edit `static/script.js` for auto-refresh and sort behavior
- Test by restarting the dashboard: `sudo systemctl restart exam-dashboard`

### Adding a New Firewall Feature
1. Add the logic function to `firewall.py`
2. Add a Flask route to `app.py`
3. Add a button or form to `templates/index.html`
4. Test on a non-production server first

### Updating the Blocked Domain List
Edit `dns/blocked_domains.conf` — add lines like:
```
address=/newsite.com/192.168.50.1
```
Then on the server: `sudo systemctl restart dnsmasq`

### Updating Dependencies
```bash
source venv/bin/activate
pip install --upgrade flask gunicorn werkzeug
pip freeze > requirements.txt
```

> ⚠️ Test thoroughly after upgrading — Flask and Werkzeug breaking changes have caused issues before.

---

## Deploying Changes

After pushing to GitHub, on each server:
```bash
cd ~/exam-firewall
git pull
sudo systemctl restart exam-dashboard exam-analytics
```

There are currently **3 servers**:
| Server | IP | Room |
|--------|----|------|
| node1 (master) | 10.10.32.70 | Main classroom |
| adminlinux | 10.10.32.68 | Second classroom |
| node3 | 10.10.32.28 | Dr. Tupper's room |

---

## Things to Be Careful About

- **Never flush iptables without restoring rules** — students lose internet instantly
- **dnsmasq needs `restart` not `reload`** to pick up new conf files
- **The `youtube-block.conf` file must NOT be in `/etc/dnsmasq.d/`** — it will block YouTube for everyone
- **EXAM_BLOCK chain must exist before adding rules** — check `ensure_chain()` in `firewall.py`
- **Test on a non-production server first** before deploying to classrooms

---

## Suggesting Changes

If you're not sure about a change, open a GitHub Issue describing:
- What problem you're solving
- What you plan to change
- Any risks or side effects

---

## Architecture Notes for Future Developers

The system uses a dual-DNS approach for per-device YouTube blocking:
- Main dnsmasq runs on port 53 (normal DNS)
- Secondary dnsmasq runs on port 5353 (blocks YouTube domains)
- When a student's YouTube is blocked, iptables redirects their DNS port 53 → 5353

The blocked domains resolve to `192.168.50.1` (the firewall server's LAN IP) instead of `0.0.0.0` so students see a "BUSTED" page instead of a connection error.

---

## License

This project is for educational and school use only. See [LICENSE](LICENSE).
