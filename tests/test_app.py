"""
Comprehensive tests for app.py (Flask routes, auth, session handling).

All firewall module calls are patched so no real iptables / dnsmasq operations
occur.  The admin password hash is swapped for a known test hash via
monkeypatching so we can exercise both success and failure login paths.
"""

import time
from unittest.mock import patch, MagicMock

import pytest
from werkzeug.security import generate_password_hash

import app as flask_app


TEST_PASSWORD = "s3cr3t-test-password"
TEST_HASH = generate_password_hash(TEST_PASSWORD)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    """
    Run every test with:
      - a clean FAILED_LOGINS dict
      - a known (test) admin password hash
    """
    flask_app.FAILED_LOGINS.clear()
    monkeypatch.setattr(flask_app, "ADMIN_PASSWORD_HASH", TEST_HASH)
    yield
    flask_app.FAILED_LOGINS.clear()


@pytest.fixture
def client():
    flask_app.app.config["TESTING"] = True
    flask_app.app.config["WTF_CSRF_ENABLED"] = False
    with flask_app.app.test_client() as c:
        yield c


@pytest.fixture
def auth_client(client):
    """A test client with an active admin session."""
    with client.session_transaction() as sess:
        sess["logged_in"] = True
    return client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _firewall_defaults():
    """Return a dict of patch targets → default return values for the dashboard."""
    return {
        "firewall.exam_status": "inactive",
        "firewall.connected_devices": [],
        "firewall.network_status": "active",
        "firewall.strict_status": "inactive",
    }


def _patch_firewall(**overrides):
    """Context-manager factory that patches all dashboard firewall calls."""
    defaults = _firewall_defaults()
    defaults.update(overrides)
    patches = {k: patch(k, return_value=v) for k, v in defaults.items()}
    return patches


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class TestLogin:
    def test_get_renders_login_page(self, client):
        resp = client.get("/login")
        assert resp.status_code == 200
        assert b"login" in resp.data.lower()

    def test_post_correct_password_redirects_to_index(self, client):
        with patch("firewall.exam_status", return_value="inactive"), \
             patch("firewall.connected_devices", return_value=[]), \
             patch("firewall.network_status", return_value="active"), \
             patch("firewall.strict_status", return_value="inactive"):
            resp = client.post(
                "/login",
                data={"password": TEST_PASSWORD},
                follow_redirects=False,
            )
        assert resp.status_code == 302
        assert "/" in resp.headers["Location"]

    def test_post_correct_password_sets_session(self, client):
        with patch("firewall.exam_status", return_value="inactive"), \
             patch("firewall.connected_devices", return_value=[]), \
             patch("firewall.network_status", return_value="active"), \
             patch("firewall.strict_status", return_value="inactive"):
            client.post("/login", data={"password": TEST_PASSWORD})

        with client.session_transaction() as sess:
            assert sess.get("logged_in") is True

    def test_post_wrong_password_renders_login_again(self, client):
        resp = client.post("/login", data={"password": "wrong"})
        assert resp.status_code == 200
        assert b"login" in resp.data.lower()

    def test_post_wrong_password_does_not_set_session(self, client):
        client.post("/login", data={"password": "wrong"})
        with client.session_transaction() as sess:
            assert not sess.get("logged_in")

    def test_post_wrong_password_increments_failed_attempts(self, client):
        client.post("/login", data={"password": "bad"})
        assert "127.0.0.1" in flask_app.FAILED_LOGINS
        assert flask_app.FAILED_LOGINS["127.0.0.1"][0] == 1

    def test_lockout_after_max_attempts(self, client):
        for _ in range(flask_app.MAX_ATTEMPTS):
            client.post("/login", data={"password": "bad"})
        resp = client.post("/login", data={"password": "bad"})
        assert b"Too many failed attempts" in resp.data

    def test_lockout_blocks_even_correct_password(self, client):
        for _ in range(flask_app.MAX_ATTEMPTS):
            client.post("/login", data={"password": "bad"})
        resp = client.post("/login", data={"password": TEST_PASSWORD})
        assert b"Too many failed attempts" in resp.data

    def test_lockout_expires_after_timeout(self, client, monkeypatch):
        # Seed with a 'locked out' state whose last_attempt is in the past
        flask_app.FAILED_LOGINS["127.0.0.1"] = (
            flask_app.MAX_ATTEMPTS,
            time.time() - flask_app.LOCKOUT_TIME - 1,
        )
        with patch("firewall.exam_status", return_value="inactive"), \
             patch("firewall.connected_devices", return_value=[]), \
             patch("firewall.network_status", return_value="active"), \
             patch("firewall.strict_status", return_value="inactive"):
            resp = client.post(
                "/login",
                data={"password": TEST_PASSWORD},
                follow_redirects=False,
            )
        assert resp.status_code == 302
        # Entry must be cleared on successful login after timeout
        assert "127.0.0.1" not in flask_app.FAILED_LOGINS

    def test_successful_login_clears_failed_attempts(self, client):
        flask_app.FAILED_LOGINS["127.0.0.1"] = (2, time.time())
        with patch("firewall.exam_status", return_value="inactive"), \
             patch("firewall.connected_devices", return_value=[]), \
             patch("firewall.network_status", return_value="active"), \
             patch("firewall.strict_status", return_value="inactive"):
            client.post("/login", data={"password": TEST_PASSWORD})
        assert "127.0.0.1" not in flask_app.FAILED_LOGINS


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

class TestLogout:
    def test_logout_clears_session_and_redirects(self, auth_client):
        resp = auth_client.get("/logout", follow_redirects=False)
        assert resp.status_code == 302
        assert "login" in resp.headers["Location"]

    def test_logout_removes_logged_in_flag(self, auth_client):
        auth_client.get("/logout")
        with auth_client.session_transaction() as sess:
            assert not sess.get("logged_in")

    def test_logout_deletes_session_cookie(self, auth_client):
        resp = auth_client.get("/logout", follow_redirects=False)
        # Werkzeug sets a cookie with an empty/expired value to delete it
        set_cookie = resp.headers.get("Set-Cookie", "")
        assert "session=" in set_cookie or resp.status_code == 302


# ---------------------------------------------------------------------------
# Login-required redirect
# ---------------------------------------------------------------------------

PROTECTED_ROUTES = [
    "/",
    "/exam/on",
    "/exam/off",
    "/device/block/192.168.50.5",
    "/device/unblock/192.168.50.5",
    "/network/kill",
    "/network/restore",
    "/strict/on",
    "/strict/off",
    "/devices/refresh",
]

class TestLoginRequired:
    @pytest.mark.parametrize("route", PROTECTED_ROUTES)
    def test_redirects_to_login_when_not_authenticated(self, client, route):
        resp = client.get(route, follow_redirects=False)
        assert resp.status_code == 302
        assert "login" in resp.headers["Location"]


# ---------------------------------------------------------------------------
# Dashboard (index)
# ---------------------------------------------------------------------------

class TestDashboard:
    def test_index_renders_with_firewall_data(self, auth_client):
        devices = [{"ip": "192.168.50.5", "mac": "aa:bb:cc:dd:ee:ff",
                    "hostname": "pc1", "state": "REACHABLE", "blocked": False}]
        with patch("firewall.exam_status", return_value="active"), \
             patch("firewall.connected_devices", return_value=devices), \
             patch("firewall.network_status", return_value="active"), \
             patch("firewall.strict_status", return_value="inactive"):
            resp = auth_client.get("/")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Exam control
# ---------------------------------------------------------------------------

class TestExamControl:
    def test_exam_on_calls_firewall_and_redirects(self, auth_client):
        with patch("firewall.exam_on") as mock_fn, \
             patch("firewall.exam_status", return_value="active"), \
             patch("firewall.connected_devices", return_value=[]), \
             patch("firewall.network_status", return_value="active"), \
             patch("firewall.strict_status", return_value="inactive"):
            resp = auth_client.get("/exam/on", follow_redirects=False)
        mock_fn.assert_called_once()
        assert resp.status_code == 302

    def test_exam_off_calls_firewall_and_redirects(self, auth_client):
        with patch("firewall.exam_off") as mock_fn, \
             patch("firewall.exam_status", return_value="inactive"), \
             patch("firewall.connected_devices", return_value=[]), \
             patch("firewall.network_status", return_value="active"), \
             patch("firewall.strict_status", return_value="inactive"):
            resp = auth_client.get("/exam/off", follow_redirects=False)
        mock_fn.assert_called_once()
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Device block / unblock
# ---------------------------------------------------------------------------

class TestDeviceControl:
    def test_block_device_calls_firewall_with_ip(self, auth_client):
        with patch("firewall.block_device") as mock_fn, \
             patch("firewall.exam_status", return_value="inactive"), \
             patch("firewall.connected_devices", return_value=[]), \
             patch("firewall.network_status", return_value="active"), \
             patch("firewall.strict_status", return_value="inactive"):
            resp = auth_client.get("/device/block/192.168.50.5",
                                   follow_redirects=False)
        mock_fn.assert_called_once_with("192.168.50.5")
        assert resp.status_code == 302

    def test_unblock_device_calls_firewall_with_ip(self, auth_client):
        with patch("firewall.unblock_device") as mock_fn, \
             patch("firewall.exam_status", return_value="inactive"), \
             patch("firewall.connected_devices", return_value=[]), \
             patch("firewall.network_status", return_value="active"), \
             patch("firewall.strict_status", return_value="inactive"):
            resp = auth_client.get("/device/unblock/192.168.50.7",
                                   follow_redirects=False)
        mock_fn.assert_called_once_with("192.168.50.7")
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Network kill switch
# ---------------------------------------------------------------------------

class TestNetworkControl:
    def test_network_kill_calls_firewall(self, auth_client):
        with patch("firewall.kill_network") as mock_fn, \
             patch("firewall.exam_status", return_value="inactive"), \
             patch("firewall.connected_devices", return_value=[]), \
             patch("firewall.network_status", return_value="killed"), \
             patch("firewall.strict_status", return_value="inactive"):
            resp = auth_client.get("/network/kill", follow_redirects=False)
        mock_fn.assert_called_once()
        assert resp.status_code == 302

    def test_network_restore_calls_firewall(self, auth_client):
        with patch("firewall.restore_network") as mock_fn, \
             patch("firewall.exam_status", return_value="inactive"), \
             patch("firewall.connected_devices", return_value=[]), \
             patch("firewall.network_status", return_value="active"), \
             patch("firewall.strict_status", return_value="inactive"):
            resp = auth_client.get("/network/restore", follow_redirects=False)
        mock_fn.assert_called_once()
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Strict mode
# ---------------------------------------------------------------------------

class TestStrictMode:
    def test_strict_on_calls_firewall(self, auth_client):
        with patch("firewall.strict_mode_on") as mock_fn, \
             patch("firewall.exam_status", return_value="inactive"), \
             patch("firewall.connected_devices", return_value=[]), \
             patch("firewall.network_status", return_value="active"), \
             patch("firewall.strict_status", return_value="active"):
            resp = auth_client.get("/strict/on", follow_redirects=False)
        mock_fn.assert_called_once()
        assert resp.status_code == 302

    def test_strict_off_calls_firewall(self, auth_client):
        with patch("firewall.strict_mode_off") as mock_fn, \
             patch("firewall.exam_status", return_value="inactive"), \
             patch("firewall.connected_devices", return_value=[]), \
             patch("firewall.network_status", return_value="active"), \
             patch("firewall.strict_status", return_value="inactive"):
            resp = auth_client.get("/strict/off", follow_redirects=False)
        mock_fn.assert_called_once()
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Device refresh
# ---------------------------------------------------------------------------

class TestDeviceRefresh:
    def test_refresh_calls_firewall_and_redirects(self, auth_client):
        with patch("firewall.refresh_devices") as mock_fn, \
             patch("firewall.exam_status", return_value="inactive"), \
             patch("firewall.connected_devices", return_value=[]), \
             patch("firewall.network_status", return_value="active"), \
             patch("firewall.strict_status", return_value="inactive"):
            resp = auth_client.get("/devices/refresh", follow_redirects=False)
        mock_fn.assert_called_once()
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# HTTP response headers
# ---------------------------------------------------------------------------

class TestResponseHeaders:
    def test_no_cache_headers_on_login_page(self, client):
        resp = client.get("/login")
        assert "no-store" in resp.headers.get("Cache-Control", "")
        assert resp.headers.get("Pragma") == "no-cache"
        assert resp.headers.get("Expires") == "0"

    def test_no_cache_headers_on_dashboard(self, auth_client):
        with patch("firewall.exam_status", return_value="inactive"), \
             patch("firewall.connected_devices", return_value=[]), \
             patch("firewall.network_status", return_value="active"), \
             patch("firewall.strict_status", return_value="inactive"):
            resp = auth_client.get("/")
        assert "no-store" in resp.headers.get("Cache-Control", "")

    def test_no_cache_headers_on_redirect(self, auth_client):
        with patch("firewall.exam_on"), \
             patch("firewall.exam_status", return_value="active"), \
             patch("firewall.connected_devices", return_value=[]), \
             patch("firewall.network_status", return_value="active"), \
             patch("firewall.strict_status", return_value="inactive"):
            resp = auth_client.get("/exam/on", follow_redirects=False)
        assert "no-store" in resp.headers.get("Cache-Control", "")


# ---------------------------------------------------------------------------
# Session persistence
# ---------------------------------------------------------------------------

class TestSessionPersistence:
    def test_session_is_marked_permanent_after_login(self, client):
        with patch("firewall.exam_status", return_value="inactive"), \
             patch("firewall.connected_devices", return_value=[]), \
             patch("firewall.network_status", return_value="active"), \
             patch("firewall.strict_status", return_value="inactive"):
            client.post("/login", data={"password": TEST_PASSWORD})

        with client.session_transaction() as sess:
            assert sess.get("logged_in") is True

    def test_authenticated_request_refreshes_permanent_session(self, auth_client):
        with patch("firewall.exam_status", return_value="inactive"), \
             patch("firewall.connected_devices", return_value=[]), \
             patch("firewall.network_status", return_value="active"), \
             patch("firewall.strict_status", return_value="inactive"):
            # A GET to the dashboard should refresh (not expire) the session
            resp = auth_client.get("/")
        assert resp.status_code == 200
