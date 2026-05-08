import os
import subprocess

CUSTOM_BLOCK_FILE = "/etc/dnsmasq.d/custom-block.conf"


def run(cmd):
    subprocess.run(f"sudo {cmd}", shell=True)


def get_custom_blocked():
    """Get list of custom blocked domains"""
    domains = []
    if os.path.exists(CUSTOM_BLOCK_FILE):
        try:
            with open(CUSTOM_BLOCK_FILE, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("address=/"):
                        # address=/nytimes.com/0.0.0.0 -> nytimes.com
                        parts = line.split("/")
                        if len(parts) >= 2:
                            domains.append(parts[1])
        except:
            pass
    return domains


def add_custom_block(domain):
    """Add a domain to custom block list"""
    domain = domain.strip().lower()

    # Remove http/https if pasted
    domain = domain.replace("https://", "").replace("http://", "")
    # Remove trailing slash or path
    domain = domain.split("/")[0]

    if not domain:
        return False

    # Check if already blocked
    existing = get_custom_blocked()
    if domain in existing:
        return False

    # Add to file
    line = f"address=/{domain}/0.0.0.0\n"
    try:
        with open(CUSTOM_BLOCK_FILE, "a") as f:
            f.write(line)
    except PermissionError:
        run(f"bash -c 'echo \"address=/{domain}/0.0.0.0\" >> {CUSTOM_BLOCK_FILE}'")

    # Reload dnsmasq
    run("systemctl restart dnsmasq")
    return True


def remove_custom_block(domain):
    """Remove a domain from custom block list"""
    domain = domain.strip().lower()

    if not os.path.exists(CUSTOM_BLOCK_FILE):
        return False

    try:
        with open(CUSTOM_BLOCK_FILE, "r") as f:
            lines = f.readlines()

        new_lines = [l for l in lines if f"/{domain}/" not in l]

        with open(CUSTOM_BLOCK_FILE, "w") as f:
            f.writelines(new_lines)
    except PermissionError:
        run(f"sed -i '/{domain}/d' {CUSTOM_BLOCK_FILE}")

    # Reload dnsmasq
    run("systemctl reload dnsmasq")
    return True


def clear_all_custom_blocks():
    """Remove all custom blocked domains"""
    try:
        with open(CUSTOM_BLOCK_FILE, "w") as f:
            f.write("")
    except PermissionError:
        run(f"bash -c 'echo \"\" > {CUSTOM_BLOCK_FILE}'")

    run("systemctl reload dnsmasq")
