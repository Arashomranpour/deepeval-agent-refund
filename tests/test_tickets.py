"""Refund tickets: storage backends, the issuing tool, admin sign-in and the admin page."""

import os
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import admin_auth
import tickets
from tools import issue_refund_ticket

ROOT = Path(__file__).resolve().parents[1]
ADMIN_PAGE = str(ROOT / "app_pages" / "admin_page.py")


@pytest.fixture(autouse=True)
def fresh_store(monkeypatch):
    monkeypatch.setenv("TICKETS_BACKEND", "memory")
    tickets.reset_store()
    yield
    tickets.reset_store()


@pytest.fixture
def admin_env(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "correct-horse")


@pytest.mark.parametrize("make", [lambda tmp: tickets.MemoryTicketStore(),
                                  lambda tmp: tickets.SqliteTicketStore(tmp / "t.db")],
                         ids=["memory", "sqlite"])
def test_store_lifecycle(tmp_path, make):
    store = make(tmp_path)
    first = store.create("user123", 30, ["book", "pen"])
    second = store.create("user126", 45, ["backpack"])
    assert first["id"].startswith("RF-") and first["status"] == "open"
    assert first["items"] == "book, pen"
    assert {t["id"] for t in store.list()} == {first["id"], second["id"]}

    updated = store.set_status(first["id"], "approved", reviewer="admin", note="ok")
    assert updated["status"] == "approved" and updated["reviewed_by"] == "admin"
    assert [t["id"] for t in store.list("open")] == [second["id"]]
    with pytest.raises(ValueError):
        store.set_status(second["id"], "paid", reviewer="admin")
    with pytest.raises(KeyError):
        store.set_status("RF-missing", "approved", reviewer="admin")


def test_sqlite_store_persists(tmp_path):
    ticket = tickets.SqliteTicketStore(tmp_path / "t.db").create("user123", 23, ["book"])
    assert tickets.SqliteTicketStore(tmp_path / "t.db").list()[0]["id"] == ticket["id"]


def test_backend_selection(monkeypatch, tmp_path):
    monkeypatch.delenv("TICKETS_BACKEND")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("TICKETS_DB", str(tmp_path / "x.db"))
    assert tickets.get_store().backend == "sqlite"


def test_database_url_selects_postgres(monkeypatch):
    seen = {}

    class FakePostgres:
        backend = "postgres"

        def __init__(self, url):
            seen["url"] = url

    monkeypatch.delenv("TICKETS_BACKEND")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db")
    monkeypatch.setattr(tickets, "PostgresTicketStore", FakePostgres)
    assert tickets.get_store().backend == "postgres"
    assert seen["url"] == "postgresql://u:p@host/db"


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="set TEST_DATABASE_URL to test against Postgres")
def test_postgres_store_lifecycle():
    store = tickets.PostgresTicketStore(os.environ["TEST_DATABASE_URL"])
    ticket = store.create("user123", 30, ["book", "pen"])
    assert any(t["id"] == ticket["id"] and t["user"] == "user123" for t in store.list("open"))
    updated = store.set_status(ticket["id"], "rejected", reviewer="admin", note="test")
    assert updated["status"] == "rejected"
    assert all(t["id"] != ticket["id"] for t in store.list("open"))
    with pytest.raises(KeyError):
        store.set_status("RF-missing", "approved", reviewer="admin")


def test_tool_saves_a_ticket():
    out = issue_refund_ticket.invoke({"user": "user123", "refund_amount": 30, "items": ["book", "pen"]})
    saved = tickets.get_store().list()
    assert len(saved) == 1 and saved[0]["id"] in out
    assert saved[0]["user"] == "user123" and saved[0]["amount"] == 30


def test_tool_refuses_unknown_user():
    out = issue_refund_ticket.invoke({"user": "user999", "refund_amount": 30})
    assert out.startswith("No ticket issued")
    assert tickets.get_store().list() == []


def test_credentials(admin_env):
    assert admin_auth.check_credentials("admin", "correct-horse")
    assert admin_auth.check_credentials(" admin ", "correct-horse")
    assert not admin_auth.check_credentials("admin", "wrong")
    assert not admin_auth.check_credentials("root", "correct-horse")


def test_no_admin_configured(monkeypatch):
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    assert not admin_auth.admin_configured()
    assert not admin_auth.check_credentials("", "")


def test_lockout_after_repeated_failures(admin_env):
    state: dict = {}
    guard = admin_auth.LoginGuard(state)
    for _ in range(admin_auth.MAX_ATTEMPTS):
        assert not guard.attempt("admin", "wrong")
    assert guard.seconds_locked() > 0
    assert not guard.attempt("admin", "correct-horse")  # locked even with the right password
    assert "admin_user" not in state


def test_admin_page_needs_configuration(monkeypatch):
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    at = AppTest.from_file(ADMIN_PAGE, default_timeout=30).run()
    assert not at.exception
    assert "isn't configured" in at.warning[0].value
    assert len(at.dataframe) == 0


def sign_in(at: AppTest, username: str, password: str) -> AppTest:
    at.text_input[0].input(username)
    at.text_input[1].input(password)
    return at.button[0].click().run()


def test_admin_page_rejects_wrong_password(admin_env):
    tickets.get_store().create("user123", 30, ["book"])
    at = AppTest.from_file(ADMIN_PAGE, default_timeout=30).run()
    proto = at.text_input[1].proto
    assert type(proto).Type.Name(proto.type) == "PASSWORD"
    sign_in(at, "admin", "wrong")
    assert any("Wrong username or password" in e.value for e in at.error)
    assert len(at.dataframe) == 0  # no ticket data before sign-in


def test_admin_can_approve_a_ticket(admin_env):
    ticket = tickets.get_store().create("user123", 30, ["book", "pen"])
    at = AppTest.from_file(ADMIN_PAGE, default_timeout=30).run()
    sign_in(at, "admin", "correct-horse")
    assert not at.exception
    assert at.metric[0].value == "1"  # open tickets
    assert len(at.dataframe) == 1

    at.button(key="FormSubmitter:review-✅ Approve").click().run()
    assert tickets.get_store().list()[0]["status"] == "approved"
    assert tickets.get_store().list()[0]["reviewed_by"] == "admin"
    assert ticket["id"] in at.dataframe[0].value["id"].tolist()


def test_demo_login_hint_only_for_admin_admin(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    at = AppTest.from_file(ADMIN_PAGE, default_timeout=30).run()
    assert any("Demo login" in i.value for i in at.info)
    monkeypatch.setenv("ADMIN_PASSWORD", "correct-horse")
    at = AppTest.from_file(ADMIN_PAGE, default_timeout=30).run()
    assert not any("Demo login" in i.value for i in at.info)
