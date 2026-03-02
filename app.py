from flask import Flask, render_template, redirect, url_for, request, session
from functools import wraps
from datetime import timedelta
from werkzeug.security import check_password_hash
from time import time
import firewall
import os

# =========================
# APP CONFIG
# =========================
app = Flask(__name__)
app.secret_key = "3f8x92Kk29dk29s0dkX"

# Session timeout (10 min inactivity)
app.permanent_session_lifetime = timedelta(minutes=10)

# =========================
# ADMIN PASSWORD HASH
# =========================
# You can either:
# 1. Keep it here (simple setup)
# 2. Or move it to environment variable for higher security

ADMIN_PASSWORD_HASH = os.environ.get(
    "ADMIN_PASSWORD_HASH",
    "scrypt:32768:8:1$HfFB1ZMCjYvHQ5wD$fb02e9e3be4c6e9053a2dac4a1099b7387fcf36b19fccc97dec1e6b38114fe6e9f853aabe626403573a270df28e6da53d8a67eb17124d094f25b0fec4f50a790"
)

# =========================
# LOGIN ATTEMPT PROTECTION
# =========================
FAILED_LOGINS = {}
MAX_ATTEMPTS = 5
LOCKOUT_TIME = 300  # 5 minutes

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

    # Check lockout
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
    devices = firewall.connected_devices()

    return render_template(
        "index.html",
        exam_status=exam_status,
        devices=devices
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
# DEVICE CONTROL
# =========================
@app.route("/device/block/<mac>")
@login_required
def block_device(mac):
    firewall.block_device(mac)
    return redirect(url_for("index"))

@app.route("/device/unblock/<mac>")
@login_required
def unblock_device(mac):
    firewall.unblock_device(mac)
    return redirect(url_for("index"))

# =========================
# RUN (LOCALHOST ONLY)
# =========================
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
