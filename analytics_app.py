from flask import Flask, render_template, redirect, url_for, request, session, jsonify
from functools import wraps
from datetime import timedelta, datetime
from werkzeug.security import check_password_hash
from time import time
import analytics
import dns_parser
import live_monitor
import os

# =========================
# APP CONFIG
# =========================
app = Flask(__name__, template_folder='templates')
app.secret_key = "an4ly71cs_s3cr3t_k3y_x9f2"

app.permanent_session_lifetime = timedelta(minutes=30)

ADMIN_PASSWORD_HASH = os.environ.get(
    "ADMIN_PASSWORD_HASH",
    "scrypt:32768:8:1$HfFB1ZMCjYvHQ5wD$fb02e9e3be4c6e9053a2dac4a1099b7387fcf36b19fccc97dec1e6b38114fe6e9f853aabe626403573a270df28e6da53d8a67eb17124d094f25b0fec4f50a790"
)

FAILED_LOGINS = {}
MAX_ATTEMPTS = 5
LOCKOUT_TIME = 300

@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

@app.before_request
def refresh_session():
    if session.get("logged_in"):
        session.permanent = True

@app.route("/login", methods=["GET", "POST"])
def login():
    client_ip = request.remote_addr
    if client_ip in FAILED_LOGINS:
        attempts, last_attempt = FAILED_LOGINS[client_ip]
        if attempts >= MAX_ATTEMPTS:
            if time() - last_attempt < LOCKOUT_TIME:
                return "Too many failed attempts. Try again in 5 minutes."
            else:
                FAILED_LOGINS.pop(client_ip)
    if request.method == "POST":
        password = request.form.get("password")
        if check_password_hash(ADMIN_PASSWORD_HASH, password):
            session.permanent = True
            session["logged_in"] = True
            FAILED_LOGINS.pop(client_ip, None)
            return redirect(url_for("index"))
        else:
            attempts, _ = FAILED_LOGINS.get(client_ip, (0, 0))
            FAILED_LOGINS[client_ip] = (attempts + 1, time())
    return render_template("analytics_login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    dns_parser.parse_dns_log()

    devices = analytics.get_device_summary()
    mode_events = analytics.get_mode_events()
    block_events = analytics.get_block_events()
    peak = analytics.get_peak_devices()
    hourly = analytics.get_hourly_counts()
    blocked_domains = dns_parser.get_blocked_domains()
    top_domains = dns_parser.get_top_blocked_domains()
    blocked_by_device = dns_parser.get_blocked_by_device()
    total_blocked = dns_parser.get_total_blocked_today()

    # Get current activity for all devices
    all_activity = live_monitor.get_all_devices_activity()

    # Get live blocked attempts from DNS log (works without exam mode)
    live_blocked_attempts = live_monitor.get_blocked_attempts(minutes=60, limit=200)

    return render_template(
        "analytics.html",
        devices=devices,
        mode_events=mode_events,
        block_events=block_events,
        peak=peak,
        hourly=hourly,
        blocked_domains=blocked_domains,
        top_domains=top_domains,
        blocked_by_device=blocked_by_device,
        total_blocked=total_blocked,
        all_activity=all_activity,
        live_blocked_attempts=live_blocked_attempts
    )

@app.route("/device/<ip>")
@login_required
def device_detail(ip):
    timeline = analytics.get_device_timeline(ip)
    dns_attempts = [d for d in dns_parser.get_blocked_domains() if d['ip'] == ip]
    live_attempts = [a for a in live_monitor.get_blocked_attempts(minutes=60, limit=200) if a['ip'] == ip]
    return render_template(
        "analytics_device.html",
        ip=ip,
        timeline=timeline,
        dns_attempts=dns_attempts,
        live_attempts=live_attempts
    )

# =========================
# API: Live blocked attempts (AJAX polling)
# =========================
@app.route("/api/blocked-attempts")
@login_required
def api_blocked_attempts():
    attempts = live_monitor.get_blocked_attempts(minutes=60, limit=200)
    return jsonify(attempts)

# =========================
# SERVER STATS API
# =========================
@app.route("/api/server-stats")
@login_required
def api_server_stats():
    stats = {}

    # RAM usage from /proc/meminfo
    try:
        with open("/proc/meminfo") as f:
            meminfo = {}
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    meminfo[parts[0].rstrip(":")] = int(parts[1])
        total = meminfo.get("MemTotal", 0)
        available = meminfo.get("MemAvailable", 0)
        used = total - available
        stats["ram_used_gb"] = round(used / 1024 / 1024, 1)
        stats["ram_total_gb"] = round(total / 1024 / 1024, 1)
        stats["ram_pct"] = round(used / total * 100) if total else 0
    except:
        stats["ram_used_gb"] = 0
        stats["ram_total_gb"] = 0
        stats["ram_pct"] = 0

    # Disk usage
    try:
        st = os.statvfs("/")
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        used = total - free
        stats["disk_used_gb"] = round(used / 1024 / 1024 / 1024, 1)
        stats["disk_total_gb"] = round(total / 1024 / 1024 / 1024, 1)
        stats["disk_pct"] = round(used / total * 100) if total else 0
    except:
        stats["disk_used_gb"] = 0
        stats["disk_total_gb"] = 0
        stats["disk_pct"] = 0

    # Uptime / last boot
    try:
        with open("/proc/uptime") as f:
            uptime_seconds = float(f.read().split()[0])
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        if days > 0:
            stats["uptime"] = f"{days}d {hours}h"
        else:
            stats["uptime"] = f"{hours}h {int((uptime_seconds % 3600) // 60)}m"
    except:
        stats["uptime"] = "unknown"

    # CPU load (1-min average)
    try:
        with open("/proc/loadavg") as f:
            stats["cpu_load"] = f.read().split()[0]
    except:
        stats["cpu_load"] = "0"

    return jsonify(stats)

# =========================
# LIVE MONITOR
# =========================
@app.route("/live/<ip>")
@login_required
def live(ip):
    devices = analytics.get_device_summary()
    hostname = "Unknown"
    for d in devices:
        if d['ip'] == ip:
            hostname = d['hostname']
            break

    activity = live_monitor.parse_live_activity(ip, minutes=10)
    current_site = live_monitor.get_current_site(ip)

    return render_template(
        "analytics_live.html",
        ip=ip,
        hostname=hostname,
        activity=activity,
        current_site=current_site
    )

if __name__ == "__main__":
    analytics.init_db()
    dns_parser.init_dns_table()
    app.run(host="0.0.0.0", port=5001)
