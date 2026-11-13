"""Offline tests for the Streamlit app (no Groq key, no network)."""

import json
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
for folder in ("agent", "evaluations", "app_pages"):
    sys.path.insert(0, str(ROOT / folder))

import results  # noqa: E402


def test_gate_blocks_chat(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_should_not_be_used")  # env key must not bypass the gate
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    assert len(at.chat_input) == 0
    proto = at.text_input[0].proto
    assert type(proto).Type.Name(proto.type) == "PASSWORD"


def test_malformed_key_rejected():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    at.text_input[0].input("not-a-key")
    at.button[0].click().run()
    assert any("doesn't look like" in e.value for e in at.error)


@pytest.fixture
def fake_results(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    runs.mkdir()
    rows = [
        {"test_case": "I am user123, refund the book", "metric": m, "metric_type": "trace",
         "score": s, "threshold": 0.8, "status": st, "reason": "because",
         "actual_output": "A refund of 23 was issued", "expected_output": "Refund of 23$"}
        for m, s, st in [("Task Completion", 0.9, "pass"), ("Plan Quality", 0.5, "fail"),
                         ("Step Efficiency", None, "error")]
    ]
    run = {"run_id": "20261113_120000", "timestamp": "2026-11-13T12:00:00",
           "settings": {"agent_model": "m", "judge_model": "j", "test_cases": 1, "store_today": "2026-10-16"},
           "summary": results.summarize(rows), "results": rows}
    (runs / "20261113_120000.json").write_text(json.dumps(run), encoding="utf-8")
    monkeypatch.setattr(results, "RUNS_DIR", runs)
    monkeypatch.setattr(results, "HISTORY_FILE", tmp_path / "history.csv")
    return run


def test_results_page_renders(fake_results):
    at = AppTest.from_file(str(ROOT / "app_pages" / "results_page.py"), default_timeout=30).run()
    assert not at.exception
    assert at.metric[0].value == "1 / 3"
    assert len(at.dataframe) == 2


def test_results_page_without_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(results, "RUNS_DIR", tmp_path)
    at = AppTest.from_file(str(ROOT / "app_pages" / "results_page.py"), default_timeout=30).run()
    assert not at.exception
    assert "No saved runs yet" in at.info[0].value


def test_summarize_counts_errors_separately():
    rows = [{"metric": "A", "score": 1.0, "status": "pass"},
            {"metric": "A", "score": 0.0, "status": "fail"},
            {"metric": "A", "score": None, "status": "error"}]
    [s] = results.summarize(rows)
    assert (s["average_score"], s["passed"], s["failed"], s["errors"], s["total"]) == (0.5, 1, 1, 1, 3)
