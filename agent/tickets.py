"""Refund ticket storage.

One small interface, three backends, picked at runtime:

- ``azure``:  Azure Table Storage, authenticated with the app's managed identity (no keys).
              Used when ``AZURE_TABLES_ENDPOINT`` is set (Terraform sets it on the Container App).
- ``sqlite``: a local file (``data/tickets.db``) for running on a laptop. The default.
- ``memory``: a process-local dict, for tests and evaluation runs (keeps eval traffic out of
              the real ticket list).

Override the choice with ``TICKETS_BACKEND=azure|sqlite|memory``.
"""

from __future__ import annotations

import logging
import os
import secrets
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

STATUSES = ("open", "approved", "rejected")
ROOT = Path(__file__).resolve().parents[1]
PARTITION = "ticket"

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def new_ticket_id() -> str:
    """Short, readable and unguessable enough for a demo: RF-20261113-7F3A2C."""
    return f"RF-{datetime.now(UTC):%Y%m%d}-{secrets.token_hex(3).upper()}"


def _new_ticket(user: str, amount: float, items: list[str] | None) -> dict:
    now = _now()
    return {
        "id": new_ticket_id(),
        "user": user,
        "amount": float(amount),
        "items": ", ".join(items or []),
        "status": "open",
        "created_at": now,
        "updated_at": now,
        "reviewed_by": "",
        "note": "",
    }


class TicketStore(Protocol):
    backend: str

    def create(self, user: str, amount: float, items: list[str] | None = None) -> dict: ...
    def list(self, status: str | None = None) -> list[dict]: ...
    def set_status(self, ticket_id: str, status: str, reviewer: str, note: str = "") -> dict: ...


def _check_status(status: str) -> None:
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")


def _review(ticket: dict, status: str, reviewer: str, note: str) -> dict:
    _check_status(status)
    ticket.update(status=status, reviewed_by=reviewer, note=note[:500], updated_at=_now())
    return ticket


def _sorted(tickets: list[dict], status: str | None) -> list[dict]:
    if status:
        tickets = [t for t in tickets if t["status"] == status]
    return sorted(tickets, key=lambda t: t["created_at"], reverse=True)


class MemoryTicketStore:
    backend = "memory"

    def __init__(self) -> None:
        self._tickets: dict[str, dict] = {}
        self._lock = threading.Lock()

    def create(self, user, amount, items=None):
        ticket = _new_ticket(user, amount, items)
        with self._lock:
            self._tickets[ticket["id"]] = ticket
        return dict(ticket)

    def list(self, status=None):
        with self._lock:
            return _sorted([dict(t) for t in self._tickets.values()], status)

    def set_status(self, ticket_id, status, reviewer, note=""):
        with self._lock:
            if ticket_id not in self._tickets:
                raise KeyError(ticket_id)
            return dict(_review(self._tickets[ticket_id], status, reviewer, note))


class SqliteTicketStore:
    backend = "sqlite"
    COLUMNS = ("id", "user", "amount", "items", "status", "created_at", "updated_at", "reviewed_by", "note")

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS tickets (id TEXT PRIMARY KEY, user TEXT, amount REAL, items TEXT,"
                " status TEXT, created_at TEXT, updated_at TEXT, reviewed_by TEXT, note TEXT)"
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def create(self, user, amount, items=None):
        ticket = _new_ticket(user, amount, items)
        with self._connect() as db:
            db.execute(
                f"INSERT INTO tickets ({', '.join(self.COLUMNS)}) VALUES ({', '.join('?' * len(self.COLUMNS))})",
                [ticket[c] for c in self.COLUMNS],
            )
        return ticket

    def list(self, status=None):
        with self._connect() as db:
            rows = [dict(r) for r in db.execute("SELECT * FROM tickets")]
        return _sorted(rows, status)

    def set_status(self, ticket_id, status, reviewer, note=""):
        with self._connect() as db:
            row = db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
            if row is None:
                raise KeyError(ticket_id)
            ticket = _review(dict(row), status, reviewer, note)
            db.execute(
                "UPDATE tickets SET status = ?, reviewed_by = ?, note = ?, updated_at = ? WHERE id = ?",
                (ticket["status"], ticket["reviewed_by"], ticket["note"], ticket["updated_at"], ticket_id),
            )
        return ticket


class AzureTableTicketStore:
    """Azure Table Storage via Entra ID: the Container App's user-assigned identity
    (``AZURE_CLIENT_ID``) or your ``az login`` locally. No account keys anywhere."""

    backend = "azure"

    def __init__(self, endpoint: str, table: str = "refundtickets") -> None:
        from azure.data.tables import TableServiceClient
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential(managed_identity_client_id=os.getenv("AZURE_CLIENT_ID"))
        service = TableServiceClient(endpoint=endpoint, credential=credential)
        self._table = service.create_table_if_not_exists(table)

    @staticmethod
    def _to_ticket(entity) -> dict:
        ticket = {k: v for k, v in entity.items() if k not in ("PartitionKey", "RowKey")}
        ticket["id"] = entity["RowKey"]
        return ticket

    def create(self, user, amount, items=None):
        ticket = _new_ticket(user, amount, items)
        entity = {k: v for k, v in ticket.items() if k != "id"}
        self._table.create_entity({"PartitionKey": PARTITION, "RowKey": ticket["id"], **entity})
        return ticket

    def list(self, status=None):
        query = f"PartitionKey eq '{PARTITION}'"
        params = None
        if status:
            _check_status(status)
            query += " and status eq @status"
            params = {"status": status}
        entities = self._table.query_entities(query, parameters=params)
        return _sorted([self._to_ticket(e) for e in entities], None)

    def set_status(self, ticket_id, status, reviewer, note=""):
        from azure.core.exceptions import ResourceNotFoundError
        from azure.data.tables import UpdateMode

        try:
            entity = self._table.get_entity(PARTITION, ticket_id)
        except ResourceNotFoundError as error:
            raise KeyError(ticket_id) from error
        ticket = _review(self._to_ticket(entity), status, reviewer, note)
        self._table.update_entity(
            {
                "PartitionKey": PARTITION,
                "RowKey": ticket_id,
                "status": ticket["status"],
                "reviewed_by": ticket["reviewed_by"],
                "note": ticket["note"],
                "updated_at": ticket["updated_at"],
            },
            mode=UpdateMode.MERGE,
        )
        return ticket


_store: TicketStore | None = None
_store_lock = threading.Lock()


def get_store() -> TicketStore:
    """The process-wide ticket store (tickets are shared by every session, unlike API keys)."""
    global _store
    with _store_lock:
        if _store is None:
            endpoint = os.getenv("AZURE_TABLES_ENDPOINT", "")
            backend = os.getenv("TICKETS_BACKEND") or ("azure" if endpoint else "sqlite")
            if backend == "azure":
                _store = AzureTableTicketStore(endpoint, os.getenv("TICKETS_TABLE", "refundtickets"))
            elif backend == "memory":
                _store = MemoryTicketStore()
            else:
                _store = SqliteTicketStore(os.getenv("TICKETS_DB", str(ROOT / "data" / "tickets.db")))
            log.info("Ticket store: %s", _store.backend)
        return _store


def reset_store() -> None:
    """Forget the cached store (tests)."""
    global _store
    with _store_lock:
        _store = None
