"""Application Insights telemetry (OpenTelemetry). A no-op unless
APPLICATIONINSIGHTS_CONNECTION_STRING is set, which the Azure deployment injects
from Key Vault. Records timings, tool names and outcomes: never API keys or message text."""

import hashlib
import logging
import os
from contextlib import contextmanager

import streamlit as st
from opentelemetry import trace

log = logging.getLogger("refund_app")


@st.cache_resource
def setup_telemetry() -> bool:
    """Configure the Azure Monitor exporter once per process."""
    if not os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        return False
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(logger_name="refund_app")
        logging.getLogger("refund_app").setLevel(logging.INFO)
        return True
    except Exception:  # telemetry must never break the app
        logging.getLogger(__name__).exception("telemetry setup failed")
        return False


def anonymous_session(session_id: str) -> str:
    return hashlib.sha256(session_id.encode()).hexdigest()[:12]


@contextmanager
def agent_turn_span(session_id: str, turn: int):
    """One span per chat turn; the caller adds tool names and the outcome."""
    tracer = trace.get_tracer("refund_app")
    with tracer.start_as_current_span("agent.turn") as span:
        span.set_attribute("app.session", anonymous_session(session_id))
        span.set_attribute("app.turn", turn)
        yield span
