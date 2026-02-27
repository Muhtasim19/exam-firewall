from flask import Flask, render_template, redirect, url_for, request, session, make_response
from functools import wraps
from datetime import timedelta
import firewall

app = Flask(__name__)
app.secret_key = "3f8x92Kk29dk29s0dkX"

# Session timeout (10 min inactivity)
app.permanent_session_lifetime = timedelta(minutes=10)

ADMIN_PASSWORD = "exam123"

# =========================
# Disable Browser Caching
# =========================
@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# =========================
# Login Required Decorator
# =========================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# =========================
# Refresh Session on Activity
# =========================
@app.before_request
def refresh_session():
    if session.get("logged_in"):
        session.permanent = True

# =========================
# LOGIN
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password")
        if password == ADMIN_PASSWORD:
            session.permanent = True
            session["logged_in"] = True
            return redirect(url_for("index"))
    return render_template("login.html")

# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():
    print("LOGOUT CALLED")
    session.clear()
    response = redirect("/login")
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
# RUN
# =========================
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
