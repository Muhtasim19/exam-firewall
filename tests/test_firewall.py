"""
Comprehensive tests for firewall.py.

Every public function is covered.  subprocess calls are always patched so
that tests run without root / iptables / dnsmasq / nmap present.
"""

import os
import tempfile
from unittest.mock import patch, MagicMock, call

import pytest

import firewall


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------

def _make_cp(stdout="", returncode=0):
    """Return a fake subprocess.CompletedProcess."""
    cp = MagicMock()
    cp.stdout = stdout
    cp.returncode = returncode
    return cp


# ---------------------------------------------------------------------------
# run / run_safe
# ---------------------------------------------------------------------------

class TestRun:
    def test_prepends_sudo_and_returns_stripped_stdout(self):
        cp = _make_cp(stdout="  hello  \n")
        with patch("subprocess.run", return_value=cp) as mock_sp:
            result = firewall.run("iptables -L")
        mock_sp.assert_called_once_with(
            "sudo iptables -L",
            shell=True,
            text=True,
            capture_output=True,
        )
        assert result == "hello"

    def test_returns_empty_string_on_no_output(self):
        with patch("subprocess.run", return_value=_make_cp()):
            assert firewall.run("anything") == ""


class TestRunSafe:
    def test_prepends_sudo_and_calls_subprocess(self):
        with patch("subprocess.run") as mock_sp:
            firewall.run_safe("iptables -F EXAM_BLOCK")
        mock_sp.assert_called_once_with("sudo iptables -F EXAM_BLOCK", shell=True)


# ---------------------------------------------------------------------------
# ensure_chain
# ---------------------------------------------------------------------------

class TestEnsureChain:
    def test_creates_chain_when_missing(self):
        outputs = iter([
            "",          # iptables -L  → chain not present
            "",          # iptables -L EXAM_BLOCK → no RETURN
            "",          # iptables -L FORWARD → chain not in forward
        ])
        with patch("firewall.run", side_effect=lambda _cmd: next(outputs)) as mock_run, \
             patch("firewall.run_safe") as mock_safe:
            firewall.ensure_chain()

        calls = [c[0][0] for c in mock_safe.call_args_list]
        assert any("iptables -N EXAM_BLOCK" in c for c in calls)
        assert any(f"iptables -A {firewall.EXAM_CHAIN} -j RETURN" in c for c in calls)
        assert any(f"iptables -I FORWARD 1 -j {firewall.EXAM_CHAIN}" in c for c in calls)

    def test_no_ops_when_chain_already_complete(self):
        def _run(cmd):
            if "iptables -L" == cmd:
                return "EXAM_BLOCK"
            if f"iptables -L {firewall.EXAM_CHAIN}" == cmd:
                return "RETURN"
            if "iptables -L FORWARD" == cmd:
                return "EXAM_BLOCK"
            return ""

        with patch("firewall.run", side_effect=_run), \
             patch("firewall.run_safe") as mock_safe:
            firewall.ensure_chain()

        mock_safe.assert_not_called()


# ---------------------------------------------------------------------------
# get_ai_ips
# ---------------------------------------------------------------------------

class TestGetAiIps:
    def _dig_output(self, ips):
        """Build a fake dig stdout string."""
        return "\n".join(ips) + "\n"

    def test_parses_valid_ipv4_into_subnets(self):
        fake = _make_cp(stdout="1.2.3.4\n5.6.7.8\n")
        with patch("subprocess.run", return_value=fake):
            result = firewall.get_ai_ips()
        assert "1.2.3.0/24" in result
        assert "5.6.7.0/24" in result

    def test_skips_cname_lines(self):
        fake = _make_cp(stdout="some.cname.domain.\n1.2.3.4\n")
        with patch("subprocess.run", return_value=fake):
            result = firewall.get_ai_ips()
        assert "1.2.3.0/24" in result
        assert not any("cname" in r for r in result)

    def test_returns_deduplicated_subnets(self):
        # Two IPs in the same /24 should appear only once
        fake = _make_cp(stdout="10.0.0.1\n10.0.0.2\n")
        with patch("subprocess.run", return_value=fake):
            result = firewall.get_ai_ips()
        assert result.count("10.0.0.0/24") == 1

    def test_returns_empty_list_on_no_output(self):
        with patch("subprocess.run", return_value=_make_cp()):
            result = firewall.get_ai_ips()
        assert result == []

    def test_skips_blank_lines(self):
        fake = _make_cp(stdout="\n\n1.2.3.4\n\n")
        with patch("subprocess.run", return_value=fake):
            result = firewall.get_ai_ips()
        assert "1.2.3.0/24" in result

    def test_skips_non_numeric_ip_octets(self):
        # Looks like four parts but contains non-numeric text → ValueError path
        fake = _make_cp(stdout="abc.def.ghi.jkl\n1.2.3.4\n")
        with patch("subprocess.run", return_value=fake):
            result = firewall.get_ai_ips()
        assert "1.2.3.0/24" in result
        assert not any("abc" in r for r in result)


# ---------------------------------------------------------------------------
# exam_on / exam_off / exam_status
# ---------------------------------------------------------------------------

class TestExamMode:
    def test_exam_on_copies_dns_file_and_blocks_ips(self, tmp_path):
        dns_src = tmp_path / "blocked_domains.conf"
        dns_src.write_text("address=/example.com/0.0.0.0\n")

        with patch.object(firewall, "DNS_SOURCE_FILE", str(dns_src)), \
             patch.object(firewall, "DNS_BLOCK_FILE", str(tmp_path / "exam-block.conf")), \
             patch("firewall.ensure_chain"), \
             patch("firewall.get_ai_ips", return_value=["1.2.3.0/24"]), \
             patch("firewall.run_safe") as mock_safe, \
             patch("firewall.run", return_value="") as mock_run:
            firewall.exam_on()

        # dnsmasq reload must be requested
        safe_cmds = [c[0][0] for c in mock_safe.call_args_list]
        assert any("systemctl reload dnsmasq" in c for c in safe_cmds)
        # At least one DROP rule must be inserted
        assert any("iptables -I FORWARD" in c and "-j DROP" in c for c in safe_cmds)

    def test_exam_on_skips_dns_copy_when_source_missing(self, tmp_path):
        with patch.object(firewall, "DNS_SOURCE_FILE", str(tmp_path / "missing.conf")), \
             patch.object(firewall, "DNS_BLOCK_FILE", str(tmp_path / "out.conf")), \
             patch("firewall.ensure_chain"), \
             patch("firewall.get_ai_ips", return_value=[]), \
             patch("firewall.run_safe") as mock_safe, \
             patch("firewall.run", return_value=""):
            firewall.exam_on()

        safe_cmds = [c[0][0] for c in mock_safe.call_args_list]
        assert not any("cp " in c for c in safe_cmds)

    def test_exam_on_does_not_add_duplicate_drop_rule(self, tmp_path):
        """If the rule already exists (run returns 'found') it is not re-added."""
        with patch.object(firewall, "DNS_SOURCE_FILE", str(tmp_path / "missing.conf")), \
             patch.object(firewall, "DNS_BLOCK_FILE", str(tmp_path / "out.conf")), \
             patch("firewall.ensure_chain"), \
             patch("firewall.get_ai_ips", return_value=["1.2.3.0/24"]), \
             patch("firewall.run_safe") as mock_safe, \
             patch("firewall.run", return_value="found"):
            firewall.exam_on()

        safe_cmds = [c[0][0] for c in mock_safe.call_args_list]
        # Only dnsmasq reload is expected; no INSERT should happen
        assert not any("iptables -I FORWARD" in c and "-j DROP" in c for c in safe_cmds)

    def test_exam_off_flushes_chain_and_removes_dns(self, tmp_path):
        block_file = tmp_path / "exam-block.conf"
        block_file.write_text("address=/x.com/0.0.0.0\n")

        iptables_output = (
            "DROP       all  --  eno1   *       1.2.3.0/24\n"
            "DROP       all  --  eno1   *       0.0.0.0/0\n"    # skipped
            "ACCEPT     all  --  *      *       0.0.0.0/0\n"    # no DROP
        )

        with patch.object(firewall, "DNS_BLOCK_FILE", str(block_file)), \
             patch("firewall.run", return_value=iptables_output) as mock_run, \
             patch("firewall.run_safe") as mock_safe:
            firewall.exam_off()

        safe_cmds = [c[0][0] for c in mock_safe.call_args_list]
        assert any(f"iptables -F {firewall.EXAM_CHAIN}" in c for c in safe_cmds)
        assert any("systemctl reload dnsmasq" in c for c in safe_cmds)
        # 0.0.0.0/0 should NOT be deleted
        assert not any("0.0.0.0/0" in c for c in safe_cmds)
        # 1.2.3.0/24 should be deleted
        assert any("1.2.3.0/24" in c for c in safe_cmds)

    def test_exam_status_active_when_block_file_exists(self, tmp_path):
        block = tmp_path / "exam-block.conf"
        block.write_text("content")
        with patch.object(firewall, "DNS_BLOCK_FILE", str(block)):
            assert firewall.exam_status() == "active"

    def test_exam_status_inactive_when_block_file_absent(self, tmp_path):
        with patch.object(firewall, "DNS_BLOCK_FILE", str(tmp_path / "missing")):
            assert firewall.exam_status() == "inactive"


# ---------------------------------------------------------------------------
# strict_mode_on / strict_mode_off / strict_status
# ---------------------------------------------------------------------------

class TestStrictMode:
    def test_strict_mode_on_inserts_whitelist_and_drop(self, tmp_path):
        dns_src = tmp_path / "blocked_domains.conf"
        dns_src.write_text("")

        with patch.object(firewall, "DNS_SOURCE_FILE", str(dns_src)), \
             patch.object(firewall, "DNS_BLOCK_FILE", str(tmp_path / "exam-block.conf")), \
             patch("firewall.ensure_chain"), \
             patch("firewall.strict_mode_off"), \
             patch("firewall.run_safe") as mock_safe, \
             patch("firewall.run", return_value=""):
            firewall.strict_mode_on()

        safe_cmds = [c[0][0] for c in mock_safe.call_args_list]
        # ACCEPT rules for whitelist IPs
        assert any("-j ACCEPT" in c for c in safe_cmds)
        # Final DROP rule with the strict comment
        assert any(firewall.STRICT_DROP_COMMENT in c and "-j DROP" in c for c in safe_cmds)

    def test_strict_mode_off_removes_whitelist_and_drop(self):
        # First call to run() returns 'found'; second returns '' to break loop
        call_counts = {}

        def _run(cmd):
            call_counts[cmd] = call_counts.get(cmd, 0) + 1
            # Let each rule be "found" once, then gone
            if call_counts[cmd] == 1:
                return "found"
            return ""

        with patch("firewall.run", side_effect=_run), \
             patch("firewall.run_safe") as mock_safe, \
             patch.object(firewall, "DNS_BLOCK_FILE", "/nonexistent/file"):
            firewall.strict_mode_off()

        safe_cmds = [c[0][0] for c in mock_safe.call_args_list]
        # Whitelist ACCEPTs must be deleted
        assert any("-j ACCEPT" in c and "-D FORWARD" in c for c in safe_cmds)
        # Strict DROP must be deleted
        assert any(firewall.STRICT_DROP_COMMENT in c and "-D FORWARD" in c for c in safe_cmds)

    def test_strict_status_active_when_comment_in_output(self):
        with patch("firewall.run", return_value=f"DROP {firewall.STRICT_DROP_COMMENT}"):
            assert firewall.strict_status() == "active"

    def test_strict_status_inactive_when_comment_absent(self):
        with patch("firewall.run", return_value="DROP all -- eno1 enp2s0"):
            assert firewall.strict_status() == "inactive"


# ---------------------------------------------------------------------------
# get_dhcp_hostnames
# ---------------------------------------------------------------------------

SAMPLE_LEASES = """
lease 192.168.50.10 {
  starts 1 2024/01/01 00:00:00;
  hardware ethernet aa:bb:cc:dd:ee:ff;
  client-hostname "alice-laptop";
}
lease 192.168.50.11 {
  starts 1 2024/01/01 01:00:00;
  hardware ethernet 11:22:33:44:55:66;
  client-hostname "bob-desktop";
}
"""

LEASES_NO_HOSTNAME = """
lease 192.168.50.12 {
  starts 1 2024/01/01 02:00:00;
  hardware ethernet aa:aa:aa:aa:aa:aa;
}
"""

def _fake_file(content):
    """Return a context-manager mock that yields a StringIO for *content*."""
    import io
    m = MagicMock()
    m.__enter__ = MagicMock(return_value=io.StringIO(content))
    m.__exit__ = MagicMock(return_value=False)
    return m


class TestGetDhcpHostnames:
    def test_parses_valid_leases(self):
        with patch("builtins.open", return_value=_fake_file(SAMPLE_LEASES)):
            result = firewall.get_dhcp_hostnames()
        assert result["192.168.50.10"] == "alice-laptop"
        assert result["192.168.50.11"] == "bob-desktop"

    def test_returns_empty_dict_when_file_missing(self):
        with patch("builtins.open", side_effect=FileNotFoundError):
            result = firewall.get_dhcp_hostnames()
        assert result == {}

    def test_skips_lease_without_hostname(self):
        with patch("builtins.open", return_value=_fake_file(LEASES_NO_HOSTNAME)):
            result = firewall.get_dhcp_hostnames()
        assert result == {}

    def test_later_lease_overwrites_earlier_for_same_ip(self):
        content = (
            'lease 192.168.50.10 {\n'
            '  hardware ethernet aa:bb:cc:dd:ee:ff;\n'
            '  client-hostname "first";\n'
            '}\n'
            'lease 192.168.50.10 {\n'
            '  hardware ethernet aa:bb:cc:dd:ee:ff;\n'
            '  client-hostname "second";\n'
            '}\n'
        )
        with patch("builtins.open", return_value=_fake_file(content)):
            result = firewall.get_dhcp_hostnames()
        assert result["192.168.50.10"] == "second"


# ---------------------------------------------------------------------------
# block_device / unblock_device / get_blocked_ips
# ---------------------------------------------------------------------------

class TestDeviceBlocking:
    def test_block_device_inserts_rule_when_not_present(self):
        with patch("firewall.run", return_value="") as mock_run, \
             patch("firewall.run_safe") as mock_safe:
            firewall.block_device("192.168.50.5")

        safe_cmds = [c[0][0] for c in mock_safe.call_args_list]
        assert any("iptables -I EXAM_BLOCK 1 -s 192.168.50.5 -j DROP" in c
                   for c in safe_cmds)

    def test_block_device_skips_insert_when_already_present(self):
        with patch("firewall.run", return_value="found"), \
             patch("firewall.run_safe") as mock_safe:
            firewall.block_device("192.168.50.5")

        mock_safe.assert_not_called()

    def test_unblock_device_deletes_until_rule_gone(self):
        # Return "found" twice, then "" to break the loop
        call_count = {"n": 0}

        def _run(_cmd):
            call_count["n"] += 1
            if call_count["n"] <= 2:
                return "found"
            return ""

        with patch("firewall.run", side_effect=_run), \
             patch("firewall.run_safe") as mock_safe:
            firewall.unblock_device("192.168.50.7")

        delete_calls = [c for c in mock_safe.call_args_list
                        if "iptables -D EXAM_BLOCK" in c[0][0]]
        assert len(delete_calls) == 2

    def test_unblock_device_does_nothing_when_not_blocked(self):
        with patch("firewall.run", return_value=""), \
             patch("firewall.run_safe") as mock_safe:
            firewall.unblock_device("192.168.50.9")

        mock_safe.assert_not_called()

    def test_get_blocked_ips_returns_lan_ips(self):
        output = (
            "DROP  all  --  192.168.50.3  0.0.0.0/0\n"
            "DROP  all  --  192.168.50.4  0.0.0.0/0\n"
            "RETURN all  --  0.0.0.0/0   0.0.0.0/0\n"
        )
        with patch("firewall.run", return_value=output):
            blocked = firewall.get_blocked_ips()

        assert "192.168.50.3" in blocked
        assert "192.168.50.4" in blocked
        # Non-LAN parts should not appear
        assert "0.0.0.0/0" not in blocked

    def test_get_blocked_ips_returns_empty_when_no_lan_rules(self):
        with patch("firewall.run", return_value="RETURN all -- 0.0.0.0/0"):
            blocked = firewall.get_blocked_ips()
        assert blocked == set()


# ---------------------------------------------------------------------------
# connected_devices
# ---------------------------------------------------------------------------

class TestConnectedDevices:
    IP_NEIGH_OUTPUT = (
        "192.168.50.10 dev eno1 lladdr aa:bb:cc:dd:ee:ff REACHABLE\n"
        "192.168.50.11 dev eno1 lladdr 11:22:33:44:55:66 STALE\n"
        "10.0.0.1 dev eno1 lladdr ff:ff:ff:ff:ff:ff REACHABLE\n"   # non-LAN
    )

    def test_returns_only_lan_devices(self):
        with patch("subprocess.check_output", return_value=self.IP_NEIGH_OUTPUT), \
             patch("firewall.run_safe"), \
             patch("firewall.get_blocked_ips", return_value=set()), \
             patch("firewall.get_dhcp_hostnames", return_value={}):
            devices = firewall.connected_devices()

        ips = {d["ip"] for d in devices}
        assert "192.168.50.10" in ips
        assert "192.168.50.11" in ips
        assert "10.0.0.1" not in ips

    def test_marks_blocked_devices(self):
        with patch("subprocess.check_output", return_value=self.IP_NEIGH_OUTPUT), \
             patch("firewall.run_safe"), \
             patch("firewall.get_blocked_ips", return_value={"192.168.50.10"}), \
             patch("firewall.get_dhcp_hostnames", return_value={}):
            devices = firewall.connected_devices()

        by_ip = {d["ip"]: d for d in devices}
        assert by_ip["192.168.50.10"]["blocked"] is True
        assert by_ip["192.168.50.11"]["blocked"] is False

    def test_resolves_hostname_from_dhcp(self):
        with patch("subprocess.check_output", return_value=self.IP_NEIGH_OUTPUT), \
             patch("firewall.run_safe"), \
             patch("firewall.get_blocked_ips", return_value=set()), \
             patch("firewall.get_dhcp_hostnames",
                   return_value={"192.168.50.10": "alice-laptop"}):
            devices = firewall.connected_devices()

        by_ip = {d["ip"]: d for d in devices}
        assert by_ip["192.168.50.10"]["hostname"] == "alice-laptop"
        assert by_ip["192.168.50.11"]["hostname"] == "Unknown"

    def test_prefers_reachable_state_over_stale(self):
        # Same IP appears twice: first STALE then REACHABLE
        output = (
            "192.168.50.10 dev eno1 lladdr aa:bb:cc:dd:ee:ff STALE\n"
            "192.168.50.10 dev eno1 lladdr aa:bb:cc:dd:ee:ff REACHABLE\n"
        )
        with patch("subprocess.check_output", return_value=output), \
             patch("firewall.run_safe"), \
             patch("firewall.get_blocked_ips", return_value=set()), \
             patch("firewall.get_dhcp_hostnames", return_value={}):
            devices = firewall.connected_devices()

        assert len(devices) == 1
        assert devices[0]["state"] == "REACHABLE"

    def test_returns_empty_list_when_no_neighbours(self):
        with patch("subprocess.check_output", return_value=""), \
             patch("firewall.run_safe"), \
             patch("firewall.get_blocked_ips", return_value=set()), \
             patch("firewall.get_dhcp_hostnames", return_value={}):
            devices = firewall.connected_devices()

        assert devices == []


# ---------------------------------------------------------------------------
# refresh_devices
# ---------------------------------------------------------------------------

class TestRefreshDevices:
    def test_flushes_neighbours_and_runs_nmap(self):
        with patch("firewall.run_safe") as mock_safe:
            firewall.refresh_devices()

        safe_cmds = [c[0][0] for c in mock_safe.call_args_list]
        assert any("ip neigh flush" in c for c in safe_cmds)
        assert any("nmap" in c for c in safe_cmds)


# ---------------------------------------------------------------------------
# kill_network / restore_network / network_status
# ---------------------------------------------------------------------------

class TestNetworkKillSwitch:
    def test_kill_network_inserts_drop_rule(self):
        # run returns '' so the while-loop exits immediately, then INSERT is called
        with patch("firewall.run", return_value=""), \
             patch("firewall.run_safe") as mock_safe:
            firewall.kill_network()

        safe_cmds = [c[0][0] for c in mock_safe.call_args_list]
        assert any("iptables -I FORWARD 1 -i eno1 -o enp2s0 -j DROP" in c
                   for c in safe_cmds)

    def test_kill_network_removes_existing_rule_before_inserting(self):
        # run returns 'found' once (existing rule), then '' (gone)
        call_count = {"n": 0}

        def _run(_cmd):
            call_count["n"] += 1
            return "found" if call_count["n"] == 1 else ""

        with patch("firewall.run", side_effect=_run), \
             patch("firewall.run_safe") as mock_safe:
            firewall.kill_network()

        safe_cmds = [c[0][0] for c in mock_safe.call_args_list]
        assert any("iptables -D FORWARD" in c for c in safe_cmds)
        assert any("iptables -I FORWARD 1" in c for c in safe_cmds)

    def test_restore_network_deletes_drop_rule(self):
        call_count = {"n": 0}

        def _run(_cmd):
            call_count["n"] += 1
            return "found" if call_count["n"] == 1 else ""

        with patch("firewall.run", side_effect=_run), \
             patch("firewall.run_safe") as mock_safe:
            firewall.restore_network()

        safe_cmds = [c[0][0] for c in mock_safe.call_args_list]
        assert any("iptables -D FORWARD -i eno1 -o enp2s0 -j DROP" in c
                   for c in safe_cmds)

    def test_restore_network_does_nothing_when_already_active(self):
        with patch("firewall.run", return_value=""), \
             patch("firewall.run_safe") as mock_safe:
            firewall.restore_network()

        mock_safe.assert_not_called()

    def test_network_status_killed_when_drop_rule_present(self):
        output = "DROP  all  --  eno1  enp2s0  0.0.0.0/0\n"
        with patch("firewall.run", return_value=output):
            assert firewall.network_status() == "killed"

    def test_network_status_active_when_no_drop_rule(self):
        output = "ACCEPT all -- eno1 enp2s0 0.0.0.0/0\n"
        with patch("firewall.run", return_value=output):
            assert firewall.network_status() == "active"

    def test_network_status_active_when_only_strict_drop_present(self):
        # A DROP line carrying the strict-mode comment should NOT trigger "killed"
        output = (
            f"DROP  all  --  eno1  enp2s0  0.0.0.0/0  /* {firewall.STRICT_DROP_COMMENT} */\n"
        )
        with patch("firewall.run", return_value=output):
            assert firewall.network_status() == "active"


# ---------------------------------------------------------------------------
# log
# ---------------------------------------------------------------------------

class TestLog:
    def test_calls_logging_info_and_print(self, capsys):
        import logging
        with patch("logging.info") as mock_log:
            firewall.log("test message")
        mock_log.assert_called_once_with("test message")
        captured = capsys.readouterr()
        assert "test message" in captured.out
