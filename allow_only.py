"""
Allow-Only mode (per device)
============================
Works like the YouTube block, but the other way round: a device in this mode
can only resolve the sites on the allowed list (dns/allowed_sites.txt) plus
anything Google. Everything else is refused.

How it works
  * A third dnsmasq instance (service: dnsmasq-allowonly, port 5354) has NO
    default upstream DNS. It only forwards names on the allowed list, so any
    other name is refused.
  * The custom block list (and the exam list while Exam Mode is on) is copied
    into that instance as address=/domain/ip lines. A more specific block
    always beats a broader allow (e.g. sites.google.com stays blocked).
  * The 🔒 button redirects that one device's DNS (port 53) to the instance
    with an iptables NAT rule, exactly like youtube_block.py does for 5353.

Only the Python standard library is used so setup_allow_only.sh can import it.
"""
import ipaddress
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from urllib.parse import urlparse

LAN_PREFIX = "192.168.50."
LAN_IFACE = "eno1"
LISTEN_IP = "192.168.50.1"
DNS_PORT = 5354
CHAIN = "ALLOWONLY_DNS"          # chain in the NAT table
SERVICE = "dnsmasq-allowonly"
CONF_PATH = "/etc/dnsmasq-allowonly.conf"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_LIST = os.path.join(BASE_DIR, "dns", "allowed_sites.txt")
CACHE_LIST = "/var/lib/exam-firewall/allowed_sites_cache.txt"

GITHUB_RAW_URL = "https://raw.githubusercontent.com/Muhtasim19/exam-firewall/main/dns/allowed_sites.txt"
GITHUB_EDIT_URL = "https://github.com/Muhtasim19/exam-firewall/edit/main/dns/allowed_sites.txt"

# Real internet DNS used for allowed sites (same as dnsmasq-youtube.conf)
UPSTREAM_DNS = ["8.8.8.8", "8.8.4.4"]

# School-internal names must go to the school DNS server so device management
# (Ivanti etc.) keeps working. Copied from dnsmasq-youtube.conf.
SCHOOL_DNS = {"cpsd.us": "172.25.205.59"}

CUSTOM_BLOCK_FILE = "/etc/dnsmasq.d/custom-block.conf"
EXAM_BLOCK_FILE = "/etc/dnsmasq.d/exam-block.conf"

_DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
_ADDRESS_RE = re.compile(r"^address=/([a-z0-9.-]+)/([0-9.]+)$")

_FETCH_TIMEOUT = 4          # seconds
_RETRY_AFTER_FAIL = 60      # don't hammer GitHub (or wait 4s per click) when it is unreachable
_last_fetch_fail = 0.0


# ------------------------------------------------------------------
# small helpers
# ------------------------------------------------------------------
def _run(args):
    return subprocess.run(args, capture_output=True, text=True)


def _ipt(*args):
    """iptables in the NAT table (through sudo, like the rest of the project)."""
    return _run(["sudo", "iptables", "-t", "nat", *args])


def _read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def _valid_lan_ip(ip):
    try:
        ip = str(ipaddress.IPv4Address(ip))
    except ValueError:
        return None
    return ip if ip.startswith(LAN_PREFIX) else None


def _service_active():
    return _run(["sudo", "systemctl", "is-active", "--quiet", SERVICE]).returncode == 0


# ------------------------------------------------------------------
# allowed list
# ------------------------------------------------------------------
def parse_site_list(text):
    """Turn the text file into a clean list of domains.

    Accepts full URLs or bare domains, ignores # comments and blank lines.
    Returns (domains, skipped_lines).
    """
    domains, skipped, seen = [], [], set()
    for raw in (text or "").splitlines():
        line = raw.split("#", 1)[0].strip().lower()
        if not line:
            continue
        if "://" in line:
            host = urlparse(line).hostname or ""
        else:
            host = line.split("/", 1)[0].split(":", 1)[0]
        host = host.lstrip("*.").strip(".")
        if not _DOMAIN_RE.match(host):
            skipped.append(raw.strip())
            continue
        if host not in seen:
            seen.add(host)
            domains.append(host)
    return domains, skipped


def _fetch_github():
    url = f"{GITHUB_RAW_URL}?t={int(time.time())}"      # query string dodges GitHub's raw cache
    req = urllib.request.Request(url, headers={"User-Agent": "exam-firewall"})
    with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
        return resp.read().decode("utf-8")


def load_allowed_sites(sync=False):
    """Load the allowed list.

    sync=True tries GitHub first. Otherwise (or if GitHub fails) the newer of
    the last GitHub sync and the copy in the repo folder is used, so a
    `git pull` and a dashboard sync both take effect.
    """
    global _last_fetch_fail
    text, source, stamp = None, None, 0.0

    if sync and time.time() - _last_fetch_fail > _RETRY_AFTER_FAIL:
        try:
            fetched = _fetch_github()
            if not parse_site_list(fetched)[0]:
                raise ValueError("GitHub list has no valid sites")
            text, source, stamp = fetched, "GitHub (just synced)", time.time()
            try:
                os.makedirs(os.path.dirname(CACHE_LIST), exist_ok=True)
                with open(CACHE_LIST, "w", encoding="utf-8") as f:
                    f.write(fetched)
            except OSError:
                pass
        except Exception:
            _last_fetch_fail = time.time()

    if text is None:
        cache_t, local_t = _mtime(CACHE_LIST), _mtime(LOCAL_LIST)
        if cache_t > local_t:
            text, source, stamp = _read_file(CACHE_LIST), "GitHub (last sync)", cache_t
        if text is None:
            text, source, stamp = _read_file(LOCAL_LIST), "copy on this server", local_t

    domains, skipped = parse_site_list(text)
    updated = time.strftime("%b %d %H:%M", time.localtime(stamp)) if stamp else "unknown"
    return {"domains": domains, "skipped": skipped, "source": source or "none", "updated": updated}


def get_status():
    """Info for the dashboard (no network access)."""
    info = load_allowed_sites(sync=False)
    info["edit_url"] = GITHUB_EDIT_URL
    return info


# ------------------------------------------------------------------
# dnsmasq config
# ------------------------------------------------------------------
def read_block_entries():
    """domain -> ip for the custom block list, plus the exam list while Exam Mode is on."""
    blocks = {}
    for path in (CUSTOM_BLOCK_FILE, EXAM_BLOCK_FILE):
        for line in (_read_file(path) or "").splitlines():
            m = _ADDRESS_RE.match(line.strip().lower())
            if m:
                blocks.setdefault(m.group(1), m.group(2))
    return blocks


def build_config(domains, blocks):
    lines = [
        "# AUTO-GENERATED by allow_only.py - do not edit by hand",
        f"port={DNS_PORT}",
        "bind-interfaces",
        f"listen-address={LISTEN_IP}",
        "no-resolv",       # no default upstream: any name not listed below is refused
        "no-hosts",
        "filter-AAAA",
        "log-queries",
        "log-facility=/var/log/dnsmasq.log",
        "",
        "# School DNS (device management)",
    ]
    for domain, dns_ip in SCHOOL_DNS.items():
        lines.append(f"server=/{domain}/{dns_ip}")

    lines += ["", "# Allowed sites"]
    for domain in domains:
        if domain in blocks or domain in SCHOOL_DNS:
            continue                                  # a block on the exact same name wins
        for upstream in UPSTREAM_DNS:
            lines.append(f"server=/{domain}/{upstream}")

    lines += ["", "# Blocked (custom block list + exam list)"]
    for domain, ip in sorted(blocks.items()):
        lines.append(f"address=/{domain}/{ip}")
    return "\n".join(lines) + "\n"


def apply_config(sync=False):
    """Regenerate /etc/dnsmasq-allowonly.conf and (re)start the service.

    Returns (ok, message).
    """
    info = load_allowed_sites(sync=sync)
    if not info["domains"]:
        return False, "The allowed list is empty or unreadable - nothing was changed."

    new_text = build_config(info["domains"], read_block_entries())

    if _read_file(CONF_PATH) == new_text and _service_active():
        return True, f"{len(info['domains'])} allowed sites (already up to date, source: {info['source']})"

    tmp = tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False)
    try:
        tmp.write(new_text)
        tmp.close()
        os.chmod(tmp.name, 0o644)
        if _run(["sudo", "cp", tmp.name, CONF_PATH]).returncode != 0:
            return False, f"Could not write {CONF_PATH}."
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    _run(["sudo", "systemctl", "restart", SERVICE])
    time.sleep(0.7)                                   # let dnsmasq fail fast if the config is bad
    if not _service_active():
        return False, (f"The {SERVICE} service is not running. "
                       f"Run 'sudo bash setup_allow_only.sh' once on this server.")
    return True, f"{len(info['domains'])} allowed sites applied (source: {info['source']})"


# ------------------------------------------------------------------
# per-device switch (iptables NAT redirect, like youtube_block.py)
# ------------------------------------------------------------------
def _ensure_chain():
    if _ipt("-n", "-L", CHAIN).returncode != 0:
        _ipt("-N", CHAIN)
    # Jump at position 1 so this wins over the YouTube-block chain and any generic port-53 redirect.
    if _ipt("-C", "PREROUTING", "-i", LAN_IFACE, "-j", CHAIN).returncode != 0:
        _ipt("-I", "PREROUTING", "1", "-i", LAN_IFACE, "-j", CHAIN)


def _redirect_rule(ip, proto):
    return ["-s", ip, "-p", proto, "--dport", "53", "-j", "REDIRECT", "--to-ports", str(DNS_PORT)]


def get_allow_only_ips():
    ips = set()
    result = _ipt("-S", CHAIN)
    if result.returncode != 0:
        return ips
    pattern = re.compile(r"-s (" + re.escape(LAN_PREFIX) + r"\d+)(?:/32)?\s.*--to-ports " + str(DNS_PORT))
    for line in result.stdout.splitlines():
        m = pattern.search(line)
        if m:
            ips.add(m.group(1))
    return ips


def _add_redirect(ip):
    for proto in ("udp", "tcp"):
        rule = _redirect_rule(ip, proto)
        if _ipt("-C", CHAIN, *rule).returncode != 0:
            _ipt("-I", CHAIN, "1", *rule)


def enable_for(ip, sync=True):
    """Put one device in Allow-Only mode. Returns (ok, message)."""
    ip = _valid_lan_ip(ip)
    if not ip:
        return False, "That is not a valid student IP address."

    ok, message = apply_config(sync=sync)
    if not ok:
        return False, message           # never redirect a device to a DNS server that isn't there

    _ensure_chain()
    _add_redirect(ip)
    return True, message


def enable_many(ips, sync=True):
    """Put many devices in Allow-Only mode with one config update
    (used by the 'Block Without Google' button). Returns (ok, message)."""
    valid = []
    for ip in ips:
        ip = _valid_lan_ip(ip)
        if ip and ip != LISTEN_IP and ip not in valid:     # never lock the server itself
            valid.append(ip)
    if not valid:
        return False, "No student devices found. Press Refresh Devices and try again."

    ok, message = apply_config(sync=sync)
    if not ok:
        return False, message

    _ensure_chain()
    for ip in valid:
        _add_redirect(ip)
    return True, f"turned on for {len(valid)} devices - {message}"


def disable_for(ip):
    ip = _valid_lan_ip(ip)
    if not ip:
        return False
    for proto in ("udp", "tcp"):
        rule = _redirect_rule(ip, proto)
        while _ipt("-C", CHAIN, *rule).returncode == 0:
            _ipt("-D", CHAIN, *rule)
    return True


def release_all():
    for ip in get_allow_only_ips():
        disable_for(ip)


def refresh_if_active():
    """Call after the custom block list or Exam Mode changes so devices in
    Allow-Only mode pick it up. Does nothing if no device is in the mode."""
    if get_allow_only_ips():
        apply_config(sync=False)


if __name__ == "__main__":
    ok, msg = apply_config(sync="--sync" in sys.argv)
    print(msg)
    sys.exit(0 if ok else 1)
