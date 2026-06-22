from flask import Flask, render_template, redirect, url_for, request, session, jsonify
from functools import wraps
from datetime import timedelta
from werkzeug.security import check_password_hash
from time import time
import firewall
import custom_block
import youtube_block
import os

# =========================
# APP CONFIG
# =========================
app = Flask(__name__)
app.secret_key = "3f8x92Kk29dk29s0dkX"
app.permanent_session_lifetime = timedelta(minutes=10)

# =========================
# ADMIN PASSWORD HASH
# =========================
ADMIN_PASSWORD_HASH = os.environ.get(
    "ADMIN_PASSWORD_HASH",
    "scrypt:32768:8:1$HfFB1ZMCjYvHQ5wD$fb02e9e3be4c6e9053a2dac4a1099b7387fcf36b19fccc97dec1e6b38114fe6e9f853aabe626403573a270df28e6da53d8a67eb17124d094f25b0fec4f50a790"
)

# =========================
# LOGIN ATTEMPT PROTECTION
# =========================
FAILED_LOGINS = {}
MAX_ATTEMPTS = 5
LOCKOUT_TIME = 300

# =========================
# DISABLE BROWSER CACHING
# =========================
@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# =========================
# LOGIN REQUIRED DECORATOR
# =========================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# =========================
# REFRESH SESSION ON ACTIVITY
# =========================
@app.before_request
def refresh_session():
    if session.get("logged_in"):
        session.permanent = True

# =========================
# LOGIN ROUTE
# =========================
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

    return render_template("login.html")

# =========================
# LOGOUT ROUTE
# =========================
@app.route("/logout")
def logout():
    session.clear()
    response = redirect(url_for("login"))
    response.delete_cookie("session")
    return response

# =========================
# DASHBOARD
# =========================
@app.route("/")
@login_required
def index():
    exam_status = firewall.exam_status()
    strict_status = firewall.strict_status()
    devices = firewall.connected_devices()
    network_status = firewall.network_status()
    custom_blocked = custom_block.get_custom_blocked()
    youtube_blocked_ips = youtube_block.get_youtube_blocked_ips()

    for device in devices:
        device["youtube_blocked"] = device["ip"] in youtube_blocked_ips

    return render_template(
        "index.html",
        exam_status=exam_status,
        strict_status=strict_status,
        devices=devices,
        network_status=network_status,
        custom_blocked=custom_blocked
    )

# =========================
# EXAM CONTROL
# =========================
@app.route("/exam/on")
@login_required
def exam_on():
    firewall.exam_on()
    return redirect(url_for("index"))

@app.route("/exam/off")
@login_required
def exam_off():
    firewall.exam_off()
    return redirect(url_for("index"))

# =========================
# STRICT MODE
# =========================
@app.route("/strict/on")
@login_required
def strict_on():
    firewall.strict_mode_on()
    return redirect(url_for("index"))

@app.route("/strict/off")
@login_required
def strict_off():
    firewall.strict_mode_off()
    return redirect(url_for("index"))

# =========================
# DEVICE CONTROL
# =========================
@app.route("/device/block/<ip>")
@login_required
def block_device(ip):
    firewall.block_device(ip)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"status": "blocked", "ip": ip})
    return redirect(url_for("index"))

@app.route("/device/unblock/<ip>")
@login_required
def unblock_device(ip):
    firewall.unblock_device(ip)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"status": "unblocked", "ip": ip})
    return redirect(url_for("index"))

# =========================
# RESET ALL BLOCKS
# =========================
@app.route("/device/reset_all")
@login_required
def reset_all_blocks():
    firewall.reset_all_blocks()
    return redirect(url_for("index"))

# =========================
# BLOCK / UNBLOCK ALL CRL
# =========================
@app.route("/device/block_all_crl")
@login_required
def block_all_crl():
    devices = firewall.connected_devices()
    firewall.block_all_devices(devices)
    return redirect(url_for("index"))

@app.route("/device/block_crl_only")
@login_required
def block_crl_only():
    devices = firewall.connected_devices()
    firewall.block_crl_only(devices)
    return redirect(url_for("index"))

@app.route("/device/unblock_all_crl")
@login_required
def unblock_all_crl():
    devices = firewall.connected_devices()
    firewall.unblock_all_devices(devices)
    return redirect(url_for("index"))

# =========================
# NETWORK KILL/RESTORE
# =========================
@app.route("/network/kill")
@login_required
def network_kill():
    firewall.kill_network()
    return redirect(url_for("index"))

@app.route("/network/restore")
@login_required
def network_restore():
    firewall.restore_network()
    return redirect(url_for("index"))

# =========================
# REFRESH DEVICES
# =========================
@app.route("/devices/refresh")
@login_required
def refresh_devices():
    firewall.connected_devices()
    return redirect(url_for("index"))

# =========================
# CUSTOM BLOCK
# =========================
@app.route("/custom/block", methods=["POST"])
@login_required
def custom_block_add():
    domain = request.form.get("domain", "").strip()
    if domain:
        custom_block.add_custom_block(domain)
    return redirect(url_for("index"))

@app.route("/custom/unblock/<domain>")
@login_required
def custom_block_remove(domain):
    custom_block.remove_custom_block(domain)
    return redirect(url_for("index"))

@app.route("/custom/clear")
@login_required
def custom_block_clear():
    custom_block.clear_all_custom_blocks()
    return redirect(url_for("index"))

# =========================
# YOUTUBE BLOCK
# =========================
@app.route("/youtube/block/<ip>")
@login_required
def youtube_block_device(ip):
    youtube_block.block_youtube(ip)
    return redirect(url_for("index"))

@app.route("/youtube/unblock/<ip>")
@login_required
def youtube_unblock_device(ip):
    youtube_block.unblock_youtube(ip)
    return redirect(url_for("index"))

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
