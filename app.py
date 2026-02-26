from flask import Flask, render_template, redirect, url_for
import firewall

app = Flask(__name__)

@app.route("/")
def index():
    exam_status = firewall.exam_status()
    devices = firewall.connected_devices()
    return render_template(
        "index.html",
        exam_status=exam_status,
        devices=devices
    )

@app.route("/exam/on")
def exam_on():
    firewall.exam_on()
    return redirect(url_for("index"))

@app.route("/exam/off")
def exam_off():
    firewall.exam_off()
    return redirect(url_for("index"))

@app.route("/device/block/<ip>")
def block_device(ip):
    firewall.block_device(ip)
    return redirect(url_for("index"))

@app.route("/device/unblock/<ip>")
def unblock_device(ip):
    firewall.unblock_device(ip)
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
