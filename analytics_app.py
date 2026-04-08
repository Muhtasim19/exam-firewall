from flask import Flask, render_template, redirect, url_for, request, session
from functools import wraps
from datetime import timedelta
from werkzeug.security import check_password_hash
from time import time
import analytics
import os

# =========================
# APP CONFIG
# =========================
app = Flask(__name__, template_folder='templates')
app.secret_key = "an4ly71cs_s3cr3t_k3y_x9f2"

app.permanent_session_lifetime = timedelta(minutes=30)

# Same password hash as main dashboard
ADMIN_PASSWORD_HASH = os.environ.get(
    "ADMIN_PASSWORD_HASH",
    "scrypt:32768:8:1$HfFB1ZMCjYvHQ5wD$fb02e9e3be4c6e9053a2dac4a1099b7387fcf36b19fccc97dec1e6b38114fe6e9f853aabe626403573a270df28e6da53d8a67eb17124d094f25b0fec4f50a790"
)

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
# LOGIN REQUIRED
# =========================
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

# =========================
# LOGIN
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

    return render_template("analytics_login.html")

# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# =========================
# MAIN DASHBOARD
# =========================
@app.route("/")
@login_required
def index():
    devices = analytics.get_device_summary()
    mode_events = analytics.get_mode_events()
    block_events = analytics.get_block_events()
    peak = analytics.get_peak_devices()
    hourly = analytics.get_hourly_counts()

    return render_template(
        "analytics.html",
        devices=devices,
        mode_events=mode_events,
        block_events=block_events,
        peak=peak,
        hourly=hourly
    )

# =========================
# DEVICE DETAIL
# =========================
@app.route("/device/<ip>")
@login_required
def device_detail(ip):
    timeline = analytics.get_device_timeline(ip)
    return render_template("analytics_device.html", ip=ip, timeline=timeline)

# =========================
# RUN
# =========================
if __name__ == "__main__":
    analytics.init_db()
    app.run(host="0.0.0.0", port=5001)
