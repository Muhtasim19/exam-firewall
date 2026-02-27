from flask import Flask, render_template, redirect, url_for, request, session
from functools import wraps
import firewall

app = Flask(__name__)
app.secret_key = "3f8x92Kk29dk29s0dkX"

from datetime import timedelta

app.permanent_session_lifetime = timedelta(minutes=10)

ADMIN_PASSWORD = "exam123"


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
# Login Route (DO NOT PROTECT)
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password")
        if password == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))

# =========================
# Protected Routes
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


@app.route("/device/block/<ip>")
@login_required
def block_device(ip):
    firewall.block_device(ip)
    return redirect(url_for("index"))


@app.route("/device/unblock/<ip>")
@login_required
def unblock_device(ip):
    firewall.unblock_device(ip)
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
