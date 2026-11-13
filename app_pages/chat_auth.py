"""Visitor sign-in for the chat page, with Clerk as the OpenID Connect provider.

Streamlit's built-in st.login() talks to Clerk through an OAuth application created in
the Clerk dashboard. Configuration lives in Streamlit secrets ([auth] and [auth.clerk]),
never in code. When it isn't configured (local runs without secrets.toml, tests), the
chat stays open, as before. The admin page has its own login and doesn't use Clerk.
"""

import streamlit as st

PROVIDER = "clerk"


def clerk_configured() -> bool:
    try:
        return PROVIDER in st.secrets.get("auth", {})
    except Exception:  # no secrets.toml at all
        return False


def signed_in() -> bool:
    # .get(): st.user may not carry the field at all (e.g. in AppTest); treat that as signed out.
    return bool(st.user.get("is_logged_in", False))


def display_name() -> str:
    """Name or e-mail for the sidebar. Never sent to telemetry or the model."""
    return str(st.user.get("name") or st.user.get("email") or "signed in")


def sign_in_button() -> None:
    st.button("🔐 Sign in with Clerk", type="primary", on_click=st.login, args=(PROVIDER,),
              use_container_width=True)


def sign_out_button() -> None:
    st.button("Sign out", on_click=st.logout, use_container_width=True)
