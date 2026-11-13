"""Admin page: sign in with the admin username/password, then review refund tickets."""

import logging

import pandas as pd
import streamlit as st

from admin_auth import LoginGuard, admin_configured
from glass import hero
from tickets import STATUSES, get_store

log = logging.getLogger(__name__)
BACKEND_LABEL = {"azure": "Azure Table Storage", "postgres": "Postgres (Neon)",
                 "sqlite": "Local SQLite file", "memory": "In-memory (tests)"}
STATUS_ICON = {"open": "🟡 open", "approved": "✅ approved", "rejected": "❌ rejected"}

hero("Back office", "Refund tickets",
     "Every refund the agent issues opens a ticket here. Sign in as the admin to review, "
     "approve or reject them.")

if not admin_configured():
    st.warning(
        "Admin sign-in isn't configured. Set `ADMIN_USERNAME` and `ADMIN_PASSWORD` in `.env` "
        "(on Azure, Terraform generates the password and stores it in Key Vault)."
    )
    st.stop()

guard = LoginGuard(st.session_state)

# --- Sign in ----------------------------------------------------------------------
if not st.session_state.get("admin_user"):
    _, middle, _ = st.columns([1, 2, 1])
    with middle:
        locked = guard.seconds_locked()
        if locked:
            st.error(f"Too many failed attempts. Try again in {locked} seconds.")
        with st.form("admin_login", clear_on_submit=True):
            st.subheader("🔐 Admin sign-in")
            username = st.text_input("Username", autocomplete="username")
            password = st.text_input("Password", type="password", autocomplete="current-password")
            submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if submitted:
            if guard.attempt(username, password):
                st.rerun()
            else:
                log.warning("failed admin sign-in")
                st.error("Wrong username or password.")
    st.stop()


def sign_out() -> None:
    st.session_state.pop("admin_user", None)


admin = st.session_state["admin_user"]
with st.sidebar:
    st.caption(f"Signed in as **{admin}**")
    st.button("Sign out", on_click=sign_out, use_container_width=True)

# --- Tickets ----------------------------------------------------------------------
try:
    store = get_store()
    tickets = store.list()
except Exception:
    log.exception("could not load tickets")
    st.error("Couldn't reach the ticket store. Check the app's logs.")
    st.stop()

st.caption(f"Storage: **{BACKEND_LABEL.get(store.backend, store.backend)}**")

open_tickets = [t for t in tickets if t["status"] == "open"]
cols = st.columns(4)
cols[0].metric("Open", len(open_tickets))
cols[1].metric("Approved", sum(t["status"] == "approved" for t in tickets))
cols[2].metric("Rejected", sum(t["status"] == "rejected" for t in tickets))
cols[3].metric("Open amount", f"${sum(t['amount'] for t in open_tickets):,.2f}")

if not tickets:
    st.info("No tickets yet. Ask the agent for a refund on the chat page (for example as `user123`).")
    st.stop()

left, right, refresh = st.columns([1, 2, 1])
status_filter = left.selectbox("Status", ["all", *STATUSES])
search = right.text_input("Search customer or ticket ID", placeholder="user123 or RF-…")
refresh.write("")
if refresh.button("🔄 Refresh", use_container_width=True):
    st.rerun()

shown = [t for t in tickets if status_filter == "all" or t["status"] == status_filter]
if search.strip():
    needle = search.strip().lower()
    shown = [t for t in shown if needle in t["user"].lower() or needle in t["id"].lower()]

table = pd.DataFrame(shown, columns=["id", "created_at", "user", "items", "amount", "status",
                                     "reviewed_by", "note", "updated_at"])
table["status"] = table["status"].map(STATUS_ICON)
st.dataframe(
    table,
    hide_index=True,
    use_container_width=True,
    column_config={
        "id": "Ticket",
        "created_at": "Created (UTC)",
        "user": "Customer",
        "items": "Items",
        "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
        "status": "Status",
        "reviewed_by": "Reviewed by",
        "note": "Note",
        "updated_at": "Updated (UTC)",
    },
)

# --- Review -----------------------------------------------------------------------
st.subheader("Review a ticket")
if not open_tickets:
    st.success("Nothing to review: every ticket has been handled.")
    st.stop()

by_id = {t["id"]: t for t in open_tickets}
with st.form("review", clear_on_submit=True):
    ticket_id = st.selectbox(
        "Open ticket", list(by_id),
        format_func=lambda i: f"{i} · {by_id[i]['user']} · ${by_id[i]['amount']:,.2f} · {by_id[i]['items'] or '-'}",
    )
    note = st.text_input("Note (optional)", max_chars=500)
    approve_col, reject_col = st.columns(2)
    approve = approve_col.form_submit_button("✅ Approve", type="primary", use_container_width=True)
    reject = reject_col.form_submit_button("❌ Reject", use_container_width=True)

if approve or reject:
    status = "approved" if approve else "rejected"
    try:
        store.set_status(ticket_id, status, reviewer=admin, note=note)
    except Exception:
        log.exception("could not update ticket")
        st.error("Couldn't update the ticket. Please try again.")
    else:
        st.toast(f"{ticket_id} {status}.")
        st.rerun()
